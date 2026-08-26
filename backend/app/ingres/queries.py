from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.ingres.query_cache import cache_get, cache_set
from app.models.groundwater import (
    AssessmentCategory,
    AssessmentUnit,
    District,
    GroundwaterAssessment,
    GroundwaterExtraction,
    GroundwaterRainfall,
    GroundwaterRecharge,
    State,
    Village,
)


def resolve_state(db: Session, state: str | None) -> State | None:
    """Canonical state for a case-insensitive name (single small lookup)."""
    if not state:
        return None
    return db.scalar(select(State).where(func.lower(State.name) == state.strip().lower()))


def resolve_district(db: Session, state_id: int | None, district: str | None) -> District | None:
    if not district or state_id is None:
        return None
    return db.scalar(
        select(District).where(
            District.state_id == state_id,
            func.lower(District.name) == district.strip().lower(),
        )
    )


def resolve_village(db: Session, district_id: int | None, village: str | None) -> Village | None:
    """Village lookup, narrowed to a district when known (avoids global scans)."""
    if not village:
        return None
    stmt = select(Village)
    if district_id is not None:
        stmt = stmt.where(Village.district_id == district_id)
    stmt = stmt.where(func.lower(Village.name) == village.strip().lower())
    return db.scalar(stmt.limit(1))


def resolve_dataset_mode(
    db: Session,
    state_id: int | None = None,
    district_id: int | None = None,
    village_id: int | None = None,
    district_ids: list[int] | None = None,
) -> str | None:
    """The dataset actually served for a scope: ``"real"`` | ``"demo"`` | ``None``.

    Real (``is_demo=False``) data is preferred: as soon as a scope contains any
    real assessment records it is served exclusively, otherwise demo assessment
    records are used, and with neither the scope is empty. This stops real and
    demo rows being double counted in the same aggregate.

    Mode is decided on assessment *records* rather than bare unit rows, so a
    scope whose real units carry no assessments (a partial import) falls back
    to its demo data instead of serving an empty aggregate.
    """
    stmt = (
        select(GroundwaterAssessment.assessment_unit_id)
        .join(AssessmentUnit, GroundwaterAssessment.assessment_unit_id == AssessmentUnit.id)
        .distinct()
    )
    if district_ids:
        stmt = stmt.where(AssessmentUnit.district_id.in_(district_ids))
    if state_id is not None:
        stmt = stmt.where(AssessmentUnit.state_id == state_id)
    if district_id is not None:
        stmt = stmt.where(AssessmentUnit.district_id == district_id)
    if village_id is not None:
        stmt = stmt.where(AssessmentUnit.village_id == village_id)
    if db.scalar(stmt.where(AssessmentUnit.is_demo.is_(False)).limit(1)) is not None:
        return "real"
    if db.scalar(stmt.where(AssessmentUnit.is_demo.is_(True)).limit(1)) is not None:
        return "demo"
    return None


def apply_dataset_filter(
    stmt,
    db: Session,
    state_id: int | None = None,
    district_id: int | None = None,
    village_id: int | None = None,
    mode: str | None = None,
    district_ids: list[int] | None = None,
):
    """Narrow ``stmt`` (built on AssessmentUnit) to the effective dataset.

    ``mode`` may be forced via ``"auto"`` (default, resolve per scope),
    ``"real"``, ``"demo"`` or ``"all"`` (no filtering).
    """
    if mode == "all":
        return stmt
    if mode is None or mode == "auto":
        mode = resolve_dataset_mode(db, state_id, district_id, village_id, district_ids=district_ids)
    if mode in ("real", "demo"):
        stmt = stmt.where(AssessmentUnit.is_demo.is_(mode == "demo"))
    return stmt


def resolve_scope_ids(
    db: Session,
    state: str | None,
    district: str | None,
    village: str | None,
) -> tuple[int | None, int | None, int | None, bool]:
    """Resolve scope names to ids. Returns (state_id, district_id, village_id, empty)."""
    state_obj = resolve_state(db, state)
    if state and state_obj is None:
        return None, None, None, True
    state_id = state_obj.id if state_obj else None
    district_obj = resolve_district(db, state_id, district)
    if district and district_obj is None:
        return state_id, None, None, True
    district_id = district_obj.id if district_obj else None
    village_obj = resolve_village(db, district_id, village)
    if village and village_obj is None:
        return state_id, district_id, None, True
    village_id = village_obj.id if village_obj else None
    return state_id, district_id, village_id, False


