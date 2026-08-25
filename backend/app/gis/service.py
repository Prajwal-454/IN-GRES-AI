"""GIS support: geometry and GeoJSON output for the groundwater maps.

With the national synthetic dataset the number of assessment units (villages)
is very large (~600k), so the service generates geometry from stored
lat/lon coordinates and aggregates to district-level features when a query
would otherwise return more than ``MAX_MAP_FEATURES`` polygons. The India
choropleth continues to aggregate by state. Both paths stay demo-labelled.
"""

from __future__ import annotations

import json
import math
from functools import lru_cache
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.gis.geo import district_polygon_for, district_placements, india_polygons, point_in_geometry
from app.ingres.demo_data import DEMO_STATES
from app.models.groundwater import (
    AssessmentUnit,
    District,
    GroundwaterAssessment,
    State,
    Village,
)

METRICS = ("stage", "recharge", "extraction", "resource")

_METRIC_COLUMN = {
    "stage": "stage_of_extraction",
    "recharge": "recharge_total",
    "extraction": "extraction_total",
    "resource": "annual_extractable_resource",
}

# Above this number of map features we aggregate to district level so the
# response stays small enough for a browser.
MAX_MAP_FEATURES = 8000

# Legacy centroids for the 2-state dev sample (kept for tests / fallback).
_UNIT_CENTROIDS: dict[str, tuple[float, float]] = {}
for _state_info in DEMO_STATES.values():
    for _district_name, (lat, lon, _profile) in _state_info["districts"].items():
        _UNIT_CENTROIDS[_district_name.lower()] = (lat, lon)


def _square_polygon(lat: float, lon: float, size: float = 0.7) -> list[list[float]]:
    h = size / 2
    return [
        [lon - h, lat - h],
        [lon + h, lat - h],
        [lon + h, lat + h],
        [lon - h, lat + h],
        [lon - h, lat - h],
    ]


def centroid_for(district_name: str) -> tuple[float, float] | None:
    return _UNIT_CENTROIDS.get(district_name.strip().lower())


def available_years(db: Session) -> list[int]:
    return _available_years_cached()


def latest_year(db: Session) -> int | None:
    years = _available_years_cached()
    return years[-1] if years else None


@lru_cache(maxsize=1)
def _available_years_cached() -> list[int]:
    db = SessionLocal()
    try:
        return list(
            db.scalars(
                select(GroundwaterAssessment.assessment_year)
                .distinct()
                .order_by(GroundwaterAssessment.assessment_year)
            )
        )
    finally:
        db.close()


def _category_for_stage(stage: float) -> str:
    if stage < 70:
        return "safe"
    if stage < 90:
        return "semi-critical"
    if stage <= 100:
        return "critical"
    return "over-exploited"


def _feature(
    unit_id: int,
    name: str,
    state: str,
    district: str,
    year: int,
    metric: str,
    metric_value: float | None,
    stage: float | None,
    category: str | None,
    is_demo: bool,
    lat: float,
    lon: float,
) -> dict:
    return {
        "type": "Feature",
        "properties": {
            "id": unit_id,
            "name": name,
            "state": state,
            "district": district,
            "year": year,
            "metric": metric,
            "metric_value": metric_value,
            "stage_of_extraction": stage,
            "category": category,
            "is_demo": is_demo,
            "latitude": lat,
            "longitude": lon,
        },
        "geometry": {
            "type": "Polygon",
            "coordinates": [_square_polygon(lat, lon)],
        },
    }


def _metric_value_of(assessment, metric: str) -> float | None:
    if assessment is None:
        return None
    raw = getattr(assessment, _METRIC_COLUMN[metric])
    return float(raw) if raw is not None else None


def _apply_geo_filters(stmt, db: Session, state: str | None, district: str | None, village: str | None):
    """Filter on AssessmentUnit FK columns (indexed) instead of name joins."""
    from app.ingres.queries import apply_dataset_filter, resolve_scope_ids

    state_id, district_id, village_id, empty = resolve_scope_ids(db, state, district, village)
    if empty:
        return stmt.where(AssessmentUnit.id.is_(None))
    if state_id is not None:
        stmt = stmt.where(AssessmentUnit.state_id == state_id)
    if district_id is not None:
        stmt = stmt.where(AssessmentUnit.district_id == district_id)
    if village_id is not None:
        stmt = stmt.where(AssessmentUnit.village_id == village_id)
    stmt = apply_dataset_filter(stmt, db, state_id, district_id, village_id)
    return stmt


