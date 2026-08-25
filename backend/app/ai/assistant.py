from __future__ import annotations

import re
from dataclasses import dataclass, field

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.ingres import predict, queries
from app.ingres.terminology import ALIAS_MAP, CANONICAL_BY_TERM, TERMS, resolve_term
from app.models.groundwater import AssessmentUnit, District, GroundwaterAssessment, State, Village

DEMO_SOURCE = "Synthetic Development Dataset"

_GREETING_WORDS = {
    "hello",
    "hi",
    "hey",
    "namaste",
    "greetings",
    "good morning",
    "good afternoon",
    "good evening",
    "నమస్కారం",
    "నమస్కారము",
    "నమస్తే",
    "నమో",
    "नमस्ते",
    "नमस्कार",
    "हैलो",
    "नमो",
    "வணக்கம்",
    "நமஸ்காரம்",
    "ஹலோ",
    "ಹಲೋ",
    "ನಮಸ್ಕಾರ",
    "ನಮಸ್ತೆ",
    "നമസ്കാരം",
    "ഹലോ",
    "വണക്കം",
    "হ্যালো",
    "নমস্কার",
    "હેલો",
    "નમસ્તે",
    "ਸਤ ਸ੍ਰੀ ਅਕਾਲ",
    "ਹੈਲੋ",
    "ନମସ୍କାର",
    "ହେଲୋ",
}

_THANKS_WORDS = {
    "thank",
    "thanks",
    "thankyou",
    "thank you",
    "ధన్యవాదాలు",
    "ధన్యవాదం",
    "धन्यवाद",
    "शुक्रिया",
    "நன்றி",
    "ಧನ್ಯವಾದ",
    "നന്ദി",
    "ধন্যবাদ",
    "આભાર",
    "ਧੰਨਵਾਦ",
    "ଧନ୍ୟବାଦ",
}

_HELP_WORDS = {
    "help",
    "assist",
    "what can you do",
    "what can i ask",
    "how do you work",
    "capabilities",
    "features",
    "సహాయం",
    "मदद",
    "क्या कर सकते हो",
    "உதவி",
    "உதவுங்கள்",
    "செய்ய முடியும்",
    "सಹಾಯ",
    "ಸಹಾಯ",
    "എന്ത് ചെയ്യാൻ കഴിയും",
    "സഹായം",
    "সাহায্য",
    "মদদ",
    "મદદ",
    "ਚ ਮਦਦ",
    "ਮਦਦ",
    "ସାହାଯ୍ୟ",
}

_RECOMMEND_WORDS = {
    "measures",
    "measure",
    "recommend",
    "recommends",
    "recommended",
    "recommendation",
    "recommendations",
    "suggest",
    "suggested",
    "suggestion",
    "suggestions",
    "conserve",
    "conservation",
    "conserving",
    "what can we do",
    "what can be done",
    "what should we do",
    "how can we",
    "how can i",
    "how to reduce",
    "how to conserve",
    "how to save",
    "save water",
    "save groundwater",
    "reduce extraction",
    # Action-oriented phrasings ("How to improve groundwater recharge …?")
    "improve",
    "improving",
    "improvement",
    "increase",
    "increasing",
    "enhance",
    "enhancing",
    "boost",
    "boosting",
    "restore",
    "restoring",
    "replenish",
    "replenishing",
    "solution",
    "solutions",
    "remedy",
    "reduce groundwater",
    "cut extraction",
    "improve recharge",
    "increase recharge",
    "water saving",
    "efficient irrigation",
    "rainwater harvesting",
    "మార్గాలు",
    "సలహా",
    "सुझाव",
    "பரிந்துரை",
    "பரிந்துரைகள்",
    "எப்படி குறைக்கலாம்",
    "ಸಲಹೆ",
    "ಸಲಹೆಗಳು",
    "ಹೇಗೆ ಉಳಿಸಬಹುದು",
    "നിർദ്ദേശങ്ങൾ",
    "സംരക്ഷണം",
    "পরামর্শ",
    "সংরক্ষণ",
    "સૂચનો",
    "કેવી રીતે બચાવવું",
    "ਸੁਝਾਅ",
    "ਸੰਭਾਲ",
    "ପରାମର୍ଶ",
    "କିପରି ସଞ୍ଚୟ କରିବେ",
}

_WHY_WORDS = {
    "why",
    "reason",
    "causes",
    "cause",
    "declining",
    "decreasing",
    "falling",
    "ஏன்",
    "காரணம்",
    "ಏಕೆ",
    "ಕಾರಣ",
    "എന്തുകൊണ്ട്",
    "കാരണം",
    "কেন",
    "কারণ",
    "શા માટે",
    "કારણ",
    "ਕਿਉਂ",
    "ਕਾਰਨ",
    "କାହିଁକି",
    "କାରଣ",
}

_METRIC_ALIASES = {
    "recharge": {"recharge", "recharged", "పునర్భరణం", "పునర్భరణ", "पुनर्भरण",
                 "நீர் நிரப்பு", "மறுநிரப்பு", "ಪುನರ್ಭರಣ", "പുനഃഭരണം",
                 "পুনর্ভরণ", "પુનર્ભરણ", "ਪੁਨਰਭਰਨ", "ପୁନର୍ଭରଣ"},
    "stage": {"stage of extraction", "stage", "stage of groundwater extraction", "soe",
              "condition", "conditions", "groundwater condition", "groundwater conditions",
              "పరిస్థితి", "దశ", "వెలికితీత దశ", "ప్రస్తుత స్థితి",
              "परिस्थिति", "स्थिति", "निष्कर्षण चरण", "दशा", "स्टेज",
              "நிலை", "பிரித்தெடுப்பு நிலை", "ಹಂತ", "ಘಟ್ಟಗಳು", "পর্যায়",
              "તબક્કો", "ਪੜਾਅ", "ପର୍ଯ୍ୟାୟ"},
    "extraction": {"extraction", "extracted", "withdrawal", "withdrawals", "వెలికితీత", "निष्कर्षण",
                   "பிரித்தெடுப்பு", "வெளியேற்றம்", "உறிஞ்சுதல்", "ಉತ್ಖನನ", "വേർതിരിച്ചെടുപ്പ്",
                   "নিষ্কাশন", "નિષ્કર્ષણ", "ਕੱਢਣ", "ନିଷ୍କାସନ"},
    "resource": {"annual extractable", "extractable resource", "extractable groundwater", "available resource"},
    "waterlevel": {"water level", "water levels", "depth to water", "నీటి మట్టం", "जल स्तर", "जलस्तर",
                   "நீர்மட்டம்", "ನೀರಿನ ಮಟ್ಟ", "ജലനിരപ്പ്", "জলস্তর",
                   "જળ સ્તર", "ਪਾਣੀ ਦਾ ਪੱਧਰ", "ଜଳସ୍ତର"},
    "category": {"category", "categories", "classification", "safe", "critical", "overexploited", "semi-critical", "over-exploited",
                 "வகை", "வகைகள்", "ವರ್ಗ", "വിഭാഗം", "শ্রেণী", "શ્રેણી", "ਸ਼੍ਰੇਣੀ", "ଶ୍ରେଣୀ"},
}

_YEAR_RE = re.compile(r"(?:20|19)\d{2}")

# Scripts the assistant recognises. ASCII plus the major Indian scripts, used to
# split messages into word tokens without mangling non-Latin text.
_WORD_SCRIPT_RANGES = (
    "a-zA-Z"
    "\\u0900-\\u097F"  # Devanagari (Hindi / Marathi)
    "\\u0980-\\u09FF"  # Bengali / Assamese
    "\\u0A00-\\u0A7F"  # Gurmukhi (Punjabi)
    "\\u0A80-\\u0AFF"  # Gujarati
    "\\u0B00-\\u0B7F"  # Odia
    "\\u0B80-\\u0BFF"  # Tamil
    "\\u0C00-\\u0C7F"  # Telugu
    "\\u0C80-\\u0CFF"  # Kannada
    "\\u0D00-\\u0D7F"  # Malayalam
)
_WORD_RE = re.compile(f"[^{_WORD_SCRIPT_RANGES}]+")

_FORECAST_WORDS = {
    "forecast",
    "forecasted",
    "forecasting",
    "predict",
    "predicted",
    "prediction",
    "predictions",
    "projection",
    "projected",
    "project",
    "projecting",
    "trend",
    "trends",
    "outlook",
    "future",
    "will be",
    "going to be",
}

