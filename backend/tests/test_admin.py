import uuid

from fastapi.testclient import TestClient


def test_admin_users(client: TestClient, auth_admin):
    resp = client.get("/api/admin/users", headers=auth_admin)
    assert resp.status_code == 200, resp.text
    emails = [u["email"] for u in resp.json()]
    assert "admin@ingres.in" in emails
    assert "user@ingres.in" in emails


def test_admin_create_update_user(client: TestClient, auth_admin):
    email = f"admin_test_{uuid.uuid4().hex[:8]}@example.com"
    created = client.post(
        "/api/admin/users",
        json={"email": email, "full_name": "Admin Test", "password": "test12345", "role": "user"},
        headers=auth_admin,
    )
    assert created.status_code == 201, created.text
    user_id = created.json()["id"]

    updated = client.patch(
        f"/api/admin/users/{user_id}",
        json={"is_active": False, "role": "expert"},
        headers=auth_admin,
    )
    assert updated.status_code == 200, updated.text
    body = updated.json()
    assert body["is_active"] is False
    assert body["role"] == "expert"


def test_admin_requires_admin_role(client: TestClient, auth_user):
    resp = client.get("/api/admin/users", headers=auth_user)
    assert resp.status_code == 403


def test_audit_logs(client: TestClient, auth_admin):
    resp = client.get("/api/admin/audit-logs", headers=auth_admin)
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


def test_datasets(client: TestClient, auth_admin):
    resp = client.get("/api/admin/datasets", headers=auth_admin)
    assert resp.status_code == 200, resp.text
    datasets = resp.json()
    assert any(d["is_demo"] for d in datasets)