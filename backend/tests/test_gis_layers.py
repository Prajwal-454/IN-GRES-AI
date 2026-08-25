"""Tests for the layered GIS map support: click-to-analyze, prediction layer
and monitoring stations."""

from fastapi.testclient import TestClient


def test_analyze_location(client: TestClient, auth_user):
    resp = client.get(
        "/api/gis/analyze",
        params={"lat": 16.5, "lon": 80.5},
        headers=auth_user,
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["location"]
    assert body["state"]
    assert body["stage"] is not None
    assert body["category"] is not None
    assert body["water_level"]["value"] is not None
    assert body["water_level"]["unit"] == "m"
    assert body["risk"] in ("Low", "Medium", "High", "Critical")
    assert body["prediction"] is not None
    assert body["prediction"]["target_year"] > body["year"]
    assert body["prediction"]["value"] is not None
    assert body["recommendation"]


def test_analyze_location_outside_returns_no_data(client: TestClient, auth_user):
    resp = client.get(
        "/api/gis/analyze",
        params={"lat": 60.0, "lon": 150.0},
        headers=auth_user,
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body.get("error") == "no_data" or body.get("location") is None


def test_prediction_geojson(client: TestClient, auth_user):
    resp = client.get(
        "/api/gis/prediction",
        params={"state": "Telangana", "target_year": 2030},
        headers=auth_user,
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["type"] == "FeatureCollection"
    assert body["features"]
    assert body["meta"]["metric"] == "prediction"
    assert body["meta"]["target_year"] == 2030
    for f in body["features"]:
        assert f["properties"]["metric_value"] is not None
        assert f["properties"]["category"] is not None


def test_stations(client: TestClient, auth_user):
    resp = client.get("/api/gis/stations", headers=auth_user)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body
    for s in body:
        assert {"latitude", "longitude", "district", "state"} <= set(s)


def test_water_level_derivation():
    from app.gis.service import water_level_from_stage

    assert water_level_from_stage(None) is None
    assert water_level_from_stage(0) == 1.2
    assert water_level_from_stage(100) == 11.2
    assert water_level_from_stage(70) == 8.2