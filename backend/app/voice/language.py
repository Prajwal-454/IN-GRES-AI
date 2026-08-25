"""Language detection for voice (English / Telugu / Hindi).

Uses script detection plus code-switching heuristics so a mixed utterance
like "AP lo groundwater extraction entha?" still lands on a usable language.
The result mirrors the shape used by the STT layer:
``{"language": "te", "confidence": 0.94}``.
"""

from __future__ import annotations

import re

from app.ai.assistant import detect_language as assistant_detect_language

_TELUGU_RE = re.compile(r"[\u0C00-\u0C7F]")
_HINDI_RE = re.compile(r"[\u0900-\u097F]")

# Common Telugu/Hindi particles embedded in otherwise-English text
# (code-switching markers) that push the utterance towards the local language.
_TELUGU_MARKERS = (
    "entha",
    "ela undi",
    "elaundi",
    "endi",
    "lo ",
    "tappithe",
    "unna",
    "ledu",
    "cheppandi",
    "telugu lo",
    "ap lo",
    "ts lo",
    "tg lo",
)
_HINDI_MARKERS = (
    "kitna",
    "kaise",
    "hai",
    "kya",
    "batao",
    "bataiye",
    "hindi me",
    "me bolo",
)


def detect_language_with_confidence(
    text: str, hint: str | None = None
) -> dict[str, float | str]:
    """Return ``{"language": "en"|"te"|"hi", "confidence": 0.0-1.0}``."""
    if hint and hint in ("en", "te", "hi"):
        return {"language": hint, "confidence": 0.99}
    lowered = text.lower()

    telugu_ratio = _ratio(_TELUGU_RE, text)
    hindi_ratio = _ratio(_HINDI_RE, text)

    if telugu_ratio > 0:
        return {"language": "te", "confidence": 0.9 + 0.1 * min(1.0, telugu_ratio)}
    if hindi_ratio > 0:
        return {"language": "hi", "confidence": 0.9 + 0.1 * min(1.0, hindi_ratio)}

    if any(m in lowered for m in _TELUGU_MARKERS):
        return {"language": "te", "confidence": 0.78}
    if any(m in lowered for m in _HINDI_MARKERS):
        return {"language": "hi", "confidence": 0.78}

    # Pure ASCII (English) — high confidence when it looks like English text.
    if re.search(r"[a-zA-Z]{2,}", text):
        return {"language": "en", "confidence": 0.9}
    return {"language": "en", "confidence": 0.55}


def _ratio(pattern: re.Pattern[str], text: str) -> float:
    matches = len(pattern.findall(text))
    letters = len(re.findall(r"[A-Za-z\u0C00-\u0C7F\u0900-\u097F]", text))
    if letters == 0:
        return 0.0
    return min(1.0, matches / max(1, letters))


# Re-export the simple detector used across the web app for convenience.
detect_language = assistant_detect_language