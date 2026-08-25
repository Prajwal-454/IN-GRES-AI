"""Fast unit tests for the AI assistant and orchestrator (no database needed)."""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.ai.assistant import (
    _contains_any_term,
    _extract_location,
    _is_definition_question,
    _mentions_state,
    _word_in,
    classify_intent,
    detect_language,
    extract_metric,
    extract_year,
)
from app.ai.orchestrator import StateGraph
from app.database import Base
from app.models.groundwater import State


def test_detect_language_english():
    assert detect_language("What is the groundwater situation?") == "en"


def test_detect_language_telugu():
    assert detect_language("తెలంగాణలో భూగర్భజల పరిస్థితి ఎలా ఉంది?") == "te"


def test_detect_language_hindi():
    assert detect_language("गुंटूर जिले में पुनर्भरण क्या है?") == "hi"


def test_detect_language_more_scripts():
    assert detect_language("தமிழ்நாட்டில் நிலத்தடி நீர் நிலை எப்படி?") == "ta"
    assert detect_language("गुजरात में भूजल कैसा है?") == "hi"  # Devanagari
    assert detect_language("ಗುಜರಾತ್ನಲ್ಲಿ ಭೂಗರ್ಭಜಲ ಹೇಗಿದೆ?") == "kn"
    assert detect_language("গুজরাতে ভূগর্ভস্থ জল কেমন?") == "bn"
    assert detect_language("ગુજરાતમાં ભૂગર્ભજળની સ્થિતિ કેવી છે?") == "gu"
    assert detect_language("പഞ്ചാബിൽ ഭൂഗർഭജലം എങ്ങനെയുണ്ട്?") == "ml"
    assert detect_language("ਪੰਜਾਬ ਵਿੱਚ ਭੂਮੀਗਤ ਪਾਣੀ ਦੀ ਸਥਿਤੀ ਕਿਵੇਂ ਹੈ?") == "pa"
    assert detect_language("ఒడిశాలో నీటి స్థితి ఎలా ఉంది?") == "te"


def test_localise_english_unchanged():
    from app.ai.assistant import _localise

    assert _localise("Hello", "en") == "Hello"
    assert _localise("Hello", "") == "Hello"


def test_localise_uses_llm_translation(monkeypatch):
    from app.ai.assistant import _localise

    def fake_translate(text, language, source_text=None):
        return f"[{language}] {text}"

    monkeypatch.setattr("app.rag.llm.translate", fake_translate)
    assert _localise("Recharge is 120.5 hm³", "te") == "[te] Recharge is 120.5 hm³"


def test_localise_falls_back_to_english(monkeypatch):
    from app.ai.assistant import _localise

    def fake_translate(text, language, source_text=None):
        return None

    monkeypatch.setattr("app.rag.llm.translate", fake_translate)
    assert _localise("Recharge is 120.5 hm³", "te") == "Recharge is 120.5 hm³"


def test_llm_translate_disabled():
    from app.rag.llm import translate

    assert translate("Recharge is 120.5 hm³", "te") is None


def test_classify_intent():
    assert classify_intent("hi") == "greeting"
    assert classify_intent("what can you do?") == "help"
    assert classify_intent("thanks!") == "thanks"
    assert classify_intent("what is an aquifer?") == "terminology"
    assert classify_intent("recharge in Guntur district") == "data_query"


def test_definition_question():
    assert _is_definition_question("What is an aquifer?")
    assert _is_definition_question("How is groundwater recharge estimated?")
    assert not _is_definition_question("Recharge in Guntur district")


def test_contains_term():
    assert _contains_any_term("explain stage of extraction")


def test_extract_metric():
    assert extract_metric("what is the recharge?") == "recharge"
    assert extract_metric("tell me extraction numbers") == "extraction"
    assert extract_metric("stage of extraction") == "stage"


def test_extract_year():
    assert extract_year("in 2022") == 2022
    assert extract_year("hello") is None


