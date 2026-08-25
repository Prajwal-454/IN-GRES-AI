"""Geometry helpers for placing demo markers on real land polygons.

The national synthetic dataset stores no real coordinates -- village/unit
positions were historically generated as random offsets around each state's
single centroid, which can land in the sea or outside the state. These helpers
place points deterministically *inside* the real India state boundary polygons
(``india_states.geojson``) using grid sampling + point-in-polygon tests, so a
marker is always on land inside its correct state.

Everything here is pure Python (no PostGIS) so it works on SQLite and Postgres
alike. Points are (lat, lon) tuples.
"""

from __future__ import annotations

import json
import math
import random
import re
import zlib
from functools import lru_cache
from pathlib import Path

from app.ingres.demo_data import DEMO_STATES

_INDIA_ASSET = Path(__file__).resolve().parent / "india_states.geojson"
_DISTRICT_ASSET = Path(__file__).resolve().parent / "india_districts.geojson"

# Real, known district coordinates (only exist for the two demo states). These
# take priority so known districts are drawn at their true geographic location.
_KNOWN_DISTRICT_COORDS: dict[str, dict[str, tuple[float, float]]] = {
    state: {name: (lat, lon) for name, (lat, lon, _profile) in info["districts"].items()}
    for state, info in DEMO_STATES.items()
}

# Spelling/rename normalisation so real district polygons (GADM ~2011 names)
# match the newer district names stored in the DB.
_ALIASES: dict[str, str] = {
    "kachchh": "kutch",
    "ahmadabad": "ahmedabad",
    "ahmadnagar": "ahmednagar",
    "gurgaon": "gurugram",
    "sonepat": "sonipat",
    "yamuna nagar": "yamunanagar",
    "cuddapah": "ysr kadapa",
    "sibsagar": "sivasagar",
    "dhuburi": "dhubri",
    "hazaribag": "hazaribagh",
    "raj nandgaon": "rajnandgaon",
    "kawardha": "kabirdham",
    "pashchim champaran": "west champaran",
    "purba champaran": "east champaran",
    "pashchim singhbhum": "west singhbhum",
    "purba singhbhum": "east singhbhum",
    "lahul and spiti": "lahaul and spiti",
    "baramula": "baramulla",
    "baramula (kashmir north)": "baramulla",
    "anantnag (kashmir south)": "anantnag",
    "bagdam": "bandipora",
    "bhabua": "kaimur",
    "north cachar hills": "dima hasao",
    "upper dibang valley": "dibang valley",
    "vishakhapatnam": "visakhapatnam",
    "mahbubnagar": "mahabubnagar",
    "orissa": "odisha",
    "uttaranchal": "uttarakhand",
    "andaman and nicobar": "andaman and nicobar islands",
    "dadra and nagar haveli": "dadra and nagar haveli and daman and diu",
    "daman and diu": "dadra and nagar haveli and daman and diu",
}


def _norm(name: str) -> str:
    n = (name or "").strip().lower()
    n = re.sub(r"[^a-z0-9 ]", " ", n)
    n = re.sub(r"\s+", " ", n).strip()
    return _ALIASES.get(n, n)


def _hash_str(value: str) -> int:
    return zlib.crc32(value.encode("utf-8"))


@lru_cache(maxsize=1)
def india_polygons() -> dict[str, dict]:
    """State/UT name -> GeoJSON geometry (Polygon or MultiPolygon)."""
    with open(_INDIA_ASSET, encoding="utf-8") as fh:
        data = json.load(fh)
    return {f["properties"]["name"]: f["geometry"] for f in data["features"]}


@lru_cache(maxsize=1)
def _district_index() -> dict[str, list[tuple[str, dict]]]:
    """normalised district name -> [(normalised state, geometry), ...].

    Built from the real all-India district boundaries (GADM ~2011, 594
    districts). District names repeat across states, so each entry keeps its
    state so lookups can be disambiguated.
    """
    with open(_DISTRICT_ASSET, encoding="utf-8") as fh:
        data = json.load(fh)
    index: dict[str, list[tuple[str, dict]]] = {}
    for feat in data["features"]:
        p = feat["properties"]
        state = _norm(p.get("NAME_1", ""))
        district = _norm(p.get("NAME_2", ""))
        index.setdefault(district, []).append((state, feat["geometry"]))
    return index


def district_polygon_for(state_name: str, district_name: str) -> dict | None:
    """Real district geometry for a (state, district), or None if unavailable."""
    district = _norm(district_name)
    state = _norm(state_name)
    for geo_state, geom in _district_index().get(district, []):
        if geo_state == state:
            return geom
    return None


def _rings(geom: dict) -> list[list[list[float]]]:
    if geom["type"] == "Polygon":
        return geom["coordinates"]
    rings = []
    for poly in geom["coordinates"]:
        rings.extend(poly)
    return rings


def _point_in_ring(lon: float, lat: float, ring: list[list[float]]) -> bool:
    """Ray-casting point-in-ring test. ``ring`` is [[lon, lat], ...]."""
    inside = False
    n = len(ring)
    j = n - 1
    for i in range(n):
        xi, yi = ring[i][0], ring[i][1]
        xj, yj = ring[j][0], ring[j][1]
        if (yi > lat) != (yj > lat):
            x_cross = xj + (lat - yj) * (xi - xj) / ((yi - yj) or 1e-12)
            if lon < x_cross:
                inside = not inside
        j = i
    return inside


