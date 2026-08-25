"""Live weather forecast endpoints (current + hourly + daily)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.database import get_db
from app.models.user import User
from app.services import weather

router = APIRouter(prefix="/weather", tags=["weather"])


@router.get("/forecast")
def forecast(
    state: str | None = Query(default=None),
    district: str | None = Query(default=None),
    village: str | None = Query(default=None),
    days: int = Query(default=7, ge=1, le=16),
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    """Live weather forecast for a groundwater scope.

    Resolves the state/district/village to coordinates from the local dataset
    and returns the current conditions plus a daily (up to 7 days) forecast.
    With ``IMD_API_KEY`` configured this uses official IMD data (city forecast +
    station observations); otherwise it falls back to Open-Meteo, which the
    response marks as non-official.
    """
    try:
        return weather.get_weather_forecast(
            db, state=state, district=district, village=village, days=days
        )
    except Exception as exc:  # noqa: BLE001 - surface a clean error to the client
        raise HTTPException(status_code=502, detail=f"Weather forecast unavailable: {exc}") from exc


@router.get("/map")
def weather_map(
    state: str | None = Query(default=None),
    district: str | None = Query(default=None),
    village: str | None = Query(default=None),
    max_points: int = Query(default=120, ge=4, le=500),
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    """Current temperature / precipitation / wind grid for a scope.

    Returns an evenly spaced grid of current conditions (Open-Meteo model
    forecast, labelled non-official) covering the scope's bounding box, so the
    map can paint an MSN-style weather heatmap with a colour-scale legend.
    """
    try:
        return weather.get_weather_map(
            db, state=state, district=district, village=village, max_points=max_points
        )
    except Exception as exc:  # noqa: BLE001 - surface a clean error to the client
        raise HTTPException(status_code=502, detail=f"Weather map unavailable: {exc}") from exc


@router.get("/map/series")
def weather_map_series(
    state: str | None = Query(default=None),
    district: str | None = Query(default=None),
    village: str | None = Query(default=None),
    max_points: int = Query(default=30, ge=4, le=80),
    hours: int = Query(default=24, ge=6, le=72),
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    """Hourly forecast time-series grid for a scope (animated map layers).

    Each grid point returns its current conditions plus ``hourly`` arrays
    (temperature, humidity, precipitation, cloud cover, wind) aligned to the
    shared ``times`` list. The frontend interpolates between consecutive hours
    so the cloud/rain/wind/temperature/humidity animations are driven by real
    model data rather than decorative randomness.

    When the weather provider is throttled/unreachable the endpoint still
    returns HTTP 200 with ``available: false`` (and any stale cached grid) so
    the map keeps working instead of failing hard.
    """
    try:
        data = weather.get_weather_map_series(
            db, state=state, district=district, village=village,
            max_points=max_points, hours=hours,
        )
        return {**data, "available": True}
    except Exception as exc:  # noqa: BLE001 - degrade gracefully
        stale = weather.load_last_series()
        base = stale or {
            "scope": village or district or state or "India",
            "bounds": {
                "min_lat": 6.5, "min_lon": 68.0, "max_lat": 37.5, "max_lon": 97.5,
            },
            "grid": [],
            "times": [],
            "time": None,
            "source": "Open-Meteo (GFS/ICON/IFS model forecast)",
            "official": False,
        }
        return {**base, "available": False, "detail": f"Weather time-series unavailable: {exc}"}


@router.get("/point")
def weather_point(
    lat: float = Query(...),
    lon: float = Query(...),
    days: int = Query(default=1, ge=1, le=7),
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    """Live weather for an arbitrary clicked map coordinate (Open-Meteo)."""
    try:
        payload = weather.fetch_openmeteo(lat, lon, days=days)
        return {
            "latitude": round(lat, 4),
            "longitude": round(lon, 4),
            "timezone": payload.get("timezone") or "auto",
            "current": weather._current(payload),
            "hourly": weather._hourly(payload),
            "daily": weather._daily(payload),
            "source": weather._OPENMETEO_SOURCE,
            "official": False,
        }
    except Exception as exc:  # noqa: BLE001 - surface a clean error to the client
        raise HTTPException(status_code=502, detail=f"Weather point unavailable: {exc}") from exc