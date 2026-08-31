"""Live weather forecast (current + hourly + daily) for a groundwater scope.

The forecast comes from official Indian sources first:

- **IMD** (India Meteorological Department, api.imd.gov.in) — the primary provider
  when ``IMD_API_KEY`` is configured. It uses the official ``cityforecastloc``
  (7-day city forecast with coordinates) and ``current_wx`` (station observations)
  endpoints. Requires free registration + IP whitelisting at api.imd.gov.in.
- **Open-Meteo** (free, key-less, model-based GFS/ICON/IFS) — automatic fallback
  when no IMD key is set or the IMD API is unreachable. This is **not** an official
  IMD product, and the response marks it as such.

The location for a state/district/village is resolved from the local dataset
(village coordinates, else the average of in-scope village coordinates) and the
nearest IMD station/city is selected by great-circle distance.

WMO weather codes are mapped to short English labels so the UI can render an
icon + readable condition. IMD's own ``01-99`` codes are a superset of the same
WW codes, so the same mapping applies.
"""

from __future__ import annotations

import json
import os
import ssl
import time
import urllib.error
import urllib.parse
import urllib.request
from functools import lru_cache
from math import asin, cos, radians, sin, sqrt
from datetime import date, timedelta

import openmeteo_requests
import pandas as pd
import requests_cache
from retry_requests import retry

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.ingres.queries import resolve_scope_ids
from app.models.groundwater import District, Village

_OPENMETEO_FORECAST = "https://api.open-meteo.com/v1/forecast"
_OPENMETEO_AIR_QUALITY = "https://air-quality-api.open-meteo.com/v1/air-quality"
_INDIA_CENTRE = (22.0, 80.0)
# Rough country bounds (min_lat, min_lon, max_lat, max_lon) used when no scope resolves.
_INDIA_BOUNDS = (6.5, 68.0, 37.5, 97.5)

_IMD_SOURCE = "India Meteorological Department (official IMD forecast & observations)"
_OPENMETEO_SOURCE = "Open-Meteo (GFS/ICON/IFS model forecast) · not official IMD data"

# WMO/IMD weather interpretation codes -> short English label.
WMO_CODES: dict[int, str] = {
    0: "Clear sky",
    1: "Mainly clear",
    2: "Partly cloudy",
    3: "Overcast",
    45: "Fog",
    48: "Depositing rime fog",
    51: "Light drizzle",
    53: "Moderate drizzle",
    55: "Dense drizzle",
    56: "Light freezing drizzle",
    57: "Dense freezing drizzle",
    61: "Slight rain",
    63: "Moderate rain",
    65: "Heavy rain",
    66: "Light freezing rain",
    67: "Heavy freezing rain",
    71: "Slight snow",
    73: "Moderate snow",
    75: "Heavy snow",
    77: "Snow grains",
    80: "Slight rain showers",
    81: "Moderate rain showers",
    82: "Violent rain showers",
    85: "Slight snow showers",
    86: "Heavy snow showers",
    95: "Thunderstorm",
    96: "Thunderstorm with slight hail",
    99: "Thunderstorm with heavy hail",
}


def weather_label(code: int | None) -> str | None:
    if code is None:
        return None
    return WMO_CODES.get(int(code), "Unknown")


def _get_json(url: str, timeout: int = 40, headers: dict[str, str] | None = None, verify: bool = True):
    ctx = None
    if not verify:
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
    req = urllib.request.Request(url, headers=headers or {})
    with urllib.request.urlopen(req, timeout=timeout, context=ctx) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _imd_headers() -> dict[str, str]:
    """Auth headers for the IMD API (X-Api-Key, the portal's documented mechanism)."""
    key = (get_settings().IMD_API_KEY or "").strip()
    return {"X-Api-Key": key} if key else {}


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371.0
    p1, p2 = radians(lat1), radians(lat2)
    dp = radians(lat2 - lat1)
    dl = radians(lon2 - lon1)
    a = sin(dp / 2) ** 2 + cos(p1) * cos(p2) * sin(dl / 2) ** 2
    return 2 * r * asin(sqrt(a))


# --------------------------------------------------------------------------
# IMD (official) fetching
# --------------------------------------------------------------------------

def _imd_get_json(path: str, timeout: int = 60):
    base = get_settings().IMD_API_BASE_URL.rstrip("/")
    url = f"{base}/{path}"
    # The IMD API currently serves a broken/self-signed certificate chain.
    return _get_json(url, timeout=timeout, headers=_imd_headers(), verify=False)


def _records(payload) -> list[dict]:
    if isinstance(payload, dict):
        for key in ("data", "result", "records"):
            if isinstance(payload.get(key), list):
                return payload[key]
        return []
    return payload if isinstance(payload, list) else []


def _to_float(value) -> float | None:
    try:
        if value is None or str(value).strip() == "":
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _field(rec: dict, *keys: str):
    """First present value among several candidate keys (IMD mixes _ and space spellings)."""
    for key in keys:
        value = rec.get(key)
        if value is not None and str(value).strip() != "":
            return value
    return None


