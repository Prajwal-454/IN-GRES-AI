from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.database import get_db
from app.ingres import queries
from app.models.user import User
from app.schemas.groundwater import (
    AssessmentOut,
    CategoryOut,
    DistrictOut,
    MessageOut,
    MetricOut,
    RainfallOut,
    StateOut,
    SummaryOut,
    VillageOut,
)

router = APIRouter(prefix="/groundwater", tags=["groundwater"])


def _normalise_state(db: Session, raw: str | None) -> str | None:
    if not raw:
        return None
    state = queries.resolve_state(db, raw)
    if state is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"Unknown state: {raw}")
    return state.name


def _contexts(db: Session, unit_ids: list[int]) -> dict[int, tuple[str, str, str]]:
    """Bulk (state, district, unit name) resolution to avoid N+1 lookups."""
    return queries.unit_context_map(db, unit_ids)


@router.get("/states", response_model=list[StateOut])
def list_states(
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    return queries.get_states(db)


@router.get("/districts", response_model=list[DistrictOut])
def list_districts(
    state: str = Query(...),
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    state = _normalise_state(db, state)
    return queries.get_districts(db, state)


@router.get("/villages", response_model=list[VillageOut])
def list_villages(
    state: str = Query(...),
    district: str = Query(...),
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    state = _normalise_state(db, state)
    return queries.get_villages(db, state, district)


@router.get("/categories", response_model=list[CategoryOut])
def list_categories(
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    return queries.get_categories(db)


@router.get("/assessment", response_model=list[AssessmentOut])
def assessments(
    state: str | None = Query(default=None),
    district: str | None = Query(default=None),
    village: str | None = Query(default=None),
    year: int | None = Query(default=None),
    category: str | None = Query(default=None),
    unit: str | None = Query(default=None),
    data_source: str = Query(
        default="auto", pattern="^(auto|real|demo|all)$"
    ),
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    state = _normalise_state(db, state)
    rows = queries.get_assessments(
        db, state=state, district=district, village=village, year=year,
        category=category, unit=unit, data_source=data_source,
    )
    ctx = _contexts(db, [r.assessment_unit_id for r in rows])
    out = []
    for r in rows:
        s, d, uname = ctx.get(r.assessment_unit_id, ("", "", ""))
        out.append(
            AssessmentOut(
                id=r.id,
                state=s,
                district=d,
                assessment_unit=uname,
                assessment_year=r.assessment_year,
                recharge_total=float(r.recharge_total) if r.recharge_total is not None else None,
                extraction_total=float(r.extraction_total) if r.extraction_total is not None else None,
                annual_extractable_resource=float(r.annual_extractable_resource) if r.annual_extractable_resource is not None else None,
                stage_of_extraction=float(r.stage_of_extraction) if r.stage_of_extraction is not None else None,
                category=r.category,
                is_demo=r.is_demo,
            )
        )
    return out


@router.get("/recharge", response_model=list[MetricOut])
def recharge(
    state: str | None = Query(default=None),
    district: str | None = Query(default=None),
    village: str | None = Query(default=None),
    year: int | None = Query(default=None),
    data_source: str = Query(default="auto", pattern="^(auto|real|demo|all)$"),
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    state = _normalise_state(db, state)
    rows = queries.get_recharge(db, state=state, district=district, village=village, year=year, data_source=data_source)
    ctx = _contexts(db, [r.assessment_unit_id for r in rows])
    out = []
    for r in rows:
        s, d, uname = ctx.get(r.assessment_unit_id, ("", "", ""))
        out.append(
            MetricOut(
                id=r.id,
                state=s,
                district=d,
                assessment_unit=uname,
                year=r.year,
                metric_type="recharge",
                value=float(r.value) if r.value is not None else None,
                unit="hm³",
                is_demo=r.is_demo,
            )
        )
    return out


@router.get("/extraction", response_model=list[MetricOut])
def extraction(
    state: str | None = Query(default=None),
    district: str | None = Query(default=None),
    village: str | None = Query(default=None),
    year: int | None = Query(default=None),
    data_source: str = Query(default="auto", pattern="^(auto|real|demo|all)$"),
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    state = _normalise_state(db, state)
    rows = queries.get_extraction(db, state=state, district=district, village=village, year=year, data_source=data_source)
    ctx = _contexts(db, [r.assessment_unit_id for r in rows])
    out = []
    for r in rows:
        s, d, uname = ctx.get(r.assessment_unit_id, ("", "", ""))
        out.append(
            MetricOut(
                id=r.id,
                state=s,
                district=d,
                assessment_unit=uname,
                year=r.year,
                metric_type="extraction",
                value=float(r.value) if r.value is not None else None,
                unit="hm³",
                is_demo=r.is_demo,
            )
        )
    return out


@router.get("/summary", response_model=SummaryOut)
def summary(
    state: str | None = Query(default=None),
    district: str | None = Query(default=None),
    village: str | None = Query(default=None),
    year: int | None = Query(default=None),
    data_source: str = Query(default="auto", pattern="^(auto|real|demo|all)$"),
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    state = _normalise_state(db, state)
    data = queries.get_summary(
        db, state=state, district=district, village=village, year=year, data_source=data_source
    )
    return SummaryOut(
        state=state or "All states",
        district=district,
        village=village,
        year=year,
        assessment_units=data["assessment_units"],
        total_recharge=data["total_recharge"],
        total_extraction=data["total_extraction"],
        average_stage_of_extraction=data["average_stage_of_extraction"],
        category_counts=data["category_counts"],
        is_demo=data["is_demo"],
        source=data["source"],
        unit="hm³",
    )


@router.get("/rainfall", response_model=list[RainfallOut])
def rainfall(
    state: str | None = Query(default=None),
    district: str | None = Query(default=None),
    village: str | None = Query(default=None),
    year: int | None = Query(default=None),
    data_source: str = Query(default="auto", pattern="^(auto|real|demo|all)$"),
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    state = _normalise_state(db, state)
    rows = queries.get_rainfall(db, state=state, district=district, village=village, year=year, data_source=data_source)
    ctx = _contexts(db, [r.assessment_unit_id for r in rows])
    out = []
    for r in rows:
        s, d, uname = ctx.get(r.assessment_unit_id, ("", "", ""))
        out.append(
            RainfallOut(
                id=r.id,
                state=s,
                district=d,
                assessment_unit=uname,
                year=r.year,
                month=r.month,
                value_mm=float(r.value_mm) if r.value_mm is not None else None,
                is_demo=r.is_demo,
            )
        )
    return out


@router.get("/health", response_model=MessageOut)
def groundwater_health(
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    states = queries.get_states(db)
    count = len(queries.get_assessments(db, limit=1))
    return MessageOut(
        message=f"Groundwater data service OK - {len(states)} states, {count} assessment records visible"
    )