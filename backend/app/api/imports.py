"""Dataset import endpoints (admin) and CSV template download."""

from __future__ import annotations

import io

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.api.deps import require_roles
from app.config import get_settings
from app.core.audit import write_audit
from app.database import get_db
from app.ingres.data_import import import_dataset, import_template_rows
from app.models.user import User
from app.services.alerts import check_alerts_for_import

router = APIRouter(prefix="/admin/datasets", tags=["admin", "import"])

_admin = Depends(require_roles("admin"))


@router.post("/import")
def upload_dataset(
    db: Session = Depends(get_db),
    admin_user: User = _admin,
    file: UploadFile = File(...),
    name: str | None = None,
    source: str | None = None,
    year: int | None = None,
):
    content = file.file.read()
    result = import_dataset(
        db=db,
        filename=file.filename or "upload",
        content=content,
        user_id=admin_user.id,
        name=name,
        source=source,
        year=year,
    )

    if result.errors:
        write_audit(
            db, admin_user, "DATASET_IMPORT_FAILED", "dataset", None,
            {"filename": file.filename, "errors": result.errors[:20], "rows_parsed": result.rows_parsed},
        )
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"errors": result.errors, "warnings": result.warnings},
        )

    alerts = []
    if get_settings().ALERT_CHECK_ON_IMPORT and result.dataset_id is not None:
        alerts = check_alerts_for_import(db, result.dataset_id)

    write_audit(
        db, admin_user, "DATASET_IMPORT", "dataset", result.dataset_id,
        {
            "filename": file.filename,
            "rows_imported": result.rows_imported,
            "states_created": result.states_created,
            "districts_created": result.districts_created,
            "units_created": result.units_created,
        },
    )

    return {
        "dataset_id": result.dataset_id,
        "rows_parsed": result.rows_parsed,
        "rows_imported": result.rows_imported,
        "states_created": result.states_created,
        "districts_created": result.districts_created,
        "units_created": result.units_created,
        "warnings": result.warnings,
        "alerts_triggered": alerts,
    }


@router.get("/import/template")
def download_template(
    _admin_user: User = _admin,
):
    """Download a CSV template matching the expected import columns."""
    rows = import_template_rows()
    header = list(rows[0].keys())
    buffer = io.StringIO()
    buffer.write(",".join(header) + "\n")
    for row in rows:
        buffer.write(",".join(str(row[h]) for h in header) + "\n")
    return StreamingResponse(
        io.BytesIO(buffer.getvalue().encode("utf-8")),
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="ingres-import-template.csv"'},
    )


@router.post("/import-real")
def import_real(
    db: Session = Depends(get_db),
    admin_user: User = _admin,
    states: list[str] | None = Query(default=None),
    refresh: bool = Query(default=False, description="Re-import states whose CSV files changed since the last import."),
    force: bool = Query(default=False, description="With refresh, re-import every selected state regardless of changes."),
):
    """Load (or refresh) the real CGWB/IMD station CSVs (``states/*.csv``).

    The CSVs are produced by the PDF-extraction pipeline and carry provenance
    (source files, pages, extraction method). Imported rows are labelled real
    (``is_demo=false``) and are served in preference to the synthetic demo set.
    A plain import is idempotent — re-running skips a dataset that already
    exists. With ``refresh=true`` changed files are detected by content hash
    and re-imported in place, keeping the live dataset current.
    """
    if refresh or force:
        from app.ingres.real_import import refresh_real_dataset

        result = refresh_real_dataset(db, states=states, force=force)
    else:
        from app.ingres.real_import import import_real_dataset

        result = import_real_dataset(db, states=states)
    if result.get("error"):
        write_audit(
            db, admin_user, "REAL_DATA_IMPORT_FAILED", "dataset", None,
            {"error": result["error"]},
        )
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"error": result["error"]},
        )

    write_audit(
        db, admin_user, "REAL_DATA_REFRESH" if (refresh or force) else "REAL_DATA_IMPORT", "dataset", result.get("dataset_id"),
        {
            "states": result.get("states", 0),
            "rows": result.get("rows", 0),
            "villages": result.get("villages", 0),
            "units": result.get("units", 0),
            "districts": result.get("districts", 0),
            "updated": result.get("updated", []),
            "unchanged": result.get("unchanged", []),
            "skipped": result.get("skipped", False),
        },
    )
    return result


@router.post("/sync-live")
def sync_live(
    db: Session = Depends(get_db),
    admin_user: User = _admin,
    states: list[str] | None = Query(default=None),
):
    """Fetch fresh government data from the live APIs and overlay it.

    Pulls the latest CGWB telemetry groundwater levels from the National Water
    Data Portal (open, no key) and, when an ``IMD_API_KEY`` is configured,
    current district rainfall from the IMD API. Live rows replace the previous
    live snapshot for the same dataset; the CSV/annual baseline is untouched.
    """
    from app.ingres.live import sync_live_data

    result = sync_live_data(db, states=states)
    write_audit(
        db, admin_user, "LIVE_DATA_SYNC", "dataset", result.get("dataset_id"),
        {
            "states": result.get("states", 0),
            "stations": result.get("stations", 0),
            "levels": result.get("levels", 0),
            "rainfall": result.get("rainfall", 0),
            "skipped": result.get("skipped", {}),
            "errors": result.get("errors", []),
            "skipped_sync": result.get("skipped", False),
        },
    )
    return result