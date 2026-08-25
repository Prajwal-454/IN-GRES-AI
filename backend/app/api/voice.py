"""Voice / telephone endpoints.

Exposes the telephony webhooks (incoming call, status, media stream), the
admin voice dashboard (calls, transcripts, analytics, config, connection
test) and the developer simulator. Every endpoint funnels through the same
LangGraph orchestrator via ``app.voice.pipeline``.
"""

from __future__ import annotations

import base64
import json
import secrets
from datetime import datetime, timezone
from urllib.parse import parse_qs

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Query,
    Request,
    WebSocket,
    WebSocketDisconnect,
    status,
)
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_roles
from app.config import get_settings
from app.database import SessionLocal, get_db
from app.models.user import User
from app.models.voice import VoiceCall, VoiceTranscription
from app.voice.pipeline import (
    build_history,
    handle_silence,
    is_end_turn,
    request_escalation,
    run_voice_turn,
)
from app.voice.stt import SttResult, MockSttProvider, get_stt_provider
from app.voice.telephony.base import (
    DEFAULT_SCRIPT,
    IncomingCall,
    WebhookValidationError,
    call_duration_seconds,
    create_call_session,
    end_call_session,
)
from app.voice.telephony.factory import get_provider

router = APIRouter(prefix="/voice", tags=["voice"])

_PROVIDER_STATE_MAP = {
    "RINGING": "RINGING",
    "IN-PROGRESS": "CONNECTED",
    "IN_PROGRESS": "CONNECTED",
    "COMPLETED": "ENDED",
    "NO-ANSWER": "FAILED",
    "NO_ANSWER": "FAILED",
    "BUSY": "FAILED",
    "CANCELED": "ENDED",
    "CANCELLED": "ENDED",
    "FAILED": "FAILED",
    "FAILURE": "FAILED",
}


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------
class CallSimulate(BaseModel):
    phone_number_masked: str | None = Field(default=None, max_length=40)
    script: list[str] | None = Field(default=None, min_length=1)


class CallOut(BaseModel):
    id: int
    user_id: int | None
    conversation_id: int | None
    phone_number_masked: str | None
    provider: str | None
    provider_call_id: str | None
    status: str
    call_state: str
    direction: str | None
    language: str | None
    intent: str | None
    ai_confidence: float | None
    escalated: bool
    response_time_ms: float | None
    duration_seconds: int | None
    started_at: object | None = None
    ended_at: object | None = None
    created_at: object | None = None


class TranscriptionOut(BaseModel):
    id: int
    voice_call_id: int
    role: str
    text: str
    language: str | None
    intent: str | None
    stt_provider: str | None
    stt_confidence: float | None
    created_at: object | None = None


class VoiceTestResult(BaseModel):
    call: CallOut
    question: str
    checks: dict[str, bool]
    response_text: str
    language: str
    intent: str | None
    location: str | None


class VoiceAnalytics(BaseModel):
    total_calls: int
    completed_calls: int
    failed_calls: int
    average_duration_seconds: float | None
    languages: dict[str, int]
    top_intents: dict[str, int]
    average_stt_confidence: float | None
    average_ai_confidence: float | None
    escalation_rate: float | None
    average_response_time_ms: float | None


class VoiceConfig(BaseModel):
    provider: str
    phone_number: str | None
    stt_provider: str
    tts_provider: str
    websocket_url: str | None
    public_url: str
    connection_status: str
    recording_enabled: bool


class TestConnectionResult(BaseModel):
    ok: bool
    provider: str
    message: str


class LinkPhone(BaseModel):
    phone_number: str = Field(min_length=5, max_length=24)


class TranscriptOut(BaseModel):
    role: str
    text: str
    language: str | None
    intent: str | None
    stt_provider: str | None
    stt_confidence: float | None
    created_at: object | None = None


