"""Tests for multi-turn chat memory (context carry-over)."""

from fastapi.testclient import TestClient


def test_follow_up_carries_over_location(client: TestClient, auth_user):
    # First turn establishes a location.
    first = client.post(
        "/api/chat/messages",
        json={"message": "What is the recharge in Andhra Pradesh?"},
        headers=auth_user,
    )
    assert first.status_code == 201, first.text
    conv_id = first.json()["conversation_id"]
    assert first.json()["assistant_message"]["location"] == "Andhra Pradesh"

    # Follow-up omits the location but keeps the state metric.
    second = client.post(
        "/api/chat/messages",
        json={"message": "What about stage of extraction?", "conversation_id": conv_id},
        headers=auth_user,
    )
    assert second.status_code == 201, second.text
    body = second.json()
    assert body["assistant_message"]["location"] == "Andhra Pradesh"
    assert "Andhra Pradesh" in body["assistant_message"]["content"]
    assert body["assistant_message"]["is_demo"] is True


def test_follow_up_carries_over_metric(client: TestClient, auth_user):
    first = client.post(
        "/api/chat/messages",
        json={"message": "What is the recharge in Telangana?"},
        headers=auth_user,
    )
    conv_id = first.json()["conversation_id"]

    # Follow-up names a new location but no metric; metric should carry over.
    second = client.post(
        "/api/chat/messages",
        json={"message": "and in Guntur?", "conversation_id": conv_id},
        headers=auth_user,
    )
    assert second.status_code == 201, second.text
    content = second.json()["assistant_message"]["content"].lower()
    assert "recharge" in content
