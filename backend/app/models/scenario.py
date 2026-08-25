"""User-saved what-if scenarios (Scenario Studio).

A saved scenario stores only the *inputs* of a projection (scope, metric,
horizon, method and the pumping/recharge change percentages) so it can be
reloaded and recomputed against the latest data at any time.
"""

from __future__ import annotations

from sqlalchemy import Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.base import TimestampMixin


class SavedScenario(TimestampMixin, Base):
    __tablename__ = "saved_scenarios"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    scope_state: Mapped[str | None] = mapped_column(String(120))
    scope_district: Mapped[str | None] = mapped_column(String(120))
    scope_village: Mapped[str | None] = mapped_column(String(120))
    scope_basin: Mapped[str | None] = mapped_column(String(120))
    metric: Mapped[str] = mapped_column(String(20), default="stage")
    horizon: Mapped[int] = mapped_column(Integer, default=5)
    method: Mapped[str] = mapped_column(String(20), default="auto")
    extraction_change: Mapped[float] = mapped_column(Float, default=0.0)
    recharge_change: Mapped[float] = mapped_column(Float, default=0.0)