def fetch_imd_city_forecast(lat: float, lon: float) -> dict | None:
    """7-day IMD city forecast, choosing the city nearest to (lat, lon).

    ``cityforecastloc`` returns every city with its forecast when called without
    an id; each record carries Latitude/Longitude so the nearest one is selected.
    """
    payload = _imd_get_json("cityforecastloc")
    best: dict | None = None
    best_d = None
    for rec in _records(payload):
        rlat = _to_float(_field(rec, "Latitude", "latitude"))
        rlon = _to_float(_field(rec, "Longitude", "longitude"))
        if rlat is None or rlon is None:
            continue
        d = _haversine_km(lat, lon, rlat, rlon)
        if best_d is None or d < best_d:
            best, best_d = rec, d
    return best


def fetch_imd_current_wx(lat: float, lon: float) -> dict | None:
    """Current IMD station observations nearest to (lat, lon), when available.

    Some responses include station coordinates; without them the current block
    degrades gracefully (temperature etc. stays null and the daily forecast is
    still returned).
    """
    payload = _imd_get_json("current_wx")
    best: dict | None = None
    best_d = None
    for rec in _records(payload):
        rlat = _to_float(_field(rec, "Latitude", "latitude"))
        rlon = _to_float(_field(rec, "Longitude", "longitude"))
        if rlat is None or rlon is None:
            continue
        d = _haversine_km(lat, lon, rlat, rlon)
        if best_d is None or d < best_d:
            best, best_d = rec, d
    return best


def _code_from_text(text: str | None) -> int | None:
    """Guess a WMO-ish code from IMD's free-text forecast so the UI gets an icon."""
    if not text:
        return None
    t = text.lower()
    if "thunder" in t or "storm" in t:
        return 95
    if "snow" in t:
        return 73
    if "shower" in t:
        return 80
    if "rain" in t or "drizzle" in t:
        return 63
    if "fog" in t or "mist" in t or "haze" in t:
        return 45
    if "partly" in t or "intermittent" in t:
        return 2
    if "cloud" in t:
        return 3
    if "clear" in t or "sunny" in t:
        return 0
    return None


def _imd_daily(record: dict, days: int) -> list[dict]:
    """Turn an IMD city-forecast record into our daily shape (Day_1..Day_7)."""
    date_obs = record.get("Date")
    try:
        start = date.fromisoformat(str(date_obs)[:10])
    except (TypeError, ValueError):
        start = date.today()
    out: list[dict] = []
    for i in range(1, days + 1):
        if i == 1:
            max_field, min_field, label_field = "Today_Max_temp", "Today_Min_temp", "Todays_Forecast"
        else:
            max_field, min_field, label_field = f"Day_{i}_Max_Temp", f"Day_{i}_Min_temp", f"Day_{i}_Forecast"
        text = record.get(label_field)
        out.append(
            {
                "date": (start + timedelta(days=i - 1)).isoformat(),
                "weather_code": _code_from_text(text),
                "weather_label": (text or "").strip() or weather_label(_code_from_text(text)),
                "temperature_2m_max": _to_float(record.get(max_field)),
                "temperature_2m_min": _to_float(record.get(min_field)),
                "apparent_temperature_max": None,
                "apparent_temperature_min": None,
                "precipitation_probability_max": None,
                "precipitation_sum": _to_float(record.get("Past_24_hrs_Rainfall")) if i == 1 else None,
                "wind_speed_10m_max": None,
            }
        )
    return out


def _imd_current(record: dict, wx: dict | None) -> dict | None:
    """Current conditions from IMD: nearest station observation, else from the city record."""
    if wx:
        code_raw = _field(wx, "Weather_Code", "Weather Code")
        code = _to_float(code_raw) if code_raw else None
        cur = {
            "time": f"{_field(wx, 'Date_of_Observation', 'Date of Observation', 'Date') or ''} "
            f"{_field(wx, 'Time_of_Observation', 'Time of Observation') or ''}".strip() or None,
            "temperature_2m": _to_float(wx.get("Temperature")),
            "apparent_temperature": None,
            "relative_humidity_2m": _to_float(wx.get("Humidity")),
            "is_day": None,
            "precipitation": _to_float(_field(wx, "Last_24_hrs_Rainfall", "Last 24 hrs Rainfall")),
            "weather_code": int(code) if code is not None else _code_from_text(record.get("Todays_Forecast")),
            "weather_label": None,
            "wind_speed_10m": _to_float(_field(wx, "Wind_Speed", "Wind Speed")),
            "pressure_msl": _to_float(wx.get("M.S.L.P")),
            "cloud_cover": None,
        }
        cur["weather_label"] = weather_label(cur["weather_code"]) or (record.get("Todays_Forecast") or "").strip() or None
        return cur

    text = record.get("Todays_Forecast")
    cur = {
        "time": record.get("Date"),
        "temperature_2m": None,
        "apparent_temperature": None,
        "relative_humidity_2m": None,
        "is_day": None,
        "precipitation": _to_float(record.get("Past_24_hrs_Rainfall")),
        "weather_code": _code_from_text(text),
        "weather_label": (text or "").strip() or weather_label(_code_from_text(text)),
        "wind_speed_10m": None,
        "pressure_msl": None,
        "cloud_cover": None,
    }
    return cur


def _forecast_from_imd(
    db: Session, lat: float, lon: float, scope: str,
    state: str | None, district: str | None, village: str | None, days: int,
) -> dict:
    record = fetch_imd_city_forecast(lat, lon)
    if not record:
        raise RuntimeError("no IMD city forecast returned")
    wx = fetch_imd_current_wx(lat, lon)
    return {
        "scope": scope,
        "state": state,
        "district": district,
        "village": village,
        "latitude": round(lat, 4),
        "longitude": round(lon, 4),
        "timezone": "Asia/Kolkata",
        "current": _imd_current(record, wx),
        "hourly": [],
        "daily": _imd_daily(record, days),
        "source": _IMD_SOURCE,
        "official": True,
    }


