"""Import of real (non-demo) CGWB / IMD station data from ``states/*.csv``.

The CSVs are produced by the PDF-extraction pipeline and contain one row per
observation station:

- Water level: ``groundwater_depth_m`` for ``observation_year``/month.
- GWRA assessment (block/mandal level): recharge, extractable resource,
  extraction and stage of extraction for ``gwra_year`` (2025), plus category.
- Rainfall: ``rainfall_mm`` (IMD gridded) for the observation month.
- Provenance: source file names, extraction method, page numbers and
  ``source_url`` per field.

Import mapping (units stay labelled real, ``is_demo=False``):

- ``State`` / ``District`` are reused (case-insensitive) so real and demo rows
  share the same admin boundaries.
- Each station becomes a real ``Village`` (``is_demo=False``) and an
  ``AssessmentUnit`` (``unit_type="station"``) with the station coordinates.
- GWRA values are converted from billion cubic metres (bcm) to the app's
  hm³ unit (1 bcm = 1000 hm³) and stored per station for ``gwra_year``.
- Water levels go into ``groundwater_levels`` and rainfall into
  ``groundwater_rainfall``.

The import is idempotent: it refuses to run twice (guarded by the dataset row)
and commits per state so a failed state does not roll back earlier ones.

``refresh_real_dataset`` extends this with change detection: each CSV is
fingerprinted (sha256) and only states whose file actually changed are
re-imported in place (their old real rows are replaced), so the live dataset
always reflects the latest ``states/*.csv`` files.
"""

from __future__ import annotations

import csv
import hashlib
from datetime import date
from decimal import Decimal
from pathlib import Path

from sqlalchemy import delete, insert, select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.ingres.data_import import CATEGORY_NORMALISATION
from app.ingres.query_cache import invalidate_analytics_cache
from app.models.groundwater import (
    AssessmentUnit,
    Dataset,
    DatasetFileState,
    District,
    GroundwaterAssessment,
    GroundwaterExtraction,
    GroundwaterLevel,
    GroundwaterRainfall,
    GroundwaterRecharge,
    State,
    Village,
)

REAL_DATASET_NAME = "CGWB & IMD Real Groundwater Data (2025)"
_BATCH = 20_000

_REQUIRED = {"state_name", "district_name", "village_name", "latitude", "longitude"}

# 1 bcm = 1,000,000,000 m³ = 1000 hm³
_BCM_TO_HM3 = 1000.0


def _normalise_category(value: str | None) -> str | None:
    if not value or value.strip() == "" or value.strip().lower() == "null":
        return None
    key = " ".join(str(value).strip().lower().split())
    return CATEGORY_NORMALISATION.get(key, key).lower()


def _num(value: str | None, scale: float | None = None) -> float | None:
    if not value or value.strip() == "" or value.strip().lower() == "null":
        return None
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    return round(parsed * scale, 3) if scale is not None else parsed


def _water_level_class(depth: float) -> str | None:
    if depth < 2:
        return "very shallow"
    if depth < 5:
        return "shallow"
    if depth < 10:
        return "moderate"
    if depth < 20:
        return "deep"
    return "very deep"


def _insert_many(db: Session, model, rows: list[dict]) -> None:
    """Bulk insert row dicts via executemany (respects bind-param limits)."""
    for start in range(0, len(rows), _BATCH):
        db.execute(insert(model), rows[start : start + _BATCH])


def _tune_for_bulk(db: Session) -> None:
    if db.bind.dialect.name != "sqlite":
        return
    from sqlalchemy import text

    db.execute(text("PRAGMA journal_mode=WAL"))
    db.execute(text("PRAGMA synchronous=OFF"))
    db.execute(text("PRAGMA cache_size=-64000"))
    db.execute(text("PRAGMA temp_store=MEMORY"))
    db.commit()


def _state_title(name: str) -> str:
    return " ".join(part.capitalize() for part in name.strip().split())


