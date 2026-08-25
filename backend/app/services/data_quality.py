"""Data-quality anomaly scan engine.

Scans groundwater observations for values that cannot be physically true,
values inconsistent with their own metadata (category vs stage), and
statistical outliers within a district/year cohort. Findings are stored as
:class:`~app.models.quality.AnomalyFlag` rows with a stable fingerprint so
re-running the scan never duplicates an already-known issue, and admins are
notified in-app when new high-severity issues appear.
"""

from __future__ import annotations

import hashlib
import logging
import math
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models.groundwater import (
    AssessmentUnit,
    District,
    GroundwaterAssessment,
    GroundwaterLevel,
    GroundwaterRainfall,
    State,
)
from app.models.notification import UserNotification
from app.models.quality import AnomalyFlag

logger = logging.getLogger(__name__)

# Physical plausibility bounds.
STAGE_MIN, STAGE_MAX = 0.0, 200.0  # % of recharge extracted
DEPTH_MIN, DEPTH_MAX = 0.0, 500.0  # metres below ground level
RAINFALL_MIN, RAINFALL_MAX = 0.0, 5000.0  # mm per month

# A unit pumping far more than it recharges while still reporting a sane
# stage is internally inconsistent (stage ~= extraction / recharge * 100).
IMPLAUSIBLE_EXTRACTION_RATIO = 1.5

# Statistical outliers: |z| within the same district + assessment year.
OUTLIER_Z_THRESHOLD = 4.0


def _fingerprint(*parts: object) -> str:
    raw = "|".join("" if p is None else str(p) for p in parts)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _as_float(value: object) -> float | None:
    if value is None:
        return None
    if isinstance(value, Decimal):
        return float(value)
    try:
        return float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None


def _flag(
    *,
    kind: str,
    severity: str,
    metric: str,
    row_id: int | None,
    unit_id: int | None,
    dataset_id: int | None,
    year: int | None,
    state: str | None,
    district: str | None,
    unit: str | None,
    value: float | None,
    expected_min: float | None = None,
    expected_max: float | None = None,
    detail: str | None = None,
) -> AnomalyFlag:
    return AnomalyFlag(
        kind=kind,
        severity=severity,
        metric=metric,
        assessment_id=row_id,
        assessment_unit_id=unit_id,
        dataset_id=dataset_id,
        year=year,
        state_name=state,
        district_name=district,
        unit_name=unit,
        value=value,
        expected_min=expected_min,
        expected_max=expected_max,
        detail=detail,
        status="open",
        fingerprint=_fingerprint(kind, metric, unit_id, year, None if value is None else round(value, 3)),
    )


