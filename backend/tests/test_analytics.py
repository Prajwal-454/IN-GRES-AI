from fastapi.testclient import TestClient


def test_trends(client: TestClient, auth_user):
    resp = client.get("/api/analytics/trends", headers=auth_user)
    assert resp.status_code == 200, resp.text
    rows = resp.json()
    assert len(rows) >= 2
    assert "year" in rows[0]
    assert "stage_of_extraction" in rows[0]


def test_trends_by_state(client: TestClient, auth_user):
    resp = client.get("/api/analytics/trends", params={"state": "Telangana"}, headers=auth_user)
    assert resp.status_code == 200
    assert resp.json()


def test_district_ranking(client: TestClient, auth_user):
    resp = client.get("/api/analytics/district-ranking", headers=auth_user)
    assert resp.status_code == 200, resp.text
    rows = resp.json()
    assert len(rows) > 0
    assert "district" in rows[0]


def test_district_ranking_metric(client: TestClient, auth_user):
    resp = client.get(
        "/api/analytics/district-ranking",
        params={"metric": "stage", "year": 2022},
        headers=auth_user,
    )
    assert resp.status_code == 200
    assert resp.json()


def test_insights(client: TestClient, auth_user):
    resp = client.get("/api/analytics/insights", headers=auth_user)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert "insights" in body
    assert "latest_year" in body