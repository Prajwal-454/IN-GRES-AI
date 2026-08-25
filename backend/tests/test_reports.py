from fastapi.testclient import TestClient


def test_report_data(client: TestClient, auth_user):
    resp = client.get("/api/reports/data", headers=auth_user)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["count"] > 0
    assert body["summary"]["assessment_units"] > 0
    assert body["rows"]


def test_report_csv(client: TestClient, auth_user):
    resp = client.get("/api/reports/export.csv", headers=auth_user)
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/csv")
    assert b"assessment_unit" in resp.content or b"District" in resp.content


def test_report_pdf(client: TestClient, auth_user):
    resp = client.get("/api/reports/export.pdf", headers=auth_user)
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("application/pdf")
    assert resp.content[:4] == b"%PDF"


def test_report_recharge_csv(client: TestClient, auth_user):
    resp = client.get(
        "/api/reports/export.csv", params={"type": "recharge"}, headers=auth_user
    )
    assert resp.status_code == 200
    assert b"year" in resp.content.lower()