def build_geojson(
    db: Session,
    state: str | None = None,
    district: str | None = None,
    village: str | None = None,
    year: int | None = None,
    metric: str = "stage",
) -> dict:
    """Build district/unit GeoJSON for a query, cached across requests.

    The underlying aggregation runs over millions of assessment rows, so the
    result is cached in-process keyed by the filter parameters (the synthetic
    dataset is static). ``db`` is kept in the signature for API compatibility.
    """
    return _build_geojson_cached(state, district, village, year, metric)


@lru_cache(maxsize=128)
def _build_geojson_cached(
    state: str | None,
    district: str | None,
    village: str | None,
    year: int | None,
    metric: str,
) -> dict:
    db = SessionLocal()
    try:
        return _build_geojson_uncached(db, state, district, village, year, metric)
    finally:
        db.close()


def _build_geojson_uncached(
    db: Session,
    state: str | None = None,
    district: str | None = None,
    village: str | None = None,
    year: int | None = None,
    metric: str = "stage",
) -> dict:
    if metric not in METRICS:
        metric = "stage"
    target_year = year or latest_year(db)

    unit_stmt = (
        select(func.count(AssessmentUnit.id))
        .join(State, AssessmentUnit.state_id == State.id)
        .outerjoin(District, AssessmentUnit.district_id == District.id)
        .outerjoin(Village, AssessmentUnit.village_id == Village.id)
    )
    unit_stmt = _apply_geo_filters(unit_stmt, db, state, district, village)
    unit_count = db.scalar(unit_stmt)
    unit_count = int(unit_count or 0)

    if unit_count > MAX_MAP_FEATURES:
        features = _district_level_features(
            db, state=state, district=district, village=village, year=target_year, metric=metric
        )
    else:
        features = _unit_level_features(
            db, state=state, district=district, village=village, year=target_year, metric=metric
        )

    return {
        "type": "FeatureCollection",
        "features": features,
        "meta": {
            "metric": metric,
            "year": target_year,
            "years": available_years(db),
            "states": sorted({s.name for s in db.scalars(select(State))}),
            "metrics": list(METRICS),
        },
    }


def _unit_level_features(
    db: Session,
    state: str | None,
    district: str | None,
    village: str | None,
    year: int,
    metric: str,
) -> list[dict]:
    """Per-assessment-unit features (used for small/sample datasets)."""
    stmt = (
        select(
            AssessmentUnit.id,
            AssessmentUnit.name,
            AssessmentUnit.latitude,
            AssessmentUnit.longitude,
            AssessmentUnit.is_demo,
            State.name.label("state_name"),
            District.name.label("district_name"),
            GroundwaterAssessment.stage_of_extraction,
            GroundwaterAssessment.recharge_total,
            GroundwaterAssessment.extraction_total,
            GroundwaterAssessment.annual_extractable_resource,
            GroundwaterAssessment.category,
            GroundwaterAssessment.is_demo.label("assessment_is_demo"),
        )
        .join(State, AssessmentUnit.state_id == State.id)
        .outerjoin(District, AssessmentUnit.district_id == District.id)
        .outerjoin(Village, AssessmentUnit.village_id == Village.id)
        .join(
            GroundwaterAssessment,
            (GroundwaterAssessment.assessment_unit_id == AssessmentUnit.id)
            & (GroundwaterAssessment.assessment_year == year),
        )
    )
    stmt = _apply_geo_filters(stmt, db, state, district, village)

    rows = list(db.execute(stmt))

    placed: dict[str, dict[str, tuple[float, float]]] = {}
    state_districts: dict[str, list[str]] = {}
    for row in rows:
        district_name = row.district_name or ""
        if district_name:
            state_districts.setdefault(row.state_name, []).append(district_name)
    for state_name, names in state_districts.items():
        for district_name, pt in district_placements(state_name, names).items():
            placed.setdefault(state_name, {})[district_name] = pt

    features = []
    for row in rows:
        district_name = row.district_name or ""
        lat = row.latitude
        lon = row.longitude
        geom = india_polygons().get(row.state_name)
        if lat is None or lon is None or (geom is not None and not point_in_geometry(lon, lat, geom)):
            pt = placed.get(row.state_name, {}).get(district_name)
            if pt:
                lat, lon = pt
            elif lat is None or lon is None:
                centroid = centroid_for(district_name)
                if not centroid:
                    continue
                lat, lon = centroid

        stage = float(row.stage_of_extraction) if row.stage_of_extraction is not None else None
        metric_value = None
        if stage is not None or row.recharge_total is not None:
            raw = getattr(row, _METRIC_COLUMN[metric])
            metric_value = float(raw) if raw is not None else None
        is_demo = bool(row.is_demo or row.assessment_is_demo)

        features.append(
            _feature(
                unit_id=row.id,
                name=row.name,
                state=row.state_name,
                district=district_name,
                year=year,
                metric=metric,
                metric_value=metric_value,
                stage=stage,
                category=row.category,
                is_demo=is_demo,
                lat=lat,
                lon=lon,
            )
        )
    return features


