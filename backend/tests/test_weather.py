"""Tests for the live weather forecast service and API."""

from __future__ import annotations

import time
import urllib.error

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base
from app.models.groundwater import District, State, Village
from app.api import weather as api_weather
from app.services import weather as svc


@pytest.fixture()
def weather_db():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    TestingSession = sessionmaker(bind=engine, expire_on_commit=False)
    db = TestingSession()
    state = State(name="Test State", code="TS", region="South")
    db.add(state)
    db.flush()
    district = District(state_id=state.id, name="Test District")
    db.add(district)
    db.flush()
    db.add_all(
        [
            Village(district_id=district.id, name="Village A", latitude=17.0, longitude=79.0, is_demo=False),
            Village(district_id=district.id, name="Village B", latitude=17.1, longitude=79.1, is_demo=False),
        ]
    )
    db.commit()
    try:
        yield db
    finally:
        db.close()
        engine.dispose()


def test_weather_label_mapping():
    assert svc.weather_label(0) == "Clear sky"
    assert svc.weather_label(61) == "Slight rain"
    assert svc.weather_label(95) == "Thunderstorm"
    assert svc.weather_label(None) is None
    assert svc.weather_label(999) == "Unknown"


def test_resolve_scope_location_village(weather_db):
    lat, lon, scope = svc.resolve_scope_location(weather_db, "Test State", "Test District", "Village A")
    assert lat == 17.0
    assert lon == 79.0
    assert scope == "Village A"


def test_resolve_scope_location_district_averages(weather_db):
    lat, lon, scope = svc.resolve_scope_location(weather_db, "Test State", "Test District", None)
    assert scope == "Test District"
    assert abs(lat - 17.05) < 0.001
    assert abs(lon - 79.05) < 0.001


def test_resolve_scope_location_state_averages(weather_db):
    # Regression: state-level scope must join through District (Village has no state_id).
    lat, lon, scope = svc.resolve_scope_location(weather_db, "Test State", None, None)
    assert scope == "Test State"
    assert abs(lat - 17.05) < 0.001
    assert abs(lon - 79.05) < 0.001


def _canned_payload():
    return {
        "timezone": "Asia/Kolkata",
        "current": {
            "time": "2026-08-19T10:00",
            "temperature_2m": 31.2,
            "apparent_temperature": 33.0,
            "relative_humidity_2m": 62,
            "is_day": 1,
            "precipitation": 0.0,
            "weather_code": 2,
            "wind_speed_10m": 9.5,
            "pressure_msl": 1006.2,
            "cloud_cover": 40,
        },
        "hourly": {
            "time": ["2026-08-19T11:00", "2026-08-19T12:00"],
            "temperature_2m": [31.5, 32.0],
            "apparent_temperature": [33.2, 33.8],
            "relative_humidity_2m": [61, 60],
            "precipitation_probability": [20, 30],
            "weather_code": [2, 61],
            "wind_speed_10m": [9.0, 10.0],
            "pressure_msl": [1006.0, 1005.8],
            "is_day": [1, 1],
        },
        "daily": {
            "time": ["2026-08-19", "2026-08-20"],
            "weather_code": [2, 61],
            "temperature_2m_max": [33.0, 31.0],
            "temperature_2m_min": [25.0, 24.0],
            "apparent_temperature_max": [35.0, 33.0],
            "apparent_temperature_min": [27.0, 26.0],
            "precipitation_probability_max": [40, 80],
            "precipitation_sum": [0.0, 6.5],
            "wind_speed_10m_max": [15.0, 18.0],
        },
    }


def test_get_weather_forecast_normalizes(weather_db, monkeypatch):
    monkeypatch.setattr(svc, "fetch_openmeteo", lambda lat, lon, days=7: _canned_payload())
    result = svc.get_weather_forecast(weather_db, "Test State", "Test District", "Village A", days=2)

    assert result["scope"] == "Village A"
    assert result["latitude"] == 17.0
    assert result["current"]["temperature_2m"] == 31.2
    assert result["current"]["weather_label"] == "Partly cloudy"
    assert len(result["hourly"]) == 2
    assert result["hourly"][1]["weather_label"] == "Slight rain"
    assert len(result["daily"]) == 2
    assert result["daily"][1]["precipitation_sum"] == 6.5
    assert "Open-Meteo" in result["source"]