_HORIZON_RE = re.compile(r"next\s+(\d{1,2})\s+years?|(\d{1,2})\s+years?\s+(?:from now|ahead|out)|by\s+(\d{4})")
_FUTURE_YEARS = {2030, 2029, 2028, 2027, 2026, 2025, 2024, 2023}

_SCENARIO_METRICS = {
    "extraction": {"pumping", "pumpage", "extraction", "withdrawal", "withdrawals", "withdraw", "abstraction"},
    "recharge": {"recharge", "rainfall", "rain"},
}
_SCENARIO_FRAMES = (
    "what if",
    "scenario",
    "effect of",
    "impact of",
    "what would",
    "what happens",
    "if we",
    "if i",
    "if the",
    "if there",
    "if pumping",
    "if extraction",
    "if recharge",
    "if rainfall",
)
_SCENARIO_UP = ("increase", "raise", "boost", "more", "higher", "up by", "rise", "goes up")
_SCENARIO_DOWN = ("decrease", "reduce", "cut", "less", "lower", "drop", "fall", "decline", "down by", "goes down")


def _has_future_year(text: str) -> bool:
    for token in _YEAR_RE.findall(text):
        if int(token) in _FUTURE_YEARS:
            return True
    return False


def extract_horizon(text: str) -> int:
    """Forecast horizon in years, defaulting to 5 when not specified."""
    m = _HORIZON_RE.search(text.lower())
    if m:
        if m.group(3):
            by = int(m.group(3))
            latest = max(
                [2022]
                + [int(t) for t in _YEAR_RE.findall(text) if int(t) <= 2022 and int(t) >= 2017]
            )
            return max(1, min(by - latest, 10))
        raw = m.group(1) or m.group(2)
        return max(1, min(int(raw), 10))
    return 5


def _parse_scenario(text: str) -> dict | None:
    """Parse a what-if change like 'pumping increases 10%' into
    ``{"metric": "extraction"|"recharge", "change_pct": float}`` or None."""
    lowered = text.lower()
    target: str | None = None
    for metric, words in _SCENARIO_METRICS.items():
        if any(w in lowered for w in words):
            target = metric
            break
    if target is None:
        return None
    direction: int | None = None
    if any(w in lowered for w in _SCENARIO_UP):
        direction = 1
    elif any(w in lowered for w in _SCENARIO_DOWN):
        direction = -1
    if direction is None:
        return None
    framed = any(f in lowered for f in _SCENARIO_FRAMES)
    pct_match = re.search(r"(\d{1,3})\s*%", lowered)
    if not framed and pct_match is None:
        return None
    pct = int(pct_match.group(1)) if pct_match else 10
    pct = max(1, min(pct, 100))
    return {"metric": target, "change_pct": direction * pct}


def _scenario_label(scenario: dict, language: str) -> str:
    pct = scenario["change_pct"]
    verb = "increase" if pct > 0 else "decrease"
    metric = scenario["metric"]
    return f"{verb} {metric} by {abs(pct)}%"

_GREETING_REPLY: dict[str, str] = {
    "en": "Namaste! I am your groundwater assistant for India. I can answer questions about groundwater recharge, extraction, stage of extraction and assessment categories — and explain groundwater terminology. Try asking: \"What is the stage of extraction in Telangana?\"",
    "te": "నమస్కారం! నేను భారతదేశ భూగర్భ జల సహాయకుడిని. భూగర్భ జల పునర్భరణం, వెలికితీత, వెలికితీత దశ మరియు అంచనా వర్గాల గురించి ప్రశ్నలు అడగవచ్చు. ఉదాహరణకు: \"తెలంగాణలో భూగర్భ జల వెలికితీత దశ ఎంత?\"",
    "hi": "नमस्ते! मैं भारत के भूजल संसाधनों के लिए आपका सहायक हूँ। मैं भूजल पुनर्भरण, निष्कर्षण, निष्कर्षण चरण और आकलन श्रेणियों के बारे में प्रश्नों का उत्तर दे सकता हूँ। उदाहरण: \"तेलंगाना में भूजल निष्कर्षण चरण कितना है?\"",
}

_HELP_REPLY: dict[str, str] = {
    "en": "Here is what I can help with:\n\n• Recharge, extraction and stage-of-extraction for any state, district or village in India\n• Assessment categories (Safe, Semi-critical, Critical, Over-exploited)\n• Forecasts — \"predicted trend in Telangana\" or \"next 5 years\" (with a confidence band)\n• What-if scenarios — \"what if pumping increases 10%?\"\n• Where the data comes from (CGWB, IMD, GRACE, etc.) and its reliability\n• Groundwater terminology and concepts\n\nI currently answer from a labelled synthetic national development dataset covering all 36 states and union territories. Mention a state, a district, or a specific village name to narrow results.",
    "te": "నేను సహాయం చేయగల విషయాలు:\n\n• భారతదేశంలోని ఏ రాష్ట్రం, జిల్లా లేదా గ్రామానికైనా పునర్భరణం, వెలికితీత, వెలికితీత దశ\n• అంచనా వర్గాలు (సురక్షితం, అర్ధ-క్లిష్ట, క్లిష్ట, అతిగా వెలికితీసిన)\n• అంచనాలు — \"తెలంగాణలో ఊహించిన ధోరణి\" లేదా \"తర్వాత 5 సంవత్సరాలు\" (విశ్వాస పరిధితో)\n• What-if దృశ్యాలు — \"పంపింగ్ 10% పెరిగితే ఏమవుతుంది?\"\n• డేటా ఎక్కడ నుండి వచ్చింది (CGWB, IMD, GRACE మొదలైనవి) మరియు దాని విశ్వసనీయత\n• భూగర్భ జల పదజాలం మరియు భావనలు\n\nప్రస్తుతం నేను అన్ని రాష్ట్రాలు మరియు కేంద్రపాలిత ప్రాంతాలను కలిగి ఉన్న లేబుల్ చేయబడిన సింథటిక్ జాతీయ డెవలప్మెంట్ డేటాసెట్ నుండి సమాధానం ఇస్తాను. ఫలితాలను ఇరుకుగా చేయడానికి ఒక రాష్ట్రం, జిల్లా లేదా నిర్దిష్ట గ్రామ పేరును పేర్కొనండి.",
    "hi": "मैं इन विषयों पर मदद कर सकता हूँ:\n\n• भारत के किसी भी राज्य, जिले या गाँव के लिए पुनर्भरण, निष्कर्षण और निष्कर्षण चरण\n• आकलन श्रेणियाँ (सुरक्षित, अर्ध-संकटग्रस्त, संकटग्रस्त, अति-दोहन)\n• पूर्वानुमान — \"तेलंगाना में अनुमानित रुझान\" या \"अगले 5 वर्ष\" (विश्वास अंतराल के साथ)\n• What-if परिदृश्य — \"यदि पंपिंग 10% बढ़ जाए तो क्या होगा?\"\n• डेटा कहाँ से आता है (CGWB, IMD, GRACE आदि) और उसकी विश्वसनीयता\n• भूजल शब्दावली और अवधारणाएँ\n\nवर्तमान में मैं सभी 36 राज्यों और केंद्र शासित प्रदेशों को शामिल करते हुए एक लेबल वाले सिंथेटिक राष्ट्रीय विकास डेटासेट से उत्तर देता हूँ। परिणाम सीमित करने के लिए कोई राज्य, जिला या विशिष्ट गाँव का नाम बताएँ।",
}

_THANKS_REPLY: dict[str, str] = {
    "en": "You're welcome! Feel free to ask more groundwater questions any time.",
    "te": "మీకు స్వాగతం! ఎప్పుడైనా మరిన్ని భూగర్భ జల ప్రశ్నలు అడగండి.",
    "hi": "आपका स्वागत है! कभी भी और भूजल प्रश्न पूछें।",
}

_CAPABILITIES_HINT = (
    "\n\nI can answer questions about recharge, extraction, stage of extraction, categories, or explain "
    "terms. Add a state (any of the 36 Indian states/UTs), a district, or a village name to narrow results."
)

_FORECAST_DISCLAIMER = (
    "This is a statistical estimate computed from the available assessment history and the listed model — "
    "not an official IN-GRES/CGWB projection. It does not include future policy, climate or pumping changes."
)

_ALL_STATES_HINT = "Across all 36 Indian states and union territories"


