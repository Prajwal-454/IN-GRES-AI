"""Tests for alerts and notifications."""

from app.services.alerts import check_all_alerts


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _create_rule(client, token: str, **overrides) -> dict:
    payload = {
        "name": "Over-exploited watch",
        "metric": "stage",
        "operator": "gt",
        "threshold": 100,
        "channels": ["in_app"],
        "cooldown_minutes": 0,
        "enabled": True,
        **overrides,
    }
    resp = client.post("/api/notifications/rules", json=payload, headers=_auth(token))
    assert resp.status_code == 201, resp.text
    return resp.json()


def test_notifications_empty_and_rule_crud(client, user_token):
    headers = _auth(user_token)
    resp = client.get("/api/notifications", headers=headers)
    assert resp.status_code == 200
    body = resp.json()
    assert "notifications" in body and "unread" in body

    rule = _create_rule(client, user_token)
    assert rule["metric"] == "stage"

    rules = client.get("/api/notifications/rules", headers=headers)
    assert len(rules.json()) == 1

    upd = client.patch(
        f"/api/notifications/rules/{rule['id']}",
        json={"enabled": False},
        headers=headers,
    )
    assert upd.status_code == 200
    assert upd.json()["enabled"] is False

    resp = client.delete(f"/api/notifications/rules/{rule['id']}", headers=headers)
    assert resp.status_code == 204


def test_alert_rule_triggers_notification(client, user_token, db_session_factory):
    # Demo data contains over-exploited units (stage > 100). A low threshold
    # with cooldown 0 should produce notifications on manual check.
    _create_rule(client, user_token, threshold=0, name="Everything alert", cooldown_minutes=0)

    resp = client.post("/api/notifications/check", headers=_auth(user_token))
    assert resp.status_code == 200
    assert resp.json()["created"] > 0

    resp = client.get("/api/notifications?unread_only=true", headers=_auth(user_token))
    assert resp.status_code == 200
    body = resp.json()
    assert body["unread"] > 0
    note = body["notifications"][0]
    assert note["title"]
    assert note["payload"]["metric"] == "stage"

    # Mark all read.
    resp = client.post("/api/notifications/read-all", headers=_auth(user_token))
    assert resp.status_code == 200
    resp = client.get("/api/notifications?unread_only=true", headers=_auth(user_token))
    assert resp.json()["unread"] == 0


def test_alert_rule_owned_by_user(client, user_token, admin_token):
    rule = _create_rule(client, user_token)
    # Admin cannot see or edit the user's rule.
    resp = client.get("/api/notifications/rules", headers=_auth(admin_token))
    assert all(r["id"] != rule["id"] for r in resp.json())
    resp = client.patch(
        f"/api/notifications/rules/{rule['id']}",
        json={"enabled": True},
        headers=_auth(admin_token),
    )
    assert resp.status_code == 404