def test_api_forecast_endpoint(client, auth_user, monkeypatch):
    import app.api.weather as api_weather

    monkeypatch.setattr(
        api_weather.weather,
        "get_weather_forecast",
        lambda db, **kw: {
            "scope": "Village A", "state": None, "district": None, "village": None,
            "latitude": 17.0, "longitude": 79.0, "timezone": "Asia/Kolkata",
            "current": {"time": "2026-08-19T10:00", "temperature_2m": 31.2,
                        "weather_code": 2, "weather_label": "Partly cloudy"},
            "hourly": [], "daily": [],
            "source": "Open-Meteo (GFS/ICON/IFS model forecast)",
        },
    )
    resp = client.get("/api/weather/forecast", params={"state": "Test State"}, headers=auth_user)
    assert resp.status_code == 200
    body = resp.json()
    assert body["current"]["temperature_2m"] == 31.2
    assert body["current"]["weather_label"] == "Partly cloudy"


# ---------------------------------------------------------------------------
# IMD (official) provider
# ---------------------------------------------------------------------------

def _canned_imd_city():
    return {
        "Station_Code": "42182",
        "Station_Name": "Hyderabad",
        "Date": "2026-08-19",
        "Latitude": "17.3850",
        "Longitude": "78.4867",
        "Today_Max_temp": "31.0",
        "Today_Min_temp": "24.0",
        "Todays_Forecast": "Partly cloudy sky with possibility of rain",
        "Day_2_Max_Temp": "30.0",
        "Day_2_Min_temp": "23.5",
        "Day_2_Forecast": "Rain or thundershowers",
        "Past_24_hrs_Rainfall": "2.4",
    }


def _canned_imd_wx():
    return {
        "Station": "Hyderabad",
        "Date of Observation": "2026-08-19",
        "Time of Observation": "09:00",
        "Temperature": "28.5",
        "Humidity": "75",
        "Wind Speed": "12",
        "M.S.L.P": "1005.0",
        "Last 24 hrs Rainfall": "2.4",
        "Weather Code": "25",
        "Latitude": "17.3850",
        "Longitude": "78.4867",
    }


class _FakeSettings:
    IMD_API_KEY = "test-key"
    IMD_API_BASE_URL = "https://api.imd.gov.in/api/v1"


def test_code_from_text_heuristics():
    assert svc._code_from_text("Thunderstorms with rain") == 95
    assert svc._code_from_text("Rain or thundershowers") == 95
    assert svc._code_from_text("Light snow") == 73
    assert svc._code_from_text("Rain showers") == 80
    assert svc._code_from_text("Moderate rain") == 63
    assert svc._code_from_text("Foggy morning") == 45
    assert svc._code_from_text("Generally cloudy") == 3
    assert svc._code_from_text("Clear sky") == 0
    assert svc._code_from_text("Partly cloudy") == 2
    assert svc._code_from_text(None) is None


def test_imd_daily_builds_seven_days():
    daily = svc._imd_daily(_canned_imd_city(), days=7)
    assert len(daily) == 7
    assert daily[0]["date"] == "2026-08-19"
    assert daily[0]["temperature_2m_max"] == 31.0
    assert daily[0]["temperature_2m_min"] == 24.0
    assert daily[0]["weather_label"] == "Partly cloudy sky with possibility of rain"
    assert daily[0]["precipitation_sum"] == 2.4
    assert daily[1]["weather_code"] == 95
    assert daily[1]["temperature_2m_max"] == 30.0
    assert daily[6]["weather_label"] is None


def test_imd_current_from_station(monkeypatch):
    cur = svc._imd_current(_canned_imd_city(), _canned_imd_wx())
    assert cur["temperature_2m"] == 28.5
    assert cur["relative_humidity_2m"] == 75
    assert cur["wind_speed_10m"] == 12
    assert cur["pressure_msl"] == 1005.0
    assert cur["precipitation"] == 2.4
    assert cur["weather_code"] == 25
    assert cur["weather_label"] is not None


