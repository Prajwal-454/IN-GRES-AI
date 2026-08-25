import uuid

from fastapi.testclient import TestClient


def test_login_and_me(client: TestClient, auth_user):
    resp = client.get("/api/auth/me", headers=auth_user)
    assert resp.status_code == 200
    me = resp.json()
    assert me["email"] == "user@ingres.in"
    assert "role" in me


def test_register_login_refresh(client: TestClient):
    email = f"pytest_{uuid.uuid4().hex[:8]}@example.com"
    register = client.post(
        "/api/auth/register",
        json={"full_name": "Pytest User", "email": email, "password": "test12345"},
    )
    assert register.status_code in (200, 201), register.text
    token = register.json().get("access_token")

    login = client.post("/api/auth/login", json={"email": email, "password": "test12345"})
    assert login.status_code == 200, login.text
    data = login.json()
    assert data["user"]["email"] == email
    assert data["access_token"]

    refresh = client.post(
        "/api/auth/refresh",
        json={"refresh_token": data["refresh_token"]},
    )
    assert refresh.status_code == 200, refresh.text
    assert refresh.json()["access_token"]


def test_login_wrong_password(client: TestClient):
    resp = client.post(
        "/api/auth/login", json={"email": "user@ingres.in", "password": "wrong-pass"}
    )
    assert resp.status_code in (400, 401)


def test_me_requires_auth(client: TestClient):
    resp = client.get("/api/auth/me")
    assert resp.status_code == 401
