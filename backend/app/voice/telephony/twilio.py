"""Twilio telephony provider (TwiML + Media Streams + signature validation)."""

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


class TwilioProvider(TelephonyProvider):
    name = "twilio"

    # -- webhook security -------------------------------------------------
    def validate_webhook(self, headers: dict, body: bytes | dict) -> bool:
        settings = get_settings()
        auth_token = settings.TWILIO_AUTH_TOKEN or settings.TELEPHONY_AUTH_TOKEN
        signature = headers.get("x-twilio-signature")
        if not auth_token or not settings.TWILIO_ACCOUNT_SID:
            # Provider not configured: trust local/dev webhooks.
            return True
        url = headers.get("x-twilio-url") or ""
        if isinstance(body, dict):
            payload_str = urlencode(sorted(body.items()))
        else:
            payload_str = urlencode(sorted(_parse_form(body)))
        expected = base64.b64encode(
            hmac.new(
                auth_token.encode(), (url + payload_str).encode(), hashlib.sha1
            ).digest()
        ).decode()
        return hmac.compare_digest(expected, signature or "")

    # -- inbound ----------------------------------------------------------
    def handle_incoming_call(
        self, db: Session, payload: dict, headers: dict | None = None
    ) -> IncomingCall:
        if not self.validate_webhook(headers or {}, payload):
            raise WebhookValidationError("Invalid Twilio webhook signature")
        settings = get_settings()
        call_sid = payload.get("CallSid")
        caller = payload.get("From")
        account = payload.get("AccountSid") or settings.TWILIO_ACCOUNT_SID
        if account and account != settings.TWILIO_ACCOUNT_SID:
            raise WebhookValidationError("Unexpected Twilio AccountSid")
        call = create_call_session(
            db,
            provider="twilio",
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
            "<Response><Connect><Stream "
            f'url="{self.stream_url()}?call_id={incoming.call_id}&amp;token={incoming.stream_token}">'
            f'<Parameter name="callId" value="{incoming.call_id}"/>'
            "</Stream></Connect>"
            f"<Say voice='Polly.Aditi' language='en-IN'>{greeting}</Say>"
            "</Response>"
        )

    # -- in-call actions ---------------------------------------------------
    def play_audio(self, call: VoiceCall, text: str) -> str:
        return (
            '<?xml version="1.0" encoding="UTF-8"?>'
            f"<Response><Say voice='Polly.Aditi' language='en-IN'>{text}</Say></Response>"
        )

    def make_call(self, db: Session, user, script: list[str]) -> VoiceCall:
        raise NotImplementedError(
            "Twilio outbound calls require account credentials and are not enabled"
        )

    def display_phone(self) -> str | None:
        return get_settings().TWILIO_PHONE_NUMBER or None


def _parse_form(body: bytes) -> list[tuple[str, str]]:
    from urllib.parse import parse_qsl

    return parse_qsl(body.decode("utf-8", errors="replace"))