def test_forecast_from_imd_uses_official_source(weather_db, monkeypatch):
    monkeypatch.setattr(svc, "fetch_imd_city_forecast", lambda lat, lon: _canned_imd_city())
    monkeypatch.setattr(svc, "fetch_imd_current_wx", lambda lat, lon: _canned_imd_wx())
    result = svc._forecast_from_imd(
        weather_db, 17.0, 79.0, "Test District",
        state="Test State", district="Test District", village=None, days=7,
    )
    assert result["official"] is True
    assert "India Meteorological Department" in result["source"]
    assert result["hourly"] == []
    assert len(result["daily"]) == 7
    assert result["current"]["temperature_2m"] == 28.5


def test_get_weather_forecast_imd_preferred_when_key_set(weather_db, monkeypatch):
    monkeypatch.setattr(svc, "get_settings", lambda: _FakeSettings())
    monkeypatch.setattr(svc, "fetch_imd_city_forecast", lambda lat, lon: _canned_imd_city())
    monkeypatch.setattr(svc, "fetch_imd_current_wx", lambda lat, lon: _canned_imd_wx())
    monkeypatch.setattr(svc, "fetch_openmeteo", lambda lat, lon, days=7: _canned_payload())

    result = svc.get_weather_forecast(weather_db, "Test State", "Test District", "Village A", days=7)
    assert result["official"] is True
    assert result["current"]["temperature_2m"] == 28.5


def test_get_weather_forecast_falls_back_when_imd_fails(weather_db, monkeypatch):
    monkeypatch.setattr(svc, "get_settings", lambda: _FakeSettings())
    monkeypatch.setattr(svc, "fetch_imd_city_forecast", lambda lat, lon: None)
    monkeypatch.setattr(svc, "fetch_openmeteo", lambda lat, lon, days=7: _canned_payload())

    result = svc.get_weather_forecast(weather_db, "Test State", "Test District", "Village A", days=2)
    assert result["official"] is False
    assert "Open-Meteo" in result["source"]
    assert result["current"]["temperature_2m"] == 31.2


# ---------------------------------------------------------------------------
# Weather map (heat grid)
# ---------------------------------------------------------------------------

def test_resolve_scope_bounds_village_padded(weather_db):
    min_lat, min_lon, max_lat, max_lon = svc.resolve_scope_bounds(
        weather_db, "Test State", "Test District", "Village A"
    )
    assert min_lat <= 17.0 <= max_lat
    assert min_lon <= 79.0 <= max_lon
    assert abs((max_lat - min_lat) - 0.3) < 1e-6
    assert abs((max_lon - min_lon) - 0.3) < 1e-6


def test_resolve_scope_bounds_district_bbox(weather_db):
    min_lat, min_lon, max_lat, max_lon = svc.resolve_scope_bounds(
        weather_db, "Test State", "Test District", None
    )
    # Villages span 17.0..17.1 lat, 79.0..79.1 lon, padded by 8% + min 0.05 deg.
    assert min_lat < 17.0 < max_lat
    assert min_lon < 79.0 < max_lon
    assert abs((max_lat - min_lat) - 0.2) < 1e-4
    assert abs((max_lon - min_lon) - 0.2) < 1e-4


def test_resolve_scope_bounds_no_scope_uses_india(weather_db):
    min_lat, min_lon, max_lat, max_lon = svc.resolve_scope_bounds(weather_db, None, None, None)
    assert min_lat < 10
    assert max_lat > 30
    assert min_lon < 75
    assert max_lon > 90


def test_grid_points_square_cells(weather_db):
    bounds = (10.0, 70.0, 20.0, 80.0)
    points = svc._grid_points(bounds, max_points=40)
    assert 2 <= len(points) <= 40
    lats = sorted({round(p[0], 4) for p in points})
    lons = sorted({round(p[1], 4) for p in points})
    assert len(lats) > 2
    assert len(lons) > 2
    # All points inside the bounds.
    for lat, lon in points:
        assert 10.0 <= lat <= 20.0
        assert 70.0 <= lon <= 80.0


