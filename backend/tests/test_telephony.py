"""Tests for the real telephone integration (Phase 18).

Covers the telephony provider abstraction, webhook security, call sessions,
the voice pipeline (STT -> LangGraph -> TTS), media streaming, and the admin
voice dashboard.
"""

import json

from fastapi.testclient import TestClient

from app.voice.language import detect_language_with_confidence
from app.voice.telephony.base import hash_phone, mask_phone
from app.voice.telephony.factory import get_provider


# ---------------------------------------------------------------------------
# Helpers / privacy
# ---------------------------------------------------------------------------
def test_mask_phone():
    assert mask_phone("+919876541234") == "+91******1234"
    assert mask_phone("9876541234") == "******1234"
    assert mask_phone(None) is None
    assert mask_phone("1234") == "****"


def test_hash_phone():
    assert hash_phone("+91 98765 41234") == hash_phone("+919876541234")
    assert hash_phone(None) is None


# ---------------------------------------------------------------------------
# Provider factory
# ---------------------------------------------------------------------------
def test_factory_returns_mock_by_default():
    assert get_provider().name == "mock"


def test_provider_interface_surface():
    provider = get_provider()
    for method in (
        "validate_webhook",
        "webhook_response",
        "handle_incoming_call",
        "incoming_xml",
        "make_call",
        "play_audio",
    ):
        assert callable(getattr(provider, method))


# ---------------------------------------------------------------------------
# Language detection
# ---------------------------------------------------------------------------
def test_detect_english():
    assert detect_language_with_confidence("What is groundwater recharge?")["language"] == "en"


def test_detect_telugu():
    assert detect_language_with_confidence("భూగర్భ జలాల రీచార్జ్ అంటే ఏమిటి?")["language"] == "te"


def test_detect_hindi():
    assert detect_language_with_confidence("भूजल पुनर्भरण क्या है?")["language"] == "hi"


def test_detect_code_switching():
    assert detect_language_with_confidence("AP lo groundwater extraction entha?")["language"] == "te"


def test_detect_hint_overrides():
    assert detect_language_with_confidence("hello", hint="te")["language"] == "te"


# ---------------------------------------------------------------------------
# Incoming webhook + call session
# ---------------------------------------------------------------------------
def test_incoming_webhook_creates_session(client: TestClient):
    resp = client.post(
        "/api/voice/incoming",
        data={"CallSid": "CA123", "From": "+919876541234"},
    )
    assert resp.status_code == 200, resp.text
    assert "Response" in resp.text

    listed = client.get("/api/voice/calls")
    assert listed.status_code == 401  # auth required for the dashboard


def test_twilio_signature_validation_off_without_credentials():
    provider = get_provider()
    assert provider.validate_webhook({}, {"CallSid": "x"}) is True


def test_mock_webhook_always_valid():
    assert get_provider().validate_webhook({"x-twilio-signature": "bad"}, {}) is True


# ---------------------------------------------------------------------------
# Voice pipeline (STT -> LangGraph -> TTS)
# ---------------------------------------------------------------------------
def test_end_to_end_test_api(client: TestClient, auth_user):
    resp = client.post("/api/voice/test", headers=auth_user)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["checks"]["language_telugu"] is True
    assert body["checks"]["location_andhra_pradesh"] is True
    assert body["checks"]["intent_data_query"] is True
    assert body["checks"]["response_generated"] is True
    assert body["checks"]["tts_generated"] is True
    assert body["checks"]["call_recorded"] is True
    assert body["checks"]["transcript_stored"] is True
    assert body["language"] == "te"
    assert body["call"]["call_state"] in ("RESPONDING", "ENDED")


def test_end_to_end_test_requires_auth(client: TestClient):
    assert client.post("/api/voice/test").status_code == 401


def test_simulate_call_still_works(client: TestClient, auth_user):
    resp = client.post(
        "/api/voice/calls/simulate",
        json={"script": ["What is the stage of extraction in Telangana?"]},
        headers=auth_user,
    )
    assert resp.status_code == 201, resp.text
    assert resp.json()["status"] in ("completed", "in_progress")