@dataclass
class AnswerResult:
    content: str
    response_type: str = "data"
    intent: str = "data_query"
    language: str = "en"
    location: str | None = None
    sources: list[str] = field(default_factory=lambda: [DEMO_SOURCE])
    is_demo: bool = True


_SCRIPT_TO_LANG: tuple[tuple[str, int, int], ...] = (
    ("te", 0x0C00, 0x0C7F),  # Telugu
    ("hi", 0x0900, 0x097F),  # Devanagari (Hindi, Marathi, ...)
    ("ta", 0x0B80, 0x0BFF),  # Tamil
    ("kn", 0x0C80, 0x0CFF),  # Kannada
    ("ml", 0x0D00, 0x0D7F),  # Malayalam
    ("bn", 0x0980, 0x09FF),  # Bengali / Assamese
    ("gu", 0x0A80, 0x0AFF),  # Gujarati
    ("pa", 0x0A00, 0x0A7F),  # Gurmukhi (Punjabi)
    ("or", 0x0B00, 0x0B7F),  # Odia
)


def detect_language(text: str) -> str:
    for code, start, end in _SCRIPT_TO_LANG:
        if re.search(f"[{chr(start)}-{chr(end)}]", text):
            return code
    return "en"


def _words(text: str) -> set[str]:
    return {w for w in _WORD_RE.split(text.lower()) if w}


def _contains_any(text: str, words: set[str]) -> bool:
    lowered = text.lower()
    for w in words:
        if w in lowered:
            return True
    return False


def _contains_any_term(text: str) -> bool:
    lowered = text.lower()
    for alias in ALIAS_MAP:
        if alias in lowered:
            return True
    for term in TERMS:
        if term["term"].lower() in lowered:
            return True
    return False


def _mentions_state(text: str) -> bool:
    """True if ``text`` references any Indian state/UT by alias or canonical name."""
    lowered = text.lower()
    if any(alias.lower() in lowered for alias, _ in _STATE_ALIASES):
        return True
    return any(name in lowered for name in _ENGLISH_STATE_NAMES)


def _wordset_match(text: str, words: set[str]) -> bool:
    """Match single words by token intersection and multi-word phrases by
    substring, so phrases like "good morning" or "ਸਤ ਸ੍ਰੀ ਅਕਾਲ" are caught."""
    lowered = text.lower()
    if _words(text) & words:
        return True
    return any(" " in phrase and phrase in lowered for phrase in words)


def _is_definition_question(text: str) -> bool:
    lowered = text.lower().strip()
    if lowered.startswith(("how much", "how many")):
        return False
    prefixes = (
        "what is",
        "what's",
        "what are",
        "whats",
        "what does",
        "what do",
        "how is",
        "how are",
        "how does",
        "how do",
        "define",
        "explain",
        "meaning of",
        "tell me about",
        "about ",
    )
    return any(lowered.startswith(p) for p in prefixes)


# Words that turn a question into a *process* explanation ("how is X measured /
# calculated / classified?") rather than a request for the X value itself.
_PROCESS_WORDS = (
    "measur",  # measure / measured / measurement
    "calculat",
    "comput",
    "deriv",
    "estimat",
    "determin",
    "classif",
    "categoris",
    "categoriz",
    "collect",
    "monitor",
)


def _is_how_it_works_question(text: str) -> bool:
    """True for questions asking HOW something works/is produced, not its value.

    e.g. "How does the water level is measured?", "How is stage of extraction
    calculated?" — these want an explanation (knowledge/web), never a number
    from the dataset.
    """
    low = text.lower().strip()
    if low.startswith(("how much", "how many")):
        return False
    asks_how = (
        low.startswith(("how ", "explain ", "what do you mean"))
        or " what do you mean" in f" {low}"
    )
    if not asks_how:
        return False
    return any(w in low for w in _PROCESS_WORDS)


# Extra English paraphrases (ASCII-safe to define here) merged into the metric
# lookup so differently-worded questions still resolve to the same metric.
_METRIC_ALIASES_EXTRA: dict[str, set[str]] = {
    "recharge": {"replenishment", "annual recharge", "rainfall recharge", "recharge rate"},
    "extraction": {"pumping", "pumped", "draft", "groundwater draft", "abstraction",
                   "groundwater drawl"},
    "stage": {"exploitation", "utilisation", "utilization", "groundwater development"},
    "resource": {"safe yield"},
}


def extract_metric(text: str) -> str | None:
    lowered = text.lower()
    for canonical, aliases in _METRIC_ALIASES_EXTRA.items():
        for alias in aliases:
            if re.search(rf"\b{re.escape(alias)}\b", lowered):
                return canonical
    for canonical, aliases in _METRIC_ALIASES.items():
        for alias in aliases:
            if alias in lowered:
                return canonical
    for alias in ALIAS_MAP:
        if alias in lowered:
            resolved = ALIAS_MAP[alias]
            if resolved == "groundwater recharge":
                return "recharge"
            if resolved == "groundwater extraction":
                return "extraction"
            if resolved == "stage of groundwater extraction":
                return "stage"
            if resolved == "annual extractable groundwater resource":
                return "resource"
    return None


def extract_year(text: str) -> int | None:
    for token in _YEAR_RE.findall(text):
        year = int(token)
        if 2017 <= year <= 2022:
            return year
    return None


