from __future__ import annotations

from sqlalchemy import JSON, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.base import TimestampMixin


class Conversation(TimestampMixin, Base):
    __tablename__ = "conversations"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True, nullable=False)
    title: Mapped[str | None] = mapped_column(String(255))
    language: Mapped[str] = mapped_column(String(10), default="en")


class Message(TimestampMixin, Base):
    __tablename__ = "messages"

    id: Mapped[int] = mapped_column(primary_key=True)
    conversation_id: Mapped[int] = mapped_column(ForeignKey("conversations.id"), index=True, nullable=False)
    role: Mapped[str] = mapped_column(String(20), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    language: Mapped[str | None] = mapped_column(String(10))
    intent: Mapped[str | None] = mapped_column(String(50))
    location: Mapped[str | None] = mapped_column(String(255))
    sources: Mapped[list | None] = mapped_column(JSON)
    response_type: Mapped[str | None] = mapped_column(String(30))
    is_demo: Mapped[bool] = mapped_column(default=False)
    sections: Mapped[dict | None] = mapped_column(JSON)
    # Phase 22: feedback loop + follow-up suggestions
    rating: Mapped[int | None] = mapped_column(default=None)  # 1 helpful / -1 not helpful
    rating_note: Mapped[str | None] = mapped_column(String(500))
    followups: Mapped[list | None] = mapped_column(JSON)