# --------------------------------------------------------------------------
# Open-Meteo (fallback) fetching
# --------------------------------------------------------------------------

_openmeteo_client: openmeteo_requests.Client | None = None


def _get_openmeteo_client() -> openmeteo_requests.Client:
    """Get or create the Open-Meteo client with caching and retry."""
    global _openmeteo_client
    if _openmeteo_client is None:
        cache_session = requests_cache.CachedSession(
            "openmeteo_cache", expire_after=3600, backend="memory"
        )
        retry_session = retry(cache_session, retries=5, backoff_factor=0.2)
        _openmeteo_client = openmeteo_requests.Client(session=retry_session)
    return _openmeteo_client


_VARIABLE_CODE_TO_NAME = {
    1: "apparent_temperature",
    3: "cloud_cover",
    19: "is_day",
    24: "precipitation",
    26: "precipitation_probability",
    27: "pressure_msl",
    29: "relative_humidity_2m",
    40: "sunrise",
    41: "sunset",
    47: "temperature_2m",
    56: "weather_code",
    57: "wind_direction_10m",
    59: "wind_speed_10m",
}


def _variable_code_to_name(code: int) -> str:
    return _VARIABLE_CODE_TO_NAME.get(code, f"unknown_{code}")


def _values_to_list(var) -> list:
    """Robustly convert an Open-Meteo variable to a Python list.

    The flatbuffer API returns ``ndarray`` for most variables but can return
    a plain ``int`` for timestamp-like fields (sunrise/sunset). This helper
    handles both without crashing (the live bug: ``'int' object has no
    attribute 'tolist'``).
    """
    try:
        vals = var.ValuesAsNumpy()
    except Exception:
        try:
            vals = var.Value()
            return [vals] if vals is not None else []
        except Exception:
            return []
    if hasattr(vals, "tolist"):
        try:
            return vals.tolist()
        except Exception:
            pass
    if isinstance(vals, (list, tuple)):
        return list(vals)
    if isinstance(vals, (int, float)):
        return [vals]
    try:
        return list(vals)  # type: ignore[arg-type]
    except Exception:
        return [vals] if vals is not None else []


def _response_to_dict(response) -> dict:
    """Convert Open-Meteo WeatherApiResponse to dict compatible with existing code."""
    result = {
        "latitude": response.Latitude(),
        "longitude": response.Longitude(),
        "generationtime_ms": response.GenerationTimeMilliseconds(),
        "utc_offset_seconds": response.UtcOffsetSeconds(),
        "timezone": response.Timezone().decode() if isinstance(response.Timezone(), bytes) else response.Timezone(),
        "timezone_abbreviation": response.TimezoneAbbreviation().decode() if isinstance(response.TimezoneAbbreviation(), bytes) else response.TimezoneAbbreviation(),
        "elevation": response.Elevation(),
    }

    current = response.Current()
    if current:
        result["current"] = {}
        for i in range(current.VariablesLength()):
            var = current.Variables(i)
            name = _variable_code_to_name(var.Variable())
            result["current"][name] = var.Value()

    hourly = response.Hourly()
    if hourly:
        result["hourly"] = {}
        # Keep ordered list to disambiguate duplicate codes (e.g., temperature_2m
        # appears once for hourly but daily has max/min sharing the same code).
        _hourly_ordered: list[tuple[str, list]] = []
        for i in range(hourly.VariablesLength()):
            var = hourly.Variables(i)
            name = _variable_code_to_name(var.Variable())
            vals = _values_to_list(var)
            # De-duplicate: hourly has unique codes, but handle gracefully
            if name in result["hourly"]:
                # preserve first, store duplicate with indexed suffix
                idx = 1
                while f"{name}__{idx}" in result["hourly"]:
                    idx += 1
                result["hourly"][f"{name}__{idx}"] = vals
            else:
                result["hourly"][name] = vals
            _hourly_ordered.append((name, vals))
        result["hourly"]["_ordered"] = _hourly_ordered  # for debugging / order-based fallback
        result["hourly"]["time"] = [
            pd.to_datetime(t, unit="s", utc=True).isoformat()
            for t in range(int(hourly.Time()), int(hourly.TimeEnd()), int(hourly.Interval()))
        ]

    daily = response.Daily()
    if daily:
        result["daily"] = {}
        _daily_ordered: list[tuple[str, list]] = []
        # Expected daily keys in the order requested by fetch_openmeteo.
        # Open-Meteo re-uses variable codes for max/min (e.g., 47 for both
        # temperature_2m_max and temperature_2m_min), so code-based mapping
        # would clobber. We keep the ordered list and remap by position.
        _EXPECTED_DAILY_KEYS = [
            "weather_code",
            "temperature_2m_max",
            "temperature_2m_min",
            "apparent_temperature_max",
            "apparent_temperature_min",
            "precipitation_sum",
            "precipitation_probability_max",
            "wind_speed_10m_max",
        ]
        for i in range(daily.VariablesLength()):
            var = daily.Variables(i)
            name = _variable_code_to_name(var.Variable())
            vals = _values_to_list(var)
            _daily_ordered.append((name, vals))
            # Also keep code-based entry for backwards-compat / debugging
            if name in result["daily"]:
                idx = 1
                while f"{name}__{idx}" in result["daily"]:
                    idx += 1
                result["daily"][f"{name}__{idx}"] = vals
            else:
                result["daily"][name] = vals
        # If ordered length matches expected, rebuild with correct max/min names
        # so _daily() finds temperature_2m_max etc. even when codes collide.
        if len(_daily_ordered) == len(_EXPECTED_DAILY_KEYS):
            for key, (_, vals) in zip(_EXPECTED_DAILY_KEYS, _daily_ordered):
                result["daily"][key] = vals
        elif len(_daily_ordered) >= 6:
            # Fallback: try to map by position for older payloads that included
            # sunrise/sunset (10 vars). Keep first 5, skip sunrise/sunset (40,41),
            # then map remaining.
            # Historical daily order with sunrise/sunset:
            # 0:weather_code, 1:temp_max, 2:temp_min, 3:apparent_max, 4:apparent_min,
            # 5:sunrise, 6:sunset, 7:precip_sum, 8:precip_prob_max, 9:wind_max
            if len(_daily_ordered) == 10 and _daily_ordered[5][0] == "sunrise":
                remapped = [
                    _daily_ordered[0], _daily_ordered[1], _daily_ordered[2],
                    _daily_ordered[3], _daily_ordered[4], _daily_ordered[7],
                    _daily_ordered[8], _daily_ordered[9],
                ]
                for key, (_, vals) in zip(_EXPECTED_DAILY_KEYS, remapped):
                    result["daily"][key] = vals
        result["daily"]["_ordered"] = _daily_ordered
        result["daily"]["time"] = [
            pd.to_datetime(t, unit="s", utc=True).date().isoformat()
            for t in range(int(daily.Time()), int(daily.TimeEnd()), int(daily.Interval()))
        ]

    return result


