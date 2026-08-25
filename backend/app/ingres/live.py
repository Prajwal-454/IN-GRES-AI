"""Live government data sync (CGWB telemetry via NWDP + IMD rainfall).

The National Water Data Portal (nwdp.nwic.gov.in) exposes the CGWB telemetry
groundwater-level dataset as an open CKAN datastore (no API key). IMD district
rainfall is served by ``api.imd.gov.in`` (free key + IP whitelisting); when no
key is configured that half is skipped.

Design
------
- The CSV-imported real dataset stays as the historical/annual baseline.
- ``sync_live_data`` overlays the freshest government readings on top:
  telemetry stations are matched to real ``AssessmentUnit`` rows (exact
  village name in the same district, else nearest station within
  ``LIVE_STATION_MATCH_RADIUS_KM``) and their latest depth is written as a
  ``GroundwaterLevel``; IMD district rainfall becomes ``GroundwaterRainfall``.
- Live rows belong to their own ``Dataset`` and are fully replaced on each
  sync, so re-running is idempotent.
"""

from __future__ import annotations

import json
import ssl
import threading
import urllib.parse
import urllib.request
from datetime import date, datetime
from decimal import Decimal
from math import asin, cos, radians, sin, sqrt

from sqlalchemy import delete, insert, select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.ingres.query_cache import invalidate_analytics_cache
from app.ingres.real_import import _insert_many, _water_level_class
from app.models.groundwater import (
    AssessmentUnit,
    Dataset,
    District,
    GroundwaterLevel,
    GroundwaterRainfall,
    State,
)

LIVE_DATASET_NAME = "CGWB Telemetry & IMD Rainfall (Live)"
_NWDP_PACKAGE = "ground-water-level-telemetry-daily-cgwb-as-assam"
_NWDP_BASE = "https://nwdp.nwic.gov.in/api/3/action"
# The (2026-2030) resources are the current/live period for every state
# (both "2026-2030" and "2026 - 2030" spellings appear in resource titles).
def _is_current_period(name: str) -> bool:
    return "2026" in name and "2030" in name
_MAX_READINGS = 100_000

_LIVE_LOCK = threading.Lock()


# --------------------------------------------------------------------------
# HTTP helpers
# --------------------------------------------------------------------------

def _get_json(url: str, timeout: int = 40, verify: bool = True, headers: dict[str, str] | None = None):
    ctx = None
    if not verify:
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
    req = urllib.request.Request(url, headers=headers or {})
    with urllib.request.urlopen(req, timeout=timeout, context=ctx) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _imd_ssl_context():
    # The IMD API currently serves a broken/self-signed certificate chain.
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    return ctx


# --------------------------------------------------------------------------
# NWDP (CGWB telemetry) fetching
# --------------------------------------------------------------------------

def _nwdp_state_key(name: str) -> str:
    return " ".join(str(name).strip().lower().split())


def fetch_nwdp_resources() -> list[dict]:
    """List the current-period telemetry resources (one per state) from the NWDP package.

    The state is taken from each telemetry record's ``State`` field (authoritative),
    not the resource title.
    """
    payload = _get_json(f"{_NWDP_BASE}/package_show?id={_NWDP_PACKAGE}")
    resources = payload.get("result", {}).get("resources", [])
    return [
        {"resource_id": r["id"], "name": r.get("name") or ""}
        for r in resources
        if _is_current_period(r.get("name") or "")
    ]


def fetch_nwdp_latest(resource_id: str) -> list[dict]:
    """Latest reading per telemetry station.

    The datastore is queried newest-first and de-duplicated by station name so
    one ``GroundwaterLevel`` is produced per station for the freshest time.
    """
    sort = urllib.parse.quote("Data Acquisition Time desc")
    seen: dict[str, dict] = {}
    offset = 0
    while offset < _MAX_READINGS:
        url = (
            f"{_NWDP_BASE}/datastore_search?resource_id={resource_id}"
            f"&sort={sort}&limit=1000&offset={offset}"
        )
        payload = _get_json(url)
        result = payload.get("result") or {}
        records = result.get("records") or []
        if not records:
            break
        for rec in records:
            station = (rec.get("Station") or "").strip()
            if not station or station in seen:
                continue
            seen[station] = rec
        # Stop once every station has a reading and we are well past the first
        # page (stations we have not seen are older than the newest data).
        if offset >= 5000:
            break
        offset += len(records)
        if len(records) < 1000:
            break
    return list(seen.values())