def get_states(db: Session) -> list[State]:
    return list(db.scalars(select(State).order_by(State.name)))


def get_districts(db: Session, state: str) -> list[District]:
    state_obj = resolve_state(db, state)
    if state_obj is None:
        return []
    return list(
        db.scalars(
            select(District)
            .where(District.state_id == state_obj.id)
            .order_by(District.name)
        )
    )


def get_villages(db: Session, state: str, district: str) -> list[Village]:
    state_obj = resolve_state(db, state)
    if state_obj is None:
        return []
    district_obj = db.scalar(
        select(District).where(
            District.state_id == state_obj.id,
            func.lower(District.name) == district.strip().lower(),
        )
    )
    if district_obj is None:
        return []
    stmt = select(Village).where(Village.district_id == district_obj.id)
    if db.scalar(
        select(Village.id)
        .where(Village.district_id == district_obj.id, Village.is_demo.is_(False))
        .limit(1)
    ):
        stmt = stmt.where(Village.is_demo.is_(False))
    return list(db.scalars(stmt.order_by(Village.name)))


def find_village(
    db: Session,
    name: str,
    state: str | None = None,
    district: str | None = None,
) -> Village | None:
    """Find a village whose name matches ``name`` exactly (case-insensitive).

    When ``state``/``district`` are provided the search is narrowed to that
    area first (so a village name shared across states resolves correctly).
    """
    state_id, district_id, _, empty = resolve_scope_ids(db, state, district, None)
    if empty:
        return None
    stmt = select(Village)
    if district_id is not None:
        stmt = stmt.where(Village.district_id == district_id)
    elif state_id is not None:
        stmt = stmt.where(
            Village.district_id.in_(select(District.id).where(District.state_id == state_id))
        )
    stmt = stmt.where(func.lower(Village.name) == name.strip().lower())
    return db.scalar(stmt.limit(1))


def get_categories(db: Session) -> list[AssessmentCategory]:
    return list(db.scalars(select(AssessmentCategory).order_by(AssessmentCategory.name)))


def unit_context_map(
    db: Session,
    unit_ids: list[int],
) -> dict[int, tuple[str, str, str]]:
    """Bulk-resolve (state, district, unit name) for many units in one query."""
    if not unit_ids:
        return {}
    rows = db.execute(
        select(
            AssessmentUnit.id,
            State.name.label("state_name"),
            District.name.label("district_name"),
            AssessmentUnit.name,
        )
        .join(State, AssessmentUnit.state_id == State.id)
        .outerjoin(District, AssessmentUnit.district_id == District.id)
        .where(AssessmentUnit.id.in_(unit_ids))
    ).all()
    return {
        row.id: (row.state_name, row.district_name or "", row.name) for row in rows
    }


def get_assessments(
    db: Session,
    state: str | None = None,
    district: str | None = None,
    year: int | None = None,
    category: str | None = None,
    unit: str | None = None,
    village: str | None = None,
    limit: int = 200,
    data_source: str = "auto",
) -> list[GroundwaterAssessment]:
    state_id, district_id, village_id, empty = resolve_scope_ids(db, state, district, village)
    if empty:
        return []
    stmt = (
        select(GroundwaterAssessment)
        .join(AssessmentUnit, GroundwaterAssessment.assessment_unit_id == AssessmentUnit.id)
        .join(District, AssessmentUnit.district_id == District.id)
        .join(State, AssessmentUnit.state_id == State.id)
        .order_by(State.name, District.name, GroundwaterAssessment.assessment_year.desc())
        .limit(limit)
    )
    if state_id is not None:
        stmt = stmt.where(AssessmentUnit.state_id == state_id)
    if district_id is not None:
        stmt = stmt.where(AssessmentUnit.district_id == district_id)
    if village_id is not None:
        stmt = stmt.where(AssessmentUnit.village_id == village_id)
    if unit:
        stmt = stmt.where(AssessmentUnit.name.ilike(f"%{unit.strip()}%"))
    if year is not None:
        stmt = stmt.where(GroundwaterAssessment.assessment_year == year)
    if category:
        stmt = stmt.where(func.lower(GroundwaterAssessment.category) == category.strip().lower())
    stmt = apply_dataset_filter(stmt, db, state_id, district_id, village_id, data_source)
    return list(db.scalars(stmt))


