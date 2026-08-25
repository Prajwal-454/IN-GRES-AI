"""Voice pipeline: STT -> language detect -> LangGraph -> TTS.

This is the single code path used by every input channel (Twilio, Exotel,
Plivo, browser microphone, mock simulator). The telephony provider only
transports audio; intelligence stays in ``app.ai.orchestrator`` (the same
LangGraph used by the web chat).

Each turn updates the call's state machine
(RINGING/CONNECTED/LISTENING/PROCESSING/RESPONDING/WAITING/ESCALATED/ENDED/FAILED)
and stores both user and assistant transcriptions for the admin dashboard.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai.orchestrator import run as run_orchestrator
from app.config import get_settings
from app.models.voice import VoiceCall, VoiceTranscription
from app.voice.language import detect_language_with_confidence
from app.voice.stt import SttResult, get_stt_provider
from app.voice.telephony.base import call_duration_seconds
from app.voice.tts import TtsResult, get_tts_provider

END_PHRASES = (
    "goodbye",
    "bye",
    "end call",
    "end the call",
    "hang up",
    "disconnect",
    "thank you",
    "thanks",
    "dhanyavaadalu",
    "dhanyavad",
    "ధన్యవాదాలు",
    "धन्यवाद",
)

_END_ACK = "Thank you for using IN-GRES AI. Goodbye."
_END_ACK_TE = "ఇన్-గ్రెస్ ఎఐ ఉపయోగించినందుకు ధన్యవాదాలు. వీడ్కోలు."
_END_ACK_HI = "इन-ग्रेस एआई का उपयोग करने के लिए धन्यवाद। अलविदा।"

_SILENCE_PROMPT = (
    "Are you still there? You can ask me about groundwater resources in India."
)
_SILENCE_PROMPT_TE = (
    "మీరు ఇంకా ఉన్నారా? భారతదేశంలోని భూగర్భ జల వనరుల గురించి నన్ను అడగవచ్చు."
)
_SILENCE_PROMPT_HI = (
    "क्या आप अभी भी हैं? आप भारत के भूजल संसाधनों के बारे में मुझसे पूछ सकते हैं।"
)


@dataclass
class VoiceTurnState:
    """LangGraph-style voice state carried between turns."""

    call_id: int | None = None
    user_id: int | None = None
    language: str = "en"
    conversation_id: int | None = None
    last_transcript: str = ""
    intent: str | None = None
    location: str | None = None
    metric: str | None = None
    year: int | None = None
    retrieved_documents: list[str] = field(default_factory=list)
    groundwater_result: str | None = None
    response_text: str = ""
    ai_confidence: float = 0.0
    escalation_required: bool = False


@dataclass
class VoiceTurnResult:
    text: str
    language: str
    intent: str | None
    location: str | None
    confidence: float
    escalation_required: bool
    is_end: bool
    stt: SttResult
    tts: TtsResult


def is_end_turn(text: str) -> bool:
    lowered = text.lower().strip()
    return any(p in lowered for p in END_PHRASES)


def handle_silence(db: Session, call: VoiceCall, silence_count: int) -> VoiceTurnResult:
    """Return the appropriate response when the caller stays silent."""
    settings = get_settings()
    lang = call.language or "en"
    if silence_count >= settings.VOICE_MAX_SILENCE_PROMPTS:
        text = {"en": _END_ACK, "te": _END_ACK_TE, "hi": _END_ACK_HI}.get(lang, _END_ACK)
        return _build_result(db, call, text, lang, intent="goodbye", is_end=True)
    text = {
        "en": _SILENCE_PROMPT,
        "te": _SILENCE_PROMPT_TE,
        "hi": _SILENCE_PROMPT_HI,
    }.get(lang, _SILENCE_PROMPT)
    return _build_result(db, call, text, lang, intent="waiting", is_end=False)


def run_voice_turn(
    db: Session,
    *,
    call: VoiceCall,
    stt: SttResult,
    history: list[dict] | None = None,
) -> VoiceTurnResult:
    """Process one spoken turn through STT -> orchestrator -> TTS."""
    call.call_state = "PROCESSING"
    db.commit()

    lang = stt.language or detect_language_with_confidence(stt.text)["language"]

    # Termination phrases end the call gracefully.
    if is_end_turn(stt.text):
        ack = {"en": _END_ACK, "te": _END_ACK_TE, "hi": _END_ACK_HI}.get(lang, _END_ACK)
        result = _build_result(db, call, ack, lang, intent="goodbye", is_end=True)
        _store_turn(db, call, role="user", text=stt.text, stt=stt, intent="goodbye")
        return result

    start = time.perf_counter()
    answer = run_orchestrator(db, stt.text, language=lang, history=history or []).result
    latency_ms = int((time.perf_counter() - start) * 1000)

    call.call_state = "RESPONDING"
    call.language = call.language or answer.language
    call.intent = answer.intent
    call.location = answer.location or call.location
    call.ai_confidence = Decimal(str(round(stt.confidence * 0.9 + 0.08, 3)))
    call.response_time_ms = float(latency_ms)
    db.commit()

    _store_turn(db, call, role="user", text=stt.text, stt=stt, intent=answer.intent)
    _store_turn(
        db,
        call,
        role="assistant",
        text=answer.content,
        stt=None,
        intent=answer.intent,
    )

    # Low-confidence / unanswerable turns can be escalated to an expert.
    escalation_required = answer.intent == "fallback" or stt.confidence < 0.5
    if escalation_required:
        call.call_state = "ESCALATED"
        call.escalated = True
        db.commit()

    tts = get_tts_provider().synthesize(answer.content, answer.language)
    return VoiceTurnResult(
        text=answer.content,
        language=answer.language,
        intent=answer.intent,
        location=answer.location,
        confidence=float(call.ai_confidence or 0),
        escalation_required=escalation_required,
        is_end=False,
        stt=stt,
        tts=tts,
    )


def _build_result(
    db: Session,
    call: VoiceCall,
    text: str,
    lang: str,
    *,
    intent: str,
    is_end: bool,
) -> VoiceTurnResult:
    tts = get_tts_provider().synthesize(text, lang)
    if is_end:
        call.call_state = "ENDED"
        call.status = "completed"
        call.ended_at = datetime.now(timezone.utc)
        if call.started_at is not None:
            call.duration_seconds = call_duration_seconds(call.started_at, call.ended_at)
        db.commit()
    return VoiceTurnResult(
        text=text,
        language=lang,
        intent=intent,
        location=call.location,
        confidence=float(call.ai_confidence or 0),
        escalation_required=False,
        is_end=is_end,
        stt=SttResult(text="", language=lang, confidence=0.0),
        tts=tts,
    )


def _store_turn(
    db: Session,
    call: VoiceCall,
    *,
    role: str,
    text: str,
    stt: SttResult | None,
    intent: str | None,
) -> None:
    row = VoiceTranscription(
        voice_call_id=call.id,
        role=role,
        text=text,
        language=call.language,
        stt_provider=stt.provider if stt else None,
        stt_confidence=Decimal(str(round(stt.confidence, 3))) if stt and stt.confidence else None,
        intent=intent,
    )
    db.add(row)
    db.commit()


def build_history(db: Session, call: VoiceCall, limit: int | None = None) -> list[dict]:
    """Recent turns of this call as orchestrator history (oldest first)."""
    settings = get_settings()
    max_turns = (limit or settings.CHAT_MEMORY_TURNS) * 2
    rows = list(
        db.scalars(
            select(VoiceTranscription)
            .where(VoiceTranscription.voice_call_id == call.id)
            .order_by(VoiceTranscription.id.desc())
            .limit(max_turns)
        )
    )
    history: list[dict] = []
    for row in reversed(rows):
        history.append(
            {
                "role": row.role,
                "content": row.text,
                "location": row.text if row.role == "assistant" else None,
            }
        )
    return history


def request_escalation(
    db: Session, call: VoiceCall, user_id: int | None = None
) -> dict:
    """Create an expert request from the last unanswered turn.

    Returns the expert-request id and a spoken acknowledgment. Uses the same
    ``ExpertRequest`` model as the web application.
    """
    from app.models.expert import ExpertRequest

    last = db.scalars(
        select(VoiceTranscription)
        .where(
            VoiceTranscription.voice_call_id == call.id,
            VoiceTranscription.role == "user",
        )
        .order_by(VoiceTranscription.id.desc())
    ).first()
    question = last.text if last else (call.transcription or "").strip() or "Phone question"

    req = ExpertRequest(
        user_id=user_id or call.user_id,
        question=question,
        language=call.language or "en",
        location=call.location,
        intent=call.intent or "fallback",
        status="NEW",
    )
    db.add(req)
    db.commit()
    db.refresh(req)

    call.call_state = "ESCALATED"
    call.escalated = True
    db.commit()

    ack = (
        "Your question has been sent to a groundwater expert. "
        "You can check the response in your IN-GRES dashboard."
    )
    tts = get_tts_provider().synthesize(ack, call.language or "en")
    return {"expert_request_id": req.id, "text": ack, "tts": tts}