def _state_code(db: Session, name: str) -> str:
    """Reuse the known code when the state exists; otherwise derive one."""
    existing = db.scalar(select(State).where(State.name.ilike(name.strip())))
    if existing:
        return existing.code
    try:
        from app.ingres.india_data import state_info

        info = state_info(_state_title(name))
        if info:
            return info["code"]
    except ImportError:  # pragma: no cover - india_data is always present
        pass
    return "".join(ch for ch in _state_title(name).upper() if ch.isalnum())[:10] or "ST"


def _state_region(name: str) -> str | None:
    try:
        from app.ingres.india_data import state_info

        info = state_info(_state_title(name))
        if info:
            return info["region"]
    except ImportError:  # pragma: no cover
        pass
    return None


def _iter_state_rows(state_csv: Path):
    with open(state_csv, encoding="utf-8-sig", newline="") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            if not any((row.get(c) or "").strip() for c in _REQUIRED):
                continue
            yield row


def _file_fingerprint(path: Path) -> str:
    """Content hash of a state CSV, used to detect updates."""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _record_fingerprints(db: Session, dataset_id: int, fingerprints: dict[str, str]) -> None:
    """Store fingerprints for the given files (other files are preserved)."""
    for filename in fingerprints:
        db.execute(
            delete(DatasetFileState).where(
                DatasetFileState.dataset_id == dataset_id,
                DatasetFileState.filename == filename,
            )
        )
    rows = [
        {"dataset_id": dataset_id, "filename": name, "sha256": digest}
        for name, digest in fingerprints.items()
    ]
    if rows:
        _insert_many(db, DatasetFileState, rows)
    db.flush()


def _stored_fingerprints(db: Session, dataset_id: int) -> dict[str, str]:
    return {
        r.filename: r.sha256
        for r in db.scalars(select(DatasetFileState).where(DatasetFileState.dataset_id == dataset_id))
    }


def _delete_state_real_data(db: Session, state_id: int) -> None:
    """Remove all real (``is_demo=False``) rows for a state so it can be re-imported.

    Districts and the state row itself are kept (they are shared with demo
    data); only the real villages, units and measurement rows are replaced.
    """
    unit_ids = select(AssessmentUnit.id).where(
        AssessmentUnit.state_id == state_id, AssessmentUnit.is_demo.is_(False)
    )
    district_ids = select(District.id).where(District.state_id == state_id)

    for model in (
        GroundwaterAssessment,
        GroundwaterRecharge,
        GroundwaterExtraction,
        GroundwaterLevel,
        GroundwaterRainfall,
    ):
        db.execute(delete(model).where(model.assessment_unit_id.in_(unit_ids)))
    db.execute(
        delete(AssessmentUnit).where(
            AssessmentUnit.state_id == state_id, AssessmentUnit.is_demo.is_(False)
        )
    )
    db.execute(
        delete(Village).where(Village.district_id.in_(district_ids), Village.is_demo.is_(False))
    )
    db.flush()


def _reimport_state(db: Session, state_csv: Path, dataset_id: int) -> dict:
    """Replace the real data for one state from its (possibly updated) CSV."""
    rows = list(_iter_state_rows(state_csv))
    if not rows:
        return {"rows": 0, "villages": 0, "units": 0, "districts": 0}
    state = db.scalar(select(State).where(State.name.ilike(rows[0]["state_name"].strip())))
    if state is not None:
        _delete_state_real_data(db, state.id)
    return _import_state(db, state_csv, dataset_id)