_STATE_ALIASES: tuple[tuple[str, str], ...] = (
    # Telangana
    ("తెలంగాణ", "Telangana"),
    ("तेलंगाना", "Telangana"),
    ("తెలంగాణలో", "Telangana"),
    ("telangana", "Telangana"),
    # Andhra Pradesh
    ("ఆంధ్ర ప్రదేశ్", "Andhra Pradesh"),
    ("ఆంధ్రప్రదేశ్", "Andhra Pradesh"),
    ("ఆంధ్ర", "Andhra Pradesh"),
    ("ఆంధ్రప్రదేశ్లో", "Andhra Pradesh"),
    ("आंध्र प्रदेश", "Andhra Pradesh"),
    ("andhra pradesh", "Andhra Pradesh"),
    ("andhra", "Andhra Pradesh"),
    # Tamil Nadu
    ("தமிழ்நாடு", "Tamil Nadu"),
    ("தமிழ் நாடு", "Tamil Nadu"),
    ("தமிழகம்", "Tamil Nadu"),
    ("தமிழ்நாட்டில்", "Tamil Nadu"),
    ("தமிழகத்தில்", "Tamil Nadu"),
    ("ತಮಿಳುನಾಡು", "Tamil Nadu"),
    ("തമിഴ്നാട്", "Tamil Nadu"),
    ("তামিলনাড়ু", "Tamil Nadu"),
    ("તમિલનાડુ", "Tamil Nadu"),
    ("ਤਾਮਿਲਨਾਡੂ", "Tamil Nadu"),
    ("ତାମିଲନାଡୁ", "Tamil Nadu"),
    ("तमिलनाडु", "Tamil Nadu"),
    ("తమిళనాడు", "Tamil Nadu"),
    ("tamil nadu", "Tamil Nadu"),
    # Karnataka
    ("கர்நாடகா", "Karnataka"),
    ("கர்நாடகாவில்", "Karnataka"),
    ("ಕರ್ನಾಟಕ", "Karnataka"),
    ("കർണാടക", "Karnataka"),
    ("কর্ণাটক", "Karnataka"),
    ("કર્ણાટક", "Karnataka"),
    ("ਕਰਨਾਟక", "Karnataka"),
    ("କର୍ଣ୍ଣାଟକ", "Karnataka"),
    ("कर्नाटक", "Karnataka"),
    ("కర్ణాటక", "Karnataka"),
    ("కర్ణాటకలో", "Karnataka"),
    ("karnataka", "Karnataka"),
    # Kerala
    ("கேரளா", "Kerala"),
    ("கேரளத்தில்", "Kerala"),
    ("ಕೇರಳ", "Kerala"),
    ("കേരളം", "Kerala"),
    ("কেরালা", "Kerala"),
    ("કેરળ", "Kerala"),
    ("ਕੇਰਲਾ", "Kerala"),
    ("केरल", "Kerala"),
    ("కేరళ", "Kerala"),
    ("kerala", "Kerala"),
    # Maharashtra
    ("மகாராஷ்டிரா", "Maharashtra"),
    ("மகாராஷ்டிராவில்", "Maharashtra"),
    ("ಮಹಾರಾಷ್ಟ್ರ", "Maharashtra"),
    ("മഹാരാഷ്ട്ര", "Maharashtra"),
    ("মহারাষ্ট্র", "Maharashtra"),
    ("મહારાષ્ટ્ર", "Maharashtra"),
    ("ਮਹਾਰਾਸ਼ਟਰ", "Maharashtra"),
    ("ମହାରାଷ୍ଟ୍ର", "Maharashtra"),
    ("महाराष्ट्र", "Maharashtra"),
    ("మహారాష్ట్ర", "Maharashtra"),
    ("maharashtra", "Maharashtra"),
    # West Bengal
    ("மேற்கு வங்காளம்", "West Bengal"),
    ("மேற்கு வங்காளத்தில்", "West Bengal"),
    ("பశ்சிம் வங்காளம்", "West Bengal"),
    ("ಪಶ್ಚಿಮ ಬಂಗಾಳ", "West Bengal"),
    ("പശ്ചിമ ബംഗാൾ", "West Bengal"),
    ("পশ্চিমবঙ্গ", "West Bengal"),
    ("পশ্চিম বঙ্গ", "West Bengal"),
    ("પશ્ચિમ બંગાળ", "West Bengal"),
    ("ਪੱਛਮੀ ਬੰਗਾਲ", "West Bengal"),
    ("ପଶ୍ଚିମ ବଙ୍ଗଳ", "West Bengal"),
    ("पश्चिम बंगाल", "West Bengal"),
    ("పశ్చిమ బెంగాల్", "West Bengal"),
    ("west bengal", "West Bengal"),
    # Punjab
    ("பஞ்சாப்", "Punjab"),
    ("பஞ்சாப்பில்", "Punjab"),
    ("ಪಂಜಾಬ್", "Punjab"),
    ("പഞ്ചാബ്", "Punjab"),
    ("পাঞ্জাব", "Punjab"),
    ("પંજાબ", "Punjab"),
    ("ਪੰਜਾਬ", "Punjab"),
    ("ପଞ୍ଜାବ", "Punjab"),
    ("पंजाब", "Punjab"),
    ("పంజాబ్", "Punjab"),
    ("punjab", "Punjab"),
    # Gujarat
    ("குஜராத்", "Gujarat"),
    ("குஜராத்தில்", "Gujarat"),
    ("ಗುಜರಾತ್", "Gujarat"),
    ("ഗുജറാത്ത്", "Gujarat"),
    ("গুজরাট", "Gujarat"),
    ("ગુજરાત", "Gujarat"),
    ("ਗੁਜਰਾਤ", "Gujarat"),
    ("ଗୁଜରାଟ", "Gujarat"),
    ("गुजरात", "Gujarat"),
    ("గుజరాత్", "Gujarat"),
    ("gujarat", "Gujarat"),
    # Odisha
    ("ஒடிசா", "Odisha"),
    ("ஒடிசாவில்", "Odisha"),
    ("ಒಡಿಶಾ", "Odisha"),
    ("ഒഡീഷ", "Odisha"),
    ("ওড়িশা", "Odisha"),
    ("ઓડિશા", "Odisha"),
    ("ਓਡੀਸ਼ਾ", "Odisha"),
    ("ओडिशा", "Odisha"),
    ("ఒడిశా", "Odisha"),
    ("ଓଡ଼ିଶା", "Odisha"),
    ("odisha", "Odisha"),
    # Bihar
    ("பீகார்", "Bihar"),
    ("பீகாரில்", "Bihar"),
    ("ಬಿಹಾರ", "Bihar"),
    ("ബീഹാർ", "Bihar"),
    ("বিহার", "Bihar"),
    ("બિહાર", "Bihar"),
    ("ਬਿਹਾਰ", "Bihar"),
    ("ବିହାର", "Bihar"),
    ("बिहार", "Bihar"),
    ("బీహార్", "Bihar"),
    ("bihar", "Bihar"),
    # Uttar Pradesh
    ("உத்தர பிரதேசம்", "Uttar Pradesh"),
    ("உத்தரப்பிரதேசம்", "Uttar Pradesh"),
    ("உத்தரப்பிரதேசத்தில்", "Uttar Pradesh"),
    ("ಉತ್ತರ ಪ್ರದೇಶ", "Uttar Pradesh"),
    ("ഉത്തർപ്രദേശ്", "Uttar Pradesh"),
    ("উত্তরপ্রদেশ", "Uttar Pradesh"),
    ("ઉત્તર પ્રદેશ", "Uttar Pradesh"),
    ("ਉੱਤਰ ਪ੍ਰਦੇਸ਼", "Uttar Pradesh"),
    ("ଉତ୍ତର ପ୍ରଦେଶ", "Uttar Pradesh"),
    ("उत्तर प्रदेश", "Uttar Pradesh"),
    ("ఉత్తర ప్రదేశ్", "Uttar Pradesh"),
    ("uttar pradesh", "Uttar Pradesh"),
    # Rajasthan
    ("ராஜஸ்தான்", "Rajasthan"),
    ("ராஜஸ்தானில்", "Rajasthan"),
    ("ರಾಜಸ್ಥಾನ", "Rajasthan"),
    ("രാജസ്ഥാൻ", "Rajasthan"),
    ("রাজস্থান", "Rajasthan"),
    ("રાજસ્થાન", "Rajasthan"),
    ("ਰਾਜਸਥਾਨ", "Rajasthan"),
    ("ରାଜସ୍ଥାନ", "Rajasthan"),
    ("राजस्थान", "Rajasthan"),
    ("రాజస్థాన్", "Rajasthan"),
    ("rajasthan", "Rajasthan"),
    # Madhya Pradesh
    ("மத்திய பிரதேசம்", "Madhya Pradesh"),
    ("மத்தியப்பிரதேசத்தில்", "Madhya Pradesh"),
    ("मध्य प्रदेश", "Madhya Pradesh"),
    ("మధ్య ప్రదేశ్", "Madhya Pradesh"),
    ("ಮಧ್ಯ ಪ್ರದೇಶ", "Madhya Pradesh"),
    ("മധ്യപ്രദേശ്", "Madhya Pradesh"),
    ("মধ্যপ্রদেশ", "Madhya Pradesh"),
    ("મધ્ય પ્રદેશ", "Madhya Pradesh"),
    ("ਮੱਧ ਪ੍ਰਦੇਸ਼", "Madhya Pradesh"),
    ("ମଧ୍ୟ ପ୍ରଦେଶ", "Madhya Pradesh"),
    ("madhya pradesh", "Madhya Pradesh"),
    # Haryana
    ("அரியானா", "Haryana"),
    ("ஹரியானா", "Haryana"),
    ("ஹரியானாவில்", "Haryana"),
    ("ಹರಿಯಾಣ", "Haryana"),
    ("ഹരിയാന", "Haryana"),
    ("হরিয়ানা", "Haryana"),
    ("હરિયાણા", "Haryana"),
    ("ਹਰਿਆਣਾ", "Haryana"),
    ("ହରିଆଣା", "Haryana"),
    ("हरियाणा", "Haryana"),
    ("హర్యానా", "Haryana"),
    ("haryana", "Haryana"),
)


# Canonical English names for every state/UT (lowercase). Used as a fallback so
# states without a regional alias in _STATE_ALIASES still resolve.
_ENGLISH_STATE_NAMES: frozenset[str] = frozenset(
    {
        "andhra pradesh",
        "arunachal pradesh",
        "assam",
        "bihar",
        "chhattisgarh",
        "goa",
        "gujarat",
        "haryana",
        "himachal pradesh",
        "jharkhand",
        "karnataka",
        "kerala",
        "madhya pradesh",
        "maharashtra",
        "manipur",
        "meghalaya",
        "mizoram",
        "nagaland",
        "odisha",
        "punjab",
        "rajasthan",
        "sikkim",
        "tamil nadu",
        "telangana",
        "tripura",
        "uttar pradesh",
        "uttarakhand",
        "west bengal",
        "andaman and nicobar islands",
        "chandigarh",
        "dadra and nagar haveli and daman and diu",
        "delhi",
        "jammu and kashmir",
        "ladakh",
        "lakshadweep",
        "puducherry",
    }
)


def _word_in(name: str, text: str) -> bool:
    """True if ``name`` appears in ``text`` as a whole word (case-insensitive).

    Uses word boundaries so a district named ``Narmada`` does not match a
    compound village name like ``Narmadamal``.
    """
    return re.search(rf"\b{re.escape(name.strip().lower())}\b", text.lower()) is not None