def test_get_weather_map_builds_grid(weather_db, monkeypatch):
    def fake_grid(points):
        return [
            {
                "current": {
                    "time": "2026-08-20T05:45",
                    "temperature_2m": 30.0 + i * 0.5,
                    "relative_humidity_2m": 55,
                    "precipitation": 0.0,
                    "weather_code": 1,
                    "wind_speed_10m": 8.0,
                }
            }
            for i in range(len(points))
        ]

    monkeypatch.setattr(svc, "fetch_openmeteo_grid", fake_grid)
    result = svc.get_weather_map(weather_db, "Test State", "Test District", "Village A", max_points=16)

    assert result["scope"] == "Village A"
    assert result["official"] is False
    assert "Open-Meteo" in result["source"]
    assert result["time"] == "2026-08-20T05:45"
    assert result["bounds"]["min_lat"] < result["bounds"]["max_lat"]
    bounds = (
        result["bounds"]["min_lat"],
        result["bounds"]["min_lon"],
        result["bounds"]["max_lat"],
        result["bounds"]["max_lon"],
    )
    assert len(result["grid"]) == len(svc._grid_points(bounds, max_points=16))
    first = result["grid"][0]
    assert first["temperature_2m"] == 30.0
    assert first["precipitation"] == 0.0
    assert first["wind_speed_10m"] == 8.0


def test_api_weather_map_endpoint(client, auth_user, monkeypatch):
    import app.api.weather as api_weather

    monkeypatch.setattr(
        api_weather.weather,
        "get_weather_map",
        lambda db, **kw: {
            "scope": "Village A",
            "bounds": {"min_lat": 16.8, "min_lon": 78.8, "max_lat": 17.2, "max_lon": 79.2},
            "grid": [
                {"lat": 17.0, "lon": 79.0, "temperature_2m": 31.2,
                 "relative_humidity_2m": 60, "precipitation": 0.0,
                 "weather_code": 1, "wind_speed_10m": 9.0}
            ],
            "time": "2026-08-20T05:45",
            "source": "Open-Meteo (GFS/ICON/IFS model forecast)",
            "official": False,
        },
    )
    resp = client.get("/api/weather/map", params={"state": "Test State"}, headers=auth_user)
    assert resp.status_code == 200
    body = resp.json()
    assert body["grid"][0]["temperature_2m"] == 31.2
    assert body["official"] is False
    assert body["bounds"]["max_lat"] == 17.2
def test_get_weather_map_series_maps_aqi_and_apparent(weather_db, monkeypatch):
    def fake_series(points, hours=48):
        n = 3
        times = [f"2026-08-20T{i:02d}:00" for i in range(10, 13)]
        rec = {
            "latitude": points[0][0],
            "longitude": points[0][1],
            "current": {"time": "2026-08-20T11:00", "temperature_2m": 30.0},
            "hourly": {
                "time": times,
                "temperature_2m": [30.0, 31.0, 32.0],
                "apparent_temperature": [33.0, 34.0, 35.0],
                "relative_humidity_2m": [60, 58, 55],
                "precipitation": [0.0, 0.5, 1.0],
                "cloud_cover": [40, 50, 60],
                "wind_speed_10m": [8.0, 9.0, 10.0],
                "wind_direction_10m": [230, 240, 250],
                "weather_code": [1, 2, 3],
                "us_aqi": [42.0, 45.0, 51.0],
            },
        }
        return [rec for _ in points], times

    monkeypatch.setattr(svc, "fetch_openmeteo_grid_series", fake_series)
    result = svc.get_weather_map_series(
        weather_db, state="Test State", district="Test District", village="Village A",
        max_points=4, hours=3,
    )
    point = result["grid"][0]
    assert point["hourly"]["apparent_temperature"] == [33.0, 34.0, 35.0]
    assert point["hourly"]["us_aqi"] == [42.0, 45.0, 51.0]
    # current time is index 1 -> us_aqi at that hour
    assert point["us_aqi"] == 45.0