def _call_out(call: VoiceCall) -> CallOut:
    return CallOut(
        id=call.id,
        user_id=call.user_id,
        conversation_id=call.conversation_id,
        phone_number_masked=call.phone_number_masked,
        provider=call.provider,
        provider_call_id=call.provider_call_id,
        status=call.status,
        call_state=call.call_state,
        direction=call.direction,
        language=call.language,
        intent=call.intent,
        ai_confidence=float(call.ai_confidence) if call.ai_confidence is not None else None,
        escalated=call.escalated,
        response_time_ms=call.response_time_ms,
        duration_seconds=call.duration_seconds,
        started_at=call.started_at,
        ended_at=call.ended_at,
        created_at=call.created_at,
    )


def _get_own_call(db: Session, call_id: int, user: User) -> VoiceCall:
    call = db.get(VoiceCall, call_id)
    if not call:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Call not found")
    if user.role == "user" and call.user_id != user.id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Not your call")
    return call


def _parse_body(body: bytes, content_type: str) -> dict:
    if not body:
        return {}
    if "json" in content_type:
        try:
            return json.loads(body.decode("utf-8"))
        except json.JSONDecodeError:
            return {}
    parsed = parse_qs(body.decode("utf-8", errors="replace"))
    return {k: v[0] if len(v) == 1 else v for k, v in parsed.items()}


# ---------------------------------------------------------------------------
# Telephony webhooks (called by the provider, no auth - signature-validated)
# ---------------------------------------------------------------------------
@router.post("/incoming", include_in_schema=True)
async def voice_incoming(request: Request, db: Session = Depends(get_db)):
    body_bytes = await request.body()
    headers = {k.lower(): v for k, v in request.headers.items()}
    payload = _parse_body(body_bytes, headers.get("content-type", ""))
    provider = get_provider()
    if not provider.validate_webhook(headers, payload):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Invalid webhook signature")
    try:
        incoming = provider.handle_incoming_call(db, payload, headers)
    except WebhookValidationError as exc:
        raise HTTPException(status.HTTP_403_FORBIDDEN, str(exc))
    return Response(content=provider.incoming_xml(incoming), media_type="application/xml")


@router.post("/status", include_in_schema=False)
async def voice_status(request: Request, db: Session = Depends(get_db)):
    body_bytes = await request.body()
    headers = {k.lower(): v for k, v in request.headers.items()}
    payload = _parse_body(body_bytes, headers.get("content-type", ""))
    provider = get_provider()
    if not provider.validate_webhook(headers, payload):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Invalid webhook signature")

    call_sid = (
        payload.get("CallSid")
        or payload.get("CallUUID")
        or payload.get("provider_call_id")
    )
    if call_sid:
        call = db.scalars(
            select(VoiceCall).where(VoiceCall.provider_call_id == str(call_sid))
        ).first()
        provider_state = str(
            payload.get("CallStatus") or payload.get("status") or ""
        ).upper()
        if call and provider_state in _PROVIDER_STATE_MAP:
            call.call_state = _PROVIDER_STATE_MAP[provider_state]
            if call.call_state == "ENDED":
                end_call_session(db, call)
            elif call.call_state == "FAILED":
                call.status = "failed"
                call.call_state = "FAILED"
                db.commit()
    return {"ok": True}


@router.post("/callback", include_in_schema=False)
async def voice_callback(request: Request, db: Session = Depends(get_db)):
    """Provider event/recording callback. Acknowledged; no audio is stored
    unless VOICE_RECORDING_ENABLED is configured with a storage backend."""
    body_bytes = await request.body()
    headers = {k.lower(): v for k, v in request.headers.items()}
    payload = _parse_body(body_bytes, headers.get("content-type", ""))
    return {"ok": True, "recording_enabled": get_settings().VOICE_RECORDING_ENABLED}


@router.post("/webhook", include_in_schema=False)
def webhook(
    payload: dict = {},
    db: Session = Depends(get_db),
):
    provider = get_provider()
    return Response(content=provider.webhook_response(db, payload), media_type="application/xml")