def _find_village(
    db: Session,
    text: str,
    state: str | None = None,
    district: str | None = None,
) -> Village | None:
    """Find a village referenced in ``text``.

    Village names are single words (e.g. ``Rampalli``) or, in the small demo
    dataset, ``"<District> Village"``. We match each word and each two-word
    phrase in the text against the exact village name (case-insensitive),
    preferring the longest candidate first so a ``"Guntur Village"`` query
    resolves to the village and a bare ``"Guntur"`` stays at district level.
    The lookup is narrowed to the resolved state/district when known.
    """
    tokens = [
        t
        for t in _WORD_RE.split(text.lower())
        if len(t) >= 3
    ]
    if not tokens:
        return None
    phrases = set(tokens)
    for i in range(len(tokens) - 1):
        phrases.add(f"{tokens[i]} {tokens[i + 1]}")
    for phrase in sorted(phrases, key=len, reverse=True):
        village = queries.find_village(db, phrase, state=state, district=district)
        if village is not None:
            return village
    return None


def _extract_location(
    db: Session, text: str
) -> tuple[str | None, str | None, str | None, str | None]:
    """Return (state_name, district_name, village_name, display_string)."""
    lowered = text.lower()

    def districts_for(state: State) -> list[District]:
        return list(db.scalars(select(District).where(District.state_id == state.id)))

    states = {s.name: s for s in queries.get_states(db)}

    matched_state: State | None = None
    for alias, canonical in _STATE_ALIASES:
        # Substring match: Telugu/Hindi case markers are concatenated to the
        # noun without spaces (e.g. "ఆంధ్రప్రదేశ్లో"), so \b boundaries would
        # miss them. State aliases are distinctive enough for substring match.
        if alias.lower() in lowered and canonical in states:
            matched_state = states[canonical]
            break

    if matched_state is None:
        # Fallback to the canonical name so states without a regional alias
        # (e.g. Mizoram, Ladakh, Tripura) still resolve.
        for name, state in states.items():
            if name.lower() in lowered:
                matched_state = state
                break

    state_name: str | None = None
    district_name: str | None = None
    if matched_state is not None:
        state_name = matched_state.name
        for district in districts_for(matched_state):
            if _word_in(district.name, lowered):
                district_name = district.name
                break
    else:
        for state in states.values():
            for district in districts_for(state):
                if _word_in(district.name, lowered):
                    state_name, district_name = state.name, district.name
                    break
            if state_name:
                break

    if state_name is None and district_name is None:
        # No state/district mention: still try a direct village-name lookup so a
        # bare "what about Rampalli?" can resolve, since village names are
        # distinctive single words. Otherwise nothing to work with.
        village = _find_village(db, lowered)
        if village is not None:
            district_name = db.scalar(
                select(District.name).where(District.id == village.district_id)
            )
            state_name = db.scalar(
                select(State.name)
                .join(District, District.state_id == State.id)
                .where(District.id == village.district_id)
            )
            suffix = "" if village.name.lower().endswith("village") else " village"
            return (state_name, district_name, village.name, f"{village.name}{suffix}, {district_name}, {state_name}")
        return (None, None, None, None)

    village = _find_village(db, lowered, state=state_name, district=district_name)
    if village is not None:
        if district_name is None:
            district_name = db.scalar(
                select(District.name).where(District.id == village.district_id)
            )
        if state_name is None:
            state_name = db.scalar(
                select(State.name)
                .join(District, District.state_id == State.id)
                .where(District.id == village.district_id)
            )
        suffix = "" if village.name.lower().endswith("village") else " village"
        display = f"{village.name}{suffix}, {district_name}, {state_name}"
        return (state_name, district_name, village.name, display)

    if district_name:
        return (state_name, district_name, None, f"{district_name}, {state_name}")
    return (state_name, None, None, state_name)


_DATA_METRICS = {"stage", "recharge", "extraction", "resource", "waterlevel"}
_DATA_QUERY_PATTERNS = {
    "which", "where", "list", "show", "districts", "states", "areas", "regions",
    "blocks", "mandals", "taluks", "villages", "units", "assessment units"
}

def classify_intent(text: str) -> str:
    if _wordset_match(text, _GREETING_WORDS) and not _contains_any(
        text,
        _METRIC_ALIASES["recharge"] | _METRIC_ALIASES["extraction"] | _METRIC_ALIASES["stage"],
    ):
        return "greeting"
    if _wordset_match(text, _THANKS_WORDS):
        return "thanks"
    if _contains_any(text, _HELP_WORDS):
        return "help"
    if _parse_scenario(text):
        return "scenario"
    if _contains_any(text, _FORECAST_WORDS) or _has_future_year(text):
        return "forecast"
    if _contains_any(text, _RECOMMEND_WORDS) and not (
        _is_definition_question(text) and extract_metric(text)
    ):
        return "recommend"
    # "How is stage of extraction measured?" asks for an explanation, not a
    # value — route it to knowledge/web even when it contains a metric keyword.
    if _is_how_it_works_question(text):
        return "terminology"
    if _contains_any(text, _WHY_WORDS) and (extract_metric(text) or _contains_any_term(text)):
        return "data_query"
    if _mentions_state(text):
        return "data_query"
    metric = extract_metric(text)
    if metric and metric in _DATA_METRICS:
        return "data_query"
    # Data query patterns (which/where/list/show + locations) override terminology
    lowered = text.lower()
    if any(p in lowered for p in _DATA_QUERY_PATTERNS):
        return "data_query"
    if _is_definition_question(text) and _contains_any_term(text):
        return "terminology"
    if _contains_any_term(text):
        return "terminology"
    return "fallback"


def _village_scope(village: str) -> str:
    if village.lower().endswith("village"):
        return village
    return f"{village} village"


def _format_scope(
    state: str | None,
    district: str | None,
    year: int | None,
    village: str | None = None,
    basin: str | None = None,
) -> str:
    from app.ingres.basins import BASIN_LABELS

    if basin:
        scope = BASIN_LABELS.get(basin, basin)
    elif village:
        scope = _village_scope(village)
        if district:
            scope = f"{scope}, {district} district, {state}"
        elif state:
            scope = f"{scope}, {state}"
    elif district:
        scope = f"{district} district, {state}"
    elif state:
        scope = state
    else:
        scope = _ALL_STATES_HINT
    if year:
        scope = f"{scope} ({year})"
    return scope


def _answer_terminology(raw: str, language: str) -> AnswerResult:
    canonical = resolve_term(raw.strip())
    if not canonical:
        canonical = None
        for term in TERMS:
            for alias in term["aliases"]:
                if alias.lower() in raw.lower():
                    canonical = term["term"]
                    break
            if canonical:
                break
    if not canonical:
        return AnswerResult(
            content="I could not find that term in my knowledge base. Try asking about recharge, extraction, stage of extraction, aquifer, assessment unit or GEC-2015.",
            response_type="terminology",
            intent="terminology",
            language=language,
        )
    entry = CANONICAL_BY_TERM[canonical]
    return AnswerResult(
        content=f"**{canonical}**: {entry['definition']}\n\nCategory: {entry['category']}.",
        response_type="terminology",
        intent="terminology",
        language=language,
    )


_SUPERLATIVE_MIN = {
    "lowest", "lower", "smallest", "small", "least", "minimum", "min",
    "bottom", "worst", "poorest", "fewest",
    # Hindi / transliterated & Telugu phrasings
    "sabse kam", "sabse kaam", "kam se kam", "sabse nyun", "nyunatam",
    "takkuva", "tagginde", "alpa",
}
_SUPERLATIVE_MAX = {
    "highest", "higher", "largest", "biggest", "most", "maximum", "max",
    "top", "best", "greatest", "richest",
    # Hindi / transliterated & Telugu phrasings
    "sabse zyada", "sabse jyada", "sabse adhik", "sarvadhik", "adhik",
    "ekkuva", "athyadhik",
}
_NUM_WORDS = {
    "two": 2, "three": 3, "four": 4, "five": 5, "six": 6,
    "seven": 7, "eight": 8, "nine": 9, "ten": 10,
}


