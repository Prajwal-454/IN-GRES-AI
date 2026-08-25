"""Speech-to-text abstraction.

The pipeline depends only on ``SttProvider.transcribe``. Providers shipped:

* ``mock``    - local dev; reads the transcript from the payload (simulators).
* ``whisper`` - FREE local Whisper (``faster-whisper`` / ctranslate2). Runs
  entirely on this machine, no API key, understands English, Telugu and Hindi.

Real paid vendors (Google, Azure, AssemblyAI...) plug in by implementing this
interface and selecting the provider with ``STT_PROVIDER``.
"""

from __future__ import annotations

import json
import os
import tempfile
import threading
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path

from app.config import get_settings
from app.voice.language import detect_language_with_confidence


@dataclass
class SttResult:
    text: str
    language: str
    confidence: float
    provider: str = "mock"


class SttProvider(ABC):
    name: str = "base"

    @abstractmethod
    def transcribe(
        self, audio: bytes, language_hint: str | None = None
    ) -> SttResult:
        raise NotImplementedError


class MockSttProvider(SttProvider):
    """Local STT: decodes the transcript carried in the payload.

    The mock is intentionally honest - it does not pretend to do real speech
    recognition. The audio payload may be raw UTF-8 text or JSON such as
    ``{"text": "...", "language": "te"}`` produced by the simulator.
    """

    name = "mock"

    def transcribe(self, audio: bytes, language_hint: str | None = None) -> SttResult:
        raw = audio.decode("utf-8", errors="replace").strip()
        text = ""
        language = language_hint
        if raw.startswith("{"):
            try:
                data = json.loads(raw)
            except json.JSONDecodeError:
                data = {}
            text = str(data.get("text") or "")
            language = data.get("language") or language
        else:
            text = raw
        text = text.strip()
        if not text:
            return SttResult(text="", language=language or "en", confidence=0.0, provider=self.name)
        detected = detect_language_with_confidence(text, language)
        return SttResult(
            text=text,
            language=detected["language"],
            confidence=detected["confidence"],
            provider=self.name,
        )


class WhisperSttProvider(SttProvider):
    """FREE local Whisper speech recognition (faster-whisper, no API key).

    The model is downloaded from Hugging Face on first use (e.g. ``base`` ~74 MB)
    and cached. Model size is set with ``STT_WHISPER_MODEL``
    (``tiny|base|small|medium``); ``small`` is best for Telugu/Hindi.
    """

    name = "whisper"
    _model = None
    _lock = threading.Lock()

    def _get_model(self):
        if self._model is None:
            with self._lock:
                if self._model is None:
                    from faster_whisper import WhisperModel

                    size = get_settings().STT_WHISPER_MODEL or "base"
                    self._model = WhisperModel(size, device="cpu", compute_type="int8")
        return self._model

    def transcribe(self, audio: bytes, language_hint: str | None = None) -> SttResult:
        if not audio:
            return SttResult(text="", language=language_hint or "en", confidence=0.0, provider=self.name)
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            tmp.write(audio)
            tmp_path = tmp.name
        try:
            model = self._get_model()
            segments, info = model.transcribe(
                tmp_path,
                language=language_hint or None,
                vad_filter=True,
            )
            text = "".join(seg.text for seg in segments).strip()
            confidences = [seg.avg_logprob for seg in segments]
            avg = sum(confidences) / len(confidences) if confidences else 0.0
            # map whisper's avg_logprob (~ -0.1 .. -1.0) into a 0..1 confidence
            confidence = max(0.1, min(0.99, 0.6 + 0.4 * (0.5 + avg)))
            lang = info.language or language_hint or detect_language_with_confidence(text)["language"]
            if not text:
                return SttResult(text="", language=lang, confidence=0.0, provider=self.name)
            return SttResult(text=text, language=lang, confidence=confidence, provider=self.name)
        except Exception:
            return SttResult(text="", language=language_hint or "en", confidence=0.0, provider=self.name)
        finally:
            try:
                os.remove(tmp_path)
            except OSError:
                pass


