"""Exotel telephony provider (Exotel XML, TwiML-compatible, API-key auth)."""

from __future__ import annotations

import hashlib
import hmac

from sqlalchemy.orm import Session

from app.config import get_settings
from app.models.voice import VoiceCall
from app.voice.telephony.base import (
    IncomingCall,
    TelephonyProvider,
    WebhookValidationError,
    create_call_session,
)


class ExotelProvider(TelephonyProvider):
    name = "exotel"

    def validate_webhook(self, headers: dict, body: bytes | dict) -> bool:
        settings = get_settings()
        api_token = settings.EXOTEL_API_TOKEN
        # Exotel signs webhooks with a shared secret (when configured).
        secret = settings.TWILIO_AUTH_TOKEN or api_token
        signature = headers.get("x-exotel-signature")
        if not secret or not signature:
            return True  # not configured -> trust dev webhooks
        if isinstance(body, dict):
            data = "&".join(f"{k}={v}" for k, v in sorted(body.items()))
        else:
            data = body.decode("utf-8", errors="replace")
        expected = hmac.new(secret.encode(), data.encode(), hashlib.sha256).hexdigest()
        return hmac.compare_digest(expected, signature)

    def handle_incoming_call(
        self, db: Session, payload: dict, headers: dict | None = None
    ) -> IncomingCall:
        if not self.validate_webhook(headers or {}, payload):
            raise WebhookValidationError("Invalid Exotel webhook signature")
        call_sid = payload.get("CallSid") or payload.get("CallId")
        caller = payload.get("From")
        call = create_call_session(
            db,
            provider="exotel",
            provider_call_id=call_sid,
            phone_number=caller,
        )
        return IncomingCall(
            call_id=call.id,
            provider_call_id=call_sid,
            phone_number_masked=call.phone_number_masked,
            stream_token=call.stream_token or "",
        )

    def incoming_xml(self, incoming: IncomingCall) -> str:
        greeting = get_settings().VOICE_GREETING
        return (
            '<?xml version="1.0" encoding="UTF-8"?>'
            f"<Response><Say language='en-IN'>{greeting}</Say>"
            f"<Redirect method='POST'>/api/voice/stream?call_id={incoming.call_id}&amp;token={incoming.stream_token}</Redirect>"
            "</Response>"
        )

    def play_audio(self, call: VoiceCall, text: str) -> str:
        return (
            '<?xml version="1.0" encoding="UTF-8"?>'
            f"<Response><Say language='en-IN'>{text}</Say></Response>"
        )

    def make_call(self, db: Session, user, script: list[str]) -> VoiceCall:
        raise NotImplementedError(
            "Exotel outbound calls require account credentials and are not enabled"
        )

    def display_phone(self) -> str | None:
        return get_settings().EXOTEL_PHONE_NUMBER or None