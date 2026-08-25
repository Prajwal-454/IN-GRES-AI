from __future__ import annotations

TERMS: list[dict] = [
    {
        "term": "groundwater",
        "aliases": ["ground water", "ground-water", "subsurface water", "underground water", "భూగర్భ జలం", "భూగర్భ జలాలు", "भूजल"],
        "definition": "Water present beneath Earth's surface in soil pore spaces and in fractures of rock formations.",
        "category": "general",
    },
    {
        "term": "groundwater recharge",
        "aliases": ["recharge", "ground water recharge", "భూగర్భ జల పునర్భరణం", "భూగర్భ జలాల పునరుద్ధరణ", "भूजल पुनर्भरण"],
        "definition": "The process by which water from precipitation or surface water enters the groundwater system.",
        "category": "metric",
    },
    {
        "term": "groundwater extraction",
        "aliases": ["extraction", "withdrawal", "ground water extraction", "భూగర్భ జల వెలికితీత", "भूजल निष्कर्षण"],
        "definition": "The volume of groundwater withdrawn from aquifers for irrigation, domestic and industrial use.",
        "category": "metric",
    },
    {
        "term": "annual extractable groundwater resource",
        "aliases": ["annual extractable resource", "extractable groundwater resource", "extractable resource", "annual extractable ground water resource", "వార్షిక వెలికితీయదగిన భూగర్భ జల వనరు", "वार्षिक निष्कर्षणीय भूजल संसाधन"],
        "definition": "The groundwater resource available for extraction in a year after keeping aside natural discharge.",
        "category": "metric",
    },
    {
        "term": "stage of groundwater extraction",
        "aliases": ["stage of extraction", "extraction stage", "stage", "భూగర్భ జల వెలికితీత దశ", "भूजल निष्कर्षण चरण"],
        "definition": "The ratio of annual groundwater extraction to annual extractable groundwater resource, expressed as a percentage.",
        "category": "metric",
    },
    {
        "term": "assessment unit",
        "aliases": ["assessment unit", "నిర్ణయ ప్రమాణం", "आकलन इकाई"],
        "definition": "The basic geographic unit (typically a mandal, block or watershed) for which groundwater resources are assessed.",
        "category": "geography",
    },
    {
        "term": "aquifer",
        "aliases": ["aquifer", "water bearing formation", "జలాశయం", "जलभृत"],
        "definition": "A body of permeable rock or sediment capable of storing and transmitting groundwater.",
        "category": "general",
    },
    {
        "term": "safe",
        "aliases": ["safe", "safe zone", "సురక్షితం", "सुरक्षित"],
        "definition": "Assessment category where stage of groundwater extraction is below 70%.",
        "category": "category",
    },
    {
        "term": "semi-critical",
        "aliases": ["semi critical", "semi-critical", "అర్ధ-క్లిష్ట", "अर्ध-संकटग्रस्त"],
        "definition": "Assessment category where stage of groundwater extraction is between 70% and 90%.",
        "category": "category",
    },
    {
        "term": "critical",
        "aliases": ["critical", "critical zone", "క్లిష్ట", "संकटग्रस्त"],
        "definition": "Assessment category where stage of groundwater extraction is between 90% and 100%.",
        "category": "category",
    },
    {
        "term": "over-exploited",
        "aliases": ["over exploited", "overexploited", "over-exploited", "అతిగా వెలికితీసిన", "अति-दोहन"],
        "definition": "Assessment category where annual groundwater extraction exceeds the annual extractable resource (stage above 100%).",
        "category": "category",
    },
    {
        "term": "GEC-2015",
        "aliases": ["GEC 2015", "Ground Water Estimation Committee", "groundwater estimation committee", "GEC"],
        "definition": "The Ground Water Estimation Committee methodology (2015) used for assessing India's groundwater resources.",
        "category": "methodology",
    },
]

CANONICAL_BY_TERM: dict[str, dict] = {t["term"]: t for t in TERMS}

ALIAS_MAP: dict[str, str] = {}
for _term in TERMS:
    for _alias in _term["aliases"]:
        ALIAS_MAP[_alias.lower()] = _term["term"]


def resolve_term(raw: str) -> str | None:
    lookup = raw.strip().lower()
    if lookup in ALIAS_MAP:
        return ALIAS_MAP[lookup]
    for term in TERMS:
        if term["term"].lower() == lookup:
            return term["term"]
    return None


def get_definition(term: str) -> str | None:
    canonical = resolve_term(term)
    if canonical:
        return CANONICAL_BY_TERM[canonical]["definition"]
    return None