class VoskSttProvider(SttProvider):
    """FREE local speech recognition using Vosk (no API key, offline).

    Models live in ``STT_VOSK_MODEL_DIR`` (one folder per language:
    vosk-model-small-en-us-0.15 / -te-0.42 / -hi-0.22). Audio is decoded with
    PyAV and resampled to 16 kHz mono PCM. English is attempted first; if the
    result contains Telugu/Hindi script it is re-transcribed with the right
    model (only for non-English speech).
    """

    name = "vosk"
    _models: dict[str, object] = {}
    _lock = threading.Lock()

    MODEL_DIRS = {
        "en": "vosk-model-small-en-us-0.15",
        "te": "vosk-model-small-te-0.42",
        "hi": "vosk-model-small-hi-0.22",
    }

    def _base_dir(self) -> Path:
        from app.config import get_settings as _gs

        p = Path(_gs().STT_VOSK_MODEL_DIR or "voice_models")
        if p.is_absolute():
            return p
        for base in (Path.cwd(), Path(__file__).resolve().parents[2]):
            candidate = base / p
            if candidate.is_dir():
                return candidate
        return Path.cwd() / p

    def _model_path(self, lang: str) -> Path | None:
        candidate = self._base_dir() / self.MODEL_DIRS.get(lang, "en")
        return candidate if candidate.is_dir() else None

    def _get_model(self, lang: str):
        if lang not in self._models:
            with self._lock:
                if lang not in self._models:
                    from vosk import Model

                    path = self._model_path(lang)
                    if path is None:
                        return None
                    self._models[lang] = Model(str(path))
        return self._models.get(lang)

    def transcribe(self, audio: bytes, language_hint: str | None = None) -> SttResult:
        pcm = _decode_pcm(audio)
        if not pcm:
            return SttResult(text="", language=language_hint or "en", confidence=0.0, provider=self.name)

        candidates = [language_hint] if language_hint in self.MODEL_DIRS else ["en"]
        for lang in candidates:
            model = self._get_model(lang)
            if model is None:
                continue
            text, conf = self._recognize(model, pcm)
            if text:
                script_lang = detect_language_with_confidence(text)["language"]
                if script_lang in ("te", "hi") and lang != script_lang:
                    second = self._get_model(script_lang)
                    if second is not None:
                        text, conf = self._recognize(second, pcm)
                        lang = script_lang
                return SttResult(text=text, language=lang, confidence=conf, provider=self.name)
        return SttResult(text="", language=language_hint or "en", confidence=0.0, provider=self.name)

    @staticmethod
    def _recognize(model, pcm: bytes) -> tuple[str, float]:
        from vosk import KaldiRecognizer

        rec = KaldiRecognizer(model, 16000)
        if rec.AcceptWaveform(pcm):
            result = rec.Result()
        else:
            result = rec.FinalResult()
        import json as _json

        try:
            data = _json.loads(result)
        except _json.JSONDecodeError:
            data = {}
        words = data.get("result") or []
        text = data.get("text", "").strip()
        if words:
            conf = sum(float(w.get("conf", 0.0)) for w in words) / len(words)
        else:
            conf = 0.8 if text else 0.0
        return text, max(0.0, min(1.0, conf))


def _decode_pcm(audio: bytes) -> bytes:
    """Decode audio to 16 kHz mono signed-16 PCM using PyAV."""
    import io

    import av

    if not audio:
        return b""
    try:
        container = av.open(io.BytesIO(audio))
        stream = container.streams.audio[0]
        resampler = av.AudioResampler(format="s16", layout="mono", rate=16000)
        pcm = b""
        for frame in container.decode(stream):
            for out in resampler.resample(frame):
                pcm += out.to_ndarray().tobytes()
        container.close()
        return pcm
    except Exception:
        return b""


def get_stt_provider() -> SttProvider:
    settings = get_settings()
    name = (settings.STT_PROVIDER or "mock").lower()
    if name == "whisper":
        return WhisperSttProvider()
    if name == "vosk":
        return VoskSttProvider()
    return MockSttProvider()