def _import_state(db: Session, state_csv: Path, dataset_id: int) -> dict:
    """Import one state CSV. Returns counters for this state."""
    rows = list(_iter_state_rows(state_csv))
    if not rows:
        return {"rows": 0, "villages": 0, "units": 0}

    state_name = rows[0]["state_name"].strip()
    state = db.scalar(select(State).where(State.name.ilike(state_name)))
    if state is None:
        state = State(name=_state_title(state_name), code=_state_code(db, state_name), region=_state_region(state_name))
        db.add(state)
        db.flush()
    state_id = state.id
    code_prefix = state.code or "ST"

    stats = {"rows": len(rows), "villages": 0, "units": 0, "districts": 0}

    # Group rows by district so villages are created once per district.
    districts: dict[str, list[dict]] = {}
    for row in rows:
        districts.setdefault(row["district_name"].strip(), []).append(row)

    for district_name, d_rows in districts.items():
        district = db.scalar(
            select(District).where(District.state_id == state_id, District.name.ilike(district_name))
        )
        if district is None:
            district = District(state_id=state_id, name=_state_title(district_name))
            db.add(district)
            db.flush()
        district_id = district.id
        stats["districts"] += 1

        # Villages: one per (district, village_name), is_demo=False.
        villages: dict[str, int] = {}
        village_order: list[str] = []
        village_rows: list[dict] = []
        seen_villages: set[str] = set()
        for row in d_rows:
            vname = (row["village_name"] or "").strip()
            if not vname or vname in seen_villages:
                continue
            seen_villages.add(vname)
            village_order.append(vname)
            village_rows.append(
                {
                    "district_id": district_id,
                    "name": vname,
                    "code": f"{code_prefix}-{district_id}-{len(village_rows) + 1}",
                    "population": None,
                    "latitude": _num(row.get("latitude")),
                    "longitude": _num(row.get("longitude")),
                    "is_demo": False,
                }
            )
        if village_rows:
            _insert_many(db, Village, village_rows)
            db.flush()
            v_ids = db.scalars(
                select(Village.id)
                .where(Village.district_id == district_id, Village.is_demo.is_(False))
                .order_by(Village.id)
            ).all()
            villages = dict(zip(village_order, v_ids))
            stats["villages"] += len(village_rows)

        unit_rows: list[dict] = []
        for idx, row in enumerate(d_rows):
            vname = (row["village_name"] or "").strip()
            unit_rows.append(
                {
                    "state_id": state_id,
                    "district_id": district_id,
                    "village_id": villages.get(vname),
                    "name": (row.get("location_name") or vname or f"Station {idx + 1}").strip(),
                    "code": f"{code_prefix}-{district_id}-S{idx + 1}",
                    "unit_type": "station",
                    "latitude": _num(row.get("latitude")),
                    "longitude": _num(row.get("longitude")),
                    "is_demo": False,
                }
            )
        _insert_many(db, AssessmentUnit, unit_rows)
        db.flush()
        unit_ids = db.scalars(
            select(AssessmentUnit.id)
            .where(AssessmentUnit.district_id == district_id, AssessmentUnit.is_demo.is_(False))
            .order_by(AssessmentUnit.id)
        ).all()
        stats["units"] += len(unit_ids)

        assessments: list[dict] = []
        recharges: list[dict] = []
        extractions: list[dict] = []
        levels: list[dict] = []
        rainfall: list[dict] = []

        for unit_id, row in zip(unit_ids, d_rows):
            gwra_year = _num(row.get("gwra_year"))
            gwra_year = int(gwra_year) if gwra_year is not None else None

            recharge = _num(row.get("annual_groundwater_recharge_bcm"), _BCM_TO_HM3)
            extractable = _num(row.get("annual_extractable_groundwater_resource_bcm"), _BCM_TO_HM3)
            extraction = _num(row.get("annual_groundwater_extraction_bcm"), _BCM_TO_HM3)
            stage = _num(row.get("stage_of_groundwater_extraction_percent"))
            category = _normalise_category(row.get("gwra_category"))

            if gwra_year is not None and (recharge is not None or extraction is not None or stage is not None):
                assessments.append(
                    {
                        "assessment_unit_id": unit_id,
                        "dataset_id": dataset_id,
                        "assessment_year": gwra_year,
                        "recharge_total": Decimal(str(recharge)) if recharge is not None else None,
                        "extraction_total": Decimal(str(extraction)) if extraction is not None else None,
                        "annual_extractable_resource": Decimal(str(extractable)) if extractable is not None else None,
                        "stage_of_extraction": Decimal(str(stage)) if stage is not None else None,
                        "category": category,
                        "is_demo": False,
                    }
                )
                if recharge is not None:
                    recharges.append(
                        {
                            "assessment_unit_id": unit_id,
                            "dataset_id": dataset_id,
                            "year": gwra_year,
                            "recharge_type": "total",
                            "value": Decimal(str(recharge)),
                            "is_demo": False,
                        }
                    )
                if extraction is not None:
                    extractions.append(
                        {
                            "assessment_unit_id": unit_id,
                            "dataset_id": dataset_id,
                            "year": gwra_year,
                            "extraction_type": "total",
                            "value": Decimal(str(extraction)),
                            "is_demo": False,
                        }
                    )

            depth = _num(row.get("groundwater_depth_m"))
            obs_year = _num(row.get("observation_year"))
            obs_month = _num(row.get("observation_month"))
            if depth is not None and obs_year is not None:
                levels.append(
                    {
                        "assessment_unit_id": unit_id,
                        "dataset_id": dataset_id,
                        "measured_date": date(int(obs_year), int(obs_month or 1), 1),
                        "depth_bgl": Decimal(str(round(depth, 2))),
                        "water_level_class": _water_level_class(depth),
                        "is_demo": False,
                    }
                )

            rainfall_mm = _num(row.get("rainfall_mm"))
            if rainfall_mm is not None and obs_year is not None:
                rainfall.append(
                    {
                        "assessment_unit_id": unit_id,
                        "dataset_id": dataset_id,
                        "year": int(obs_year),
                        "month": int(obs_month or 1) if obs_month is not None else None,
                        "value_mm": Decimal(str(round(rainfall_mm, 2))),
                        "is_demo": False,
                    }
                )

        if assessments:
            _insert_many(db, GroundwaterAssessment, assessments)
        if recharges:
            _insert_many(db, GroundwaterRecharge, recharges)
        if extractions:
            _insert_many(db, GroundwaterExtraction, extractions)
        if levels:
            _insert_many(db, GroundwaterLevel, levels)
        if rainfall:
            _insert_many(db, GroundwaterRainfall, rainfall)

    db.commit()
    return stats


