from fastapi.testclient import TestClient


def test_gis_map(client: TestClient, auth_user):
    resp = client.get("/api/gis/map", headers=auth_user)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["type"] == "FeatureCollection"
    assert len(body["features"]) > 0
    assert body["meta"]["metric"] == "stage"
    assert body["meta"]["states"]


def test_gis_map_by_metric(client: TestClient, auth_user):
    resp = client.get("/api/gis/map", params={"metric": "recharge"}, headers=auth_user)
    assert resp.status_code == 200
    assert resp.json()["meta"]["metric"] == "recharge"


def test_gis_map_filtered(client: TestClient, auth_user):
    resp = client.get(
        "/api/gis/map",
        params={"state": "Telangana", "year": 2022},
        headers=auth_user,
    )
    assert resp.status_code == 200
    features = resp.json()["features"]
    assert len(features) > 0
    assert all(f["properties"]["state"] == "Telangana" for f in features)
    assert all(f["properties"]["year"] == 2022 for f in features)


def test_gis_units(client: TestClient, auth_user):
    resp = client.get("/api/gis/units", headers=auth_user)
    assert resp.status_code == 200
    assert len(resp.json()) > 0


def test_gis_meta(client: TestClient, auth_user):
    resp = client.get("/api/gis/meta", headers=auth_user)
    assert resp.status_code == 200
    meta = resp.json()
    assert meta["years"]
    assert meta["metrics"]
    assert "states" in meta


def test_gis_basins(client: TestClient, auth_user):
    resp = client.get("/api/gis/basins", headers=auth_user)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["type"] == "FeatureCollection"
    assert len(body["features"]) > 0
    first = body["features"][0]["properties"]
    assert first["basin"]
    assert first["name"] == first["basin"]
    assert first["states"]
    assert first["district_count"] > 0
    assert body["meta"]["metric"] == "stage"


def test_gis_basin_single(client: TestClient, auth_user):
    resp = client.get("/api/gis/basins", params={"basin": "Krishna"}, headers=auth_user)
    assert resp.status_code == 200, resp.text
    features = resp.json()["features"]
    assert len(features) == 1
    p = features[0]["properties"]
    assert p["name"] == "Krishna"
    assert p["metric_value"] is not None
    assert p["category"] in ("safe", "semi-critical", "critical", "over-exploited")
    assert features[0]["geometry"]["type"] == "MultiPolygon"


def test_gis_india(client: TestClient, auth_user):
    resp = client.get("/api/gis/india", headers=auth_user)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["type"] == "FeatureCollection"
    assert len(body["features"]) >= 30
    assert body["meta"]["metric"] == "stage"
    assert "units" in body
    names = {f["properties"]["name"] for f in body["features"]}
    assert {"Telangana", "Andhra Pradesh", "Ladakh", "Odisha", "Kerala"} <= names


def test_gis_india_data_states(client: TestClient, auth_user):
    resp = client.get("/api/gis/india", headers=auth_user)
    body = resp.json()
    by_name = {f["properties"]["name"]: f["properties"] for f in body["features"]}

    telangana = by_name["Telangana"]
    assert telangana["has_data"] is True
    assert telangana["unit_count"] > 0
    assert telangana["metric_value"] is not None
    assert telangana["stage_of_extraction"] is not None
    assert telangana["is_demo"] is True

    andhra = by_name["Andhra Pradesh"]
    assert andhra["has_data"] is True
    assert andhra["unit_count"] > 0

    no_data = by_name["Kerala"]
    assert no_data["has_data"] is False
    assert no_data["unit_count"] == 0
    assert no_data["metric_value"] is None


def test_gis_india_metric(client: TestClient, auth_user):
    resp = client.get("/api/gis/india", params={"metric": "recharge"}, headers=auth_user)
    assert resp.status_code == 200
    body = resp.json()
    assert body["meta"]["metric"] == "recharge"
    telangana = next(f for f in body["features"] if f["properties"]["name"] == "Telangana")
    assert telangana["properties"]["metric_value"] is not None


def test_gis_compare_default_years(client: TestClient, auth_user):
    resp = client.get("/api/gis/compare", headers=auth_user)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["type"] == "FeatureCollection"
    assert body["meta"]["year_a"] < body["meta"]["year_b"]
    assert len(body["features"]) > 0
    props = body["features"][0]["properties"]
    for key in ("metric_value_a", "metric_value_b", "delta", "category_a", "category_b"):
        assert key in props
    assert "category_changed" in props


def test_gis_compare_years(client: TestClient, auth_user):
    resp = client.get(
        "/api/gis/compare",
        params={"state": "Telangana", "year_a": 2017, "year_b": 2022},
        headers=auth_user,
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["meta"]["year_a"] == 2017
    assert body["meta"]["year_b"] == 2022
    assert len(body["features"]) > 0
    assert all(f["properties"]["state"] == "Telangana" for f in body["features"])
    telangana = body["features"][0]["properties"]
    assert telangana["metric_value_a"] is not None
    assert telangana["metric_value_b"] is not None
    assert telangana["delta"] is not None


def test_gis_compare_swapped_years(client: TestClient, auth_user):
    resp = client.get(
        "/api/gis/compare",
        params={"year_a": 2022, "year_b": 2017},
        headers=auth_user,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["meta"]["year_a"] <= body["meta"]["year_b"]


def test_gis_compare_india(client: TestClient, auth_user):
    resp = client.get("/api/gis/compare/india", headers=auth_user)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["type"] == "FeatureCollection"
    assert body["meta"]["year_a"] < body["meta"]["year_b"]
    assert len(body["features"]) >= 30
    by_name = {f["properties"]["name"]: f["properties"] for f in body["features"]}
    assert by_name["Telangana"]["delta"] is not None
    assert "category_changed" in by_name["Telangana"]