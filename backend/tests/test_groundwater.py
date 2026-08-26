from fastapi.testclient import TestClient


def test_states(client: TestClient, auth_user):
    resp = client.get("/api/groundwater/states", headers=auth_user)
    assert resp.status_code == 200
    names = [s["name"] for s in resp.json()]
    assert "Telangana" in names
    assert "Andhra Pradesh" in names


def test_categories(client: TestClient, auth_user):
    resp = client.get("/api/groundwater/categories", headers=auth_user)
    assert resp.status_code == 200
    assert any(c["label"] == "Safe" for c in resp.json())


def test_summary(client: TestClient, auth_user):
    resp = client.get("/api/groundwater/summary", headers=auth_user)
    assert resp.status_code == 200
    summary = resp.json()
    assert summary["assessment_units"] > 0
    assert summary["is_demo"] is False
    assert summary["total_recharge"] > 0


def test_summary_filtered_by_state(client: TestClient, auth_user):
    resp = client.get(
        "/api/groundwater/summary", params={"state": "Telangana"}, headers=auth_user
    )
    assert resp.status_code == 200
    assert resp.json()["assessment_units"] > 0


def test_assessments(client: TestClient, auth_user):
    resp = client.get("/api/groundwater/assessment", headers=auth_user)
    assert resp.status_code == 200
    rows = resp.json()
    assert len(rows) > 0
    assert all("stage_of_extraction" in r for r in rows)


def test_recharge_and_extraction(client: TestClient, auth_user):
    for path in ("recharge", "extraction"):
        resp = client.get(f"/api/groundwater/{path}", headers=auth_user)
        assert resp.status_code == 200
        rows = resp.json()
        assert len(rows) > 0
        assert "year" in rows[0]
        assert "value" in rows[0]


def test_districts_for_state(client: TestClient, auth_user):
    resp = client.get(
        "/api/groundwater/districts", params={"state": "Telangana"}, headers=auth_user
    )
    assert resp.status_code == 200
    rows = resp.json()
    assert len(rows) > 0
    assert all("name" in d and "id" in d for d in rows)


def test_districts_unknown_state_404(client: TestClient, auth_user):
    resp = client.get(
        "/api/groundwater/districts", params={"state": "Nope"}, headers=auth_user
    )
    assert resp.status_code == 404


def test_villages_for_district(client: TestClient, auth_user):
    districts = client.get(
        "/api/groundwater/districts", params={"state": "Telangana"}, headers=auth_user
    ).json()
    assert districts
    resp = client.get(
        "/api/groundwater/villages",
        params={"state": "Telangana", "district": districts[0]["name"]},
        headers=auth_user,
    )
    assert resp.status_code == 200
    rows = resp.json()
    assert len(rows) > 0
    assert all("name" in v and "id" in v for v in rows)


def test_assessments_filtered_by_village(client: TestClient, auth_user):
    districts = client.get(
        "/api/groundwater/districts", params={"state": "Telangana"}, headers=auth_user
    ).json()
    assert districts
    villages = client.get(
        "/api/groundwater/villages",
        params={"state": "Telangana", "district": districts[0]["name"]},
        headers=auth_user,
    ).json()
    assert villages
    resp = client.get(
        "/api/groundwater/assessment",
        params={"state": "Telangana", "village": villages[0]["name"]},
        headers=auth_user,
    )
    assert resp.status_code == 200
    rows = resp.json()
    assert len(rows) > 0
    assert all(r["assessment_unit"] == villages[0]["name"] for r in rows)


def test_summary_filtered_by_village(client: TestClient, auth_user):
    districts = client.get(
        "/api/groundwater/districts", params={"state": "Telangana"}, headers=auth_user
    ).json()
    assert districts
    villages = client.get(
        "/api/groundwater/villages",
        params={"state": "Telangana", "district": districts[0]["name"]},
        headers=auth_user,
    ).json()
    assert villages
    resp = client.get(
        "/api/groundwater/summary",
        params={"state": "Telangana", "village": villages[0]["name"]},
        headers=auth_user,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["assessment_units"] > 0
    assert body["village"] == villages[0]["name"]


def test_groundwater_requires_auth(client: TestClient):
    assert client.get("/api/groundwater/states").status_code == 401