def _district_level_features(
    db: Session,
    state: str | None,
    district: str | None,
    village: str | None,
    year: int,
    metric: str,
) -> list[dict]:
    """Aggregated district-level features when there are too many units to map."""
    stmt = (
        select(
            District.id.label("district_id"),
            District.name.label("district_name"),
            State.name.label("state_name"),
            func.avg(AssessmentUnit.latitude).label("avg_lat"),
            func.avg(AssessmentUnit.longitude).label("avg_lon"),
            func.avg(GroundwaterAssessment.stage_of_extraction).label("avg_stage"),
            func.avg(func.coalesce(GroundwaterAssessment.recharge_total, 0)).label("avg_recharge"),
            func.avg(func.coalesce(GroundwaterAssessment.extraction_total, 0)).label("avg_extraction"),
            func.avg(func.coalesce(GroundwaterAssessment.annual_extractable_resource, 0)).label("avg_resource"),
            func.count(AssessmentUnit.id).label("unit_count"),
            func.max(func.coalesce(GroundwaterAssessment.is_demo, False)).label("any_demo"),
        )
        .join(State, AssessmentUnit.state_id == State.id)
        .outerjoin(District, AssessmentUnit.district_id == District.id)
        .outerjoin(Village, AssessmentUnit.village_id == Village.id)
        .join(
            GroundwaterAssessment,
            (GroundwaterAssessment.assessment_unit_id == AssessmentUnit.id)
            & (GroundwaterAssessment.assessment_year == year),
        )
        .group_by(District.id, District.name, State.name)
        .order_by(District.name)
    )
    stmt = _apply_geo_filters(stmt, db, state, district, village)

    column = {
        "stage": "avg_stage",
        "recharge": "avg_recharge",
        "extraction": "avg_extraction",
        "resource": "avg_resource",
    }[metric]

    rows = list(db.execute(stmt))

    placed: dict[str, dict[str, tuple[float, float]]] = {}
    state_districts: dict[str, list[str]] = {}
    for row in rows:
        if not row.district_id:
            continue
        state_districts.setdefault(row.state_name, []).append(row.district_name)
    for state_name, names in state_districts.items():
        for district_name, pt in district_placements(state_name, names).items():
            placed.setdefault(state_name, {})[district_name] = pt

    features = []
    for row in rows:
        if not row.district_id:
            continue
        pt = placed.get(row.state_name, {}).get(row.district_name)
        lat = pt[0] if pt else (float(row.avg_lat) if row.avg_lat is not None else 22.0)
        lon = pt[1] if pt else (float(row.avg_lon) if row.avg_lon is not None else 80.0)
        stage = float(row.avg_stage) if row.avg_stage is not None else None
        metric_value = float(row._mapping[column]) if row._mapping[column] is not None else None
        category = _category_for_stage(stage) if stage is not None else None

        features.append(
            _feature(
                unit_id=row.district_id,
                name=row.district_name,
                state=row.state_name,
                district=row.district_name,
                year=year,
                metric=metric,
                metric_value=metric_value,
                stage=stage,
                category=category,
                is_demo=bool(row.any_demo),
                lat=lat,
                lon=lon,
            )
        )
    return features