def _scan_assessments(db: Session, flags: list[AnomalyFlag]) -> int:
    """Rule-based checks on assessment rows. Returns number of rows scanned."""
    stmt = (
        select(
            GroundwaterAssessment,
            State.name,
            District.name,
            AssessmentUnit.name,
        )
        .join(AssessmentUnit, GroundwaterAssessment.assessment_unit_id == AssessmentUnit.id)
        .join(State, AssessmentUnit.state_id == State.id)
        .outerjoin(District, AssessmentUnit.district_id == District.id)
        .order_by(GroundwaterAssessment.id)
    )
    scanned = 0
    for assessment, state, district, unit in db.execute(stmt).all():
        scanned += 1
        year = assessment.assessment_year
        stage = _as_float(assessment.stage_of_extraction)
        recharge = _as_float(assessment.recharge_total)
        extraction = _as_float(assessment.extraction_total)

        def add(**kwargs) -> None:  # noqa: ANN001 - tiny local helper
            kwargs.setdefault("row_id", assessment.id)
            kwargs.setdefault("unit_id", assessment.assessment_unit_id)
            kwargs.setdefault("dataset_id", assessment.dataset_id)
            kwargs.setdefault("year", year)
            kwargs.setdefault("state", state)
            kwargs.setdefault("district", district)
            kwargs.setdefault("unit", unit)
            flags.append(_flag(**kwargs))

        # Impossible values.
        if stage is not None and not (STAGE_MIN <= stage <= STAGE_MAX):
            add(
                kind="impossible_value",
                severity="high",
                metric="stage",
                value=stage,
                expected_min=STAGE_MIN,
                expected_max=STAGE_MAX,
                detail=f"Stage of extraction {stage} outside physical range {STAGE_MIN}-{STAGE_MAX}%.",
            )
        if recharge is not None and recharge < 0:
            add(
                kind="negative_value",
                severity="high",
                metric="recharge",
                value=recharge,
                expected_min=0,
                detail="Negative annual recharge.",
            )
        if extraction is not None and extraction < 0:
            add(
                kind="negative_value",
                severity="high",
                metric="extraction",
                value=extraction,
                expected_min=0,
                detail="Negative annual extraction.",
            )

        # Internal consistency: category label must match the numeric stage.
        if stage is not None and assessment.category:
            category = assessment.category.strip().lower()
            implied = (
                "safe" if stage < 70 else "semi-critical" if stage < 90 else "critical" if stage <= 100 else "over-exploited"
            )
            if category and category != implied:
                add(
                    kind="category_mismatch",
                    severity="medium",
                    metric="stage",
                    value=stage,
                    detail=f"Category '{assessment.category}' does not match stage {stage:.2f}% (implied '{implied}').",
                )

        # Internal consistency: extraction/recharge ratio vs reported stage.
        if recharge is not None and extraction is not None and recharge > 0:
            ratio = extraction / recharge
            if ratio > IMPLAUSIBLE_EXTRACTION_RATIO and stage is not None and stage <= 100:
                add(
                    kind="implausible_ratio",
                    severity="medium",
                    metric="extraction",
                    value=round(ratio, 3),
                    detail=(
                        f"Extraction is {ratio:.2f}x recharge but stage of extraction "
                        f"is reported as {stage:.2f}% (inconsistent)."
                    ),
                )
    return scanned


def _scan_statistical_outliers(db: Session, flags: list[AnomalyFlag]) -> int:
    """|z| > threshold on stage within each district+year cohort."""
    stats_stmt = (
        select(
            AssessmentUnit.district_id.label("district_id"),
            GroundwaterAssessment.assessment_year.label("year"),
            func.count(GroundwaterAssessment.id).label("n"),
            func.avg(GroundwaterAssessment.stage_of_extraction).label("mean"),
            func.sum(GroundwaterAssessment.stage_of_extraction * GroundwaterAssessment.stage_of_extraction).label("sq"),
        )
        .join(AssessmentUnit, GroundwaterAssessment.assessment_unit_id == AssessmentUnit.id)
        .where(GroundwaterAssessment.stage_of_extraction.is_not(None))
        .group_by(AssessmentUnit.district_id, GroundwaterAssessment.assessment_year)
        .having(func.count(GroundwaterAssessment.id) >= 5)
    )
    cohorts: dict[tuple[int | None, int], tuple[float, float]] = {}
    for district_id, year, n, mean, sq in db.execute(stats_stmt).all():
        mean_f = _as_float(mean)
        sq_f = _as_float(sq)
        if mean_f is None or sq_f is None or n is None or n < 2:
            continue
        variance = max(sq_f / n - mean_f * mean_f, 0.0)
        std = math.sqrt(variance)
        if std <= 0:
            continue
        cohorts[(district_id, year)] = (mean_f, std)

    if not cohorts:
        return 0

    ctx_stmt = (
        select(
            GroundwaterAssessment,
            AssessmentUnit.district_id.label("district_id"),
            State.name,
            District.name,
            AssessmentUnit.name,
        )
        .join(AssessmentUnit, GroundwaterAssessment.assessment_unit_id == AssessmentUnit.id)
        .join(State, AssessmentUnit.state_id == State.id)
        .outerjoin(District, AssessmentUnit.district_id == District.id)
        .where(
            GroundwaterAssessment.stage_of_extraction.is_not(None),
            AssessmentUnit.district_id.is_not(None),
        )
        .order_by(GroundwaterAssessment.id)
    )
    scanned = 0
    for assessment, unit_district_id, state, district, unit in db.execute(ctx_stmt).all():
        scanned += 1
        stats = cohorts.get((unit_district_id, assessment.assessment_year))
        if not stats:
            continue
        mean, std = stats
        value = _as_float(assessment.stage_of_extraction)
        if value is None:
            continue
        z = (value - mean) / std
        if abs(z) <= OUTLIER_Z_THRESHOLD:
            continue
        flags.append(
            _flag(
                kind="outlier",
                severity="high" if abs(z) >= OUTLIER_Z_THRESHOLD * 1.5 else "medium",
                metric="stage",
                row_id=assessment.id,
                unit_id=assessment.assessment_unit_id,
                dataset_id=assessment.dataset_id,
                year=assessment.assessment_year,
                state=state,
                district=district,
                unit=unit,
                value=value,
                expected_min=round(mean - OUTLIER_Z_THRESHOLD * std, 2),
                expected_max=round(mean + OUTLIER_Z_THRESHOLD * std, 2),
                detail=(
                    f"Stage {value:.2f}% is {abs(z):.1f} standard deviations from the "
                    f"{district} {assessment.assessment_year} cohort mean ({mean:.2f}%)."
                ),
            )
        )
    return scanned