def fetch_openmeteo(lat: float, lon: float, days: int = 7) -> dict:
    """Call the Open-Meteo forecast API and return the raw JSON payload."""
    # Bump to v2 to bust old cache that had broken daily mapping / int sunrise bug
    sig = f"fcst2|{days}|{lat:.4f}/{lon:.4f}"
    disk = _disk_entry(sig)
    if disk and time.time() - disk.get("fetched_at", 0) < _SERIES_CACHE_TTL:
        return disk["payload"]

    client = _get_openmeteo_client()
    params = {
        "latitude": lat,
        "longitude": lon,
        "current": [
            "temperature_2m",
            "apparent_temperature",
            "relative_humidity_2m",
            "is_day",
            "precipitation",
            "weather_code",
            "wind_speed_10m",
            "pressure_msl",
            "cloud_cover",
        ],
        "hourly": [
            "temperature_2m",
            "apparent_temperature",
            "relative_humidity_2m",
            "precipitation_probability",
            "weather_code",
            "wind_speed_10m",
            "pressure_msl",
            "is_day",
        ],
        "daily": [
            "weather_code",
            "temperature_2m_max",
            "temperature_2m_min",
            "apparent_temperature_max",
            "apparent_temperature_min",
            "precipitation_sum",
            "precipitation_probability_max",
            "wind_speed_10m_max",
        ],
        "timezone": "auto",
        "forecast_days": days,
    }
    try:
        responses = client.weather_api(_OPENMETEO_FORECAST, params=params)
    except Exception as exc:
        if disk is not None:
            return disk["payload"]
        raise RuntimeError(f"Open-Meteo unavailable: {exc}") from exc

    payload = _response_to_dict(responses[0])
    _save_disk_cache(sig, {"fetched_at": time.time(), "payload": payload})
    return payload


def resolve_scope_location(
    db: Session, state: str | None, district: str | None, village: str | None
) -> tuple[float, float, str]:
    """Resolve a scope to (latitude, longitude, label) using local coordinates."""
    state_id, district_id, village_id, _ = resolve_scope_ids(db, state, district, village)
    scope = village or district or state or "India"

    if village_id:
        v = db.get(Village, village_id)
        if v and v.latitude is not None and v.longitude is not None:
            return v.latitude, v.longitude, scope

    stmt = select(func.avg(Village.latitude), func.avg(Village.longitude)).where(
        Village.latitude.isnot(None), Village.longitude.isnot(None)
    )
    if district_id:
        stmt = stmt.where(Village.district_id == district_id)
    elif state_id:
        stmt = stmt.join(District, Village.district_id == District.id).where(
            District.state_id == state_id
        )

    row = db.execute(stmt).one()
    lat, lon = row[0], row[1]
    if lat is None or lon is None:
        lat, lon = _INDIA_CENTRE
    return float(lat), float(lon), scope


def _current(payload: dict) -> dict | None:
    cur = payload.get("current")
    if not cur:
        return None
    code = cur.get("weather_code")
    return {
        "time": cur.get("time"),
        "temperature_2m": cur.get("temperature_2m"),
        "apparent_temperature": cur.get("apparent_temperature"),
        "relative_humidity_2m": cur.get("relative_humidity_2m"),
        "is_day": cur.get("is_day"),
        "precipitation": cur.get("precipitation"),
        "weather_code": code,
        "weather_label": weather_label(code),
        "wind_speed_10m": cur.get("wind_speed_10m"),
        "pressure_msl": cur.get("pressure_msl"),
        "cloud_cover": cur.get("cloud_cover"),
    }


