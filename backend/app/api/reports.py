"""Report generation: JSON data, CSV export, PDF export and schedules."""

from __future__ import annotations

import csv
import io
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.audit import write_audit
from app.database import get_db
from app.ingres import queries
from app.models.schedule import ReportSchedule
from app.models.user import User
from app.reports import assessment
from app.services import digests

router = APIRouter(prefix="/reports", tags=["reports"])


def _contexts(db: Session, unit_ids: list[int]) -> dict[int, tuple[str, str, str]]:
    return queries.unit_context_map(db, unit_ids)


def _assessment_rows(db: Session, state=None, district=None, village=None, year=None) -> list[dict]:
    rows = queries.get_assessments(
        db, state=state, district=district, village=village, year=year, limit=10000
    )
    ctx = _contexts(db, [r.assessment_unit_id for r in rows])
    out = []
    for r in rows:
        s, d, uname = ctx.get(r.assessment_unit_id, ("", "", ""))
        out.append(
            {
                "state": s,
                "district": d,
                "assessment_unit": uname,
                "year": r.assessment_year,
                "recharge_total": float(r.recharge_total) if r.recharge_total is not None else None,
                "extraction_total": float(r.extraction_total) if r.extraction_total is not None else None,
                "annual_extractable_resource": float(r.annual_extractable_resource)
                if r.annual_extractable_resource is not None
                else None,
                "stage_of_extraction": float(r.stage_of_extraction)
                if r.stage_of_extraction is not None
                else None,
                "category": r.category,
                "is_demo": False,
            }
        )
    return out


def _metric_rows(db: Session, kind: str, state=None, district=None, village=None, year=None) -> list[dict]:
    if kind == "recharge":
        rows = queries.get_recharge(
            db, state=state, district=district, village=village, year=year, limit=10000
        )
    else:
        rows = queries.get_extraction(
            db, state=state, district=district, village=village, year=year, limit=10000
        )
    ctx = _contexts(db, [r.assessment_unit_id for r in rows])
    out = []
    for r in rows:
        s, d, uname = ctx.get(r.assessment_unit_id, ("", "", ""))
        out.append(
            {
                "state": s,
                "district": d,
                "assessment_unit": uname,
                "year": r.year,
                "value": float(r.value) if r.value is not None else None,
                "type": getattr(r, "recharge_type", None) or getattr(r, "extraction_type", None),
                "is_demo": False,
            }
        )
    return out