def unit_centroids(
    db: Session,
    state: str | None = None,
    district: str | None = None,
    village: str | None = None,
) -> list[dict]:
    unit_count = db.scalar(select(func.count(AssessmentUnit.id)))
    unit_count = int(unit_count or 0)

    if unit_count > MAX_MAP_FEATURES:
        stmt = (
            select(
                District.id.label("district_id"),
                District.name.label("district_name"),
                State.name.label("state_name"),
                func.avg(AssessmentUnit.latitude).label("lat"),
                func.avg(AssessmentUnit.longitude).label("lon"),
            )
            .join(State, AssessmentUnit.state_id == State.id)
            .outerjoin(District, AssessmentUnit.district_id == District.id)
            .outerjoin(Village, AssessmentUnit.village_id == Village.id)
            .group_by(District.id, District.name, State.name)
        )
        stmt = _apply_geo_filters(stmt, db, state, district, village)
        rows = list(db.execute(stmt))

        placed: dict[str, dict[str, tuple[float, float]]] = {}
        state_districts: dict[str, list[str]] = {}
        for row in rows:
            if row.district_id is None:
                continue
            state_districts.setdefault(row.state_name, []).append(row.district_name)
        for state_name, names in state_districts.items():
            for district_name, pt in district_placements(state_name, names).items():
                placed.setdefault(state_name, {})[district_name] = pt

        out = []
        for row in rows:
            if row.district_id is None:
                continue
            pt = placed.get(row.state_name, {}).get(row.district_name)
            lat = pt[0] if pt else (float(row.lat) if row.lat is not None else None)
            lon = pt[1] if pt else (float(row.lon) if row.lon is not None else None)
            if lat is None or lon is None:
                continue
            out.append(
                {
                    "id": row.district_id,
                    "name": row.district_name,
                    "state": row.state_name,
                    "district": row.district_name,
                    "latitude": lat,
                    "longitude": lon,
                }
            )
        return out

    stmt = (
        select(
            AssessmentUnit.id,
            AssessmentUnit.name,
            AssessmentUnit.latitude,
            AssessmentUnit.longitude,
            State.name.label("state_name"),
            District.name.label("district_name"),
        )
        .join(State, AssessmentUnit.state_id == State.id)
        .outerjoin(District, AssessmentUnit.district_id == District.id)
        .outerjoin(Village, AssessmentUnit.village_id == Village.id)
    )
    stmt = _apply_geo_filters(stmt, db, state, district, village)

    out = []
    for row in db.execute(stmt):
        lat = row.latitude
        lon = row.longitude
        if lat is None or lon is None:
            centroid = centroid_for(row.district_name or "")
            if not centroid:
                continue
            lat, lon = centroid
        out.append(
            {
                "id": row.id,
                "name": row.name,
                "state": row.state_name,
                "district": row.district_name,
                "latitude": lat,
                "longitude": lon,
            }
        )
    return out


def build_compare(
    db: Session,
    state: str | None = None,
    district: str | None = None,
    village: str | None = None,
    year_a: int | None = None,
    year_b: int | None = None,
    metric: str = "stage",
) -> dict:
    """Per-feature comparison between two years (change / delta).

    Reuses the cached year maps for both years and emits a FeatureCollection
    whose features carry ``metric_value_a``, ``metric_value_b``, ``delta`` and
    the categories in both years so the frontend can colour the change.
    """
    if metric not in METRICS:
        metric = "stage"
    years = available_years(db)
    if not years:
        return {"type": "FeatureCollection", "features": [], "meta": {}}
    ya = year_a or years[0]
    yb = year_b or years[-1]
    if ya > yb:
        ya, yb = yb, ya

    geo_a = _build_geojson_cached(state, district, village, ya, metric)
    geo_b = _build_geojson_cached(state, district, village, yb, metric)
    map_b = {f["properties"]["id"]: f for f in geo_b["features"]}

    features = []
    for fa in geo_a["features"]:
        pa = fa["properties"]
        pb = map_b.get(pa["id"], {}).get("properties") or {}
        va, vb = pa.get("metric_value"), pb.get("metric_value")
        delta = (vb - va) if (va is not None and vb is not None) else None
        cat_a, cat_b = pa.get("category"), pb.get("category")
        props = {
            **pa,
            "metric_value_a": va,
            "metric_value_b": vb,
            "delta": round(delta, 2) if delta is not None else None,
            "category_a": cat_a,
            "category_b": cat_b,
            "category_changed": bool(cat_a is not None and cat_b is not None and cat_a != cat_b),
            "metric_value": vb if vb is not None else va,
            "category": cat_b if cat_b is not None else cat_a,
            "stage_of_extraction": (
                pb.get("stage_of_extraction")
                if pb.get("stage_of_extraction") is not None
                else pa.get("stage_of_extraction")
            ),
            "year": yb,
        }
        features.append(
            {"type": "Feature", "properties": props, "geometry": fa["geometry"]}
        )

    return {
        "type": "FeatureCollection",
        "features": features,
        "meta": {
            "metric": metric,
            "year_a": ya,
            "year_b": yb,
            "years": years,
            "states": geo_a["meta"]["states"],
            "metrics": list(METRICS),
        },
    }


