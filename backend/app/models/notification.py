from __future__ import annotations

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.base import TimestampMixin


class AlertRule(TimestampMixin, Base):
    """A threshold rule a user subscribes to. Evaluation scans assessment
    units and emits a UserNotification whenever the condition is met."""

    __tablename__ = "alert_rules"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    metric: Mapped[str] = mapped_column(String(50), nullable=False)  # stage | recharge | extraction | resource
    operator: Mapped[str] = mapped_column(String(10), nullable=False)  # gt | gte | lt | lte
    threshold: Mapped[float] = mapped_column(nullable=False)
    state: Mapped[str | None] = mapped_column(String(120))
    district: Mapped[str | None] = mapped_column(String(120))
    village: Mapped[str | None] = mapped_column(String(120))
    year: Mapped[int | None] = mapped_column(Integer)
    channels: Mapped[list | None] = mapped_column(JSON)  # ["in_app", "email"]
    cooldown_minutes: Mapped[int] = mapped_column(Integer, default=1440)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    last_triggered_at: Mapped[object | None] = mapped_column(DateTime(timezone=True), nullable=True)


class UserNotification(TimestampMixin, Base):
    """A notification delivered to a user (in-app, optionally email)."""

    __tablename__ = "user_notifications"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True, nullable=False)
    rule_id: Mapped[int | None] = mapped_column(ForeignKey("alert_rules.id"), index=True)
    kind: Mapped[str] = mapped_column(String(50), default="alert")  # alert | system | import
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    body: Mapped[str | None] = mapped_column(Text)
    payload: Mapped[dict | None] = mapped_column(JSON)
    read: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