def test_word_in_respects_boundaries():
    assert _word_in("Narmada", "what about narmadamal?") is False
    assert _word_in("Narmada", "recharge in narmada district") is True
    assert _word_in("East Godavari", "data for east godavari please") is True
    assert _word_in("East Godavari", "east godavaripuram village") is False
    assert _word_in("Guntur", "recharge in Guntur Village") is True


def test_words_split_keeps_all_scripts():
    from app.ai.assistant import _words

    assert "தமிழ்நாட்டில்" in _words("தமிழ்நாட்டில் நிலத்தடி நீர் நிலை எப்படி?")
    assert "ಕರ್ನಾಟಕದಲ್ಲಿ" in _words("ಕರ್ನಾಟಕದಲ್ಲಿ ನೀರಿನ ಮಟ್ಟ ಹೇಗಿದೆ?")
    assert "పునర్భరణం" in _words("కర్ణాటకలో పునర్భరణం ఎంత?")
    assert "ਪੰਜਾਬ" in _words("ਪੰਜਾਬ ਵਿੱਚ ਭੂਮੀਗਤ ਪਾਣੀ ਦੀ ਸਥਿਤੀ ਕਿਵੇਂ ਹੈ?")
    assert "پنجاب" not in _words("پنجاب")  # Urdu script not yet supported
    assert "recharge" in _words("Recharge in Telangana")


def test_classify_intent_multilingual():
    assert classify_intent("வணக்கம்") == "greeting"
    assert classify_intent("ನಮಸ್ಕಾರ") == "greeting"
    assert classify_intent("നമസ്കാരം") == "greeting"
    assert classify_intent("হ্যালো") == "greeting"
    assert classify_intent("ನಮಸ್ತೆ") == "greeting"
    assert classify_intent("ਸਤ ਸ੍ਰੀ ਅਕਾਲ") == "greeting"
    assert classify_intent("ହେଲୋ") == "greeting"
    assert classify_intent("நன்றி") == "thanks"
    assert classify_intent("ধন্যবাদ") == "thanks"
    assert classify_intent("ಧನ್ಯವಾದ") == "thanks"
    assert classify_intent("എന്ത് ചെയ്യാൻ കഴിയും?") == "help"
    assert classify_intent("এটা সাহায্য") == "help"
    assert classify_intent("மகாராஷ்டிராவில் பிரித்தெடுப்பு நிலை என்ன?") == "data_query"
    assert classify_intent("ಕರ್ನಾಟಕದಲ್ಲಿ ನೀರಿನ ಮಟ್ಟ ಹೇಗಿದೆ?") == "data_query"
    assert classify_intent("ਪੰਜਾਬ ਵਿੱਚ ਪਾਣੀ ਕੱਢਣ ਕਿਵੇਂ ਹੈ?") == "data_query"
    assert classify_intent("ఒడిశాలో భూగర్భ జల వెలికితీత ఎలా ఉంది?") == "data_query"


def test_classify_intent_why_multilingual():
    assert classify_intent("தமிழ்நாட்டில் நிலத்தடி நீர் நிலை ஏன் குறைகிறது?") == "data_query"
    assert classify_intent("கேரளத்தில் நீர் நிலை ஏன் குறைகிறது?") == "data_query"


def test_classify_intent_state_mention_is_data_query():
    assert classify_intent("What is the groundwater situation in Mizoram?") == "data_query"
    assert classify_intent("Tell me about Ladakh water levels") == "data_query"
    assert classify_intent("what is an aquifer?") == "terminology"
    assert classify_intent("define over-exploited") == "terminology"


def test_mentions_state_covers_all_36():
    assert _mentions_state("What is the groundwater situation in Mizoram?")
    assert _mentions_state("Tell me about Ladakh water levels")
    assert _mentions_state("Tripura stage of extraction?")
    assert _mentions_state("What about Andaman and Nicobar Islands?")
    assert _mentions_state("chandigarh status")
    assert _mentions_state("தமிழ்நாட்டில் நிலை")
    assert not _mentions_state("what is groundwater?")


