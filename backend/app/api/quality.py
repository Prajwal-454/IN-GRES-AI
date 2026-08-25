"""Data-quality endpoints: anomaly scan, flag review workflow, summary.

Reads and mutations are admin-only — the review dashboard lives in the
admin console (Admin -> Data Quality).
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import require_roles
from app.core.audit import write_audit
from app.database import get_db
from app.models.quality import AnomalyFlag
from app.models.user import User
from app.services.data_quality import open_flags_summary, run_quality_scan

router = APIRouter(prefix="/quality", tags=["quality"])

_admin = Depends(require_roles("admin"))

_FLAG_KINDS = (
    "impossible_value",
    "negative_value",
    "category_mismatch",
    "implausible_ratio",
    "outlier",
    "level_depth_out_of_range",
    "rainfall_out_of_range",
)


class FlagReview(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    status: str | None = Field(default=None, pattern="^(open|acknowledged|resolved|dismissed)$")
    review_note: str | None = Field(default=None, max_length=500)


class FlagOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    kind: str
    severity: str
    metric: str
    year: int | None
    state_name: str | None
    district_name: str | None
    unit_name: str | None
    value: float | None
    expected_min: float | None
    expected_max: float | None
    detail: str | None
    status: str
    review_note: str | None
    created_at: object | None


@router.get("/summary")
def quality_summary(
    db: Session = Depends(get_db),
    _admin_user: User = _admin,
):
    return open_flags_summary(db)


@router.get("/flags")
def list_flags(
    status_filter: str = Query(
        default="open",
        alias="status",
        pattern="^(all|open|acknowledged|resolved|dismissed)$",
    ),
    kind: str | None = Query(default=None),
    severity: str | None = Query(default=None, pattern="^(high|medium|low)$"),
    state: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    _admin_user: User = _admin,
):
    stmt = select(AnomalyFlag).order_by(AnomalyFlag.created_at.desc(), AnomalyFlag.id.desc())
    count_stmt = select(func.count(AnomalyFlag.id))
    if status_filter != "all":
        stmt = stmt.where(AnomalyFlag.status == status_filter)
        count_stmt = count_stmt.where(AnomalyFlag.status == status_filter)
    if kind:
        stmt = stmt.where(AnomalyFlag.kind == kind)
        count_stmt = count_stmt.where(AnomalyFlag.kind == kind)
    if severity:
        stmt = stmt.where(AnomalyFlag.severity == severity)
        count_stmt = count_stmt.where(AnomalyFlag.severity == severity)
    if state:
        stmt = stmt.where(func.lower(AnomalyFlag.state_name) == state.strip().lower())
        count_stmt = count_stmt.where(func.lower(AnomalyFlag.state_name) == state.strip().lower())

    total = int(db.scalar(count_stmt) or 0)
    rows = list(db.scalars(stmt.limit(limit).offset(offset)))
    return {
        "total": total,
        "count": len(rows),
        "limit": limit,
        "offset": offset,
        "flags": [FlagOut.model_validate(r).model_dump(mode="json") for r in rows],
        "kinds": list(_FLAG_KINDS),
    }


@router.post("/scan", status_code=status.HTTP_200_OK)
def trigger_scan(
    db: Session = Depends(get_db),
    admin_user: User = _admin,
):
    """Run the anomaly scan now. Idempotent per fingerprint."""
    result = run_quality_scan(db)
    write_audit(
        db,
        admin_user,
        "QUALITY_SCAN",
        resource="anomaly_scan",
        details={"created": result["created"], "scanned": result["scanned"]},
    )
    return result


@router.patch("/flags/{flag_id}")
def review_flag(
    flag_id: int,
    data: FlagReview,
    db: Session = Depends(get_db),
    admin_user: User = _admin,
):
    flag = db.get(AnomalyFlag, flag_id)
    if not flag:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Flag not found")

    changes = data.model_dump(exclude_unset=True, exclude_none=False)
    if "status" in changes and changes["status"]:
        flag.status = changes["status"]
        flag.reviewed_by = admin_user.id
    if "review_note" in changes:
        flag.review_note = changes["review_note"]
    if not changes:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "No fields to update")
    db.commit()

    write_audit(
        db,
        admin_user,
        "QUALITY_FLAG_REVIEW",
        resource="anomaly_flag",
        resource_id=flag.id,
        details={"status": flag.status, "note": bool(flag.review_note)},
    )
    return FlagOut.model_validate(flag).model_dump(mode="json")
