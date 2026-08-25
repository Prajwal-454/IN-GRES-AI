from fastapi.testclient import TestClient


def _simulate_call(client: TestClient, auth_user):
    resp = client.post(
        "/api/voice/calls/simulate",
        json={
            "phone_number_masked": "1800123456",
            "script": ["Hi, what is the groundwater situation in Nizamabad?"],
        },
        headers=auth_user,
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


def test_simulate_call(client: TestClient, auth_user):
    body = _simulate_call(client, auth_user)
    assert body["status"] in ("completed", "in_progress")


def test_list_calls_and_transcriptions(client: TestClient, auth_user):
    created = _simulate_call(client, auth_user)

    listed = client.get("/api/voice/calls", headers=auth_user)
    assert listed.status_code == 200
    assert any(c["id"] == created["id"] for c in listed.json())

    trans = client.get(f"/api/voice/calls/{created['id']}/transcriptions", headers=auth_user)
    assert trans.status_code == 200, trans.text
    rows = trans.json()
    assert len(rows) > 0
    assert "text" in rows[0]


def test_voice_requires_auth(client: TestClient):
    assert client.get("/api/voice/calls").status_code == 401