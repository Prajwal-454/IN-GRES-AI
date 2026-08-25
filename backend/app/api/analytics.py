"""Analytics endpoints: trends, district rankings and computed insights."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.database import get_db
from app.ingres.query_cache import cache_get, cache_set
from app.ingres.queries import apply_dataset_filter, resolve_state
from app.models.groundwater import (
    AssessmentUnit,
    District,
    GroundwaterAssessment,
)
from app.models.user import User

router = APIRouter(prefix="/analytics", tags=["analytics"])

CATEGORY_ORDER = ["safe", "semi-critical", "critical", "over-exploited"]


def _state_id(db: Session, state: str | None) -> int | None:
    if not state:
        return None
    obj = resolve_state(db, state)
    return obj.id if obj else None


def trends_data(db: Session, state: str | None = None) -> list[dict]:
    key = ("trends", state)
    cached = cache_get(key)
    if cached is not None:
        return [dict(p) for p in cached]

    state_id = _state_id(db, state)
    base = select(
        GroundwaterAssessment.assessment_year.label("year"),
        func.sum(GroundwaterAssessment.recharge_total).label("recharge"),
        func.sum(GroundwaterAssessment.extraction_total).label("extraction"),
        func.avg(GroundwaterAssessment.stage_of_extraction).label("stage"),
    )
    if state_id is not None:
        base = base.join(
            AssessmentUnit, GroundwaterAssessment.assessment_unit_id == AssessmentUnit.id
        ).where(AssessmentUnit.state_id == state_id)
    stmt = base.group_by(GroundwaterAssessment.assessment_year).order_by(
        GroundwaterAssessment.assessment_year
    )
    rows = db.execute(stmt).all()

    cat_stmt = (
        select(
            GroundwaterAssessment.assessment_year.label("year"),
            GroundwaterAssessment.category,
            func.count(GroundwaterAssessment.id).label("cnt"),
        )
    )
    if state_id is not None:
        cat_stmt = cat_stmt.join(
            AssessmentUnit, GroundwaterAssessment.assessment_unit_id == AssessmentUnit.id
        ).where(AssessmentUnit.state_id == state_id)
    cat_rows = db.execute(
        cat_stmt.group_by(GroundwaterAssessment.assessment_year, GroundwaterAssessment.category)
    ).all()

    year_counts: dict[int, dict[str, int]] = {}
    for year, cat, cnt in cat_rows:
        if cat:
            year_counts.setdefault(year, {})[cat] = int(cnt)

    out = []
    for row in rows:
        counts = {c: 0 for c in CATEGORY_ORDER}
        for cat, cnt in year_counts.get(row.year, {}).items():
            counts[cat] = cnt
        out.append(
            {
                "year": row.year,
                "recharge": round(float(row.recharge or 0), 2),
                "extraction": round(float(row.extraction or 0), 2),
                "stage_of_extraction": round(float(row.stage or 0), 2),
                "categories": counts,
            }
        )
    cache_set(key, out)
    return out


def district_ranking_data(
    db: Session,
    state: str | None = None,
    year: int | None = None,
    metric: str = "extraction",
) -> list[dict]:
    if metric not in ("recharge", "extraction", "stage"):
        metric = "extraction"
    key = ("ranking", state, year, metric)
    cached = cache_get(key)
    if cached is not None:
        return list(cached)

    target = "stage_of_extraction" if metric == "stage" else f"{metric}_total"
    state_id = _state_id(db, state)
    stmt = (
        select(
            District.name.label("district"),
            func.sum(getattr(GroundwaterAssessment, target)).label("value"),
            func.avg(GroundwaterAssessment.stage_of_extraction).label("stage"),
        )
        .select_from(GroundwaterAssessment)
        .join(AssessmentUnit, GroundwaterAssessment.assessment_unit_id == AssessmentUnit.id)
        .join(District, AssessmentUnit.district_id == District.id)
        .group_by(District.id, District.name)
    )
    if state_id is not None:
        stmt = stmt.where(AssessmentUnit.state_id == state_id)
    if year is not None:
        stmt = stmt.where(GroundwaterAssessment.assessment_year == year)
    stmt = apply_dataset_filter(stmt, db, state_id)

    rows = []
    for district, value, stage in db.execute(stmt).all():
        rows.append(
            {
                "district": district,
                "value": round(float(value or 0), 2),
                "stage_of_extraction": round(float(stage or 0), 2),
                "year": year,
            }
        )
    rows.sort(key=lambda r: r["value"], reverse=True)
    cache_set(key, rows)
    return rows


def insights_data(db: Session, state: str | None = None) -> list[dict]:
    trend_rows = trends_data(db, state)
    if not trend_rows:
        return []

    latest = trend_rows[-1]
    first = trend_rows[0]
    scope = state or "all of India"
    insights_list: list[dict] = []

    stage_delta = latest["stage_of_extraction"] - first["stage_of_extraction"]
    direction = "rising" if stage_delta > 1 else "falling" if stage_delta < -1 else "stable"
    insights_list.append(
        {
            "type": "trend",
            "text": f"Average stage of groundwater extraction across {scope} went from "
            f"{first['stage_of_extraction']:.1f}% ({first['year']}) to "
            f"{latest['stage_of_extraction']:.1f}% ({latest['year']}) — {direction}.",
        }
    )

    over = latest["categories"].get("over-exploited", 0)
    crit = latest["categories"].get("critical", 0)
    total = sum(latest["categories"].values())
    if total:
        share = (over + crit) * 100 / total
        insights_list.append(
            {
                "type": "stress",
                "text": f"In {latest['year']}, {share:.0f}% of assessment units in {scope} are "
                f"critical or over-exploited ({over + crit} of {total} units).",
            }
        )

    ranking = district_ranking_data(db, state, year=latest["year"], metric="stage")
    if ranking:
        most = ranking[0]
        insights_list.append(
            {
                "type": "top",
                "text": f"The most stressed district in {latest['year']} is {most['district']} "
                f"with an average stage of extraction of {most['stage_of_extraction']:.1f}%.",
            }
        )

    if first["recharge"]:
        pct = (latest["recharge"] - first["recharge"]) * 100 / first["recharge"]
        insights_list.append(
            {
                "type": "recharge",
                "text": f"Total annual recharge in {scope} changed by {pct:+.1f}% between "
                f"{first['year']} and {latest['year']}.",
            }
        )

    return insights_list


@router.get("/trends")
def trends(
    state: str | None = Query(default=None),
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    return trends_data(db, state)


@router.get("/district-ranking")
def district_ranking(
    state: str | None = Query(default=None),
    year: int | None = Query(default=None),
    metric: str = Query(default="extraction", pattern="^(recharge|extraction|stage)$"),
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    return district_ranking_data(db, state=state, year=year, metric=metric)


@router.get("/insights")
def insights(
    state: str | None = Query(default=None),
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    items = insights_data(db, state)
    years = trends_data(db, state)
    latest_year = years[-1]["year"] if years else None
    return {"insights": items, "state": state, "latest_year": latest_year}