# ---------------------------------------------------------------------------
# Media streaming (WebSocket)
# ---------------------------------------------------------------------------
@router.websocket("/stream")
async def voice_stream(
    websocket: WebSocket,
    call_id: int | None = Query(default=None),
    token: str | None = Query(default=None),
):
    await websocket.accept()
    db = SessionLocal()
    call = db.get(VoiceCall, call_id) if call_id else None
    if not call:
        await websocket.close(code=4001)
        db.close()
        return
    real_provider = call.provider not in ("mock", "simulation", None)
    if real_provider and (not token or call.stream_token != token):
        await websocket.close(code=4001)
        db.close()
        return

    try:
        while True:
            data = await websocket.receive_json()
            mtype = data.get("type", "media")

            if mtype == "text":
                stt = MockSttProvider().transcribe(str(data.get("text", "")).encode("utf-8"))
            elif mtype == "media":
                audio = base64.b64decode(data.get("audio") or "")
                stt = get_stt_provider().transcribe(audio)
            elif mtype == "status":
                state = str(data.get("state", "")).upper()
                if state in _PROVIDER_STATE_MAP.values():
                    call.call_state = state
                    db.commit()
                continue
            elif mtype == "escalate":
                res = request_escalation(db, call)
                await websocket.send_json(
                    {
                        "type": "response",
                        "text": res["text"],
                        "escalated": True,
                        "expert_request_id": res["expert_request_id"],
                    }
                )
                continue
            elif mtype == "silence":
                res = handle_silence(db, call, int(data.get("count", 1)))
                await websocket.send_json(
                    {
                        "type": "response",
                        "text": res.text,
                        "language": res.language,
                        "is_end": res.is_end,
                        "audio": res.tts.audio_base64,
                    }
                )
                if res.is_end:
                    break
                continue
            else:
                await websocket.send_json({"type": "error", "text": "Unknown message type"})
                continue

            if not stt.text:
                await websocket.send_json({"type": "error", "text": "No speech detected"})
                continue

            result = run_voice_turn(
                db,
                call=call,
                stt=stt,
                history=build_history(db, call),
            )
            await websocket.send_json(
                {
                    "type": "response",
                    "text": result.text,
                    "language": result.language,
                    "intent": result.intent,
                    "location": result.location,
                    "confidence": result.confidence,
                    "escalated": result.escalation_required,
                    "is_end": result.is_end,
                    "audio": result.tts.audio_base64,
                }
            )
            if result.is_end:
                break
    except WebSocketDisconnect:
        pass
    finally:
        if call.call_state not in ("ENDED", "FAILED"):
            call.call_state = "ENDED"
            call.status = "completed"
            call.ended_at = datetime.now(timezone.utc)
            if call.started_at is not None:
                call.duration_seconds = call_duration_seconds(call.started_at, call.ended_at)
            db.commit()
        db.close()