@router.get("/data")
def report_data(
    state: str | None = Query(default=None),
    district: str | None = Query(default=None),
    village: str | None = Query(default=None),
    year: int | None = Query(default=None),
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    rows = _assessment_rows(db, state=state, district=district, village=village, year=year)
    summary = queries.get_summary(db, state=state, district=district, village=village, year=year)
    summary["state"] = state or "All states"
    summary["district"] = district
    summary["village"] = village
    summary["year"] = year
    return {"rows": rows, "summary": summary, "count": len(rows)}


@router.get("/export.csv")
def export_csv(
    type: str = Query(default="assessment", pattern="^(assessment|recharge|extraction)$"),
    state: str | None = Query(default=None),
    district: str | None = Query(default=None),
    village: str | None = Query(default=None),
    year: int | None = Query(default=None),
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    if type == "assessment":
        rows = _assessment_rows(db, state, district, village, year)
        fields = [
            "state",
            "district",
            "assessment_unit",
            "year",
            "recharge_total",
            "extraction_total",
            "annual_extractable_resource",
            "stage_of_extraction",
            "category",
            "is_demo",
        ]
    else:
        rows = _metric_rows(db, type, state, district, village, year)
        fields = ["state", "district", "assessment_unit", "year", "value", "type", "is_demo"]

    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=fields, extrasaction="ignore")
    writer.writeheader()
    for row in rows:
        writer.writerow(row)

    filename = f"ingres-{type}-report-{year or 'all'}.csv"
    return StreamingResponse(
        iter([buf.getvalue()]),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


def _build_pdf(summary: dict, rows: list[dict]) -> bytes:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.platypus import (
        Paragraph,
        SimpleDocTemplate,
        Spacer,
        Table,
        TableStyle,
    )

    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        leftMargin=18 * mm,
        rightMargin=18 * mm,
        topMargin=18 * mm,
        bottomMargin=18 * mm,
        title="IN-GRES AI Report",
    )
    styles = getSampleStyleSheet()
    story = []
    story.append(Paragraph("IN-GRES AI — Groundwater Report", styles["Title"]))
    story.append(Paragraph("Indian Groundwater Resource Estimation System", styles["Normal"]))
    story.append(
        Paragraph(
            f"Generated {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}",
            styles["Normal"],
        )
    )
    story.append(
        Paragraph(
            "Source: IN-GRES Assessment Dataset (CGWB/IMD observations).",
            styles["Normal"],
        )
    )
    story.append(Spacer(1, 6 * mm))

    scope = summary.get("state") or "All states"
    if summary.get("district"):
        scope += f" · {summary['district']}"
    if summary.get("village"):
        scope += f" · {summary['village']}"
    story.append(Paragraph(f"Scope: <b>{scope}</b>", styles["Heading2"]))
    story.append(
        Paragraph(
            f"Assessment units: <b>{summary['assessment_units']}</b> | "
            f"Total recharge: <b>{summary['total_recharge']:,.1f} hm³</b> | "
            f"Total extraction: <b>{summary['total_extraction']:,.1f} hm³</b> | "
            f"Average stage of extraction: <b>{summary['average_stage_of_extraction']:.1f}%</b>",
            styles["Normal"],
        )
    )
    story.append(Spacer(1, 4 * mm))

    cat_rows = [["Category", "Units"]]
    for cc in summary.get("category_counts", []):
        cat_rows.append([cc["category"], str(cc["count"])])
    cat_table = Table(cat_rows)
    cat_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0f766e")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("GRID", (0, 0), (-1, -1), 0.4, colors.grey),
            ]
        )
    )
    story.append(Paragraph("Category breakdown", styles["Heading3"]))
    story.append(cat_table)
    story.append(Spacer(1, 6 * mm))

    table_rows = [["State", "District", "Assessment unit", "Year", "Recharge", "Extraction", "Stage %", "Category"]]
    for r in rows:
        table_rows.append(
            [
                r["state"],
                r["district"],
                r["assessment_unit"],
                str(r["year"]),
                f"{r['recharge_total']:,.1f}" if r["recharge_total"] is not None else "-",
                f"{r['extraction_total']:,.1f}" if r["extraction_total"] is not None else "-",
                f"{r['stage_of_extraction']:.1f}" if r["stage_of_extraction"] is not None else "-",
                r["category"] or "-",
            ]
        )

    if len(table_rows) > 1:
        story.append(Paragraph("Assessment unit detail", styles["Heading3"]))
        detail = Table(table_rows, repeatRows=1)
        detail.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0f766e")),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                    ("GRID", (0, 0), (-1, -1), 0.3, colors.lightgrey),
                    ("FONTSIZE", (0, 0), (-1, -1), 7),
                ]
            )
        )
        story.append(detail)

    doc.build(story)
    return buf.getvalue()


