"""Mock telephony provider for local development.

The mock runs a scripted inbound call through the exact same orchestrator /
voice pipeline used by the web application, recording the call and every turn
in the database. It requires no external credentials, so the full phone-voice
flow is observable locally and in the test-suite.
"""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai.orchestrator import run as run_orchestrator
from app.config import get_settings
from app.models.user import User
from app.models.voice import VoiceCall, VoiceTranscription
from app.voice.telephony.base import (
    DEFAULT_SCRIPT,
    IncomingCall,
    TelephonyProvider,
    create_call_session,
)


class MockProvider(TelephonyProvider):
    name = "mock"

    def validate_webhook(self, headers: dict, body: bytes | dict) -> bool:
        return True

    def handle_incoming_call(
        self, db: Session, payload: dict, headers: dict | None = None
    ) -> IncomingCall:
        phone = payload.get("From") or get_settings().TELEPHONY_PHONE_NUMBER
        call = create_call_session(
            db,
            provider="mock",
            provider_call_id=payload.get("CallSid") or f"mock-{payload.get('call_id', 'dev')}",
            phone_number=phone,
        )
        return IncomingCall(
            call_id=call.id,
            provider_call_id=call.provider_call_id,
            phone_number_masked=call.phone_number_masked,
            stream_token=call.stream_token or "",
        )

    def incoming_xml(self, incoming: IncomingCall) -> str:
        return (
            '<?xml version="1.0" encoding="UTF-8"?>'
            f"<Response><Say language='en-IN'>{get_settings().VOICE_GREETING}</Say>"
            "</Response>"
        )

    def play_audio(self, call: VoiceCall, text: str) -> str:
        return (
            '<?xml version="1.0" encoding="UTF-8"?>'
            f"<Response><Say language='en-IN'>{text}</Say></Response>"
        )

    def make_call(self, db: Session, user: User, script: list[str]) -> VoiceCall:
        call = VoiceCall(
            user_id=user.id,
            phone_number_masked=get_settings().TELEPHONY_PHONE_NUMBER,
            phone_number_hash=None,
            provider="mock",
            provider_call_id=f"mock-{datetime.now(timezone.utc).microsecond}",
            status="in_progress",
            call_state="CONNECTED",
            direction="inbound",
            stream_token=None,
            started_at=datetime.now(timezone.utc),
        )
        db.add(call)
        db.flush()

        script = script or list(DEFAULT_SCRIPT)
        for idx, utterance in enumerate(script):
            call.call_state = "LISTENING"
            db.add(
                VoiceTranscription(
                    voice_call_id=call.id,
                    role="user",
                    text=utterance,
                    language=None,
                    stt_provider="mock",
                    stt_confidence=Decimal("0.98"),
                )
            )
            db.flush()
            result = run_orchestrator(db, utterance).result
            call.call_state = "RESPONDING"
            call.language = call.language or result.language
            call.intent = result.intent
            call.ai_confidence = Decimal("0.97")
            db.add(
                VoiceTranscription(
                    voice_call_id=call.id,
                    role="assistant",
                    text=result.content,
                    language=result.language,
                    stt_provider="mock",
                    stt_confidence=None,
                    intent=result.intent,
                )
            )
            if idx == len(script) - 1:
                call.call_state = "ENDED"
                call.status = "completed"
                call.ended_at = datetime.now(timezone.utc)
                call.duration_seconds = 30 + idx * 12
                call.transcription = "\n".join(
                    f"{'USER' if i % 2 == 0 else 'AI'}: {row.text}"
                    for i, row in enumerate(
                        db.scalars(
                            select(VoiceTranscription)
                            .where(VoiceTranscription.voice_call_id == call.id)
                            .order_by(VoiceTranscription.id)
                        )
                    )
                )

        db.commit()
        db.refresh(call)
        return call

    def display_phone(self) -> str | None:
        return get_settings().TELEPHONY_PHONE_NUMBER or None