def import_real_dataset(
    db: Session,
    states_dir: Path | str | None = None,
    states: list[str] | None = None,
    dataset_name: str = REAL_DATASET_NAME,
) -> dict:
    """Import the real CGWB/IMD station CSVs into the database.

    Idempotent: returns ``{"skipped": True, "dataset_id": ...}`` when the
    dataset is already present. ``states`` optionally restricts to a subset of
    state file basenames.
    """
    existing = db.scalar(select(Dataset).where(Dataset.name == dataset_name))
    if existing:
        return {"skipped": True, "dataset_id": existing.id}

    dir_path = Path(states_dir) if states_dir is not None else get_settings().states_data_dir
    files = sorted(dir_path.glob("*.csv"))
    if not files:
        return {"skipped": False, "error": f"No state CSV files found in {dir_path}", "rows": 0}

    wanted = {s.strip().lower() for s in states} if states else None
    if wanted is not None:
        files = [f for f in files if f.stem.lower() in wanted]

    _tune_for_bulk(db)

    dataset = Dataset(
        name=dataset_name,
        description=(
            "Real groundwater observation data extracted from CGWB dynamic "
            "ground water resource assessments and monthly water-level bulletins, "
            "combined with IMD gridded rainfall. Station-level measurements with "
            "block/mandal-level GWRA assessment attributes."
        ),
        source="CGWB Dynamic Ground Water Resources Assessment & IMD Gridded Rainfall",
        source_url="https://cgwb.gov.in",
        publication_year=2025,
        version="1.0",
        geographic_level="station",
        unit="hm³",
        validation_status="validated",
        is_demo=False,
    )
    db.add(dataset)
    db.flush()
    dataset_id = dataset.id

    stats: dict = {"states": 0, "rows": 0, "villages": 0, "units": 0, "districts": 0}
    imported_files: list[Path] = []
    for f in files:
        try:
            state_stats = _import_state(db, f, dataset_id)
        except Exception as exc:  # noqa: BLE001 - keep going across states
            db.rollback()
            stats.setdefault("errors", []).append(f"{f.stem}: {exc}")
            continue
        imported_files.append(f)
        stats["states"] += 1
        stats["rows"] += state_stats.get("rows", 0)
        stats["villages"] += state_stats.get("villages", 0)
        stats["units"] += state_stats.get("units", 0)
        stats["districts"] += state_stats.get("districts", 0)
        print(f"  [{f.stem}] rows={state_stats.get('rows', 0)} units={state_stats.get('units', 0)}")

    _record_fingerprints(db, dataset_id, {f.name: _file_fingerprint(f) for f in imported_files})
    db.commit()
    invalidate_analytics_cache()
    stats["dataset_id"] = dataset_id
    stats["skipped"] = False
    return stats