def parse_superlative(text: str) -> tuple[str, int] | None:
    """Detect a ranking request like ``lowest recharge`` / ``top 5 districts``.

    Returns ``(direction, limit)`` where direction is ``min`` or ``max`` and
    limit is how many entries the user asked for (default 1), or ``None`` when
    the message contains no superlative phrasing.
    """
    lowered = text.lower()
    direction: str | None = None
    if re.search(r"\brank(?:s|ed|ing)?\s+(?:first|1st|#?\b1\b|number\s*(?:one|1))\b", lowered) or re.search(
        r"\b(?:number|#)\s*1\b", lowered
    ):
        return ("max", 1)
    if re.search(r"\brank(?:s|ed|ing)?\s+last\b", lowered):
        return ("min", 1)
    for w in _SUPERLATIVE_MAX:
        if re.search(rf"\b{re.escape(w)}\b", lowered):
            direction = "max"
            break
    if direction is None:
        for w in _SUPERLATIVE_MIN:
            if re.search(rf"\b{re.escape(w)}\b", lowered):
                direction = "min"
                break
    if direction is None:
        return None
    limit = 1
    m = (
        re.search(rf"\b(?:{'|'.join(_SUPERLATIVE_MAX | _SUPERLATIVE_MIN)})\s+(\d+)", lowered)
        or re.search(r"\b(\d+)\s+(?:states?|districts?|villages?|units?)", lowered)
        or re.search(r"\b(?:top|bottom)\s+(\d+)", lowered)
    )
    if m:
        try:
            limit = max(1, min(10, int(m.group(1))))
        except ValueError:
            limit = 1
    else:
        for w, n in _NUM_WORDS.items():
            if re.search(rf"\b(?:{'|'.join(_SUPERLATIVE_MAX | _SUPERLATIVE_MIN)})\s+{w}\b", lowered) or re.search(
                rf"\b{w}\s+(?:states?|districts?|villages?)\b", lowered
            ):
                limit = n
                break
    return (direction, limit)


def _answer_ranking(
    db: Session,
    language: str,
    metric: str,
    direction: str,
    limit: int,
    state: str | None,
    year: int | None,
    source_text: str,
) -> AnswerResult:
    """Rank states (or districts within a state) by an assessment metric."""
    metric_col = {
        "recharge": GroundwaterAssessment.recharge_total,
        "extraction": GroundwaterAssessment.extraction_total,
        "resource": GroundwaterAssessment.annual_extractable_resource,
    }.get(metric)
    value_expr = (
        func.sum(metric_col)
        if metric_col is not None
        else func.sum(GroundwaterAssessment.extraction_total)
        * 100.0
        / func.nullif(func.sum(GroundwaterAssessment.annual_extractable_resource), 0)
    )
    unit = "%" if metric == "stage" else "hm³"

    state_row = queries.resolve_state(db, state) if state else None

    def _base(demo: bool):
        q = (
            select(
                State.name if state_row is None else District.name,
                value_expr,
            )
            .select_from(GroundwaterAssessment)
            .join(AssessmentUnit, AssessmentUnit.id == GroundwaterAssessment.assessment_unit_id)
            .join(State, State.id == AssessmentUnit.state_id)
            .where(GroundwaterAssessment.is_demo == demo)
        )
        if state_row is not None:
            q = q.join(District, District.id == AssessmentUnit.district_id).where(
                District.state_id == state_row.id
            )
            group_col = District.name
        else:
            group_col = State.name
        return q.group_by(group_col)

    # Prefer real CGWB/IMD rows; fall back to the synthetic demo dataset only
    # when no real assessments exist at all.
    demo_pref = False
    latest = (
        db.query(func.max(GroundwaterAssessment.assessment_year))
        .join(AssessmentUnit, AssessmentUnit.id == GroundwaterAssessment.assessment_unit_id)
        .filter(GroundwaterAssessment.is_demo == demo_pref)
        .scalar()
    )
    if not latest:
        demo_pref = True
        latest = db.query(func.max(GroundwaterAssessment.assessment_year)).scalar()
    chosen_year = year or int(latest or 0)
    if not chosen_year:
        return AnswerResult(
            content="I could not find any groundwater assessment data to rank.",
            response_type="data", intent="data_query", language=language,
            sources=[], is_demo=False,
        )

    rows = db.execute(
        _base(demo_pref)
        .where(GroundwaterAssessment.assessment_year == chosen_year)
        .order_by(value_expr.asc() if direction == "min" else value_expr.desc())
        .limit(max(limit + 2, 3))
    ).all()
    rows = [(name, float(val) if val is not None else 0.0) for name, val in rows]
    if not rows:
        return AnswerResult(
            content=f"I could not find {metric} data for {chosen_year} to compare.",
            response_type="data", intent="data_query", language=language,
            sources=[], is_demo=demo_pref,
        )

    scope_label = f"districts in {state_row.name}" if state_row else "states & UTs"
    adj = {"min": "lowest", "max": "highest"}[direction]
    top_name, top_val = rows[0]
    body = (
        f"**{top_name}** has the {adj} annual groundwater {metric} among {scope_label}: "
        f"**{top_val:,.1f} {unit}** ({chosen_year})."
    )
    shown = rows[:limit]
    if limit > 1 and len(shown) > 1:
        word = {"min": "Lowest", "max": "Highest"}[direction]
        plural = "s" if len(shown) > 1 else ""
        listing = "\n".join(
            f"{i + 1}. **{name}** — {val:,.1f} {unit}"
            for i, (name, val) in enumerate(shown)
        )
        body += f"\n\n{word} {len(shown)} {scope_label}{plural}:\n{listing}"
    elif len(rows) > 1:
        nxt_name, nxt_val = rows[1]
        word = {"min": "Next lowest", "max": "Next highest"}[direction]
        body += f"\n\n{word}: **{nxt_name}** ({nxt_val:,.1f} {unit})."

    is_demo = demo_pref
    disclaimer = (
        f"\n\n⚠️ These figures are from {DEMO_SOURCE} and are for demonstration only."
        if is_demo
        else "\n\n📊 Source: CGWB/IMD real groundwater observations (imported dataset)."
    )
    content = f"{body}{disclaimer}"
    return AnswerResult(
        content=content,
        response_type="data",
        intent="data_query",
        language=language,
        location=state_row.name if state_row else None,
        sources=["CGWB/IMD imported observations"] if not is_demo else [DEMO_SOURCE],
        is_demo=is_demo,
    )