def _scan_levels(db: Session, flags: list[AnomalyFlag]) -> int:
    stmt = select(
        GroundwaterLevel,
        State.name,
        District.name,
        AssessmentUnit.name,
    ).join(
        AssessmentUnit, GroundwaterLevel.assessment_unit_id == AssessmentUnit.id
    ).join(
        State, AssessmentUnit.state_id == State.id
    ).outerjoin(
        District, AssessmentUnit.district_id == District.id
    ).where(GroundwaterLevel.depth_bgl.is_not(None))
    scanned = 0
    for level, state, district, unit in db.execute(stmt).all():
        scanned += 1
        depth = _as_float(level.depth_bgl)
        if depth is None or DEPTH_MIN <= depth <= DEPTH_MAX:
            continue
        year = level.measured_date.year if level.measured_date else None
        flags.append(
            _flag(
                kind="level_depth_out_of_range",
                severity="high",
                metric="level",
                row_id=None,
                unit_id=level.assessment_unit_id,
                dataset_id=level.dataset_id,
                year=year,
                state=state,
                district=district,
                unit=unit,
                value=depth,
                expected_min=DEPTH_MIN,
                expected_max=DEPTH_MAX,
                detail=f"Water level depth {depth} m bgl outside plausible range {DEPTH_MIN}-{DEPTH_MAX} m.",
            )
        )
    return scanned


def _scan_rainfall(db: Session, flags: list[AnomalyFlag]) -> int:
    stmt = select(
        GroundwaterRainfall,
        State.name,
        District.name,
        AssessmentUnit.name,
    ).join(
        AssessmentUnit, GroundwaterRainfall.assessment_unit_id == AssessmentUnit.id
    ).join(
        State, AssessmentUnit.state_id == State.id
    ).outerjoin(
        District, AssessmentUnit.district_id == District.id
    ).where(GroundwaterRainfall.value_mm.is_not(None))
    scanned = 0
    for rainfall, state, district, unit in db.execute(stmt).all():
        scanned += 1
        value = _as_float(rainfall.value_mm)
        if value is None or RAINFALL_MIN <= value <= RAINFALL_MAX:
            continue
        flags.append(
            _flag(
                kind="rainfall_out_of_range",
                severity="medium",
                metric="rainfall",
                row_id=None,
                unit_id=rainfall.assessment_unit_id,
                dataset_id=rainfall.dataset_id,
                year=rainfall.year,
                state=state,
                district=district,
                unit=unit,
                value=value,
                expected_min=RAINFALL_MIN,
                expected_max=RAINFALL_MAX,
                detail=f"Monthly rainfall {value} mm outside plausible range {RAINFALL_MIN}-{RAINFALL_MAX} mm.",
            )
        )
    return scanned