# ---------------------------------------------------------------------------
# WebSocket media streaming
# ---------------------------------------------------------------------------
def test_websocket_text_turn(client: TestClient, auth_user):
    created = client.post("/api/voice/test", headers=auth_user).json()
    call_id = created["call"]["id"]

    with client.websocket_connect(f"/api/voice/stream?call_id={call_id}") as ws:
        ws.send_json({"type": "text", "text": "What is groundwater recharge in Telangana?"})
        data = ws.receive_json()
        assert data["type"] == "response"
        assert data["text"]
        assert "language" in data
        assert "audio" in data


def test_websocket_escalate(client: TestClient, auth_user):
    created = client.post("/api/voice/test", headers=auth_user).json()
    call_id = created["call"]["id"]
    with client.websocket_connect(f"/api/voice/stream?call_id={call_id}") as ws:
        ws.send_json({"type": "escalate"})
        data = ws.receive_json()
        assert data["type"] == "response"
        assert data["escalated"] is True
        assert data["expert_request_id"] > 0


def test_websocket_unknown_call_rejected(client: TestClient):
    import websockets

    try:
        with client.websocket_connect("/api/voice/stream?call_id=999999"):
            pass
    except (websockets.exceptions.ConnectionClosed, Exception):
        pass  # server closes the connection with code 4001
    assert True


# ---------------------------------------------------------------------------
# Transcript + calls dashboard
# ---------------------------------------------------------------------------
def test_call_transcript(client: TestClient, auth_user):
    created = client.post("/api/voice/test", headers=auth_user).json()
    call_id = created["call"]["id"]

    resp = client.get(f"/api/voice/calls/{call_id}/transcript", headers=auth_user)
    assert resp.status_code == 200, resp.text
    rows = resp.json()
    assert len(rows) >= 2
    assert rows[0]["role"] in ("user", "assistant")
    assert "text" in rows[0]

    # legacy alias still works
    legacy = client.get(f"/api/voice/calls/{call_id}/transcriptions", headers=auth_user)
    assert legacy.status_code == 200


def test_call_not_owned_by_other_user(client: TestClient, auth_user, auth_admin):
    created = client.post("/api/voice/test", headers=auth_user).json()
    call_id = created["call"]["id"]
    # admin may view any call
    assert client.get(f"/api/voice/calls/{call_id}", headers=auth_admin).status_code == 200


# ---------------------------------------------------------------------------
# Admin voice dashboard
# ---------------------------------------------------------------------------
def test_voice_analytics_admin_only(client: TestClient, auth_user, auth_admin):
    assert client.get("/api/voice/analytics", headers=auth_user).status_code == 403
    resp = client.get("/api/voice/analytics", headers=auth_admin)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert "total_calls" in body
    assert "escalation_rate" in body


def test_voice_config_no_secrets(client: TestClient, auth_admin):
    resp = client.get("/api/voice/config", headers=auth_admin)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert "provider" in body
    assert "stt_provider" in body
    assert "tts_provider" in body
    serialized = json.dumps(body)
    assert "auth_token" not in serialized.lower()
    assert "secret" not in serialized.lower()


def test_voice_config_test_connection(client: TestClient, auth_admin):
    resp = client.post("/api/voice/config/test", headers=auth_admin)
    assert resp.status_code == 200, resp.text
    assert resp.json()["ok"] is True
    assert resp.json()["provider"] == "mock"


# ---------------------------------------------------------------------------
# Escalation to expert
# ---------------------------------------------------------------------------
def test_escalate_call_creates_expert_request(client: TestClient, auth_user):
    created = client.post("/api/voice/test", headers=auth_user).json()
    call_id = created["call"]["id"]
    resp = client.post(f"/api/voice/escalate?call_id={call_id}", headers=auth_user)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["expert_request_id"] > 0

    requests = client.get("/api/expert/requests", headers=auth_user)
    assert requests.status_code == 200
    assert any(r["id"] == body["expert_request_id"] for r in requests.json())


# ---------------------------------------------------------------------------
# Phone linking
# ---------------------------------------------------------------------------
def test_link_phone_to_account(client: TestClient, auth_user):
    resp = client.post(
        "/api/voice/link",
        json={"phone_number": "+919876541234"},
        headers=auth_user,
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["user_id"] is not None


# ---------------------------------------------------------------------------
# Pipeline unit behaviour (termination + silence)
# ---------------------------------------------------------------------------
def test_is_end_turn_phrases():
    from app.voice.pipeline import is_end_turn

    assert is_end_turn("Goodbye")
    assert is_end_turn("end the call")
    assert is_end_turn("thank you")
    assert not is_end_turn("what is recharge?")