def _hourly(payload: dict) -> list[dict]:
    h = payload.get("hourly") or {}
    times = h.get("time") or []
    out = []
    for i, t in enumerate(times):
        code = h.get("weather_code", [])[i] if i < len(h.get("weather_code") or []) else None
        out.append(
            {
                "time": t,
                "temperature_2m": h.get("temperature_2m", [])[i] if i < len(h.get("temperature_2m") or []) else None,
                "apparent_temperature": h.get("apparent_temperature", [])[i] if i < len(h.get("apparent_temperature") or []) else None,
                "relative_humidity_2m": h.get("relative_humidity_2m", [])[i] if i < len(h.get("relative_humidity_2m") or []) else None,
                "precipitation_probability": h.get("precipitation_probability", [])[i] if i < len(h.get("precipitation_probability") or []) else None,
                "weather_code": code,
                "weather_label": weather_label(code),
                "wind_speed_10m": h.get("wind_speed_10m", [])[i] if i < len(h.get("wind_speed_10m") or []) else None,
                "pressure_msl": h.get("pressure_msl", [])[i] if i < len(h.get("pressure_msl") or []) else None,
                "is_day": h.get("is_day", [])[i] if i < len(h.get("is_day") or []) else None,
            }
        )
    return out


def _daily(payload: dict) -> list[dict]:
    d = payload.get("daily") or {}
    times = d.get("time") or []
    out = []
    for i, t in enumerate(times):
        code = d.get("weather_code", [])[i] if i < len(d.get("weather_code") or []) else None
        out.append(
            {
                "date": t,
                "weather_code": code,
                "weather_label": weather_label(code),
                "temperature_2m_max": d.get("temperature_2m_max", [])[i] if i < len(d.get("temperature_2m_max") or []) else None,
                "temperature_2m_min": d.get("temperature_2m_min", [])[i] if i < len(d.get("temperature_2m_min") or []) else None,
                "apparent_temperature_max": d.get("apparent_temperature_max", [])[i] if i < len(d.get("apparent_temperature_max") or []) else None,
                "apparent_temperature_min": d.get("apparent_temperature_min", [])[i] if i < len(d.get("apparent_temperature_min") or []) else None,
                "precipitation_probability_max": d.get("precipitation_probability_max", [])[i] if i < len(d.get("precipitation_probability_max") or []) else None,
                "precipitation_sum": d.get("precipitation_sum", [])[i] if i < len(d.get("precipitation_sum") or []) else None,
                "wind_speed_10m_max": d.get("wind_speed_10m_max", [])[i] if i < len(d.get("wind_speed_10m_max") or []) else None,
            }
        )
    return out


def _forecast_from_openmeteo(
    db: Session, lat: float, lon: float, scope: str,
    state: str | None, district: str | None, village: str | None, days: int,
) -> dict:
    payload = fetch_openmeteo(lat, lon, days=days)
    return {
        "scope": scope,
        "state": state,
        "district": district,
        "village": village,
        "latitude": round(lat, 4),
        "longitude": round(lon, 4),
        "timezone": (payload.get("timezone") or "auto"),
        "current": _current(payload),
        "hourly": _hourly(payload),
        "daily": _daily(payload),
        "source": _OPENMETEO_SOURCE,
        "official": False,
    }


# --------------------------------------------------------------------------
# Weather map (temperature / precipitation heat grid)
# --------------------------------------------------------------------------

def resolve_scope_bounds(
    db: Session, state: str | None, district: str | None, village: str | None
) -> tuple[float, float, float, float]:
    """Bounding box (min_lat, min_lon, max_lat, max_lon) for a scope.

    A village gets a small padded box around its coordinates; a state/district
    uses the bounding box of its villages; no scope returns the country box.
    """
    state_id, district_id, village_id, _ = resolve_scope_ids(db, state, district, village)

    if not state_id and not district_id and not village_id:
        return _INDIA_BOUNDS

    if village_id:
        v = db.get(Village, village_id)
        if v and v.latitude is not None and v.longitude is not None:
            pad = 0.15
            return (
                v.latitude - pad,
                v.longitude - pad,
                v.latitude + pad,
                v.longitude + pad,
            )

    stmt = (
        select(
            func.min(Village.latitude),
            func.min(Village.longitude),
            func.max(Village.latitude),
            func.max(Village.longitude),
        )
        .join(District, Village.district_id == District.id)
        .where(Village.latitude.isnot(None), Village.longitude.isnot(None))
    )
    if district_id:
        stmt = stmt.where(Village.district_id == district_id)
    elif state_id:
        stmt = stmt.where(District.state_id == state_id)

    row = db.execute(stmt).one()
    min_lat, min_lon, max_lat, max_lon = row
    if min_lat is None or max_lat is None or min_lon is None or max_lon is None:
        return _INDIA_BOUNDS

    pad_lat = max((max_lat - min_lat) * 0.08, 0.05)
    pad_lon = max((max_lon - min_lon) * 0.08, 0.05)
    return (
        float(min_lat - pad_lat),
        float(min_lon - pad_lon),
        float(max_lat + pad_lat),
        float(max_lon + pad_lon),
    )