@router.get("/export.pdf")
def export_pdf(
    state: str | None = Query(default=None),
    district: str | None = Query(default=None),
    village: str | None = Query(default=None),
    year: int | None = Query(default=None),
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    rows = _assessment_rows(db, state=state, district=district, village=village, year=year)
    summary = queries.get_summary(db, state=state, district=district, village=village, year=year)
    summary["state"] = state or "All states"
    summary["district"] = district
    summary["village"] = village
    summary["year"] = year
    pdf = _build_pdf(summary, rows)
    filename = f"ingres-report-{year or 'all'}.pdf"
    return StreamingResponse(
        io.BytesIO(pdf),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/assessment")
def assessment_report(
    state: str | None = Query(default=None),
    district: str | None = Query(default=None),
    year_from: int | None = Query(default=None),
    year_to: int | None = Query(default=None),
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    """AI-generated groundwater assessment report as structured JSON."""
    return assessment.build_assessment_report(
        db, state=state, district=district, year_from=year_from, year_to=year_to
    )


@router.get("/assessment.pdf")
def assessment_report_pdf(
    state: str | None = Query(default=None),
    district: str | None = Query(default=None),
    year_from: int | None = Query(default=None),
    year_to: int | None = Query(default=None),
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    report = assessment.build_assessment_report(
        db, state=state, district=district, year_from=year_from, year_to=year_to
    )
    pdf = assessment.render_assessment_pdf(report)
    safe = (district or state or "all").replace(" ", "_").replace("/", "_")
    filename = f"ingres-assessment-{safe}.pdf"
    return StreamingResponse(
        io.BytesIO(pdf),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/assessment.xlsx")
def assessment_report_xlsx(
    state: str | None = Query(default=None),
    district: str | None = Query(default=None),
    year_from: int | None = Query(default=None),
    year_to: int | None = Query(default=None),
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    report = assessment.build_assessment_report(
        db, state=state, district=district, year_from=year_from, year_to=year_to
    )
    xlsx = assessment.render_assessment_xlsx(report)
    safe = (district or state or "all").replace(" ", "_").replace("/", "_")
    filename = f"ingres-assessment-{safe}.xlsx"
    return StreamingResponse(
        io.BytesIO(xlsx),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


# ---------------------------------------------------------------------------
# Scheduled reports (digests)
# ---------------------------------------------------------------------------


class ScheduleCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    state: str | None = Field(default=None, max_length=120)
    district: str | None = Field(default=None, max_length=120)
    village: str | None = Field(default=None, max_length=120)
    frequency: str = Field(default="weekly", pattern="^(weekly|monthly)$")
    recipients: list[str] = Field(default_factory=list, max_length=20)
    enabled: bool = True


class ScheduleUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    frequency: str | None = Field(default=None, pattern="^(weekly|monthly)$")
    recipients: list[str] | None = Field(default=None, max_length=20)
    enabled: bool | None = None


def _clean_recipients(raw: list[str]) -> list[str]:
    cleaned: list[str] = []
    for item in raw:
        address = item.strip()
        if not address:
            continue
        if not digests.valid_email(address):
            raise HTTPException(status.HTTP_400_BAD_REQUEST, f"Invalid email address: {address}")
        cleaned.append(address.lower())
    return cleaned


def _validate_scope(db: Session, data: ScheduleCreate) -> None:
    """404 when the named scope does not exist in the database."""
    state_obj = queries.resolve_state(db, data.state) if data.state else None
    if data.state and state_obj is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"Unknown state: {data.state}")
    if data.district:
        district = queries.resolve_district(
            db,
            state_obj.id if state_obj else None,
            data.district,
        )
        if district is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, f"Unknown district: {data.district}")
    if data.village:
        village = queries.find_village(db, data.village, state=data.state, district=data.district)
        if village is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, f"Unknown village: {data.village}")


def _serialize_schedule(schedule: ReportSchedule) -> dict:
    latest = digests.latest_file(schedule.id)
    return {
        "id": schedule.id,
        "name": schedule.name,
        "state": schedule.state,
        "district": schedule.district,
        "village": schedule.village,
        "scope_label": digests.scope_label(schedule),
        "frequency": schedule.frequency,
        "recipients": list(schedule.recipients or []),
        "enabled": bool(schedule.enabled),
        "next_run_at": schedule.next_run_at.isoformat() if schedule.next_run_at else None,
        "last_run_at": schedule.last_run_at.isoformat() if schedule.last_run_at else None,
        "last_status": schedule.last_status,
        "last_error": schedule.last_error,
        "has_file": latest is not None,
    }


def _get_owned_schedule(
    schedule_id: int, db: Session, user: User
) -> ReportSchedule:
    schedule = db.get(ReportSchedule, schedule_id)
    if not schedule or (schedule.user_id != user.id and user.role != "admin"):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Schedule not found")
    return schedule


@router.get("/schedules")
def list_schedules(
    all: bool = Query(default=False, description="Admins: list every user's schedules"),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    stmt = select(ReportSchedule).order_by(ReportSchedule.created_at.desc())
    if not (all and user.role == "admin"):
        stmt = stmt.where(ReportSchedule.user_id == user.id)
    rows = list(db.scalars(stmt))
    return {"schedules": [_serialize_schedule(s) for s in rows], "count": len(rows)}


@router.post("/schedules", status_code=status.HTTP_201_CREATED)
def create_schedule(
    data: ScheduleCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    _validate_scope(db, data)
    recipients = _clean_recipients(data.recipients)
    schedule = ReportSchedule(
        user_id=user.id,
        name=data.name.strip(),
        state=data.state,
        district=data.district,
        village=data.village,
        frequency=data.frequency,
        recipients=recipients,
        enabled=data.enabled,
        # Due immediately so the first issue is generated on the next tick
        # (or right away via POST /{id}/run).
        next_run_at=datetime.now(timezone.utc),
    )
    db.add(schedule)
    db.commit()
    write_audit(db, user, "SCHEDULE_CREATE", resource="report_schedule", resource_id=schedule.id, details={"frequency": schedule.frequency})
    return _serialize_schedule(schedule)


@router.patch("/schedules/{schedule_id}")
def update_schedule(
    schedule_id: int,
    data: ScheduleUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    schedule = _get_owned_schedule(schedule_id, db, user)
    if data.name is not None:
        schedule.name = data.name.strip()
    if data.frequency is not None:
        schedule.frequency = data.frequency
    if data.recipients is not None:
        schedule.recipients = _clean_recipients(data.recipients)
    if data.enabled is not None:
        schedule.enabled = data.enabled
    db.commit()
    write_audit(db, user, "SCHEDULE_UPDATE", resource="report_schedule", resource_id=schedule.id)
    return _serialize_schedule(schedule)


@router.delete("/schedules/{schedule_id}", status_code=status.HTTP_200_OK)
def delete_schedule(
    schedule_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    schedule = _get_owned_schedule(schedule_id, db, user)
    for stale in digests._schedule_dir().glob(f"ingres-digest-{schedule.id}-*.pdf"):
        try:
            stale.unlink(missing_ok=True)
        except OSError:  # pragma: no cover - best-effort cleanup
            pass
    db.delete(schedule)
    db.commit()
    write_audit(db, user, "SCHEDULE_DELETE", resource="report_schedule", resource_id=schedule_id)
    return {"deleted": schedule_id}


@router.post("/schedules/{schedule_id}/run")
def run_schedule_now(
    schedule_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Generate an issue of this digest immediately."""
    schedule = _get_owned_schedule(schedule_id, db, user)
    result = digests.run_schedule(db, schedule)
    write_audit(
        db,
        user,
        "SCHEDULE_RUN",
        resource="report_schedule",
        resource_id=schedule.id,
        details={"status": result["status"], "emailed": result["emailed"]},
    )
    return result


@router.get("/schedules/{schedule_id}/download-latest")
def download_latest_digest(
    schedule_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    schedule = _get_owned_schedule(schedule_id, db, user)
    path = digests.latest_file(schedule.id)
    if path is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No generated report yet — run it first.")
    return StreamingResponse(
        io.BytesIO(path.read_bytes()),
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="{path.name}"'
        },
    )