# --------------------------------------------------------------------------
# IMD rainfall fetching
# --------------------------------------------------------------------------

def fetch_imd_rainfall() -> list[dict] | None:
    """Latest monthly actual rainfall per district from the IMD API.

    Returns ``None`` when no ``IMD_API_KEY`` is configured (skipped).
    """
    settings = get_settings()
    if not settings.IMD_API_KEY:
        return None
    url = f"{settings.IMD_API_BASE_URL.rstrip('/')}/districtrainfall"
    payload = _get_json(
        url, timeout=60, verify=False, headers={"X-Api-Key": settings.IMD_API_KEY}
    )
    if not isinstance(payload, list):
        return []
    out = []
    for row in payload:
        district = (row.get("District") or "").strip()
        monthly = (row.get("Monthly Actual") or "").strip()
        monthly_date = (row.get("Monthly Date") or "").strip()
        if not district:
            continue
        out.append(
            {
                "state": (row.get("State") or "").strip(),
                "district": district,
                "monthly_date": monthly_date,
                "monthly_actual": monthly,
            }
        )
    return out


# --------------------------------------------------------------------------
# Matching telemetry stations to villages
# --------------------------------------------------------------------------

def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371.0
    p1, p2 = radians(lat1), radians(lat2)
    dp = radians(lat2 - lat1)
    dl = radians(lon2 - lon1)
    a = sin(dp / 2) ** 2 + cos(p1) * cos(p2) * sin(dl / 2) ** 2
    return 2 * r * asin(sqrt(a))


def _normalise(name: str) -> str:
    return "".join(ch for ch in name.lower() if ch.isalnum())


def _unit_index(db: Session, state_id: int) -> list[dict]:
    """In-memory index of real units for one state: (id, district, village, lat, lon)."""
    rows = db.execute(
        select(
            AssessmentUnit.id,
            District.name,
            AssessmentUnit.name,
            AssessmentUnit.latitude,
            AssessmentUnit.longitude,
        )
        .join(District, AssessmentUnit.district_id == District.id)
        .where(
            AssessmentUnit.state_id == state_id,
            AssessmentUnit.is_demo.is_(False),
            AssessmentUnit.latitude.isnot(None),
            AssessmentUnit.longitude.isnot(None),
        )
    ).all()
    return [
        {
            "id": r[0],
            "district": _normalise(r[1] or ""),
            "name": _normalise(r[2] or ""),
            "lat": float(r[3]),
            "lon": float(r[4]),
        }
        for r in rows
    ]


def match_unit(
    index: list[dict],
    district_name: str,
    station_name: str,
    lat: float,
    lon: float,
    radius_km: float,
) -> int | None:
    """Best real unit for a telemetry station: exact village/name in-district, else nearest within radius."""
    dist = _normalise(district_name)
    name = _normalise(station_name)
    in_district = [u for u in index if u["district"] == dist]
    pool = in_district or index

    for u in pool:
        if name and (u["name"] == name or name in u["name"] or u["name"] in name):
            return u["id"]

    best, best_d = None, None
    for u in pool:
        d = _haversine_km(lat, lon, u["lat"], u["lon"])
        if d <= radius_km and (best_d is None or d < best_d):
            best, best_d = u["id"], d
    return best