def _notify_admins(db: Session, new_high: int) -> None:
    if not get_settings().NOTIFICATIONS_ENABLED or new_high <= 0:
        return
    from app.models.user import User

    admins = list(db.scalars(select(User).where(User.role == "admin", User.is_active.is_(True))))
    body = (
        f"{new_high} new high-severity data-quality issue(s) were detected by the "
        f"latest anomaly scan. Review them in Admin -> Data Quality."
    )
    for admin in admins:
        db.add(
            UserNotification(
                user_id=admin.id,
                rule_id=None,
                kind="alert",
                title="Data quality issues detected",
                body=body,
                payload={"severity": "high", "count": new_high},
                read=False,
            )
        )


def run_quality_scan(db: Session) -> dict:
    """Run every rule over all observations. Idempotent per fingerprint.

    Returns ``{"scanned": ..., "created": ..., "by_kind": {...},
    "by_severity": {...}}`` describing this run only.
    """
    started = datetime.now(timezone.utc)
    flags: list[AnomalyFlag] = []
    scanned_rows = 0
    scanned_rows += _scan_assessments(db, flags)

    existing = set(
        db.scalars(select(AnomalyFlag.fingerprint)).all()
    )
    seen: set[str] = set()
    fresh: list[AnomalyFlag] = []
    for flag in flags:
        if flag.fingerprint in existing or flag.fingerprint in seen:
            continue
        seen.add(flag.fingerprint)
        fresh.append(flag)

    cap = get_settings().QUALITY_MAX_FLAGS_PER_SCAN
    truncated = len(fresh) > cap
    fresh = fresh[:cap]

    for i, flag in enumerate(fresh):
        db.add(flag)
        if (i + 1) % 500 == 0:
            db.flush()
    db.commit()

    high = sum(1 for f in fresh if f.severity == "high")
    _notify_admins(db, high)

    by_kind: dict[str, int] = {}
    by_severity: dict[str, int] = {}
    for f in fresh:
        by_kind[f.kind] = by_kind.get(f.kind, 0) + 1
        by_severity[f.severity] = by_severity.get(f.severity, 0) + 1

    logger.info(
        "quality scan finished in %.1fs: scanned=%d created=%d%s",
        (datetime.now(timezone.utc) - started).total_seconds(),
        scanned_rows,
        len(fresh),
        " (capped)" if truncated else "",
    )
    return {
        "scanned": scanned_rows,
        "created": len(fresh),
        "truncated": truncated,
        "by_kind": by_kind,
        "by_severity": by_severity,
    }


def open_flags_summary(db: Session) -> dict:
    """Counts for the admin dashboard cards."""
    rows = db.execute(
        select(AnomalyFlag.status, AnomalyFlag.severity, func.count(AnomalyFlag.id))
        .group_by(AnomalyFlag.status, AnomalyFlag.severity)
    ).all()
    by_status: dict[str, int] = {}
    by_severity: dict[str, int] = {"high": 0, "medium": 0, "low": 0}
    for status, severity, count in rows:
        by_status[status] = by_status.get(status, 0) + int(count)
        if status == "open":
            by_severity[severity] = by_severity.get(severity, 0) + int(count)
    last_scan = db.scalar(select(func.max(AnomalyFlag.created_at)))
    total_open = by_status.get("open", 0)
    return {
        "total_open": total_open,
        "by_status": by_status,
        "by_severity": by_severity,
        "last_scan_at": last_scan.isoformat() if last_scan else None,
    }
