"""Registration CAPTCHA: signed question, expiry, tamper-proofing."""

import time
import uuid

from fastapi.testclient import TestClient


def _enable_captcha(monkeypatch):
    from app.config import get_settings

    monkeypatch.setattr(get_settings(), "REGISTRATION_CAPTCHA_ENABLED", True)


def test_register_blocked_without_captcha(client: TestClient, monkeypatch):
    _enable_captcha(monkeypatch)
    email = f"cap_{uuid.uuid4().hex[:8]}@example.com"
    resp = client.post(
        "/api/auth/register",
        json={"full_name": "No Captcha", "email": email, "password": "test12345"},
    )
    assert resp.status_code == 400, resp.text
    assert "CAPTCHA" in resp.json()["detail"]


def test_register_rejects_wrong_answer(client: TestClient, monkeypatch):
    from app.core import captcha as cap

    _enable_captcha(monkeypatch)
    cid, _question, answer = cap.generate()
    email = f"cap_{uuid.uuid4().hex[:8]}@example.com"
    resp = client.post(
        "/api/auth/register",
        json={
            "full_name": "Wrong",
            "email": email,
            "password": "test12345",
            "captcha_id": cid,
            "captcha_answer": str(answer + 1),
        },
    )
    assert resp.status_code == 400, resp.text


def test_register_succeeds_with_valid_captcha(client: TestClient, monkeypatch):
    from app.core import captcha as cap

    _enable_captcha(monkeypatch)
    cid, _question, answer = cap.generate()
    email = f"cap_{uuid.uuid4().hex[:8]}@example.com"
    resp = client.post(
        "/api/auth/register",
        json={
            "full_name": "Captcha OK",
            "email": email,
            "password": "test12345",
            "captcha_id": cid,
            "captcha_answer": str(answer),
        },
    )
    assert resp.status_code in (200, 201), resp.text
    assert resp.json()["access_token"]


def test_captcha_endpoint_returns_svg_and_id(client: TestClient):
    resp = client.get("/api/auth/captcha")
    assert resp.status_code == 200
    body = resp.json()
    assert body["captcha_id"]
    assert body["svg"].startswith("<svg")
    # The id must not leak the answer as plain text.
    import base64

    raw = base64.urlsafe_b64decode(
        body["captcha_id"].split(".")[0] + "=" * (-len(body["captcha_id"].split(".")[0]) % 4)
    )
    assert b'"ans"' not in raw and b"answer" not in raw


def test_verify_tampered_and_expired():
    from app.core import captcha as cap

    cid, _q, answer = cap.generate()

    assert cap.verify(cid, answer) is True
    assert cap.verify(cid, answer + 1) is False

    # Tamper with the payload (flip a digit inside the body).
    head, sig = cid.rsplit(".", 1)
    tampered = head[:-2] + ("0" if head[-1] != "0" else "1") + "." + sig
    assert cap.verify(tampered, answer) is False

    # Expired id.
    expired_body = '{"a":5,"op":"+","b":3,"exp":1000000000}'
    import base64
    import hashlib
    import hmac as hmac_mod

    from app.config import get_settings

    sig_exp = hmac_mod.new(
        get_settings().JWT_SECRET.encode(), expired_body.encode(), hashlib.sha256
    ).hexdigest()
    expired_cid = (
        base64.urlsafe_b64encode(expired_body.encode()).decode().rstrip("=") + "." + sig_exp
    )
    assert cap.verify(expired_cid, 8) is False

    # Garbage ids fail safely.
    assert cap.verify(None, 1) is False
    assert cap.verify("garbage", 1) is False
    assert cap.verify(cid, "not-a-number") is False


def test_generate_produces_fresh_ids():
    from app.core import captcha as cap

    seen = set()
    for _ in range(20):
        cid, q, a = cap.generate()
        assert cid not in seen
        seen.add(cid)
        parts = q.split()
        expected = int(parts[0]) + int(parts[2]) if parts[1] == "+" else int(parts[0]) - int(parts[2])
        assert a == expected