def _parse_measured_date(value: str) -> date | None:
    for fmt in ("%d-%m-%Y %H:%M", "%d-%m-%Y", "%Y-%m-%d", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(value.strip(), fmt).date()
        except (ValueError, TypeError):
            continue
    return None


def _as_float(value) -> float | None:
    if value is None:
        return None
    try:
        parsed = float(str(value).strip())
    except (TypeError, ValueError):
        return None
    return parsed


# --------------------------------------------------------------------------
# Sync orchestration
# --------------------------------------------------------------------------

def _live_dataset(db: Session) -> Dataset:
    existing = db.scalar(select(Dataset).where(Dataset.name == LIVE_DATASET_NAME))
    if existing:
        return existing
    dataset = Dataset(
        name=LIVE_DATASET_NAME,
        description=(
            "Live groundwater levels from the CGWB telemetry network (Digital "
            "Water Level Recorders) via the National Water Data Portal, plus "
            "current district rainfall from the IMD API. Overlaid on the "
            "annual CGWB/IMD CSV baseline."
        ),
        source="CGWB telemetry (NWDP) & IMD rainfall API",
        source_url="https://nwdp.nwic.gov.in",
        publication_year=date.today().year,
        version="live",
        geographic_level="station",
        unit="hm³",
        validation_status="validated",
        is_demo=False,
    )
    db.add(dataset)
    db.flush()
    return dataset


def _replace_live_rows(db: Session, dataset_id: int, state_ids: set[int] | None = None) -> None:
    """Drop the previous live rows so the sync can replace them.

    When ``state_ids`` is given (partial sync), only live rows whose unit
    belongs to one of those states are replaced, so other states' live
    readings are preserved.
    """
    unit_ids = None
    if state_ids:
        unit_ids = select(AssessmentUnit.id).where(
            AssessmentUnit.state_id.in_(state_ids),
            AssessmentUnit.is_demo.is_(False),
        )
    for model in (GroundwaterLevel, GroundwaterRainfall):
        stmt = delete(model).where(model.dataset_id == dataset_id)
        if unit_ids is not None:
            stmt = stmt.where(model.assessment_unit_id.in_(unit_ids))
        db.execute(stmt)
    db.flush()


def sync_live_data(db: Session, states: list[str] | None = None) -> dict:
    """Fetch fresh CGWB telemetry water levels (+ IMD rainfall) and overlay them.

    Replaces the previous live rows for the same dataset (idempotent). Any
    state/API failure is recorded in ``errors`` and does not abort the rest.
    """
    if not _LIVE_LOCK.acquire(blocking=False):
        return {"skipped": True, "reason": "live-data sync already running"}
    try:
        return _sync_live_data_locked(db, states)
    finally:
        _LIVE_LOCK.release()


def _sync_live_data_locked(db: Session, states: list[str] | None = None) -> dict:
    settings = get_settings()
    stats: dict = {
        "states": 0,
        "stations": 0,
        "levels": 0,
        "rainfall": 0,
        "skipped": {"imd": "no IMD_API_KEY configured"},
        "errors": [],
        "dataset_id": None,
    }

    wanted = {_nwdp_state_key(s) for s in states} if states else None

    try:
        dataset = _live_dataset(db)
        stats["dataset_id"] = dataset.id
        state_ids = None
        if wanted:
            state_ids = set()
            for key in wanted:
                sid = db.scalar(select(State.id).where(State.name.ilike(key)))
                if sid is not None:
                    state_ids.add(sid)
        _replace_live_rows(db, dataset.id, state_ids)
    except Exception as exc:  # noqa: BLE001
        stats["errors"].append(f"dataset-setup: {exc}")
        return stats

    try:
        resources = fetch_nwdp_resources()
    except Exception as exc:  # noqa: BLE001
        stats["errors"].append(f"nwdp-resources: {exc}")
        resources = []

    levels: list[dict] = []
    units_by_state: dict[int, list[dict]] = {}
    matched_states: set[str] = set()

    for resource in resources:
        try:
            readings = fetch_nwdp_latest(resource["resource_id"])
        except Exception as exc:  # noqa: BLE001
            stats["errors"].append(f"nwdp-{resource['name']}: {exc}")
            continue
        if not readings:
            continue

        by_state: dict[str, list[dict]] = {}
        for rec in readings:
            by_state.setdefault(_nwdp_state_key(rec.get("State") or ""), []).append(rec)

        for key, state_readings in by_state.items():
            if not key:
                continue
            if wanted is not None and key not in wanted:
                continue
            state = db.scalar(select(State).where(State.name.ilike(key)))
            if state is None:
                continue

            index = units_by_state.get(state.id)
            if index is None:
                index = _unit_index(db, state.id)
                units_by_state[state.id] = index

            matched = 0
            for rec in state_readings:
                depth = _as_float(rec.get("Groundwater Level Telemetry 6 Hourly (meter)"))
                lat = _as_float(rec.get("Latitude"))
                lon = _as_float(rec.get("Longitude"))
                measured = _parse_measured_date(str(rec.get("Data Acquisition Time") or ""))
                if depth is None or lat is None or lon is None or measured is None:
                    continue
                unit_id = match_unit(
                    index,
                    rec.get("District") or "",
                    (rec.get("Station") or "") + " " + (rec.get("Village") or ""),
                    lat,
                    lon,
                    settings.LIVE_STATION_MATCH_RADIUS_KM,
                )
                if unit_id is None:
                    continue
                depth_bgl = abs(depth) if depth < 0 else depth
                levels.append(
                    {
                        "assessment_unit_id": unit_id,
                        "dataset_id": dataset.id,
                        "measured_date": measured,
                        "depth_bgl": Decimal(str(round(depth_bgl, 2))),
                        "water_level_class": _water_level_class(depth_bgl),
                        "is_demo": False,
                    }
                )
                matched += 1

            if matched:
                matched_states.add(key)
                stats["states"] += 1
                stats["stations"] += len(state_readings)
                print(f"  [live {key}] stations={len(state_readings)} matched={matched}")
            stats.setdefault("levels_by_state", {})[key] = matched

    rainfall_rows: list[dict] = []
    imd = None
    try:
        imd = fetch_imd_rainfall()
    except Exception as exc:  # noqa: BLE001
        stats["errors"].append(f"imd: {exc}")
    if imd:
        stats["skipped"]["imd"] = False
        for row in imd:
            district = db.scalar(select(District).where(District.name.ilike(row["district"].strip())))
            if district is None:
                continue
            unit_ids = db.scalars(
                select(AssessmentUnit.id).where(
                    AssessmentUnit.district_id == district.id,
                    AssessmentUnit.is_demo.is_(False),
                )
            ).all()
            if not unit_ids:
                continue
            monthly = _as_float(row.get("monthly_actual"))
            ym = _parse_month(row.get("monthly_date") or "")
            if monthly is None or ym is None:
                continue
            for uid in unit_ids:
                rainfall_rows.append(
                    {
                        "assessment_unit_id": uid,
                        "dataset_id": dataset.id,
                        "year": ym[0],
                        "month": ym[1],
                        "value_mm": Decimal(str(round(monthly, 2))),
                        "is_demo": False,
                    }
                )
        stats["rainfall"] = len(rainfall_rows)

    if levels:
        _insert_many(db, GroundwaterLevel, levels)
    if rainfall_rows:
        _insert_many(db, GroundwaterRainfall, rainfall_rows)
    stats["levels"] = len(levels)

    db.commit()
    invalidate_analytics_cache()
    return stats


def _parse_month(value: str) -> tuple[int, int] | None:
    value = value.strip().lower()
    # "01-08-2026 To 31-08-2026" / "01-08-2026" / "2026-08"
    for fmt in ("%d-%m-%Y", "%Y-%m"):
        try:
            dt = datetime.strptime(value.split(" to ")[0], fmt)
            return dt.year, dt.month
        except ValueError:
            continue
    return None


def main() -> None:
    """CLI: ``python -m app.ingres.live [--states ...]``."""
    import argparse

    from app.database import SessionLocal

    parser = argparse.ArgumentParser(description="Sync live CGWB/IMD government data.")
    parser.add_argument("--states", nargs="*", default=None, help="Only these state names.")
    args = parser.parse_args()

    db = SessionLocal()
    try:
        result = sync_live_data(db, states=args.states)
        print(result)
    finally:
        db.close()


if __name__ == "__main__":
    main()