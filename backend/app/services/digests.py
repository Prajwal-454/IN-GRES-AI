"""Scheduled-report (digest) generation and delivery.

Turns a :class:`~app.models.schedule.ReportSchedule` into the standard
assessment PDF via ``app.reports.assessment``, stores it under
``DATA_DIR/scheduled_reports`` and — when SMTP is configured — emails it to
the schedule's recipients. The background loop in ``app.main`` calls
``process_due_schedules`` periodically; ``run_schedule`` is also exposed so
the API can generate an issue immediately.
"""

from __future__ import annotations

import logging
import re
import smtplib
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models.schedule import ReportSchedule

logger = logging.getLogger(__name__)

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

# Keep at most this many generated files per schedule.
FILES_TO_KEEP = 3


def valid_email(address: str) -> bool:
    return bool(EMAIL_RE.match(address.strip()))


def _schedule_dir() -> Path:
    directory = get_settings().data_dir / get_settings().SCHEDULED_REPORTS_DIR
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def _next_run_at(frequency: str, now: datetime) -> datetime:
    if frequency == "monthly":
        month = now.month % 12 + 1
        year = now.year + (1 if month == 1 else 0)
        try:
            return now.replace(year=year, month=month)
        except ValueError:  # e.g. Jan 31 -> Feb 31; clamp to end of month
            for day in (28, 27, 26):
                try:
                    return now.replace(year=year, month=month, day=day)
                except ValueError:
                    continue
    return now + timedelta(days=7)


def scope_label(schedule: ReportSchedule) -> str:
    parts = [p for p in (schedule.state, schedule.district, schedule.village) if p]
    return " · ".join(parts) if parts else "All India"


def build_digest_pdf(db: Session, schedule: ReportSchedule) -> bytes:
    from fastapi import HTTPException

    from app.reports import assessment

    try:
        report = assessment.build_assessment_report(
            db, state=schedule.state, district=schedule.district
        )
    except HTTPException as exc:  # empty scope -> no report possible
        raise ValueError(f"No assessment data available for {scope_label(schedule)}.") from exc
    return assessment.render_assessment_pdf(report)


def _store_pdf(schedule_id: int, pdf: bytes) -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    filename = f"ingres-digest-{schedule_id}-{stamp}.pdf"
    path = _schedule_dir() / filename
    path.write_bytes(pdf)

    # Prune older issues beyond the retention window.
    siblings = sorted(
        (p for p in _schedule_dir().glob(f"ingres-digest-{schedule_id}-*.pdf")),
        key=lambda p: p.name,
    )
    for stale in siblings[:-FILES_TO_KEEP]:
        try:
            stale.unlink(missing_ok=True)
        except OSError:  # pragma: no cover - best-effort cleanup
            logger.warning("could not prune old digest file %s", stale)
    return filename


def latest_file(schedule_id: int) -> Path | None:
    matches = sorted(_schedule_dir().glob(f"ingres-digest-{schedule_id}-*.pdf"))
    return matches[-1] if matches else None


def send_digest_email(schedule: ReportSchedule, pdf: bytes) -> bool:
    """Email the PDF to every recipient. Returns True when all sends succeeded."""
    settings = get_settings()
    if not settings.EMAIL_NOTIFICATIONS_ENABLED or not settings.SMTP_HOST:
        return False
    recipients = [r.strip() for r in (schedule.recipients or []) if r.strip()]
    if not recipients:
        return False
    period = "monthly" if schedule.frequency == "monthly" else "weekly"
    message = EmailMessage()
    message["Subject"] = f"[IN-GRES AI] {period.title()} groundwater digest — {scope_label(schedule)}"
    message["From"] = settings.SMTP_FROM
    message["To"] = ", ".join(recipients)
    message.set_content(
        f"Your {period} IN-GRES AI groundwater digest for {scope_label(schedule)} "
        f"is attached ({datetime.now(timezone.utc):%d %b %Y}).\n\n"
        "Figures come from the labelled dataset in use and are never official "
        "IN-GRES/CGWB data unless stated otherwise."
    )
    message.add_attachment(
        pdf,
        maintype="application",
        subtype="pdf",
        filename=f"ingres-digest-{period}-{datetime.now(timezone.utc):%Y-%m-%d}.pdf",
    )
    failures = 0
    try:
        with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=20) as server:
            if settings.SMTP_USE_TLS:
                server.starttls()
            if settings.SMTP_USERNAME:
                server.login(settings.SMTP_USERNAME, settings.SMTP_PASSWORD)
            server.send_message(message)
    except Exception as exc:  # noqa: BLE001 - delivery must never break scheduling
        logger.warning("digest email failed for schedule %s: %s", schedule.id, exc)
        failures += 1
    return failures == 0


def run_schedule(db: Session, schedule: ReportSchedule, now: datetime | None = None) -> dict:
    """Generate (and email) one issue of a schedule. Updates its run bookkeeping."""
    now = now or datetime.now(timezone.utc)
    status = "generated"
    error: str | None = None
    emailed = False
    filename: str | None = None
    try:
        pdf = build_digest_pdf(db, schedule)
        filename = _store_pdf(schedule.id, pdf)
        emailed = send_digest_email(schedule, pdf)
        if emailed:
            status = "sent"
    except Exception as exc:  # noqa: BLE001 - keep the loop alive per schedule
        status = "failed"
        error = str(exc)[:480]
        logger.exception("digest generation failed for schedule %s", schedule.id)

    schedule.last_run_at = now
    schedule.next_run_at = _next_run_at(schedule.frequency, now)
    schedule.last_status = status
    schedule.last_error = error
    schedule.last_file = filename
    db.commit()
    return {
        "id": schedule.id,
        "status": status,
        "emailed": emailed,
        "file": filename,
        "error": error,
        "next_run_at": schedule.next_run_at.isoformat() if schedule.next_run_at else None,
    }


def process_due_schedules(db: Session, now: datetime | None = None) -> list[dict]:
    """Generate every enabled, due schedule. Called by the scheduler loop."""
    now = now or datetime.now(timezone.utc)
    schedules = list(
        db.scalars(
            select(ReportSchedule).where(
                ReportSchedule.enabled.is_(True),
                (ReportSchedule.next_run_at.is_(None)) | (ReportSchedule.next_run_at <= now),
            )
        )
    )
    return [run_schedule(db, schedule, now) for schedule in schedules]
