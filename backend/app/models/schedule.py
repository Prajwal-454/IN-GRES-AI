"""Scheduled groundwater reports (digests).

A user subscribes a scope (state/district/village) to a weekly or monthly
PDF digest. The background scheduler in ``app.main`` periodically calls
``process_due_schedules``; each due schedule is rendered through the
existing assessment-report pipeline, stored under ``DATA_DIR`` and emailed
to the recipients when SMTP is configured.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, JSON, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.base import TimestampMixin


class ReportSchedule(TimestampMixin, Base):
    __tablename__ = "report_schedules"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    state: Mapped[str | None] = mapped_column(String(120))
    district: Mapped[str | None] = mapped_column(String(120))
    village: Mapped[str | None] = mapped_column(String(120))
    frequency: Mapped[str] = mapped_column(String(20), default="weekly")  # weekly | monthly
    recipients: Mapped[list | None] = mapped_column(JSON)  # email addresses
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    next_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    last_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_status: Mapped[str | None] = mapped_column(String(50))  # sent | generated | failed
    last_error: Mapped[str | None] = mapped_column(String(500))
    last_file: Mapped[str | None] = mapped_column(String(255))