def build_india_compare(
    db: Session,
    year_a: int | None = None,
    year_b: int | None = None,
    metric: str = "stage",
) -> dict:
    """State-level comparison between two years for the All-India choropleth."""
    if metric not in METRICS:
        metric = "stage"
    years = available_years(db)
    if not years:
        return {"type": "FeatureCollection", "features": [], "meta": {}}
    ya = year_a or years[0]
    yb = year_b or years[-1]
    if ya > yb:
        ya, yb = yb, ya

    geo_a = _build_india_geojson_cached(ya, metric)
    geo_b = _build_india_geojson_cached(yb, metric)
    map_b = {f["properties"]["name"]: f for f in geo_b["features"]}

    features = []
    for fa in geo_a["features"]:
        pa = fa["properties"]
        pb = map_b.get(pa["name"], {}).get("properties") or {}
        va, vb = pa.get("metric_value"), pb.get("metric_value")
        delta = (vb - va) if (va is not None and vb is not None) else None
        cat_a, cat_b = pa.get("category"), pb.get("category")
        props = {
            **pa,
            "metric_value_a": va,
            "metric_value_b": vb,
            "delta": round(delta, 2) if delta is not None else None,
            "category_a": cat_a,
            "category_b": cat_b,
            "category_changed": bool(cat_a is not None and cat_b is not None and cat_a != cat_b),
            "metric_value": vb if vb is not None else va,
            "category": cat_b if cat_b is not None else cat_a,
            "stage_of_extraction": (
                pb.get("stage_of_extraction")
                if pb.get("stage_of_extraction") is not None
                else pa.get("stage_of_extraction")
            ),
            "year": yb,
        }
        features.append(
            {"type": "Feature", "properties": props, "geometry": fa["geometry"]}
        )

    return {
        "type": "FeatureCollection",
        "features": features,
        "meta": {
            "metric": metric,
            "year_a": ya,
            "year_b": yb,
            "years": years,
            "states": geo_a["meta"]["states"],
            "metrics": list(METRICS),
        },
    }


_INDIA_ASSET = Path(__file__).resolve().parent / "india_states.geojson"


@lru_cache(maxsize=1)
def _load_india_states() -> dict:
    with open(_INDIA_ASSET, encoding="utf-8") as fh:
        return json.load(fh)


def india_state_names() -> list[str]:
    return [f["properties"]["name"] for f in _load_india_states()["features"]]


def build_india_geojson(
    db: Session,
    year: int | None = None,
    metric: str = "stage",
) -> dict:
    """Full-India FeatureCollection of all states/UTs, cached across requests.

    Wraps the heavy state aggregation in an in-process cache keyed by
    (year, metric); the underlying national aggregate is otherwise recomputed
    from millions of assessment rows on every call.
    """
    return _build_india_geojson_cached(year, metric)


@lru_cache(maxsize=16)
def _build_india_geojson_cached(year: int | None, metric: str) -> dict:
    db = SessionLocal()
    try:
        return _build_india_geojson_uncached(db, year, metric)
    finally:
        db.close()


def _build_india_geojson_uncached(
    db: Session,
    year: int | None = None,
    metric: str = "stage",
) -> dict:
    """Full-India FeatureCollection of all states/UTs with per-state aggregates.

    States with no synthetic data keep their boundary but are flagged with
    ``has_data=false`` so the frontend can render them as "no data" regions.
    """
    units = build_geojson(db, year=year, metric=metric)
    target_year = units["meta"]["year"]

    agg: dict[str, dict] = {}
    for feat in units["features"]:
        p = feat["properties"]
        a = agg.setdefault(
            p["state"],
            {
                "count": 0,
                "metric_sum": 0.0,
                "metric_n": 0,
                "stage_sum": 0.0,
                "stage_n": 0,
                "categories": {},
                "any_demo": False,
            },
        )
        a["count"] += 1
        if p["metric_value"] is not None:
            a["metric_sum"] += p["metric_value"]
            a["metric_n"] += 1
        if p["stage_of_extraction"] is not None:
            a["stage_sum"] += p["stage_of_extraction"]
            a["stage_n"] += 1
        if p["category"]:
            a["categories"][p["category"]] = a["categories"].get(p["category"], 0) + 1
        if p["is_demo"]:
            a["any_demo"] = True

    features = []
    for feat in _load_india_states()["features"]:
        name = feat["properties"]["name"]
        a = agg.get(name)
        props: dict = {
            "name": name,
            "has_data": bool(a),
            "unit_count": a["count"] if a else 0,
            "metric_value": (
                round(a["metric_sum"] / a["metric_n"], 2) if a and a["metric_n"] else None
            ),
            "stage_of_extraction": (
                round(a["stage_sum"] / a["stage_n"], 2) if a and a["stage_n"] else None
            ),
            "category": (
                max(a["categories"], key=a["categories"].get) if a and a["categories"] else None
            ),
            "is_demo": bool(a and a["any_demo"]),
            "year": target_year,
            "metric": metric,
        }
        features.append(
            {
                "type": "Feature",
                "properties": props,
                "geometry": feat["geometry"],
            }
        )

    return {
        "type": "FeatureCollection",
        "features": features,
        "units": units,
        "meta": units["meta"],
    }


