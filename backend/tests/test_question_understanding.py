"""Question-understanding pipeline: clarify ambiguity, verdicts, comparisons."""

import re

from fastapi.testclient import TestClient


def _ask(client: TestClient, headers: dict, message: str) -> dict:
    resp = client.post("/api/chat/messages", json={"message": message}, headers=headers)
    assert resp.status_code == 201, resp.text
    return resp.json()["assistant_message"]


def test_ambiguous_place_reference_asks_clarification(client: TestClient, auth_user):
    """'there' with no resolvable antecedent must not produce an all-India dump."""
    msg = _ask(client, auth_user, "How is the water situation there?")
    assert msg["response_type"] == "clarify"
    assert "which location" in msg["content"].lower()


def test_resolved_followup_still_answers(client: TestClient, auth_user):
    """A location in the previous turn must carry over — no re-clarification."""
    first = client.post(
        "/api/chat/messages",
        json={"message": "What is the groundwater status of Telangana?"},
        headers=auth_user,
    )
    conv_id = first.json()["conversation_id"]
    follow = client.post(
        "/api/chat/messages",
        json={"message": "How is the water situation there?", "conversation_id": conv_id},
        headers=auth_user,
    )
    assert follow.status_code == 201, follow.text
    msg = follow.json()["assistant_message"]
    assert msg["response_type"] != "clarify"
    assert "Telangana" in (msg["location"] or "") or "Telangana" in msg["content"]


def test_whether_question_leads_with_verdict(client: TestClient, auth_user):
    msg = _ask(
        client,
        auth_user,
        "Is the stage of extraction rising or declining in Telangana?",
    )
    assert re.match(r"^\s*(Yes|No)\b", msg["content"]), msg["content"][:120]


def test_comparison_table_answer(client: TestClient, auth_user):
    msg = _ask(
        client,
        auth_user,
        "Compare groundwater in Telangana and Andhra Pradesh.",
    )
    assert "|" in msg["content"], "expected a markdown comparison table"
    assert "Recharge" in msg["content"]
    low = msg["content"].lower()
    assert "better shape" in low or "stage of extraction" in low