def _grid_points(
    bounds: tuple[float, float, float, float], max_points: int = 120
) -> list[tuple[float, float]]:
    """Evenly spaced lat/lon grid covering ``bounds``, keeping cells near-square."""
    min_lat, min_lon, max_lat, max_lon = bounds
    lat_span = max(max_lat - min_lat, 1e-6)
    lon_span = max(max_lon - min_lon, 1e-6)
    cols = max(2, min(40, round((max_points * lon_span / lat_span) ** 0.5)))
    rows = max(2, min(40, round(max_points / cols)))
    while cols * rows > max_points and cols > 2 and rows > 2:
        if cols >= rows:
            cols -= 1
        else:
            rows -= 1
    lats = [min_lat + lat_span * i / (rows - 1) for i in range(rows)]
    lons = [min_lon + lon_span * i / (cols - 1) for i in range(cols)]
    return [(la, lo) for la in lats for lo in lons]


def fetch_openmeteo_grid(points: list[tuple[float, float]]) -> list[dict]:
    """Fetch current conditions for many coordinates in a single API call.

    Open-Meteo accepts comma-separated latitudes/longitudes and returns one
    object per coordinate (same order as requested). Each coordinate counts
    against the provider's per-minute quota, so callers should keep ``points``
    small; results are cached in memory and on disk to survive throttling.
    """
    sig = f"cur|{len(points)}|{','.join(f'{la:.2f}/{lo:.2f}' for la, lo in points)}"
    cached = _grid_cache.get(sig)
    if cached and time.time() - cached[0] < _SERIES_CACHE_TTL:
        return cached[1]

    disk = _disk_entry(sig)
    if disk and time.time() - disk.get("fetched_at", 0) < _SERIES_CACHE_TTL:
        _grid_cache[sig] = (disk["fetched_at"], disk["payload"])
        return disk["payload"]

    client = _get_openmeteo_client()
    lats = [f"{la:.4f}" for la, _ in points]
    lons = [f"{lo:.4f}" for _, lo in points]
    params = {
        "latitude": lats,
        "longitude": lons,
        "current": [
            "temperature_2m",
            "relative_humidity_2m",
            "precipitation",
            "weather_code",
            "wind_speed_10m",
            "wind_direction_10m",
            "cloud_cover",
        ],
        "timezone": "auto",
        "forecast_days": 1,
    }
    try:
        responses = client.weather_api(_OPENMETEO_FORECAST, params=params)
    except Exception as exc:
        if disk is not None:
            return disk["payload"]
        raise RuntimeError(f"Open-Meteo unavailable: {exc}") from exc

    payload = [_response_to_dict(r) for r in responses]
    _grid_cache[sig] = (time.time(), payload)
    _save_disk_cache(sig, {"fetched_at": time.time(), "payload": payload})
    return payload


_SERIES_CACHE_TTL = 600  # seconds; Open-Meteo updates every ~15 min

_series_cache: dict[str, tuple[float, list[dict], list[str] | None]] = {}
_grid_cache: dict[str, tuple[float, list[dict]]] = {}


def _cache_file_path() -> str:
    return os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "weather_cache.json")


