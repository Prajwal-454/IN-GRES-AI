from fastapi.testclient import TestClient


def _create_request(client: TestClient, auth_user):
    resp = client.post(
        "/api/expert/requests",
        json={"question": "Why is extraction rising in Yadadri?", "location": "Yadadri"},
        headers=auth_user,
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


def test_create_request(client: TestClient, auth_user):
    body = _create_request(client, auth_user)
    assert body["status"] == "NEW"
    assert body["user_id"] > 0


def test_list_and_get_request(client: TestClient, auth_user):
    created = _create_request(client, auth_user)
    listed = client.get("/api/expert/requests", headers=auth_user)
    assert listed.status_code == 200
    assert any(r["id"] == created["id"] for r in listed.json())

    got = client.get(f"/api/expert/requests/{created['id']}", headers=auth_user)
    assert got.status_code == 200
    assert got.json()["question"] == created["question"]


def test_update_requires_expert(client: TestClient, auth_user, admin_token: str):
    created = _create_request(client, auth_user)

    denied = client.patch(
        f"/api/expert/requests/{created['id']}",
        json={"status": "RESOLVED"},
        headers=auth_user,
    )
    assert denied.status_code == 403

    allowed = client.patch(
        f"/api/expert/requests/{created['id']}",
        json={"status": "RESOLVED", "priority": "HIGH", "resolution": "Reviewed."},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert allowed.status_code == 200, allowed.text
    body = allowed.json()
    assert body["status"] == "RESOLVED"
    assert body["priority"] == "HIGH"
    assert body["resolution"] == "Reviewed."