def get_recharge(
    db: Session,
    state: str | None = None,
    district: str | None = None,
    year: int | None = None,
    village: str | None = None,
    limit: int = 200,
    data_source: str = "auto",
) -> list[GroundwaterRecharge]:
    state_id, district_id, village_id, empty = resolve_scope_ids(db, state, district, village)
    if empty:
        return []
    stmt = (
        select(GroundwaterRecharge)
        .join(AssessmentUnit, GroundwaterRecharge.assessment_unit_id == AssessmentUnit.id)
        .join(District, AssessmentUnit.district_id == District.id)
        .join(State, AssessmentUnit.state_id == State.id)
        .order_by(State.name, District.name, GroundwaterRecharge.year.desc())
        .limit(limit)
    )
    if state_id is not None:
        stmt = stmt.where(AssessmentUnit.state_id == state_id)
    if district_id is not None:
        stmt = stmt.where(AssessmentUnit.district_id == district_id)
    if village_id is not None:
        stmt = stmt.where(AssessmentUnit.village_id == village_id)
    if year is not None:
        stmt = stmt.where(GroundwaterRecharge.year == year)
    stmt = apply_dataset_filter(stmt, db, state_id, district_id, village_id, data_source)
    return list(db.scalars(stmt))


def get_extraction(
    db: Session,
    state: str | None = None,
    district: str | None = None,
    year: int | None = None,
    village: str | None = None,
    limit: int = 200,
    data_source: str = "auto",
) -> list[GroundwaterExtraction]:
    state_id, district_id, village_id, empty = resolve_scope_ids(db, state, district, village)
    if empty:
        return []
    stmt = (
        select(GroundwaterExtraction)
        .join(AssessmentUnit, GroundwaterExtraction.assessment_unit_id == AssessmentUnit.id)
        .join(District, AssessmentUnit.district_id == District.id)
        .join(State, AssessmentUnit.state_id == State.id)
        .order_by(State.name, District.name, GroundwaterExtraction.year.desc())
        .limit(limit)
    )
    if state_id is not None:
        stmt = stmt.where(AssessmentUnit.state_id == state_id)
    if district_id is not None:
        stmt = stmt.where(AssessmentUnit.district_id == district_id)
    if village_id is not None:
        stmt = stmt.where(AssessmentUnit.village_id == village_id)
    if year is not None:
        stmt = stmt.where(GroundwaterExtraction.year == year)
    stmt = apply_dataset_filter(stmt, db, state_id, district_id, village_id, data_source)
    return list(db.scalars(stmt))


def get_latest_year(
    db: Session,
    state: str | None = None,
    district: str | None = None,
    village: str | None = None,
) -> int | None:
    """Most recent assessment year for a scope (used for village snapshots)."""
    state_id, district_id, village_id, empty = resolve_scope_ids(db, state, district, village)
    if empty:
        return None
    stmt = (
        select(func.max(GroundwaterAssessment.assessment_year))
        .join(AssessmentUnit, GroundwaterAssessment.assessment_unit_id == AssessmentUnit.id)
    )
    if state_id is not None:
        stmt = stmt.where(AssessmentUnit.state_id == state_id)
    if district_id is not None:
        stmt = stmt.where(AssessmentUnit.district_id == district_id)
    if village_id is not None:
        stmt = stmt.where(AssessmentUnit.village_id == village_id)
    stmt = apply_dataset_filter(stmt, db, state_id, district_id, village_id)
    return db.scalar(stmt)


