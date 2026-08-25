from fastapi.testclient import TestClient

from app.config import get_settings
from app.models.push import PushSubscription
from app.services import push


def test_push_config_default_disabled(client: TestClient, auth_user):
    resp = client.get("/api/push/config", headers=auth_user)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["enabled"] is False
    assert body["supported"] is True


def test_push_subscribe_when_disabled(client: TestClient, auth_user):
    resp = client.post(
        "/api/push/subscribe",
        json={"endpoint": "https://push.example.com/sub", "keys": {"p256dh": "a" * 43, "auth": "b" * 16}},
        headers=auth_user,
    )
    assert resp.status_code == 400
    assert "not enabled" in resp.json()["detail"]


def test_push_config_requires_auth(client: TestClient):
    resp = client.get("/api/push/config")
    assert resp.status_code == 401


def test_vapid_keys_generated():
    public_key, private_key = push._load_or_create_keys()
    assert len(public_key) >= 43
    assert len(private_key) >= 43
    assert push.vapid_public_key() == public_key


def test_push_enabled_defaults_false():
    assert push.push_enabled() is False


def test_save_and_remove_subscription(db_session_factory):
    db = db_session_factory()
    try:
        from app.models.user import User

        user = db.query(User).first()
        sub = push.save_subscription(
            db, user, "https://push.example.com/abc", "p256dh-value", "auth-value", "test-agent"
        )
        assert sub.id is not None
        assert sub.endpoint == "https://push.example.com/abc"
        again = push.save_subscription(db, user, "https://push.example.com/abc", "new", "new", None)
        assert again.id == sub.id
        assert push.remove_subscription(db, user, "https://push.example.com/abc") is True
        assert push.remove_subscription(db, user, "https://push.example.com/abc") is False
    finally:
        db.close()


def test_send_push_returns_false_when_disabled(db_session_factory):
    db = db_session_factory()
    try:
        from app.models.user import User

        user = db.query(User).first()
        sub = push.save_subscription(db, user, "https://push.example.com/x", "p", "a", None)
        assert push.send_push(sub, "title", "body") is False
    finally:
        db.close()