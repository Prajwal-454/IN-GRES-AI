"""Data-quality anomaly flags raised by the scan engine.

Each flag points at one suspect observation (assessment row, groundwater
level or rainfall reading), carries the rule that fired and a review
workflow (open -> acknowledged -> resolved/dismissed) driven from the
admin console. ``fingerprint`` is a stable hash of (rule, scope, value)
so re-running a scan never duplicates an already-known flag.
"""

from __future__ import annotations

from sqlalchemy import Float, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.base import TimestampMixin


class AnomalyFlag(TimestampMixin, Base):
    __tablename__ = "anomaly_flags"
    __table_args__ = (
        Index("ix_anomaly_flags_status_severity", "status", "severity"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    kind: Mapped[str] = mapped_column(String(50), index=True, nullable=False)
    # impossible_value | negative_value | category_mismatch | implausible_ratio | outlier | level_depth_out_of_range | rainfall_out_of_range
    severity: Mapped[str] = mapped_column(String(20), default="medium", index=True)  # low | medium | high
    metric: Mapped[str] = mapped_column(String(50), nullable=False)  # stage | recharge | extraction | level | rainfall
    assessment_id: Mapped[int | None] = mapped_column(ForeignKey("groundwater_assessments.id"), index=True)
    assessment_unit_id: Mapped[int | None] = mapped_column(ForeignKey("assessment_units.id"), index=True)
    dataset_id: Mapped[int | None] = mapped_column(ForeignKey("datasets.id"), index=True)
    year: Mapped[int | None] = mapped_column(Integer)
    state_name: Mapped[str | None] = mapped_column(String(120))
    district_name: Mapped[str | None] = mapped_column(String(120))
    unit_name: Mapped[str | None] = mapped_column(String(255))
    value: Mapped[float | None] = mapped_column(Float)
    expected_min: Mapped[float | None] = mapped_column(Float)
    expected_max: Mapped[float | None] = mapped_column(Float)
    detail: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), default="open", index=True)  # open | acknowledged | resolved | dismissed
    reviewed_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    review_note: Mapped[str | None] = mapped_column(String(500))
    fingerprint: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