def _load_disk_cache() -> dict:
    try:
        with open(_cache_file_path(), "r", encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return {}


def _save_disk_cache(entry_key: str, entry: dict) -> None:
    try:
        data = _load_disk_cache()
        data[entry_key] = entry
        path = _cache_file_path()
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(data, fh)
    except OSError:
        pass  # disk cache is best-effort


def _disk_entry(entry_key: str) -> dict | None:
    data = _load_disk_cache()
    return data.get(entry_key)


def _fetch_with_retry(url: str, entry_key: str, kind: str, attempts: int = 3):
    """Fetch ``url`` with backoff; fall back to stale disk cache on 429/5xx.

    Returns the JSON payload. Raises ``RuntimeError`` only when no data is
    available at all (never cached and the provider is down/throttled).
    """
    last_err: Exception | None = None
    for i in range(attempts):
        try:
            return _get_json(url, timeout=40)
        except urllib.error.HTTPError as exc:
            last_err = exc
            if exc.code in (429, 502, 503, 504):
                stale = _disk_entry(entry_key)
                if stale is not None:
                    # Serve last-known-good data while the provider cools down.
                    if kind == "grid":
                        _grid_cache[entry_key] = (time.time(), stale["payload"])
                        return stale["payload"]
                    _series_cache[entry_key] = (time.time(), stale["payload"], stale.get("times"))
                    return stale["payload"]
                if exc.code == 429:
                    time.sleep(min(2 ** i * 2, 10))
            else:
                raise
        except Exception as exc:  # noqa: BLE001 - transient network errors
            last_err = exc
            time.sleep(min(2 ** i * 1.5, 8))
    raise RuntimeError(f"Open-Meteo unavailable: {last_err}")


def fetch_openmeteo_grid_series(
    points: list[tuple[float, float]], hours: int = 48
) -> tuple[list[dict], list[str] | None]:
    """Fetch an hourly forecast time-series for many coordinates in one call.

    Returns ``(per_point_records, times)`` where each record has an ``hourly``
    block with arrays aligned to ``times``. This is the real temporal data that
    drives the animated cloud/rain/wind/temperature/humidity layers. Results are
    cached (memory + disk, 10 min TTL) and stale copies are served if the
    provider throttles us, so a 429 can never break the map.
    """
    sig = f"aq|{hours}|{len(points)}|{','.join(f'{la:.2f}/{lo:.2f}' for la, lo in points)}"
    cached = _series_cache.get(sig)
    if cached and time.time() - cached[0] < _SERIES_CACHE_TTL:
        return cached[1], cached[2]

    disk = _disk_entry(sig)
    if disk and time.time() - disk.get("fetched_at", 0) < _SERIES_CACHE_TTL:
        _series_cache[sig] = (disk["fetched_at"], disk["payload"], disk.get("times"))
        return disk["payload"], disk.get("times")

    client = _get_openmeteo_client()
    lats = [f"{la:.4f}" for la, _ in points]
    lons = [f"{lo:.4f}" for _, lo in points]
    params = {
        "latitude": lats,
        "longitude": lons,
        "current": [
            "temperature_2m",
            "relative_humidity_2m",
            "precipitation",
            "weather_code",
            "wind_speed_10m",
            "wind_direction_10m",
            "cloud_cover",
        ],
        "hourly": [
            "temperature_2m",
            "apparent_temperature",
            "relative_humidity_2m",
            "precipitation",
            "cloud_cover",
            "wind_speed_10m",
            "wind_direction_10m",
            "weather_code",
        ],
        "timezone": "auto",
        "forecast_hours": hours,
    }
    try:
        responses = client.weather_api(_OPENMETEO_FORECAST, params=params)
    except Exception as exc:
        if disk is not None:
            return disk["payload"], disk.get("times")
        raise RuntimeError(f"Open-Meteo unavailable: {exc}") from exc

    if not responses:
        return [], None
    payload = [_response_to_dict(r) for r in responses]
    # Best-effort air-quality merge (separate CAMS API; optional — the map
    # works fine without it, so any failure here just omits AQI). Uses the
    # plain REST endpoint: the openmeteo SDK returns empty arrays here.
    try:
        aq_url = (
            f"{_OPENMETEO_AIR_QUALITY}?latitude={','.join(lats)}"
            f"&longitude={','.join(lons)}&hourly=us_aqi&timezone=auto&forecast_hours={hours}"
        )
        aq_payload = _get_json(aq_url, timeout=40)
        aq_records = aq_payload if isinstance(aq_payload, list) else [aq_payload]
        for rec, aq in zip(payload, aq_records):
            hourly = rec.setdefault("hourly", {})
            n = len(hourly.get("time") or [])
            aq_hourly = ((aq or {}).get("hourly") or {}).get("us_aqi") or []
            if aq_hourly:
                hourly["us_aqi"] = [
                    v if v is not None else None for v in aq_hourly[:n]
                ] + [None] * max(0, n - len(aq_hourly))
    except Exception:  # noqa: BLE001 - AQI is optional
        pass
    times = payload[0].get("hourly", {}).get("time")
    _series_cache[sig] = (time.time(), payload, times)
    _save_disk_cache(sig, {"fetched_at": time.time(), "payload": payload, "times": times})
    return payload, times


def load_last_series() -> dict | None:
    """Return the most recent successfully fetched series (any scope) from disk.

    Used to degrade gracefully when the live provider is throttled: the map can
    keep showing the last-known-good animated grid instead of blanking.
    """
    try:
        data = _load_disk_cache()
        best: dict | None = None
        best_at = -1.0
        for key, entry in data.items():
            if not key.startswith("series|") and "times" not in entry:
                continue
            at = entry.get("fetched_at", 0)
            if at > best_at:
                best_at = at
                best = entry
        if not best:
            return None
        payload = best.get("payload") or []
        times = best.get("times") or []
        grid = []
        observed_time = None
        for i, rec in enumerate(payload):
            if not isinstance(rec, dict):
                continue
            cur = rec.get("current") or {}
            observed_time = observed_time or cur.get("time")
            h = rec.get("hourly") or {}
            lat = rec.get("latitude") or (22.0 if i == 0 else 22.0)
            lon = rec.get("longitude") or (80.0 if i == 0 else 80.0)
            grid.append(
                {
                    "lat": round(lat, 4),
                    "lon": round(lon, 4),
                    "temperature_2m": cur.get("temperature_2m"),
                    "relative_humidity_2m": cur.get("relative_humidity_2m"),
                    "precipitation": cur.get("precipitation"),
                    "weather_code": cur.get("weather_code"),
                    "wind_speed_10m": cur.get("wind_speed_10m"),
                    "wind_direction_10m": cur.get("wind_direction_10m"),
                    "cloud_cover": cur.get("cloud_cover"),
                    "us_aqi": (h.get("us_aqi") or [None])[0],
                    "hourly": {
                        "temperature_2m": h.get("temperature_2m") or [],
                        "apparent_temperature": h.get("apparent_temperature") or [],
                        "relative_humidity_2m": h.get("relative_humidity_2m") or [],
                        "precipitation": h.get("precipitation") or [],
                        "cloud_cover": h.get("cloud_cover") or [],
                        "wind_speed_10m": h.get("wind_speed_10m") or [],
                        "wind_direction_10m": h.get("wind_direction_10m") or [],
                        "weather_code": h.get("weather_code") or [],
                        "us_aqi": h.get("us_aqi") or [],
                    },
                }
            )
        if not grid:
            return None
        return {
            "scope": "India (last cached)",
            "bounds": {
                "min_lat": round(min(g["lat"] for g in grid), 4),
                "min_lon": round(min(g["lon"] for g in grid), 4),
                "max_lat": round(max(g["lat"] for g in grid), 4),
                "max_lon": round(max(g["lon"] for g in grid), 4),
            },
            "grid": grid,
            "times": times,
            "time": observed_time,
            "source": "Open-Meteo (cached, may be stale)",
            "official": False,
        }
    except (OSError, ValueError, KeyError):
        return None


def get_weather_map_series(
    db: Session,
    state: str | None = None,
    district: str | None = None,
    village: str | None = None,
    max_points: int = 80,
    hours: int = 48,
) -> dict:
    """Hourly forecast time-series grid for a scope (animated map overlay).

    Each grid point carries ``current`` conditions plus ``hourly`` arrays aligned
    to the shared ``times`` list. The frontend interpolates between consecutive
    hours to animate clouds/rain/wind/temperature/humidity with real data.
    """
    bounds = resolve_scope_bounds(db, state, district, village)
    points = _grid_points(bounds, max_points=max_points)
    payload, times = fetch_openmeteo_grid_series(points, hours=hours)

    grid: list[dict] = []
    observed_time = None
    for i, (lat, lon) in enumerate(points):
        rec = payload[i] if i < len(payload) else {}
        cur = rec.get("current") or {}
        observed_time = observed_time or cur.get("time")
        h = rec.get("hourly") or {}
        cur_aqi = None
        aqi_series = h.get("us_aqi") or []
        if aqi_series:
            times_list = h.get("time") or []
            cur_time = cur.get("time")
            if cur_time and cur_time in times_list:
                idx = times_list.index(cur_time)
                cur_aqi = aqi_series[idx] if idx < len(aqi_series) else None
            elif aqi_series:
                cur_aqi = aqi_series[0]
        grid.append(
            {
                "lat": round(lat, 4),
                "lon": round(lon, 4),
                "temperature_2m": cur.get("temperature_2m"),
                "relative_humidity_2m": cur.get("relative_humidity_2m"),
                "precipitation": cur.get("precipitation"),
                "weather_code": cur.get("weather_code"),
                "wind_speed_10m": cur.get("wind_speed_10m"),
                "wind_direction_10m": cur.get("wind_direction_10m"),
                "cloud_cover": cur.get("cloud_cover"),
                "us_aqi": cur_aqi,
                "hourly": {
                    "temperature_2m": h.get("temperature_2m") or [],
                    "apparent_temperature": h.get("apparent_temperature") or [],
                    "relative_humidity_2m": h.get("relative_humidity_2m") or [],
                    "precipitation": h.get("precipitation") or [],
                    "cloud_cover": h.get("cloud_cover") or [],
                    "wind_speed_10m": h.get("wind_speed_10m") or [],
                    "wind_direction_10m": h.get("wind_direction_10m") or [],
                    "weather_code": h.get("weather_code") or [],
                    "us_aqi": aqi_series,
                },
            }
        )

    min_lat, min_lon, max_lat, max_lon = bounds
    return {
        "scope": village or district or state or "India",
        "bounds": {
            "min_lat": round(min_lat, 4),
            "min_lon": round(min_lon, 4),
            "max_lat": round(max_lat, 4),
            "max_lon": round(max_lon, 4),
        },
        "grid": grid,
        "times": times or [],
        "time": observed_time,
        "source": _OPENMETEO_SOURCE,
        "official": False,
    }


def get_weather_map(
    db: Session,
    state: str | None = None,
    district: str | None = None,
    village: str | None = None,
    max_points: int = 120,
) -> dict:
    """Current temperature/precipitation/wind grid for a scope (map overlay).

    Returns a ``grid`` of points within the scope bounding box with current
    conditions from Open-Meteo (model forecast, labelled non-official) so the
    frontend can paint an MSN-style weather heatmap.
    """
    bounds = resolve_scope_bounds(db, state, district, village)
    points = _grid_points(bounds, max_points=max_points)
    payload = fetch_openmeteo_grid(points)

    grid: list[dict] = []
    observed_time = None
    for i, (lat, lon) in enumerate(points):
        rec = payload[i] if i < len(payload) else {}
        cur = rec.get("current") or {}
        observed_time = observed_time or cur.get("time")
        grid.append(
            {
                "lat": round(lat, 4),
                "lon": round(lon, 4),
                "temperature_2m": cur.get("temperature_2m"),
                "relative_humidity_2m": cur.get("relative_humidity_2m"),
                "precipitation": cur.get("precipitation"),
                "weather_code": cur.get("weather_code"),
                "wind_speed_10m": cur.get("wind_speed_10m"),
                "wind_direction_10m": cur.get("wind_direction_10m"),
            }
        )

    min_lat, min_lon, max_lat, max_lon = bounds
    return {
        "scope": village or district or state or "India",
        "bounds": {
            "min_lat": round(min_lat, 4),
            "min_lon": round(min_lon, 4),
            "max_lat": round(max_lat, 4),
            "max_lon": round(max_lon, 4),
        },
        "grid": grid,
        "time": observed_time,
        "source": _OPENMETEO_SOURCE,
        "official": False,
    }


def get_weather_forecast(
    db: Session,
    state: str | None = None,
    district: str | None = None,
    village: str | None = None,
    days: int = 7,
) -> dict:
    """Weather forecast (current / daily) for a scope from official IMD data.

    Falls back to Open-Meteo (clearly labelled as non-official) when no
    ``IMD_API_KEY`` is configured or the IMD API is unreachable.
    """
    lat, lon, scope = resolve_scope_location(db, state, district, village)
    if (get_settings().IMD_API_KEY or "").strip():
        try:
            return _forecast_from_imd(db, lat, lon, scope, state, district, village, days)
        except Exception:  # noqa: BLE001 - degrade to the fallback provider
            pass
    return _forecast_from_openmeteo(db, lat, lon, scope, state, district, village, days)