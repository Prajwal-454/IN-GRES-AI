"""Saved what-if scenarios (Scenario Studio).

Users persist scenario inputs (scope, metric, horizon, method and the
pumping/recharge change percentages) so they can reload and recompute them
against the latest dataset at any time.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.database import get_db
from app.ingres import basins, queries
from app.models.scenario import SavedScenario
from app.models.user import User

router = APIRouter(prefix="/scenarios", tags=["scenarios"])


class ScenarioCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    state: str | None = Field(default=None, max_length=120)
    district: str | None = Field(default=None, max_length=120)
    village: str | None = Field(default=None, max_length=120)
    basin: str | None = Field(default=None, max_length=120)
    metric: str = Field(default="stage", pattern="^(stage|recharge|extraction)$")
    horizon: int = Field(default=5, ge=1, le=10)
    method: str = Field(
        default="auto",
        pattern="^(linear|moving_average|exponential|arima|holt|ensemble|auto|lstm|transformer|ml)$",
    )
    extraction_change: float = Field(default=0.0, ge=-90, le=300)
    recharge_change: float = Field(default=0.0, ge=-90, le=300)


def _serialize(scenario: SavedScenario) -> dict:
    return {
        "id": scenario.id,
        "name": scenario.name,
        "state": scenario.scope_state,
        "district": scenario.scope_district,
        "village": scenario.scope_village,
        "basin": scenario.scope_basin,
        "metric": scenario.metric,
        "horizon": scenario.horizon,
        "method": scenario.method,
        "extraction_change": scenario.extraction_change,
        "recharge_change": scenario.recharge_change,
        "created_at": scenario.created_at.isoformat() if scenario.created_at else None,
    }


def _validate_scope(db: Session, data: ScenarioCreate) -> None:
    if data.state and queries.resolve_state(db, data.state) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"Unknown state: {data.state}")
    if data.basin and not basins.basin_district_ids(db, data.basin):
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"Unknown basin: {data.basin}")
    if data.district:
        state_obj = queries.resolve_state(db, data.state) if data.state else None
        district = queries.resolve_district(
            db, state_obj.id if state_obj else None, data.district
        )
        if district is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, f"Unknown district: {data.district}")
    if data.village:
        village = queries.find_village(db, data.village, state=data.state, district=data.district)
        if village is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, f"Unknown village: {data.village}")


@router.get("")
def list_scenarios(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    rows = list(
        db.scalars(
            select(SavedScenario)
            .where(SavedScenario.user_id == user.id)
            .order_by(SavedScenario.created_at.desc())
        )
    )
    return {"scenarios": [_serialize(s) for s in rows], "count": len(rows)}


@router.post("", status_code=status.HTTP_201_CREATED)
def create_scenario(
    data: ScenarioCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    _validate_scope(db, data)
    scenario = SavedScenario(
        user_id=user.id,
        name=data.name.strip(),
        scope_state=data.state,
        scope_district=data.district,
        scope_village=data.village,
        scope_basin=data.basin,
        metric=data.metric,
        horizon=data.horizon,
        method=data.method,
        extraction_change=data.extraction_change,
        recharge_change=data.recharge_change,
    )
    db.add(scenario)
    db.commit()
    return _serialize(scenario)


@router.delete("/{scenario_id}")
def delete_scenario(
    scenario_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    scenario = db.get(SavedScenario, scenario_id)
    if not scenario or scenario.user_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Scenario not found")
    db.delete(scenario)
    db.commit()
    return {"deleted": scenario_id}