def test_extract_location_fallback_to_canonical_state_names():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(bind=engine)
    db = sessionmaker(bind=engine)()
    try:
        db.add_all([State(name="Mizoram", code="MZ"), State(name="Ladakh", code="LA")])
        db.commit()
        assert _extract_location(db, "What is the groundwater situation in Mizoram?")[0] == "Mizoram"
        assert _extract_location(db, "Tell me about Ladakh water levels")[0] == "Ladakh"
    finally:
        db.close()
        engine.dispose()


def test_extract_metric_multilingual():
    assert extract_metric("தமிழ்நாட்டில் பிரித்தெடுப்பு நிலை") == "stage"
    assert extract_metric("மகாராஷ்டிராவில் வெளியேற்றம்") == "extraction"
    assert extract_metric("കർണാടകയിലെ പുനഃഭരണം") == "recharge"
    assert extract_metric("ভূগর্ভস্থ জল নিষ্কাশন") == "extraction"
    assert extract_metric("पश्चिम बंगाल में निष्कर्षण") == "extraction"
    assert extract_metric("गुजरात में निष्कर्षण चरण") == "stage"
    assert extract_metric("ਪੰਜਾਬ ਵਿੱਚ ਪਾਣੀ ਦਾ ਪੱਧਰ") == "waterlevel"
    assert extract_metric("ଜଳସ୍ତର") == "waterlevel"
    assert extract_metric("ತಮಿಳುನಾಡಿನಲ್ಲಿ ವರ್ಗ") == "category"


def test_state_aliases_cover_scripts():
    from app.ai.assistant import _STATE_ALIASES

    aliases = dict(_STATE_ALIASES)
    assert aliases["தமிழ்நாடு"] == "Tamil Nadu"
    assert aliases["தமிழ்நாட்டில்"] == "Tamil Nadu"
    assert aliases["తమిళనాడు"] == "Tamil Nadu"
    assert aliases["तमिलनाडु"] == "Tamil Nadu"
    assert aliases["ಕರ್ನಾಟಕ"] == "Karnataka"
    assert aliases["కర్ణాటకలో"] == "Karnataka"
    assert aliases["कर्नाटक"] == "Karnataka"
    assert aliases["కేరళ"] == "Kerala"
    assert aliases["ಕೇರಳ"] == "Kerala"
    assert aliases["മഹാരാഷ്ട്ര"] == "Maharashtra"
    assert aliases["महाराष्ट्र"] == "Maharashtra"
    assert aliases["মহারাষ্ট্র"] == "Maharashtra"
    assert aliases["পশ্চিমবঙ্গ"] == "West Bengal"
    assert aliases["पश्चिम बंगाल"] == "West Bengal"
    assert aliases["ਪੰਜਾਬ"] == "Punjab"
    assert aliases["गुजरात"] == "Gujarat"
    assert aliases["ગુજરાત"] == "Gujarat"
    assert aliases["ଓଡ଼ିଶା"] == "Odisha"
    assert aliases["ఒడిశా"] == "Odisha"
    assert aliases["बिहार"] == "Bihar"
    assert aliases["उत्तर प्रदेश"] == "Uttar Pradesh"
    assert aliases["राजस्थान"] == "Rajasthan"
    assert aliases["हरियाणा"] == "Haryana"


def test_state_graph_invoke():
    calls: list[str] = []

    def a(state: dict, db):
        calls.append("a")
        state["x"] = 1
        return "b"

    def b(state: dict, db):
        calls.append("b")
        state["done"] = True
        return None

    graph = StateGraph()
    graph.set_entry("a")
    graph.add_node("a", a, route=lambda state: "b")
    graph.add_node("b", b)

    result = graph.invoke({"trace": []}, db=None)
    assert result["x"] == 1
    assert result["done"] is True
    assert calls == ["a", "b"]


def test_state_graph_max_steps():
    def loop(state: dict, db):
        state.setdefault("n", 0)
        state["n"] += 1
        return "loop"

    graph = StateGraph()
    graph.set_entry("loop")
    graph.add_node("loop", loop)
    result = graph.invoke({"trace": []}, db=None)
    assert result["n"] <= 12
