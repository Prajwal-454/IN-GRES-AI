"""Plivo telephony provider (Plivo XML + X-Plivo-Signature validation)."""

from __future__ import annotations

import base64
import hashlib
import hmac
from urllib.parse import urlencode

from sqlalchemy.orm import Session

from app.config import get_settings
from app.models.voice import VoiceCall
from app.voice.telephony.base import (
    IncomingCall,
    TelephonyProvider,
    WebhookValidationError,
    create_call_session,
)


class PlivoProvider(TelephonyProvider):
    name = "plivo"

    def validate_webhook(self, headers: dict, body: bytes | dict) -> bool:
        settings = get_settings()
        auth_token = settings.PLIVO_AUTH_TOKEN
        signature = headers.get("x-plivo-signature")
        if not auth_token or not signature:
            return True  # not configured -> trust dev webhooks
        url = headers.get("x-plivo-url") or ""
        if isinstance(body, dict):
            payload_str = urlencode(sorted(body.items()))
        else:
            payload_str = urlencode(sorted(_parse_form(body)))
        expected = base64.b64encode(
            hmac.new(
                auth_token.encode(), (url + payload_str).encode(), hashlib.sha256
            ).digest()
        ).decode()
        return hmac.compare_digest(expected, signature)

    def handle_incoming_call(
        self, db: Session, payload: dict, headers: dict | None = None
    ) -> IncomingCall:
        if not self.validate_webhook(headers or {}, payload):
            raise WebhookValidationError("Invalid Plivo webhook signature")
        call_uuid = payload.get("CallUUID")
        caller = payload.get("From")
        call = create_call_session(
            db,
            provider="plivo",
            provider_call_id=call_uuid,
            phone_number=caller,
        )
        return IncomingCall(
            call_id=call.id,
            provider_call_id=call_uuid,
            phone_number_masked=call.phone_number_masked,
            stream_token=call.stream_token or "",
        )

    def incoming_xml(self, incoming: IncomingCall) -> str:
        greeting = get_settings().VOICE_GREETING
        return (
            '<?xml version="1.0" encoding="UTF-8"?>'
            f"<Response><Speak language='en-IN'>{greeting}</Speak>"
            "</Response>"
        )

    def play_audio(self, call: VoiceCall, text: str) -> str:
        return (
            '<?xml version="1.0" encoding="UTF-8"?>'
            f"<Response><Speak language='en-IN'>{text}</Speak></Response>"
        )

    def make_call(self, db: Session, user, script: list[str]) -> VoiceCall:
        raise NotImplementedError(
            "Plivo outbound calls require account credentials and are not enabled"
        )

    def display_phone(self) -> str | None:
        return get_settings().PLIVO_PHONE_NUMBER or None


def _parse_form(body: bytes) -> list[tuple[str, str]]:
    from urllib.parse import parse_qsl

    return parse_qsl(body.decode("utf-8", errors="replace"))