def _answer_data(
    text: str,
    db: Session,
    language: str,
    metric: str | None,
    state: str | None = None,
    district: str | None = None,
    village: str | None = None,
) -> AnswerResult:
    # Superlative / ranking questions ("which state has the lowest recharge?",
    # "top 5 districts by extraction") compare scopes instead of aggregating
    # one scope, so handle them before the single-scope summary path.
    sup = parse_superlative(text)
    if sup and metric in ("recharge", "extraction", "resource", "stage"):
        direction, limit = sup
        # Re-extract the scope with ranking keywords stripped: otherwise place
        # names like the village "Top" (Bargarh, Odisha) hijack "top N …".
        cleaned = re.sub(
            r"\b(top|bottom|lowest|low|highest|high|least|most|smallest|largest"
            r"|biggest|greatest|minimum|maximum|min|max|best|worst)\b",
            " ", text, flags=re.IGNORECASE,
        )
        rank_state, _d, _v, _disp = _extract_location(db, cleaned)
        return _answer_ranking(
            db, language, metric, direction, limit,
            state=rank_state, year=extract_year(text), source_text=text,
        )
    if state is None and district is None and village is None:
        state, district, village, display = _extract_location(db, text)
    elif village:
        display = _village_scope(village)
        if district:
            display = f"{display}, {district}, {state}"
        elif state:
            display = f"{display}, {state}"
    elif district:
        display = f"{district}, {state}"
    else:
        display = state
    year = extract_year(text)

    # A village-level question without an explicit year is a request for the
    # current snapshot, so default to the most recent assessment year rather
    # than aggregating the whole history into a confusing category breakdown.
    if village and year is None:
        latest = queries.get_latest_year(db, state=state, district=district, village=village)
        if latest:
            year = latest

    filters: dict = {"state": state, "district": district, "village": village}
    if year:
        filters["year"] = year
    summary = queries.get_summary(db, **filters)

    scope = _format_scope(state, district, year, village)

    unit = "hm³"
    cat_counts = {c["category"]: c["count"] for c in summary["category_counts"]}
    total_cats = sum(cat_counts.values())

    def cat_line() -> str:
        if not cat_counts:
            return ""
        order = ["Safe", "Semi-critical", "Critical", "Over-exploited"]
        parts = [f"{c}: {cat_counts.get(c, 0)}" for c in order if c in cat_counts]
        return f"Category breakdown ({total_cats} units) — " + "; ".join(parts) + "."

    def single_cat() -> str:
        if total_cats == 1:
            return next(iter(cat_counts), "")
        return ""

    units_txt = (
        ""
        if village
        else f" across {summary['assessment_units']} assessment units"
    )

    if metric == "recharge":
        body = (
            f"Annual groundwater recharge for {scope} is approximately "
            f"**{summary['total_recharge']:,.1f} {unit}**{units_txt}."
        )
    elif metric == "extraction":
        body = (
            f"Annual groundwater extraction for {scope} is approximately "
            f"**{summary['total_extraction']:,.1f} {unit}**{units_txt}."
        )
    elif metric == "resource":
        body = (
            f"The annual extractable groundwater resource for {scope} is approximately "
            f"**{summary['total_extraction'] / summary['average_stage_of_extraction'] * 100 if summary['average_stage_of_extraction'] else 0:,.1f} {unit}** (estimated from stage-of-extraction)."
        )
    elif metric == "stage":
        body = (
            f"The stage of groundwater extraction for {scope} is "
            f"**{summary['average_stage_of_extraction']:.1f}%** "
            f"(annual extraction ÷ annual extractable resource).\n"
            f"{f'Assessment category: {single_cat()}.' if single_cat() else cat_line()}"
        )
    elif metric == "category":
        if single_cat():
            body = f"The assessment category for {scope} is **{single_cat()}**."
        else:
            body = f"Assessment categories for {scope}:\n{cat_line()}"
    elif metric == "waterlevel":
        body = (
            f"Water level data is not present in the current dataset, so I cannot give "
            f"depth-to-water values for {scope}. I can instead share recharge, extraction, stage of extraction or category data."
        )
    else:
        body = (
            f"For {scope}, annual recharge is approximately **{summary['total_recharge']:,.1f} {unit}** "
            f"and annual extraction is approximately **{summary['total_extraction']:,.1f} {unit}**{units_txt}.\n"
            f"The stage of groundwater extraction is **{summary['average_stage_of_extraction']:.1f}%**.\n"
            f"{f'Assessment category: {single_cat()}.' if single_cat() else cat_line()}"
        )

    if summary["is_demo"]:
        disclaimer = (
            f"\n\n⚠️ These figures are from {DEMO_SOURCE} and are for demonstration only, not official IN-GRES/CGWB data."
        )
    else:
        disclaimer = (
            f"\n\n📊 Source: {summary['source']} — real CGWB/IMD groundwater observation data."
        )

    content = f"{body}{disclaimer}"
    return AnswerResult(
        content=content,
        response_type="data",
        intent="data_query",
        language=language,
        location=display or state,
        sources=[summary["source"]],
        is_demo=summary["is_demo"],
    )


_SUPERLATIVE_FIELD: dict[str, tuple[str, str]] = {
    "recharge": ("total_recharge", "annual recharge"),
    "extraction": ("total_extraction", "annual extraction"),
    "stage": ("average_stage_of_extraction", "stage of extraction"),
}


def _answer_superlative(
    db: Session,
    language: str,
    metric: str,
    direction: str,
) -> AnswerResult:
    """Backwards-compatible wrapper: rank all states/UTs on a metric.

    Delegates to the single-query ranking engine (`_answer_ranking`) instead of
    issuing one summary query per state, which made these replies very slow on
    large datasets.
    """
    return _answer_ranking(
        db, language, metric,
        "min" if direction == "low" else "max",
        limit=3, state=None, year=None, source_text="",
    )


def _category_label(stage: float | None) -> str:
    if stage is None:
        return "Unknown"
    if stage >= 100:
        return "Over-exploited"
    if stage >= 90:
        return "Critical"
    if stage >= 70:
        return "Semi-critical"
    return "Safe"


def _recommendations_for_stage(stage: float | None) -> list[str]:
    """Rule-based groundwater management measures keyed on stage of extraction."""
    if stage is None:
        return [
            "Collect more assessment data to determine the stage of extraction before planning interventions.",
            "Start a groundwater monitoring programme covering water levels, abstraction and recharge.",
        ]
    if stage >= 100:
        return [
            "Stop issuing new groundwater abstraction permits in the area.",
            "Enforce extraction limits/quotas and meter all major wells.",
            "Build artificial recharge structures — recharge pits, check dams and percolation tanks.",
            "Switch to micro-irrigation (drip/sprinkler) and diversify away from water-intensive crops.",
            "Introduce volumetric water pricing to discourage excessive pumping.",
        ]
    if stage >= 90:
        return [
            "Pause new drilling permits and strictly monitor existing abstraction.",
            "Accelerate community-scale recharge — rooftop harvesting, farm ponds and check dams.",
            "Convert flood irrigation to drip/sprinkler for high-water crops.",
            "Use treated surface water conjunctively to reduce groundwater dependence.",
        ]
    if stage >= 70:
        return [
            "Promote efficient irrigation (drip, sprinkler) and mulching.",
            "Encourage rooftop rainwater harvesting and farm ponds.",
            "Monitor water levels and extraction regularly.",
            "Shift gradually towards low-water crops.",
        ]
    return [
        "Keep monitoring water levels and extraction to stay ahead of change.",
        "Encourage rainwater harvesting to preserve the buffer.",
        "Maintain efficient irrigation practices as a precaution.",
    ]


def _answer_recommend(
    text: str,
    db: Session,
    language: str,
    context: dict,
) -> AnswerResult:
    state = context.get("state_name")
    district = context.get("district")
    village = context.get("village")
    if state is None and district is None and village is None:
        state, district, village, _display = _extract_location(db, text)
    display = _format_scope(state, district, None, village)

    summary = queries.get_summary(db, state=state, district=district, village=village)
    stage = summary["average_stage_of_extraction"]

    measures = _recommendations_for_stage(stage)
    bullets = "\n".join(f"• {m}" for m in measures)
    if summary["is_demo"]:
        data_note = f"from the {DEMO_SOURCE} for demonstration"
    else:
        data_note = f"based on real {summary['source']}"
    content = (
        f"Groundwater management recommendations for {display} "
        f"(average stage of extraction **{stage:.1f}%** — {_category_label(stage)}):\n\n"
        f"{bullets}\n\n"
        f"⚠️ These are generic suggestions generated {data_note}. "
        f"Always consult local hydrogeologists and official CGWB guidance before acting."
    )
    return AnswerResult(
        content=content,
        response_type="recommend",
        intent="recommend",
        language=language,
        location=display or state,
        sources=[summary["source"]],
        is_demo=summary["is_demo"],
    )


def _forecast_scope(
    db: Session,
    text: str,
    context: dict,
) -> tuple[str | None, str | None, str | None, str | None, str]:
    """Resolve (state, district, village, basin, display) for a forecast query."""
    state = context.get("state_name")
    district = context.get("district")
    village = context.get("village")
    basin = context.get("basin")
    if basin is None:
        basin = _extract_basin(text)
    if basin is not None:
        state = district = village = None
    elif state is None and district is None and village is None:
        state, district, village, _display = _extract_location(db, text)
    return state, district, village, basin, _format_scope(state, district, None, village, basin)


def _extract_basin(text: str) -> str | None:
    """Detect an Indian river basin name in free text.

    Matches canonical names and the short forms users type ("godavari basin",
    "krishna river"). Returns the canonical basin name or ``None``.
    """
    from app.ingres.basins import BASIN_LABELS

    lowered = f" {text.lower().strip()} "
    for name in BASIN_LABELS:
        label = BASIN_LABELS[name].lower()
        if f" {label} " in lowered or f" {name.lower()} " in lowered:
            return name
        if label.endswith("river basin") and f" {label[:-len(' river basin')]} " in lowered:
            return name
    return None


def _model_line(fc: dict) -> str:
    best = fc.get("best_method")
    validation = fc.get("validation") or {}
    rmse = None
    if best and validation.get(best):
        rmse = validation[best].get("rmse")
    line = f"Model: {fc.get('method_label', fc.get('method'))} (selected by out-of-sample validation"
    if rmse is not None:
        line += f"; RMSE {rmse} {fc.get('unit')}"
    return line + ")."