# ---------------------------------------------------------------------------
# End-to-end developer test (auth)
# ---------------------------------------------------------------------------
@router.post("/test", response_model=VoiceTestResult)
def run_voice_test(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Run the full voice path end-to-end with a Telugu groundwater question."""
    question = "ఆంధ్రప్రదేశ్‌లో భూగర్భ జలాల పరిస్థితి ఎలా ఉంది?"
    stt = MockSttProvider().transcribe(
        json.dumps({"text": question, "language": "te"}).encode("utf-8")
    )
    call = create_call_session(
        db,
        provider="mock",
        provider_call_id=f"test-{secrets.token_hex(4)}",
        phone_number=get_settings().TELEPHONY_PHONE_NUMBER,
        user_id=user.id,
    )
    result = run_voice_turn(db, call=call, stt=stt)

    checks = {
        "language_telugu": result.language == "te",
        "location_andhra_pradesh": bool(result.location and "Andhra Pradesh" in str(result.location)),
        "intent_data_query": result.intent in ("data_query", "terminology"),
        "response_generated": bool(result.text.strip()),
        "tts_generated": bool(result.tts and (result.tts.audio_base64 or result.tts.text)),
        "call_recorded": bool(call.id),
        "transcript_stored": bool(
            db.scalar(
                select(func.count(VoiceTranscription.id)).where(
                    VoiceTranscription.voice_call_id == call.id
                )
            )
        ),
    }
    return VoiceTestResult(
        call=_call_out(call),
        question=question,
        checks=checks,
        response_text=result.text,
        language=result.language,
        intent=result.intent,
        location=result.location,
    )


@router.post("/escalate", response_model=dict)
def escalate_call(
    call_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    call = _get_own_call(db, call_id, user)
    res = request_escalation(db, call, user_id=user.id)
    return {"expert_request_id": res["expert_request_id"], "message": res["text"]}


@router.post("/link", response_model=CallOut)
def link_phone(
    data: LinkPhone,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Optionally link the caller's phone number to their account so phone
    queries show up in the web dashboard history."""
    from app.voice.telephony.base import hash_phone

    call = db.scalars(
        select(VoiceCall)
        .where(VoiceCall.phone_number_hash == hash_phone(data.phone_number))
        .order_by(VoiceCall.created_at.desc())
    ).first()
    if not call:
        call = create_call_session(
            db,
            provider="mock",
            provider_call_id=None,
            phone_number=data.phone_number,
            user_id=user.id,
        )
    else:
        call.user_id = user.id
        call.status = "linked"
        db.commit()
        db.refresh(call)
    return _call_out(call)


# ---------------------------------------------------------------------------
# Calls + transcripts (auth)
# ---------------------------------------------------------------------------
@router.post("/calls/simulate", response_model=CallOut, status_code=status.HTTP_201_CREATED)
def simulate_call(
    data: CallSimulate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    provider = get_provider()
    script = data.script or DEFAULT_SCRIPT
    call = provider.make_call(db, user, script)
    return _call_out(call)


@router.get("/calls", response_model=list[CallOut])
def list_calls(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    stmt = select(VoiceCall).order_by(VoiceCall.created_at.desc())
    if user.role == "user":
        stmt = stmt.where(VoiceCall.user_id == user.id)
    return [_call_out(c) for c in db.scalars(stmt)]


@router.get("/calls/{call_id}", response_model=CallOut)
def get_call(
    call_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return _call_out(_get_own_call(db, call_id, user))


@router.get("/calls/{call_id}/transcript", response_model=list[TranscriptOut])
def get_transcript(
    call_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    _get_own_call(db, call_id, user)
    rows = list(
        db.scalars(
            select(VoiceTranscription)
            .where(VoiceTranscription.voice_call_id == call_id)
            .order_by(VoiceTranscription.id)
        )
    )
    return [
        TranscriptOut(
            role=r.role,
            text=r.text,
            language=r.language,
            intent=r.intent,
            stt_provider=r.stt_provider,
            stt_confidence=float(r.stt_confidence) if r.stt_confidence is not None else None,
            created_at=r.created_at,
        )
        for r in rows
    ]


@router.get("/calls/{call_id}/transcriptions", response_model=list[TranscriptionOut])
def get_transcriptions(
    call_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Backward-compatible alias of ``/transcript``."""
    _get_own_call(db, call_id, user)
    rows = list(
        db.scalars(
            select(VoiceTranscription)
            .where(VoiceTranscription.voice_call_id == call_id)
            .order_by(VoiceTranscription.id)
        )
    )
    return [
        TranscriptionOut(
            id=r.id,
            voice_call_id=r.voice_call_id,
            role=r.role,
            text=r.text,
            language=r.language,
            intent=r.intent,
            stt_provider=r.stt_provider,
            stt_confidence=float(r.stt_confidence) if r.stt_confidence is not None else None,
            created_at=r.created_at,
        )
        for r in rows
    ]


# ---------------------------------------------------------------------------
# Admin voice dashboard
# ---------------------------------------------------------------------------
@router.get("/analytics", response_model=VoiceAnalytics)
def voice_analytics(
    db: Session = Depends(get_db),
    _admin: User = Depends(require_roles("admin")),
):
    total = db.scalar(select(func.count(VoiceCall.id))) or 0
    completed = (
        db.scalar(
            select(func.count(VoiceCall.id)).where(VoiceCall.status == "completed")
        )
        or 0
    )
    failed = (
        db.scalar(
            select(func.count(VoiceCall.id)).where(VoiceCall.call_state == "FAILED")
        )
        or 0
    )
    avg_duration = db.scalar(
        select(func.avg(VoiceCall.duration_seconds)).where(
            VoiceCall.duration_seconds.isnot(None)
        )
    )
    avg_resp = db.scalar(
        select(func.avg(VoiceCall.response_time_ms)).where(
            VoiceCall.response_time_ms.isnot(None)
        )
    )
    avg_stt_conf = db.scalar(
        select(func.avg(VoiceTranscription.stt_confidence)).where(
            VoiceTranscription.stt_confidence.isnot(None)
        )
    )
    avg_ai_conf = db.scalar(select(func.avg(VoiceCall.ai_confidence)))
    escalated = (
        db.scalar(select(func.count(VoiceCall.id)).where(VoiceCall.escalated.is_(True)))
        or 0
    )

    languages = {
        lang: count
        for lang, count in db.execute(
            select(VoiceCall.language, func.count(VoiceCall.id))
            .where(VoiceCall.language.isnot(None))
            .group_by(VoiceCall.language)
        ).all()
    }
    intents = {
        intent: count
        for intent, count in db.execute(
            select(VoiceCall.intent, func.count(VoiceCall.id))
            .where(VoiceCall.intent.isnot(None))
            .group_by(VoiceCall.intent)
        ).all()
    }

    return VoiceAnalytics(
        total_calls=total,
        completed_calls=completed,
        failed_calls=failed,
        average_duration_seconds=float(avg_duration) if avg_duration else None,
        languages=languages,
        top_intents=intents,
        average_stt_confidence=float(avg_stt_conf) if avg_stt_conf else None,
        average_ai_confidence=float(avg_ai_conf) if avg_ai_conf else None,
        escalation_rate=round(escalated / total, 3) if total else None,
        average_response_time_ms=float(avg_resp) if avg_resp else None,
    )


@router.get("/config", response_model=VoiceConfig)
def voice_config(
    _admin: User = Depends(require_roles("admin")),
):
    settings = get_settings()
    provider = get_provider()
    provider_name = provider.name
    configured = bool(
        settings.TWILIO_ACCOUNT_SID
        or settings.EXOTEL_API_KEY
        or settings.PLIVO_AUTH_ID
        or settings.VOICE_PUBLIC_URL
    )
    return VoiceConfig(
        provider=provider_name,
        phone_number=provider.display_phone(),
        stt_provider=settings.STT_PROVIDER or "mock",
        tts_provider=settings.TTS_PROVIDER or "mock",
        websocket_url=f"{settings.VOICE_PUBLIC_URL.rstrip('/')}/api/voice/stream"
        if settings.VOICE_PUBLIC_URL
        else None,
        public_url=settings.VOICE_PUBLIC_URL or "",
        connection_status="configured" if configured else "not configured",
        recording_enabled=settings.VOICE_RECORDING_ENABLED,
    )


@router.post("/config/test", response_model=TestConnectionResult)
def test_connection(
    db: Session = Depends(get_db),
    _admin: User = Depends(require_roles("admin")),
):
    """Verify the telephony provider can create a call session."""
    settings = get_settings()
    provider = get_provider()
    if provider.name in ("twilio", "exotel", "plivo"):
        configured = bool(
            provider.display_phone()
            and (settings.TWILIO_ACCOUNT_SID or settings.EXOTEL_API_KEY or settings.PLIVO_AUTH_ID)
            and (settings.TWILIO_AUTH_TOKEN or settings.EXOTEL_API_TOKEN or settings.PLIVO_AUTH_TOKEN)
        )
        if not configured:
            return TestConnectionResult(
                ok=False,
                provider=provider.name,
                message="Provider credentials are not configured. Add them to .env and set VOICE_PUBLIC_URL.",
            )
        call = create_call_session(
            db, provider=provider.name, provider_call_id=f"test-conn-{secrets.token_hex(4)}"
        )
        end_call_session(db, call)
        return TestConnectionResult(
            ok=True,
            provider=provider.name,
            message=f"Connection OK. Incoming webhook: {settings.VOICE_PUBLIC_URL or '(set VOICE_PUBLIC_URL)'}/api/voice/incoming",
        )
    call = create_call_session(
        db, provider="mock", provider_call_id=f"test-conn-{secrets.token_hex(4)}"
    )
    end_call_session(db, call)
    return TestConnectionResult(
        ok=True,
        provider="mock",
        message="Mock provider OK. No external credentials required for local development.",
    )