def water_level_from_stage(stage: float | None) -> float | None:
    """Derived depth-to-water (m) for demo display, from stage of extraction.

    The synthetic dataset stores no real water-level records, so a monotonic
    mapping stage(0-100%) -> depth(1.2-11.2 m) is used. Always demo-labelled.
    """
    if stage is None:
        return None
    return round(1.2 + (max(0.0, float(stage)) / 100) * 10.0, 1)


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def nearest_scope(db: Session, lat: float, lon: float) -> dict | None:
    """Nearest (state, district) to a click point, from the placed centroids.

    Clicks far outside India (beyond ``_CLICK_RANGE_KM``) resolve to None.
    """
    stations = unit_centroids(db)
    if not stations:
        return None
    best = min(
        stations,
        key=lambda s: _haversine_km(lat, lon, float(s["latitude"]), float(s["longitude"])),
    )
    dist = _haversine_km(lat, lon, float(best["latitude"]), float(best["longitude"]))
    if dist > _CLICK_RANGE_KM:
        return None
    return {
        "state": best["state"],
        "district": best["district"],
        "location": f"{best['district']}, {best['state']}",
    }


# Max distance (km) between a click and the nearest district centroid before we
# treat the click as outside the dataset.
_CLICK_RANGE_KM = 1500.0


def _linear_fit(xs: list[float], ys: list[float]) -> tuple[float, float]:
    n = len(xs)
    xm = sum(xs) / n
    ym = sum(ys) / n
    sxx = sum((x - xm) ** 2 for x in xs)
    sxy = sum((x - xm) * (y - ym) for x, y in zip(xs, ys))
    slope = sxy / sxx if sxx else 0.0
    return slope, ym - slope * xm


def _risk_for_category(category: str | None) -> str | None:
    return {
        "Safe": "Low",
        "Semi-critical": "Medium",
        "Critical": "High",
        "Over-exploited": "Critical",
    }.get(category)


def analyze_location(
    db: Session,
    lat: float,
    lon: float,
    year: int | None = None,
    target_year: int | None = None,
) -> dict:
    """AI-style analysis for a clicked map location.

    Resolves the nearest district, then computes status (stage/category), a
    derived water level and its trend, a risk label, a linear prediction to
    ``target_year`` and rule-based recommendations. All demo-labelled.
    """
    from app.ai.assistant import _category_label, _recommendations_for_stage
    from app.ingres import predict, queries

    scope = nearest_scope(db, lat, lon)
    if scope is None:
        return {"error": "no_data", "location": None, "is_demo": True}

    years = available_years(db)
    latest = year or (years[-1] if years else None)
    target = (target_year or (latest + 5 if latest else None))
    if latest is None or target is None or target <= latest:
        target = latest + 5 if latest else None

    summary = queries.get_summary(db, state=scope["state"], district=scope["district"])
    stage = summary["average_stage_of_extraction"]
    category = _category_label(stage) if stage else None

    stage_series = predict.get_scope_series(
        db, state=scope["state"], district=scope["district"], metric="stage"
    )
    depth = water_level_from_stage(stage)
    slope = None
    if len(stage_series) >= 2:
        slope, _intercept = _linear_fit(
            [float(p["year"]) for p in stage_series], [p["value"] for p in stage_series]
        )
    depth_trend = round(-slope * 0.1, 2) if slope is not None else None

    prediction = None
    if target is not None:
        horizon = max(1, min(int(target - latest), 10))
        fc = predict.forecast(
            db,
            state=scope["state"],
            district=scope["district"],
            metric="stage",
            horizon=horizon,
            method="auto",
        )
        if fc["forecast"]:
            pred_stage = fc["forecast"][-1]["value"]
            prediction = {
                "target_year": target,
                "value": water_level_from_stage(pred_stage),
                "unit": "m",
                "stage": round(pred_stage, 1),
                "category": fc.get("risk") or _category_label(pred_stage),
            }

    return {
        "location": scope["location"],
        "district": scope["district"],
        "state": scope["state"],
        "year": latest,
        "stage": round(stage, 1) if stage else None,
        "category": category,
        "water_level": {
            "value": depth,
            "unit": "m",
            "trend_per_year": depth_trend,
        },
        "risk": _risk_for_category(category),
        "prediction": prediction,
        "recommendation": _recommendations_for_stage(stage)[:4],
        "is_demo": True,
    }