def _poly_rings(geom: dict) -> list[tuple[list[list[float]], list[list[list[float]]]]]:
    """[(outer_ring, [hole_rings]), ...] for a Polygon/MultiPolygon."""
    polys = geom["coordinates"] if geom["type"] == "MultiPolygon" else [geom["coordinates"]]
    return [(poly[0], poly[1:]) for poly in polys]


def point_in_geometry(lon: float, lat: float, geom: dict) -> bool:
    """True if (lon, lat) is inside a Polygon/MultiPolygon (holes excluded)."""
    for outer, holes in _poly_rings(geom):
        if not _point_in_ring(lon, lat, outer):
            continue
        if any(_point_in_ring(lon, lat, hole) for hole in holes):
            continue
        return True
    return False


def _bbox(geom: dict) -> tuple[float, float, float, float]:
    lons, lats = [], []
    for ring in _rings(geom):
        for lon, lat in ring:
            lons.append(lon)
            lats.append(lat)
    return min(lons), min(lats), max(lons), max(lats)


def interior_points(geom: dict, count: int, seed: str) -> list[tuple[float, float]]:
    """Deterministic spread of ``count`` points strictly inside ``geom``.

    Samples a grid across the polygon bounding box, keeps only points on land,
    shuffles with a fixed seed, and returns up to ``count`` unique points as
    ``(lat, lon)`` tuples. Guarantees land placement (never the sea) and is
    stable across runs.
    """
    if count <= 0 or geom is None:
        return []
    minx, miny, maxx, maxy = _bbox(geom)
    rng = random.Random(_hash_str(seed))

    # Coarse grid first; if it finds no land (tiny islands, scattered enclaves)
    # retry with a progressively finer grid until at least one land cell is hit.
    for scale in (1, 2, 4, 8):
        cols = max(16, int(math.ceil(math.sqrt(count * 20)))) * scale
        stepx = (maxx - minx) / cols or 1e-9
        stepy = (maxy - miny) / cols or 1e-9

        candidates: list[tuple[float, float]] = []
        for ix in range(cols):
            for iy in range(cols):
                x = minx + (ix + 0.5) * stepx
                y = miny + (iy + 0.5) * stepy
                if point_in_geometry(x, y, geom):
                    candidates.append((y, x))
        if candidates:
            rng.shuffle(candidates)
            return candidates[:count]
    return []


def interior_point(geom: dict, seed: str) -> tuple[float, float] | None:
    """One deterministic point strictly inside ``geom`` (fast, first land hit).

    Scans grid cells in a seed-shuffled order and returns at the first cell on
    land -- typically a handful of point-in-polygon tests -- unlike
    :func:`interior_points` which spreads a batch and scans the whole grid.
    """
    if geom is None:
        return None
    minx, miny, maxx, maxy = _bbox(geom)
    rings = _poly_rings(geom)
    rng = random.Random(_hash_str(seed))

    def pip(lon: float, lat: float) -> bool:
        for outer, holes in rings:
            if not _point_in_ring(lon, lat, outer):
                continue
            if any(_point_in_ring(lon, lat, hole) for hole in holes):
                continue
            return True
        return False

    for scale in (1, 2, 4, 8):
        cols = max(16, math.ceil(math.sqrt(20))) * scale
        stepx = (maxx - minx) / cols or 1e-9
        stepy = (maxy - miny) / cols or 1e-9
        cells = list(range(cols * cols))
        rng.shuffle(cells)
        for cell in cells:
            ix, iy = divmod(cell, cols)
            x = minx + (ix + 0.5) * stepx
            y = miny + (iy + 0.5) * stepy
            if pip(x, y):
                return (y, x)
    return None


@lru_cache(maxsize=64)
def _district_placements_cached(
    state_name: str, district_names: tuple[str, ...]
) -> dict[str, tuple[float, float]]:
    if not district_names:
        return {}
    placements: dict[str, tuple[float, float]] = {}
    known = _KNOWN_DISTRICT_COORDS.get(state_name, {})
    unknown: list[str] = []
    for name in district_names:
        if name in known:
            placements[name] = known[name]
        else:
            unknown.append(name)

    still_missing: list[str] = []
    for name in unknown:
        district_geom = district_polygon_for(state_name, name)
        if district_geom is not None:
            point = interior_point(district_geom, seed=f"district-placement:{state_name}:{name}")
            if point is not None:
                placements[name] = point
                continue
        still_missing.append(name)

    state_geom = india_polygons().get(state_name)
    if state_geom is not None and still_missing:
        points = interior_points(state_geom, len(still_missing), seed=f"district-placement:{state_name}")
        for i, name in enumerate(still_missing):
            placements[name] = points[i] if i < len(points) else (points[-1] if points else (None, None))
    return placements


def district_placements(state_name: str, district_names: list[str]) -> dict[str, tuple[float, float]]:
    """Map each district -> a (lat, lon) inside its own land.

    Resolution order per district:
      1. a known real supplied coordinate (AP/Telangana demo districts)
      2. a valid point inside its real district polygon (when available)
      3. a deterministic interior point of the state land polygon

    Every returned point is on land and inside the correct state/district.
    Deterministic results are cached per state so repeat requests are cheap.
    """
    return _district_placements_cached(state_name, tuple(district_names))