def test_fetch_series_survives_air_quality_failure(monkeypatch):
    """AQI is optional: if the air-quality API fails the weather grid still loads."""
    from app.services import weather as svc_mod

    class _FakeResp:
        Variables = lambda self, i: None  # noqa: E731

    class _FakeClient:
        def weather_api(self, url, params=None):
            return [_FakeResp()]

    def fake_get_json(url, timeout=40, headers=None, verify=True):
        if "air-quality" in url:
            raise RuntimeError("air quality down")
        return {"hourly": {"time": ["2026-08-20T00:00"], "temperature_2m": [30.0]}}

    monkeypatch.setattr(svc_mod, "_get_openmeteo_client", lambda: _FakeClient())
    monkeypatch.setattr(svc_mod, "_response_to_dict", lambda r: {"hourly": {"time": ["2026-08-20T00:00"], "temperature_2m": [30.0]}})
    monkeypatch.setattr(svc_mod, "_get_json", fake_get_json)
    monkeypatch.setattr(svc_mod, "_series_cache", {})
    monkeypatch.setattr(svc_mod, "_cache_file_path", lambda: str(tmp_path_none()))
    payload, times = svc_mod.fetch_openmeteo_grid_series([(22.0, 80.0)], hours=1)
    assert times == ["2026-08-20T00:00"]
    assert payload[0]["hourly"]["temperature_2m"] == [30.0]
    assert "us_aqi" not in payload[0]["hourly"]


def tmp_path_none():
    import tempfile
    import os
    fd, path = tempfile.mkstemp(suffix=".json")
    os.close(fd)
    os.unlink(path)
    return path


def test_weather_map_series_endpoint(monkeypatch, client, auth_user):
    monkeypatch.setattr(
        api_weather.weather,
        "get_weather_map_series",
        lambda db, **kw: {
            "scope": "Village A",
            "bounds": {"min_lat": 16.8, "min_lon": 78.8, "max_lat": 17.2, "max_lon": 79.2},
            "grid": [
                {
                    "lat": 17.0, "lon": 79.0, "temperature_2m": 31.2,
                    "relative_humidity_2m": 60, "precipitation": 0.0,
                    "weather_code": 1, "wind_speed_10m": 9.0,
                    "wind_direction_10m": 240, "cloud_cover": 40,
                    "hourly": {
                        "temperature_2m": [30.0, 31.2], "relative_humidity_2m": [65, 60],
                        "precipitation": [0.0, 0.0], "cloud_cover": [50, 40],
                        "wind_speed_10m": [8.0, 9.0], "wind_direction_10m": [230, 240],
                        "weather_code": [1, 1],
                    },
                }
            ],
            "times": ["2026-08-20T11:00", "2026-08-20T12:00"],
            "time": "2026-08-20T12:00",
            "source": "Open-Meteo (GFS/ICON/IFS model forecast)",
            "official": False,
        },
    )
    resp = client.get("/api/weather/map/series", params={"state": "Test State"}, headers=auth_user)
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["times"]) == 2
    assert body["grid"][0]["hourly"]["wind_direction_10m"] == [230, 240]
    assert body["grid"][0]["cloud_cover"] == 40

def test_weather_map_series_degrades_gracefully(monkeypatch, client, auth_user):
    def boom(db, **kw):
        raise RuntimeError("Open-Meteo unavailable: HTTP Error 429: Too Many Requests")
    monkeypatch.setattr(api_weather.weather, "get_weather_map_series", boom)
    monkeypatch.setattr(api_weather.weather, "load_last_series", lambda: None)
    resp = client.get("/api/weather/map/series", params={"state": "Test State"}, headers=auth_user)
    assert resp.status_code == 200
    body = resp.json()
    assert body["available"] is False
    assert body["grid"] == []
    assert "429" in body["detail"]


def test_fetch_series_serves_stale_disk_cache_on_429(monkeypatch, tmp_path):
    from app.services import weather as svc_mod
    stale = {
        "fetched_at": time.time() - svc_mod._SERIES_CACHE_TTL - 10,
        "payload": [{"hourly": {"time": ["2026-08-20T00:00"]}}],
        "times": ["2026-08-20T00:00"],
    }
    key = "aq|24|1|22.00/80.00"
    monkeypatch.setattr(svc_mod, "_cache_file_path", lambda: str(tmp_path / "wc.json"))
    svc_mod._save_disk_cache(key, stale)

    def raise_error(*args, **kwargs):
        raise RuntimeError("Open-Meteo unavailable: HTTP Error 429: Too Many Requests")

    monkeypatch.setattr(
        svc_mod._get_openmeteo_client(),
        "weather_api",
        raise_error,
    )
    payload, times = svc_mod.fetch_openmeteo_grid_series([(22.0, 80.0)], hours=24)
    assert payload == stale["payload"]
    assert times == ["2026-08-20T00:00"]