def build_prediction_geojson(
    db: Session,
    state: str | None = None,
    district: str | None = None,
    village: str | None = None,
    year: int | None = None,
    target_year: int | None = None,
    metric: str = "stage",
) -> dict:
    """District-level forecast choropleth for the prediction layer.

    Runs a per-district linear fit over the yearly stage series and colours each
    district by its predicted category/stage at ``target_year``. Reuses the
    cached stage geometry so layer switches do not move the shapes.
    """
    return _build_prediction_geojson_cached(
        state, district, village, year, target_year, metric
    )


@lru_cache(maxsize=32)
def _build_prediction_geojson_cached(
    state: str | None,
    district: str | None,
    village: str | None,
    year: int | None,
    target_year: int | None,
    metric: str,
) -> dict:
    db = SessionLocal()
    try:
        return _build_prediction_geojson_uncached(
            db, state, district, village, year, target_year, metric
        )
    finally:
        db.close()


def _build_prediction_geojson_uncached(
    db: Session,
    state: str | None,
    district: str | None,
    village: str | None,
    year: int | None,
    target_year: int | None,
    metric: str,
) -> dict:
    base = _build_geojson_cached(state, district, village, year, "stage")
    years = available_years(db)
    base_year = base["meta"]["year"]
    target = target_year or base_year + 5
    if target <= base_year:
        target = base_year + 1

    stmt = (
        select(
            AssessmentUnit.district_id.label("district_id"),
            GroundwaterAssessment.assessment_year.label("year"),
            func.avg(GroundwaterAssessment.stage_of_extraction).label("stage"),
        )
        .join(AssessmentUnit, GroundwaterAssessment.assessment_unit_id == AssessmentUnit.id)
        .group_by(AssessmentUnit.district_id, GroundwaterAssessment.assessment_year)
    )
    stmt = _apply_geo_filters(stmt, db, state, district, village)

    series: dict[int, list[tuple[int, float]]] = {}
    for district_id, yr, stage in db.execute(stmt):
        if stage is None:
            continue
        series.setdefault(int(district_id), []).append((int(yr), float(stage)))

    forecasts: dict[int, float | None] = {}
    for did, pts in series.items():
        pts.sort()
        vals = [p[1] for p in pts]
        if len(pts) >= 2:
            xs = [float(i) for i in range(len(pts))]
            slope, intercept = _linear_fit(xs, vals)
            k = len(pts) - 1 + (target - pts[-1][0])
            forecasts[did] = intercept + slope * k
        else:
            forecasts[did] = vals[-1] if vals else None

    features = []
    for feat in base["features"]:
        pid = feat["properties"]["id"]
        value = forecasts.get(pid)
        predicted = round(value, 2) if value is not None else None
        props = {
            **feat["properties"],
            "year": target,
            "metric": "prediction",
            "metric_value": predicted,
            "stage_of_extraction": predicted,
            "category": _category_for_stage(predicted) if predicted is not None else None,
        }
        features.append({"type": "Feature", "properties": props, "geometry": feat["geometry"]})

    return {
        "type": "FeatureCollection",
        "features": features,
        "meta": {
            **base["meta"],
            "metric": "prediction",
            "year": target,
            "target_year": target,
            "base_year": base_year,
            "years": years,
        },
    }


def build_basin_geojson(
    db: Session,
    basin: str | None = None,
    year: int | None = None,
    metric: str = "stage",
) -> dict:
    """Basin-level choropleth aggregating district features by river basin.

    Districts belonging to a basin (see :mod:`app.ingres.basins`) are averaged
    into a single multi-polygon feature per basin, mirroring how the India view
    aggregates states from districts. Basins without any data in the database
    are omitted. The result is cached in-process, like the other layers.
    """
    return _build_basin_geojson_cached(basin, year, metric)