def _answer_forecast(
    text: str,
    db: Session,
    language: str,
    context: dict,
) -> AnswerResult:
    metric = context.get("metric") or extract_metric(text) or "stage"
    horizon = extract_horizon(text)
    state, district, village, basin, display = _forecast_scope(db, text, context)

    fc = predict.forecast(
        db,
        state=state,
        district=district,
        village=village,
        basin=basin,
        metric=metric,
        horizon=horizon,
        method="auto",
    )
    unit = fc["unit"]
    label = predict.METRIC_LABELS.get(metric, metric)
    summary = queries.get_summary(
        db, state=state, district=district, village=village, basin=basin
    )

    if not fc["forecast"]:
        return AnswerResult(
            content=f"{fc.get('note', '')}\n\n⚠️ {_FORECAST_DISCLAIMER}",
            response_type="forecast",
            intent="forecast",
            language=language,
            location=display or fc["scope"],
            sources=[summary["source"]],
            is_demo=summary["is_demo"],
        )

    last_value = fc["historical"][-1]["value"]
    last_year = fc["historical"][-1]["year"]
    first_pt = fc["forecast"][0]
    last_pt = fc["forecast"][-1]
    direction = fc["direction"]

    lines = [
        f"Projection for {display}: over the next {horizon} year(s), {label} is projected to be "
        f"**~{fc['end_value']:,.1f} {unit}** by {last_pt['year']} ({direction}).",
        f"95% forecast band for {first_pt['year']}: **{first_pt['lower']:,.1f}–{first_pt['upper']:,.1f} {unit}**.",
    ]
    if fc.get("pct_change") is not None:
        lines.append(
            f"That is a change of about {abs(fc['pct_change']):.1f}% from the last observed value "
            f"({last_value:,.1f} {unit} in {last_year})."
        )
    if fc.get("r2") is not None:
        lines.append(f"Trend fit R² = {fc['r2']:.3f}.")
    if metric == "stage" and fc.get("risk"):
        lines.append(
            f"Projected end-of-horizon category: **{fc['risk'].replace('-', ' ').title()}**."
        )
    if fc.get("years_to_threshold"):
        lines.append(
            f"At this pace, the over-exploited threshold (100%) is crossed in about "
            f"{fc['years_to_threshold']} year(s)."
        )
    lines.append(_model_line(fc))
    lines.append(f"\n⚠️ {_FORECAST_DISCLAIMER}")

    return AnswerResult(
        content="\n".join(lines),
        response_type="forecast",
        intent="forecast",
        language=language,
        location=display or fc["scope"],
        sources=[summary["source"]],
        is_demo=summary["is_demo"],
    )


def _answer_scenario(
    text: str,
    db: Session,
    language: str,
    context: dict,
) -> AnswerResult:
    scenario = _parse_scenario(text)
    if scenario is None:
        return AnswerResult(
            content=(
                "I can run what-if scenarios on pumping or recharge, for example "
                "\"what if extraction increases 10%?\" or \"what if recharge decreases 20% in Telangana?\". "
                "Mention a place and a percentage to get a scenario forecast."
            ),
            response_type="fallback",
            intent="scenario",
            language=language,
            location=context.get("location_display"),
            sources=[],
            is_demo=False,
        )

    metric = context.get("metric") or extract_metric(text) or "stage"
    horizon = extract_horizon(text)
    state, district, village, basin, display = _forecast_scope(db, text, context)

    baseline = predict.forecast(
        db,
        state=state,
        district=district,
        village=village,
        basin=basin,
        metric=metric,
        horizon=horizon,
        method="auto",
    )
    scen = predict.forecast(
        db,
        state=state,
        district=district,
        village=village,
        basin=basin,
        metric=metric,
        horizon=horizon,
        method="auto",
        scenario=scenario,
    )
    unit = scen["unit"]
    label = predict.METRIC_LABELS.get(metric, metric)
    summary = queries.get_summary(
        db, state=state, district=district, village=village, basin=basin
    )

    if not scen["forecast"] or not baseline["forecast"]:
        return AnswerResult(
            content=f"{scen.get('note', '')}\n\n⚠️ {_FORECAST_DISCLAIMER}",
            response_type="forecast",
            intent="scenario",
            language=language,
            location=display or scen["scope"],
            sources=[summary["source"]],
            is_demo=summary["is_demo"],
        )

    last_pt = scen["forecast"][-1]
    scen_end = scen["end_value"]
    base_end = baseline["end_value"]
    delta = scen_end - base_end
    sign = "+" if delta >= 0 else ""

    lines = [
        f"Scenario — {_scenario_label(scenario, language)}.",
        f"Projected {label} for {display} over the next {horizon} year(s): "
        f"**~{scen_end:,.1f} {unit}** by {last_pt['year']}, compared with ~{base_end:,.1f} {unit} "
        f"without the change ({sign}{delta:,.1f} {unit}).",
        f"95% band in {last_pt['year']}: **{last_pt['lower']:,.1f}–{last_pt['upper']:,.1f} {unit}**.",
    ]
    if metric == "stage" and scen.get("risk"):
        lines.append(
            f"Projected end-of-horizon category under this scenario: "
            f"**{scen['risk'].replace('-', ' ').title()}**."
        )
    lines.append(_model_line(scen))
    lines.append(f"\n⚠️ {_FORECAST_DISCLAIMER}")

    return AnswerResult(
        content="\n".join(lines),
        response_type="forecast",
        intent="scenario",
        language=language,
        location=display or scen["scope"],
        sources=[summary["source"]],
        is_demo=summary["is_demo"],
    )


def _localise(content: str, language: str, source_text: str | None = None) -> str:
    """Translate an answer into the user's language via the LLM.

    Returns the original (English) content unchanged when the language is English
    or when the LLM is disabled/unreachable, so behaviour is deterministic offline.
    """
    if not content or not language or language == "en":
        return content
    from app.rag.llm import translate as llm_translate

    translated = llm_translate(content, language, source_text=source_text)
    return translated if translated else content


def answer(
    text: str,
    db: Session,
    language: str | None = None,
    context: dict | None = None,
) -> AnswerResult:
    """Answer a message.

    ``context`` may supply pre-extracted entities (from the orchestrator,
    including multi-turn carry-over) as ``{"metric", "state_name", "district",
    "village"}`` so the data path does not re-extract (and lose) them.

    The reply is always produced in the user's language: the final content is
    translated via the LLM whenever the detected language is not English.
    """
    context = context or {}
    lang = language or detect_language(text)
    intent = classify_intent(text)

    if intent == "greeting":
        result = AnswerResult(
            content=_GREETING_REPLY.get(lang, _GREETING_REPLY["en"]),
            response_type="greeting", intent="greeting", language=lang,
            sources=[], is_demo=False,
        )
    elif intent == "thanks":
        result = AnswerResult(
            content=_THANKS_REPLY.get(lang, _THANKS_REPLY["en"]),
            response_type="thanks", intent="thanks", language=lang,
            sources=[], is_demo=False,
        )
    elif intent == "help":
        result = AnswerResult(
            content=_HELP_REPLY.get(lang, _HELP_REPLY["en"]),
            response_type="help", intent="help", language=lang,
            sources=[], is_demo=False,
        )
    elif intent == "scenario":
        result = _answer_scenario(text, db, lang, context)
    elif intent == "forecast":
        result = _answer_forecast(text, db, lang, context)
    elif intent == "recommend":
        result = _answer_recommend(text, db, lang, context)
    elif intent == "terminology":
        state = context.get("state_name")
        metric = context.get("metric") or extract_metric(text)
        district = context.get("district")
        village = context.get("village")
        if not state:
            state, district, village, _display = _extract_location(db, text)
        if state and metric:
            result = _answer_data(
                text, db, lang, metric,
                state=state, district=district, village=village,
            )
        else:
            result = _answer_terminology(text, lang)
    else:
        metric = context.get("metric") or extract_metric(text)
        state = context.get("state_name")
        if intent == "data_query" or state:
            # Superlative phrasing ("lowest recharge", "top 5 districts…") is
            # handled inside _answer_data, which ranks states nationally or
            # districts within the resolved scope.
            result = _answer_data(
                text, db, lang, metric,
                state=state,
                district=context.get("district"),
                village=context.get("village"),
            )
        else:
            state, _district, _village, _display = _extract_location(db, text)
            if state:
                result = _answer_data(text, db, lang, metric, state=state)
            else:
                result = AnswerResult(
                    content="I'm not sure how to answer that yet." + _CAPABILITIES_HINT,
                    response_type="fallback", intent="fallback", language=lang,
                    sources=[], is_demo=False,
                )

    if lang != "en":
        result.content = _localise(result.content, lang, source_text=text)
    return result