from fastapi.testclient import TestClient


def _create(client: TestClient, headers, **overrides) -> dict:
    payload = {
        "name": "Weekly Telangana digest",
        "state": "Telangana",
        "frequency": "weekly",
        "recipients": ["officer@example.com"],
    }
    payload.update(overrides)
    resp = client.post("/api/reports/schedules", json=payload, headers=headers)
    assert resp.status_code == 201, resp.text
    return resp.json()


def test_schedule_crud_and_run(client: TestClient, auth_user):
    created = _create(client, auth_user)
    schedule_id = created["id"]
    try:
        assert created["state"] == "Telangana"
        assert created["frequency"] == "weekly"
        assert created["next_run_at"] is not None  # due immediately

        listed = client.get("/api/reports/schedules", headers=auth_user).json()
        assert any(s["id"] == schedule_id for s in listed["schedules"])

        updated = client.patch(
            f"/api/reports/schedules/{schedule_id}",
            json={"frequency": "monthly", "enabled": False},
            headers=auth_user,
        )
        assert updated.status_code == 200
        body = updated.json()
        assert body["frequency"] == "monthly"
        assert body["enabled"] is False

        # Run immediately (SMTP disabled in tests -> generated, not emailed).
        run = client.post(f"/api/reports/schedules/{schedule_id}/run", headers=auth_user)
        assert run.status_code == 200, run.text
        result = run.json()
        assert result["status"] == "generated"
        assert result["emailed"] is False
        assert result["file"] and result["file"].endswith(".pdf")

        download = client.get(
            f"/api/reports/schedules/{schedule_id}/download-latest",
            headers=auth_user,
        )
        assert download.status_code == 200
        assert download.headers["content-type"].startswith("application/pdf")
        assert download.content[:4] == b"%PDF"
    finally:
        deleted = client.delete(f"/api/reports/schedules/{schedule_id}", headers=auth_user)
        assert deleted.status_code == 200
    # Files were cleaned up with the schedule.
    gone = client.get(
        f"/api/reports/schedules/{schedule_id}/download-latest",
        headers=auth_user,
    )
    assert gone.status_code == 404


def test_schedule_scope_validation(client: TestClient, auth_user):
    assert (
        client.post(
            "/api/reports/schedules",
            json={"name": "bad state", "state": "Atlantis"},
            headers=auth_user,
        ).status_code
        == 404
    )
    bad_email = client.post(
        "/api/reports/schedules",
        json={"name": "bad email", "recipients": ["not-an-email"]},
        headers=auth_user,
    )
    assert bad_email.status_code == 400
    bad_freq = client.post(
        "/api/reports/schedules",
        json={"name": "bad freq", "frequency": "daily"},
        headers=auth_user,
    )
    assert bad_freq.status_code == 422


def test_schedule_ownership(client: TestClient, auth_user, auth_admin, user_token):
    created = _create(client, auth_user, name="private digest")
    other_id = created["id"]

    # A second regular user must not see or touch it.
    reg = client.post(
        "/api/auth/register",
        json={
            "email": "schedule-other@example.com",
            "full_name": "Other User",
            "password": "other-pass-123",
        },
    )
    assert reg.status_code in (200, 201), reg.text
    login = client.post(
        "/api/auth/login",
        json={"email": "schedule-other@example.com", "password": "other-pass-123"},
    )
    assert login.status_code == 200
    other_headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    mine = client.get("/api/reports/schedules", headers=other_headers).json()
    assert not any(s["id"] == other_id for s in mine["schedules"])
    assert (
        client.post(f"/api/reports/schedules/{other_id}/run", headers=other_headers).status_code
        == 404
    )

    # Admin sees every user's schedules with ?all=true and may run them.
    everything = client.get(
        "/api/reports/schedules",
        params={"all": True},
        headers=auth_admin,
    ).json()
    assert any(s["id"] == other_id for s in everything["schedules"])
    admin_run = client.post(f"/api/reports/schedules/{other_id}/run", headers=auth_admin)
    assert admin_run.status_code == 200

    assert client.delete(f"/api/reports/schedules/{other_id}", headers=auth_user).status_code == 200


def test_schedules_require_auth(client: TestClient):
    assert client.get("/api/reports/schedules").status_code in (401, 403)