def get_rainfall(
    db: Session,
    state: str | None = None,
    district: str | None = None,
    village: str | None = None,
    year: int | None = None,
    limit: int = 200,
    data_source: str = "auto",
) -> list[GroundwaterRainfall]:
    state_id, district_id, village_id, empty = resolve_scope_ids(db, state, district, village)
    if empty:
        return []
    stmt = (
        select(GroundwaterRainfall)
        .join(AssessmentUnit, GroundwaterRainfall.assessment_unit_id == AssessmentUnit.id)
        .join(District, AssessmentUnit.district_id == District.id)
        .join(State, AssessmentUnit.state_id == State.id)
        .order_by(State.name, District.name, GroundwaterRainfall.year.desc())
        .limit(limit)
    )
    if state_id is not None:
        stmt = stmt.where(AssessmentUnit.state_id == state_id)
    if district_id is not None:
        stmt = stmt.where(AssessmentUnit.district_id == district_id)
    if village_id is not None:
        stmt = stmt.where(AssessmentUnit.village_id == village_id)
    if year is not None:
        stmt = stmt.where(GroundwaterRainfall.year == year)
    stmt = apply_dataset_filter(stmt, db, state_id, district_id, village_id, data_source)
    return list(db.scalars(stmt))


def get_summary(
    db: Session,
    state: str | None = None,
    district: str | None = None,
    year: int | None = None,
    village: str | None = None,
    data_source: str = "auto",
    basin: str | None = None,
) -> dict:
    key = ("summary", state, district, village, year, data_source, basin)
    cached = cache_get(key)
    if cached is not None:
        return dict(cached)

    state_id, district_id, village_id, empty = resolve_scope_ids(db, state, district, village)
    basin_ids: list[int] = []
    if basin:
        from app.ingres.basins import basin_district_ids

        basin_ids = basin_district_ids(db, basin)
        if not basin_ids:
            return _empty_summary()
        empty = False
    if empty:
        return _empty_summary()

    mode = resolve_dataset_mode(db, state_id, district_id, village_id, district_ids=basin_ids or None)
    eff_mode = data_source if data_source in ("real", "demo") else mode

    base = select(GroundwaterAssessment).join(
        AssessmentUnit, GroundwaterAssessment.assessment_unit_id == AssessmentUnit.id
    )
    if basin_ids:
        base = base.where(AssessmentUnit.district_id.in_(basin_ids))
    elif state_id is not None:
        base = base.where(AssessmentUnit.state_id == state_id)
    if district_id is not None:
        base = base.where(AssessmentUnit.district_id == district_id)
    if village_id is not None:
        base = base.where(AssessmentUnit.village_id == village_id)
    if year is not None:
        base = base.where(GroundwaterAssessment.assessment_year == year)
    if basin_ids:
        base = apply_dataset_filter(base, db, mode=eff_mode, district_ids=basin_ids)
    else:
        base = apply_dataset_filter(base, db, state_id, district_id, village_id, eff_mode)

    sub = base.subquery()
    total_recharge, total_extraction, avg_stage, unit_count = db.execute(
        select(
            func.coalesce(func.sum(sub.c.recharge_total), 0),
            func.coalesce(func.sum(sub.c.extraction_total), 0),
            func.avg(sub.c.stage_of_extraction),
            func.count(func.distinct(sub.c.assessment_unit_id)),
        ).select_from(sub)
    ).one()

    counts_rows = db.execute(
        select(sub.c.category, func.count(sub.c.id))
        .select_from(sub)
        .group_by(sub.c.category)
    ).all()
    category_counts = [{"category": row[0], "count": row[1]} for row in counts_rows if row[0]]

    if eff_mode == "real":
        is_demo = False
        source = "CGWB Dynamic Ground Water Resources Assessment & IMD Gridded Rainfall (2025)"
    else:
        is_demo = True
        source = "IN-GRES Assessment Dataset (CGWB/IMD observations)"

    result = {
        "total_recharge": round(float(total_recharge or 0), 2),
        "total_extraction": round(float(total_extraction or 0), 2),
        "average_stage_of_extraction": round(float(avg_stage or 0), 2),
        "assessment_units": int(unit_count or 0),
        "category_counts": category_counts,
        "is_demo": is_demo,
        "source": source,
    }
    cache_set(key, result)
    return result


def _empty_summary() -> dict:
    return {
        "total_recharge": 0.0,
        "total_extraction": 0.0,
        "average_stage_of_extraction": 0.0,
        "assessment_units": 0,
        "category_counts": [],
        "is_demo": True,
        "source": "IN-GRES Assessment Dataset",
    }