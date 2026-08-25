"""Telephony provider abstraction.

Every telephony vendor (Twilio, Exotel, Plivo) and the local development
mock is reached only through this interface. The AI pipeline
(``app.voice.pipeline``) never talks to a specific vendor, so the provider
can be swapped with ``TELEPHONY_PROVIDER`` without changing the AI system.
"""

from __future__ import annotations

import hashlib
import hmac
import re
import secrets
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.config import get_settings
from app.models.user import User
from app.models.voice import VoiceCall

DEFAULT_SCRIPT = [
    "hello",
    "what is the stage of extraction in Telangana?",
    "which districts are over-exploited?",
    "thank you",
]


class WebhookValidationError(Exception):
    """Raised when an inbound telephony webhook cannot be trusted."""


@dataclass
class IncomingCall:
    """Result of handling an inbound webhook: the recorded call + stream token."""

    call_id: int
    provider_call_id: str | None
    phone_number_masked: str | None
    stream_token: str


def mask_phone(number: str | None) -> str | None:
    """Mask a phone number for display, e.g. +919876541234 -> +91******1234."""
    if not number:
        return None
    cleaned = re.sub(r"\s+", "", number)
    digits = re.sub(r"\D", "", cleaned)
    if len(digits) <= 4:
        return "*" * len(digits)

    prefix = ""
    i = 0
    while i < len(cleaned) and not cleaned[i].isdigit():
        prefix += cleaned[i]
        i += 1
    country_digits = 0
    if prefix:  # only "+91 ..." style numbers keep their country code
        while i < len(cleaned) and cleaned[i].isdigit() and country_digits < 2:
            prefix += cleaned[i]
            i += 1
            country_digits += 1

    tail = digits[-4:]
    return f"{prefix}{'*' * (len(digits) - country_digits - 4)}{tail}"


def hash_phone(number: str | None) -> str | None:
    """SHA-256 hash of the raw phone number so it is never stored in plaintext."""
    if not number:
        return None
    return hashlib.sha256(re.sub(r"\s+", "", number).encode()).hexdigest()


def new_stream_token() -> str:
    return secrets.token_urlsafe(32)


def create_call_session(
    db: Session,
    *,
    provider: str,
    provider_call_id: str | None = None,
    phone_number: str | None = None,
    user_id: int | None = None,
) -> VoiceCall:
    """Record a new inbound call session (RINGING) and return it."""
    call = VoiceCall(
        user_id=user_id,
        phone_number_masked=mask_phone(phone_number),
        phone_number_hash=hash_phone(phone_number),
        provider=provider,
        provider_call_id=provider_call_id,
        status="in_progress",
        call_state="RINGING",
        direction="inbound",
        stream_token=new_stream_token(),
        started_at=datetime.now(timezone.utc),
    )
    db.add(call)
    db.commit()
    db.refresh(call)
    return call


def call_duration_seconds(started_at, ended_at) -> int | None:
    """Compute call duration handling naive/aware datetime mismatches (SQLite)."""
    if started_at is None or ended_at is None:
        return None
    try:
        return max(0, int((ended_at - started_at).total_seconds()))
    except TypeError:
        delta = ended_at.replace(tzinfo=None) - started_at.replace(tzinfo=None)
        return max(0, int(delta.total_seconds()))


def end_call_session(db: Session, call: VoiceCall) -> None:
    """Close a call session and record its duration."""
    if call.ended_at is None:
        call.ended_at = datetime.now(timezone.utc)
    if call.started_at is not None and call.duration_seconds is None:
        call.duration_seconds = call_duration_seconds(call.started_at, call.ended_at)
    call.call_state = "ENDED" if call.call_state != "FAILED" else "FAILED"
    call.status = "completed"
    db.commit()


def validate_hmac_signature(secret: str, signature: str | None, data: bytes) -> bool:
    """Generic HMAC validation used by Twilio/Exotel/Plivo style webhooks."""
    if not signature:
        return False
    expected = hmac.new(secret.encode(), data, hashlib.sha1).digest()
    provided = _b64decode_or_raw(signature)
    return provided is not None and hmac.compare_digest(expected, provided)


def _b64decode_or_raw(value: str) -> bytes | None:
    import base64

    try:
        return base64.b64decode(value)
    except Exception:
        return value.encode()


class TelephonyProvider(ABC):
    """Interface implemented by every telephony provider."""

    name: str = "base"

    @abstractmethod
    def validate_webhook(self, headers: dict, body: bytes | dict) -> bool:
        """Return True when the inbound webhook is genuinely from the provider."""
        raise NotImplementedError

    @abstractmethod
    def handle_incoming_call(
        self, db: Session, payload: dict, headers: dict | None = None
    ) -> IncomingCall:
        """Validate + record an incoming call and return the session."""
        raise NotImplementedError

    def webhook_response(self, db: Session, payload: dict) -> str:
        """Provider XML/TwiML telling the provider how to handle the call.

        Convenience used by the mock/simulator path. The live webhook endpoint
        calls ``handle_incoming_call`` once and then ``incoming_xml`` so the
        call session is only ever created a single time.
        """
        incoming = self.handle_incoming_call(db, payload)
        return self.incoming_xml(incoming)

    @abstractmethod
    def incoming_xml(self, incoming: IncomingCall) -> str:
        """Provider XML/TwiML for an already-recorded incoming call."""
        raise NotImplementedError

    @abstractmethod
    def make_call(self, db: Session, user: User, script: list[str]) -> VoiceCall:
        """Place a scripted call. Real providers require credentials."""
        raise NotImplementedError

    def end_call(self, db: Session, call: VoiceCall) -> None:
        """Best-effort provider-side call termination (no-op unless overridden)."""
        return None

    def stream_url(self) -> str | None:
        """Public WebSocket URL the provider should stream audio to."""
        public = get_settings().VOICE_PUBLIC_URL.strip().rstrip("/")
        if not public:
            return None
        return f"{public}/api/voice/stream"

    def play_audio(self, call: VoiceCall, text: str) -> str:
        """Return provider XML that speaks ``text`` (used by the pipeline)."""
        raise NotImplementedError

    def display_phone(self) -> str | None:
        """Provider's configured phone number, or None when not configured."""
        return None