@lru_cache(maxsize=64)
def _build_basin_geojson_cached(
    basin: str | None,
    year: int | None,
    metric: str,
) -> dict:
    db = SessionLocal()
    try:
        return _build_basin_geojson_uncached(db, basin, year, metric)
    finally:
        db.close()


def _build_basin_geojson_uncached(
    db: Session,
    basin: str | None,
    year: int | None,
    metric: str,
) -> dict:
    from app.ingres import basins as basin_mod

    if metric not in METRICS:
        metric = "stage"
    target_year = year or latest_year(db)
    names = [basin] if basin else [b["name"] for b in basin_mod.list_basins(db)]

    features = []
    for name in names:
        district_ids = basin_mod.basin_district_ids(db, name)
        if not district_ids:
            continue

        rows = list(
            db.execute(
                select(
                    State.name.label("state_name"),
                    District.name.label("district_name"),
                    District.id.label("district_id"),
                    func.avg(GroundwaterAssessment.stage_of_extraction).label("avg_stage"),
                    func.avg(func.coalesce(GroundwaterAssessment.recharge_total, 0)).label("avg_recharge"),
                    func.avg(func.coalesce(GroundwaterAssessment.extraction_total, 0)).label("avg_extraction"),
                    func.avg(func.coalesce(GroundwaterAssessment.annual_extractable_resource, 0)).label("avg_resource"),
                    func.count(AssessmentUnit.id).label("unit_count"),
                    func.max(func.coalesce(GroundwaterAssessment.is_demo, False)).label("any_demo"),
                )
                .join(AssessmentUnit, AssessmentUnit.district_id == District.id)
                .join(State, AssessmentUnit.state_id == State.id)
                .join(
                    GroundwaterAssessment,
                    (GroundwaterAssessment.assessment_unit_id == AssessmentUnit.id)
                    & (GroundwaterAssessment.assessment_year == target_year),
                )
                .where(District.id.in_(district_ids))
                .group_by(State.name, District.name, District.id)
            )
        )
        if not rows:
            continue

        states = sorted({row.state_name for row in rows})
        geoms: list[list[list[list[float]]]] = []
        metric_vals: list[float] = []
        stage_vals: list[float] = []
        categories: dict[str, int] = {}
        unit_count = 0
        any_demo = False
        for row in rows:
            geom = district_polygon_for(row.state_name, row.district_name)
            if geom:
                if geom.get("type") == "Polygon":
                    geoms.append(geom["coordinates"])
                elif geom.get("type") == "MultiPolygon":
                    geoms.extend(geom["coordinates"])
            column = {
                "stage": "avg_stage",
                "recharge": "avg_recharge",
                "extraction": "avg_extraction",
                "resource": "avg_resource",
            }[metric]
            value = float(row._mapping[column]) if row._mapping[column] is not None else None
            if value is not None:
                metric_vals.append(value)
            stage = float(row.avg_stage) if row.avg_stage is not None else None
            if stage is not None:
                stage_vals.append(stage)
                cat = _category_for_stage(stage)
                categories[cat] = categories.get(cat, 0) + 1
            unit_count += int(row.unit_count or 0)
            any_demo = any_demo or bool(row.any_demo)

        if not geoms:
            geoms = [[_square_polygon(22.0, 80.0)]]

        stage_avg = sum(stage_vals) / len(stage_vals) if stage_vals else None
        metric_value = sum(metric_vals) / len(metric_vals) if metric_vals else None
        category = max(categories, key=lambda c: categories[c]) if categories else None

        features.append(
            {
                "type": "Feature",
                "properties": {
                    "id": len(features) + 1,
                    "name": name,
                    "state": "",
                    "district": "",
                    "basin": name,
                    "year": target_year,
                    "metric": metric,
                    "metric_value": round(metric_value, 2) if metric_value is not None else None,
                    "stage_of_extraction": round(stage_avg, 2) if stage_avg is not None else None,
                    "category": category,
                    "is_demo": any_demo,
                    "latitude": None,
                    "longitude": None,
                    "states": states,
                    "unit_count": unit_count,
                    "district_count": len(rows),
                },
                "geometry": {"type": "MultiPolygon", "coordinates": geoms},
            }
        )

    return {
        "type": "FeatureCollection",
        "features": features,
        "meta": {
            "metric": metric,
            "year": target_year,
            "years": available_years(db),
            "states": sorted({s.name for s in db.scalars(select(State))}),
            "metrics": list(METRICS),
        },
    }
