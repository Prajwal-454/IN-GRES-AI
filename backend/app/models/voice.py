from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.base import TimestampMixin

# Detailed call state machine used for monitoring / the admin dashboard.
CALL_STATES = (
    "RINGING",
    "CONNECTED",
    "LISTENING",
    "PROCESSING",
    "RESPONDING",
    "WAITING",
    "ESCALATED",
    "ENDED",
    "FAILED",
)


class VoiceCall(TimestampMixin, Base):
    __tablename__ = "voice_calls"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), index=True)
    conversation_id: Mapped[int | None] = mapped_column(
        ForeignKey("conversations.id"), index=True
    )
    phone_number_masked: Mapped[str | None] = mapped_column(String(40))
    phone_number_hash: Mapped[str | None] = mapped_column(String(64))
    provider: Mapped[str | None] = mapped_column(String(50))
    provider_call_id: Mapped[str | None] = mapped_column(String(255))
    status: Mapped[str] = mapped_column(String(30), default="initiated")
    call_state: Mapped[str] = mapped_column(String(20), default="RINGING")
    direction: Mapped[str | None] = mapped_column(String(10))
    language: Mapped[str | None] = mapped_column(String(10))
    intent: Mapped[str | None] = mapped_column(String(50))
    location: Mapped[str | None] = mapped_column(String(255))
    ai_confidence: Mapped[Decimal | None] = mapped_column(Numeric(4, 3))
    escalated: Mapped[bool] = mapped_column(Boolean, default=False)
    stream_token: Mapped[str | None] = mapped_column(String(64))
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    duration_seconds: Mapped[int | None] = mapped_column(Integer)
    transcription: Mapped[str | None] = mapped_column(Text)
    response_time_ms: Mapped[float | None] = mapped_column(Float)


class VoiceTranscription(TimestampMixin, Base):
    __tablename__ = "voice_transcriptions"

    id: Mapped[int] = mapped_column(primary_key=True)
    voice_call_id: Mapped[int] = mapped_column(ForeignKey("voice_calls.id"), index=True, nullable=False)
    role: Mapped[str] = mapped_column(String(20), default="user")
    text: Mapped[str] = mapped_column(Text, nullable=False)
    language: Mapped[str | None] = mapped_column(String(10))
    stt_provider: Mapped[str | None] = mapped_column(String(50))
    stt_confidence: Mapped[Decimal | None] = mapped_column(Numeric(4, 3))
    intent: Mapped[str | None] = mapped_column(String(50))