def refresh_real_dataset(
    db: Session,
    states_dir: Path | str | None = None,
    states: list[str] | None = None,
    force: bool = False,
    dataset_name: str = REAL_DATASET_NAME,
) -> dict:
    """Import or refresh the real CGWB/IMD dataset from the state CSVs.

    On first run this behaves exactly like ``import_real_dataset``. Once the
    dataset exists, each CSV is fingerprinted (sha256) and only states whose
    file actually changed are re-imported in place (their old real rows are
    replaced), so queries always reflect the latest ``states/*.csv`` files.
    Pass ``force=True`` to re-import every selected state regardless of changes.
    """
    dir_path = Path(states_dir) if states_dir is not None else get_settings().states_data_dir
    files = sorted(dir_path.glob("*.csv"))
    if not files:
        return {"skipped": False, "error": f"No state CSV files found in {dir_path}", "rows": 0}

    wanted = {s.strip().lower() for s in states} if states else None
    if wanted is not None:
        files = [f for f in files if f.stem.lower() in wanted]
    if not files:
        return {"skipped": False, "error": "No matching state CSV files", "rows": 0}

    existing = db.scalar(select(Dataset).where(Dataset.name == dataset_name))
    if existing is None:
        result = import_real_dataset(db, states_dir=dir_path, states=states, dataset_name=dataset_name)
        recorded = set(_stored_fingerprints(db, dataset_id=result.get("dataset_id") or 0))
        result["updated"] = [f.stem for f in files if f.name in recorded]
        result["unchanged"] = []
        return result

    dataset_id = existing.id
    stored = _stored_fingerprints(db, dataset_id)
    _tune_for_bulk(db)

    stats: dict = {
        "states": 0, "rows": 0, "villages": 0, "units": 0, "districts": 0,
        "updated": [], "unchanged": [], "skipped": False, "dataset_id": dataset_id,
    }
    fingerprints: dict[str, str] = {}
    for f in files:
        digest = _file_fingerprint(f)
        if not force and stored.get(f.name) == digest:
            fingerprints[f.name] = digest
            stats["unchanged"].append(f.stem)
            continue
        try:
            state_stats = _reimport_state(db, f, dataset_id)
        except Exception as exc:  # noqa: BLE001 - keep going across states
            db.rollback()
            stats.setdefault("errors", []).append(f"{f.stem}: {exc}")
            continue
        fingerprints[f.name] = digest
        stats["states"] += 1
        stats["rows"] += state_stats.get("rows", 0)
        stats["villages"] += state_stats.get("villages", 0)
        stats["units"] += state_stats.get("units", 0)
        stats["districts"] += state_stats.get("districts", 0)
        stats["updated"].append(f.stem)
        print(f"  [updated {f.stem}] rows={state_stats.get('rows', 0)} units={state_stats.get('units', 0)}")

    _record_fingerprints(db, dataset_id, fingerprints)
    db.commit()
    invalidate_analytics_cache()
    return stats


def main() -> None:
    """CLI: ``python -m app.ingres.real_import [--refresh] [--force] [--states ...]``."""
    import argparse

    from app.database import SessionLocal

    parser = argparse.ArgumentParser(description="Import or refresh real CGWB/IMD state CSVs.")
    parser.add_argument("--states", nargs="*", default=None, help="Only these state file basenames.")
    parser.add_argument(
        "--refresh",
        action="store_true",
        help="Re-import only the states whose CSV files changed since the last import.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="With --refresh, re-import every selected state regardless of changes.",
    )
    args = parser.parse_args()

    db = SessionLocal()
    try:
        if args.refresh or args.force:
            result = refresh_real_dataset(db, states=args.states, force=args.force)
        else:
            result = import_real_dataset(db, states=args.states)
        print(result)
    finally:
        db.close()


if __name__ == "__main__":
    main()