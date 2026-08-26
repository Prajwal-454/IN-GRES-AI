from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

import pytest


def test_create_and_list_conversation(client: TestClient, auth_user):
    created = client.post("/api/chat/conversations", json={}, headers=auth_user)
    assert created.status_code == 201, created.text
    conv_id = created.json()["id"]

    listed = client.get("/api/chat/conversations", headers=auth_user)
    assert listed.status_code == 200
    assert any(c["id"] == conv_id for c in listed.json())


def test_send_data_query(client: TestClient, auth_user):
    resp = client.post(
        "/api/chat/messages",
        json={"message": "What is the stage of extraction in Telangana?"},
        headers=auth_user,
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["assistant_message"]["content"]
    assert body["assistant_message"]["is_demo"] is False
    assert "latency_ms" in body


def test_send_terminology_query(client: TestClient, auth_user):
    resp = client.post(
        "/api/chat/messages",
        json={"message": "What is an aquifer?"},
        headers=auth_user,
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["assistant_message"]["response_type"] in ("terminology", "knowledge")
    assert body["assistant_message"]["content"]


def test_send_telugu_query(client: TestClient, auth_user):
    resp = client.post(
        "/api/chat/messages",
        json={"message": "తెలంగాణలో భూగర్భజల పరిస్థితి ఎలా ఉంది?"},
        headers=auth_user,
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["language"] in ("te", "en")
    assert body["assistant_message"]["content"]


def test_send_hindi_query(client: TestClient, auth_user):
    resp = client.post(
        "/api/chat/messages",
        json={"message": "गुंटूर जिले में पुनर्भरण क्या है?"},
        headers=auth_user,
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["assistant_message"]["content"]


def test_websocket_chat(client: TestClient, user_token: str):
    with client.websocket_connect(f"/api/chat/ws/chat?token={user_token}") as ws:
        ws.send_json({"message": "Recharge in Guntur district"})
        reply = ws.receive_json()
        assert reply["content"]
        assert reply["conversation_id"] > 0
        assert "latency_ms" in reply


def test_websocket_rejects_bad_token(client: TestClient):
    with pytest.raises(WebSocketDisconnect) as exc_info:
        with client.websocket_connect("/api/chat/ws/chat?token=bogus"):
            pass
    assert exc_info.value.code in (1008, 4401)


def test_chat_requires_auth(client: TestClient):
    assert client.post("/api/chat/messages", json={"message": "hi"}).status_code == 401


def test_chat_voice_detects_language(client: TestClient, auth_user):
    payload = (
        '{"text": "తెలంగాణలో భూగర్భజల పరిస్థితి ఎలా ఉంది?", "language": "te"}'
    ).encode("utf-8")
    resp = client.post(
        "/api/chat/voice",
        files={"audio": ("recording.webm", payload, "audio/webm")},
        headers=auth_user,
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["transcript"].strip()
    assert body["detected_language"] == "te"
    assert body["assistant_message"]["content"]
    assert body["stt_provider"] == "mock"
    assert body["tts_has_audio"] is False
    assert body["audio_base64"]
    assert "audio_format" in body


def test_chat_voice_empty_audio(client: TestClient, auth_user):
    resp = client.post(
        "/api/chat/voice",
        files={"audio": ("recording.webm", b"", "audio/webm")},
        headers=auth_user,
    )
    assert resp.status_code == 422


def test_chat_voice_no_speech(client: TestClient, auth_user):
    resp = client.post(
        "/api/chat/voice",
        files={"audio": ("recording.webm", b"\x00\x01\x02", "audio/webm")},
        headers=auth_user,
    )
    assert resp.status_code == 422