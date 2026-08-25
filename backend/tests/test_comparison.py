from fastapi.testclient import TestClient


def test_compare_two_states(client: TestClient, auth_user):
    resp = client.get(
        "/api/comparison/metrics",
        params={"scopes": "state:Telangana,state:Andhra Pradesh"},
        headers=auth_user,
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["count"] == 2
    scopes = body["scopes"]
    assert all(s["resolved"] for s in scopes)
    for s in scopes:
        assert s["summary"] is not None
        assert "total_recharge" in s["summary"]
        assert s["trend"], f"{s['key']} should have trend rows"
        row = s["trend"][-1]
        assert {"year", "stage_of_extraction", "recharge", "extraction"} <= set(row)
        assert s["latest_year"] is not None
    verdict = body["verdict"]
    assert verdict is not None
    assert verdict["metric"] == "stage_of_extraction"
    assert verdict["best_key"] and verdict["worst_key"]


def test_compare_mixed_kinds(client: TestClient, auth_user):
    resp = client.get(
        "/api/comparison/metrics",
        params={"scopes": "district:Guntur,village:Guntur Village,basin:Krishna,state:Telangana"},
        headers=auth_user,
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    by_key = {s["key"]: s for s in body["scopes"]}
    assert by_key["district:Guntur"]["resolved"]
    assert "Andhra Pradesh" in by_key["district:Guntur"]["label"]
    assert by_key["village:Guntur Village"]["resolved"]
    assert by_key["village:Guntur Village"]["summary"]["assessment_units"] > 0
    # The Krishna basin covers the demo districts (AP + TS), so it resolves.
    assert by_key["basin:Krishna"]["resolved"]
    assert by_key["basin:Krishna"]["trend"]


def test_compare_unknown_scope_unresolved(client: TestClient, auth_user):
    resp = client.get(
        "/api/comparison/metrics",
        params={"scopes": "state:Atlantis,district:Nowhere"},
        headers=auth_user,
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    scopes = {s["key"]: s for s in body["scopes"]}
    assert scopes["state:Atlantis"]["resolved"] is False
    assert scopes["state:Atlantis"]["summary"] is None
    assert scopes["district:Nowhere"]["resolved"] is False
    # Only one resolvable scope at most -> no verdict.
    assert body["verdict"] is None


def test_compare_invalid_token_400(client: TestClient, auth_user):
    resp = client.get(
        "/api/comparison/metrics",
        params={"scopes": "Telangana"},
        headers=auth_user,
    )
    assert resp.status_code == 400
    assert "kind:name" in resp.json()["detail"]


def test_compare_too_many_scopes_400(client: TestClient, auth_user):
    scopes = ",".join(f"state:S{i}" for i in range(7))
    resp = client.get("/api/comparison/metrics", params={"scopes": scopes}, headers=auth_user)
    assert resp.status_code == 400


def test_compare_requires_auth(client: TestClient):
    resp = client.get("/api/comparison/metrics", params={"scopes": "state:Telangana"})
    assert resp.status_code in (401, 403)


def test_compare_missing_scopes_param(client: TestClient, auth_user):
    resp = client.get("/api/comparison/metrics", headers=auth_user)
    assert resp.status_code == 422
