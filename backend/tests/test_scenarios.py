from fastapi.testclient import TestClient


def test_scenario_compare_returns_baseline_and_scenario(client: TestClient, auth_user):
    resp = client.get(
        "/api/predictions/scenario-compare",
        params={
            "state": "Telangana",
            "metric": "stage",
            "horizon": 4,
            "method": "linear",
            "extraction_change": -20,
            "recharge_change": 0,
        },
        headers=auth_user,
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["scope"] == "Telangana"
    assert body["metric"] == "stage"
    assert body["baseline"]["forecast"], "baseline must have forecast points"
    assert body["scenario"]["forecast"], "scenario must have forecast points"
    # Reducing pumping must project a LOWER stage than the baseline.
    end_b = body["delta"]["end_baseline"]
    end_s = body["delta"]["end_scenario"]
    assert end_b is not None and end_s is not None
    assert end_s < end_b
    assert body["delta"]["end_delta"] < 0
    assert body["scenario"]["scenario"]["change_pct"] == -20.0


def test_scenario_compare_combined_changes(client: TestClient, auth_user):
    resp = client.get(
        "/api/predictions/scenario-compare",
        params={
            "state": "Telangana",
            "metric": "stage",
            "method": "linear",
            "extraction_change": -10,
            "recharge_change": 10,
        },
        headers=auth_user,
    )
    assert resp.status_code == 200
    delta = resp.json()["delta"]
    assert delta["end_delta"] is not None and delta["end_delta"] < 0


def test_scenario_compare_zero_changes_matches_baseline(client: TestClient, auth_user):
    resp = client.get(
        "/api/predictions/scenario-compare",
        params={"state": "Telangana", "metric": "recharge", "method": "linear"},
        headers=auth_user,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["delta"]["end_baseline"] == body["delta"]["end_scenario"]
    assert body["delta"]["end_delta"] == 0


def test_scenario_compare_requires_auth(client: TestClient):
    assert (
        client.get("/api/predictions/scenario-compare", params={"state": "Telangana"}).status_code
        in (401, 403)
    )


def test_saved_scenario_crud_and_reload(client: TestClient, auth_user):
    created = client.post(
        "/api/scenarios",
        json={
            "name": "Cut pumping 20%",
            "state": "Telangana",
            "district": "Warangal",
            "metric": "stage",
            "horizon": 5,
            "method": "auto",
            "extraction_change": -20,
            "recharge_change": 0,
        },
        headers=auth_user,
    )
    assert created.status_code == 201, created.text
    scenario = created.json()
    sid = scenario["id"]
    try:
        assert scenario["state"] == "Telangana"
        assert scenario["extraction_change"] == -20

        listed = client.get("/api/scenarios", headers=auth_user).json()
        assert any(s["id"] == sid for s in listed["scenarios"])

        deleted = client.delete(f"/api/scenarios/{sid}", headers=auth_user)
        assert deleted.status_code == 200
        assert client.delete(f"/api/scenarios/{sid}", headers=auth_user).status_code == 404
    except AssertionError:
        raise


def test_saved_scenario_validation(client: TestClient, auth_user):
    bad_state = client.post(
        "/api/scenarios",
        json={"name": "bad", "state": "Atlantis"},
        headers=auth_user,
    )
    assert bad_state.status_code == 404
    bad_metric = client.post(
        "/api/scenarios",
        json={"name": "bad", "metric": "vibes"},
        headers=auth_user,
    )
    assert bad_metric.status_code == 422
    bad_change = client.post(
        "/api/scenarios",
        json={"name": "bad", "recharge_change": -500},
        headers=auth_user,
    )
    assert bad_change.status_code == 422


def test_saved_scenarios_require_auth(client: TestClient):
    assert client.get("/api/scenarios").status_code in (401, 403)
