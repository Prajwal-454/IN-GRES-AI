"""Text-to-speech abstraction.

The pipeline depends only on ``TtsProvider.synthesize``. Three providers ship
with IN-GRES:

* ``mock``   - local dev, returns the text itself (no audio).
* ``edge``   - FREE Microsoft Edge neural voices via ``edge-tts``. No API key,
  works for English, Telugu (te-IN-ShrutiNeural) and Hindi (hi-IN-MadhurNeural).
* ``browser`` - alias for mock (the web page plays text via SpeechSynthesis).

Real paid vendors (Polly, Google, ElevenLabs) plug in by implementing this
interface and selecting the provider with ``TTS_PROVIDER``.
"""

from __future__ import annotations

import base64
import os
import subprocess
import sys
import tempfile
from abc import ABC, abstractmethod
from dataclasses import dataclass

from app.config import get_settings

# language -> edge-tts neural voice (free, multilingual)
EDGE_VOICES: dict[str, str] = {
    "en": "en-IN-PrabhatNeural",
    "te": "te-IN-ShrutiNeural",
    "hi": "hi-IN-MadhurNeural",
}

# gender preference -> language -> edge-tts neural voice
VOICE_OPTIONS: dict[str, dict[str, str]] = {
    "female": {
        "en": "en-IN-NeerjaNeural",
        "te": "te-IN-ShrutiNeural",
        "hi": "hi-IN-SwaraNeural",
    },
    "male": {
        "en": "en-IN-PrabhatNeural",
        "te": "te-IN-MohanNeural",
        "hi": "hi-IN-MadhurNeural",
    },
}


@dataclass
class TtsResult:
    text: str
    language: str
    provider: str
    audio_base64: str | None = None


class TtsProvider(ABC):
    name: str = "base"

    @abstractmethod
    def synthesize(
        self, text: str, language: str, voice: str | None = None
    ) -> TtsResult:
        raise NotImplementedError


class MockTtsProvider(TtsProvider):
    """Local TTS: carries the text as-is, optionally as a base64 payload."""

    name = "mock"

    def synthesize(
        self, text: str, language: str, voice: str | None = None
    ) -> TtsResult:
        payload = base64.b64encode(text.encode("utf-8")).decode("ascii")
        return TtsResult(
            text=text,
            language=language,
            provider="mock",
            audio_base64=payload,
        )


class EdgeTtsProvider(TtsProvider):
    """FREE Microsoft neural TTS (edge-tts) - no API key required.

    Renders through the ``edge-tts`` CLI so it works in both sync and async
    contexts. Audio is cached in memory per (text, language, voice).
    """

    name = "edge"
    _cache: dict[tuple[str, str, str], str] = {}

    def synthesize(
        self, text: str, language: str, voice: str | None = None
    ) -> TtsResult:
        key = (text, language, voice or "")
        if key in self._cache:
            return TtsResult(
                text=text,
                language=language,
                provider="edge",
                audio_base64=self._cache[key],
            )

        voice_name = self._resolve_voice(language, voice)
        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as tmp:
            tmp_path = tmp.name
        try:
            cmd = [
                sys.executable,
                "-m",
                "edge_tts",
                "--voice",
                voice_name,
                "--text",
                text,
                "--write-media",
                tmp_path,
            ]
            result = subprocess.run(
                cmd,
                capture_output=True,
                timeout=120,
            )
            if result.returncode != 0 or not os.path.getsize(tmp_path):
                return self._fallback(text, language)
            with open(tmp_path, "rb") as fh:
                audio = base64.b64encode(fh.read()).decode("ascii")
            self._cache[key] = audio
            return TtsResult(
                text=text, language=language, provider="edge", audio_base64=audio
            )
        except Exception:
            return self._fallback(text, language)
        finally:
            try:
                os.remove(tmp_path)
            except OSError:
                pass

    @staticmethod
    def _resolve_voice(language: str, voice: str | None) -> str:
        gender = voice if voice in VOICE_OPTIONS else None
        if gender:
            return VOICE_OPTIONS[gender].get(language, VOICE_OPTIONS[gender]["en"])
        return get_settings().TTS_EDGE_VOICE or EDGE_VOICES.get(
            language, EDGE_VOICES["en"]
        )

    def _fallback(self, text: str, language: str) -> TtsResult:
        return MockTtsProvider().synthesize(text, language)


def get_tts_provider() -> TtsProvider:
    settings = get_settings()
    name = (settings.TTS_PROVIDER or "mock").lower()
    if name == "edge":
        return EdgeTtsProvider()
    # "browser" (web page speaks) and anything unknown fall back to mock.
    return MockTtsProvider()