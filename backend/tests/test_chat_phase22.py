"""Phase 22: feedback loop, regeneration, follow-ups and Markdown export."""

from fastapi.testclient import TestClient


def _send(client: TestClient, headers: dict, message: str) -> dict:
    resp = client.post("/api/chat/messages", json={"message": message}, headers=headers)
    assert resp.status_code == 201, resp.text
    return resp.json()


def test_followups_attached_to_data_answer(client: TestClient, auth_user):
    body = _send(client, auth_user, "What is the stage of extraction in Telangana?")
    followups = body["assistant_message"]["followups"]
    assert isinstance(followups, list)
    assert 0 < len(followups) <= 3
    assert all(isinstance(q, str) and q for q in followups)


def test_feedback_roundtrip(client: TestClient, auth_user):
    body = _send(client, auth_user, "What is recharge in Guntur district?")
    msg_id = body["assistant_message"]["id"]

    rated = client.post(
        f"/api/chat/messages/{msg_id}/feedback",
        json={"rating": 1, "note": "clear answer"},
        headers=auth_user,
    )
    assert rated.status_code == 200, rated.text
    assert rated.json()["rating"] == 1

    # The rating is persisted and comes back with the conversation history.
    conv_id = body["conversation_id"]
    history = client.get(
        f"/api/chat/conversations/{conv_id}/messages", headers=auth_user
    ).json()
    stored = next(m for m in history if m["id"] == msg_id)
    assert stored["rating"] == 1
    assert stored["rating_note"] == "clear answer"

    # Re-rating overwrites the previous value.
    rerated = client.post(
        f"/api/chat/messages/{msg_id}/feedback",
        json={"rating": -1},
        headers=auth_user,
    )
    assert rerated.status_code == 200
    assert rerated.json()["rating"] == -1
    assert rerated.json()["rating_note"] is None


def test_feedback_rejects_invalid_rating(client: TestClient, auth_user):
    body = _send(client, auth_user, "Recharge in Krishna district?")
    msg_id = body["assistant_message"]["id"]
    resp = client.post(
        f"/api/chat/messages/{msg_id}/feedback",
        json={"rating": 5},
        headers=auth_user,
    )
    assert resp.status_code == 422


def test_feedback_rejects_user_message(client: TestClient, auth_user):
    body = _send(client, auth_user, "What is an aquifer?")
    user_msg_id = body["user_message"]["id"]
    resp = client.post(
        f"/api/chat/messages/{user_msg_id}/feedback",
        json={"rating": 1},
        headers=auth_user,
    )
    assert resp.status_code == 422


def test_feedback_unknown_and_foreign_messages(client: TestClient, auth_user, auth_admin):
    assert (
        client.post(
            "/api/chat/messages/99999999/feedback",
            json={"rating": 1},
            headers=auth_user,
        ).status_code
        == 404
    )
    # Another account must not be able to rate someone else's message.
    body = _send(client, auth_user, "What is the stage of extraction in Punjab?")
    foreign = client.post(
        f"/api/chat/messages/{body['assistant_message']['id']}/feedback",
        json={"rating": -1},
        headers=auth_admin,
    )
    assert foreign.status_code == 404


def test_regenerate_replaces_last_answer(client: TestClient, auth_user):
    body = _send(client, auth_user, "What is the groundwater status of Telangana?")
    conv_id = body["conversation_id"]
    old_assistant_id = body["assistant_message"]["id"]

    regen = client.post(
        f"/api/chat/conversations/{conv_id}/regenerate", headers=auth_user
    )
    assert regen.status_code == 200, regen.text
    new_msg = regen.json()["assistant_message"]
    assert new_msg["id"] != old_assistant_id
    assert new_msg["role"] == "assistant"
    assert new_msg["content"]

    history = client.get(
        f"/api/chat/conversations/{conv_id}/messages", headers=auth_user
    ).json()
    ids = [m["id"] for m in history]
    assert old_assistant_id not in ids
    assert sum(1 for m in history if m["role"] == "assistant") == 1


def test_regenerate_requires_a_question(client: TestClient, auth_user):
    created = client.post("/api/chat/conversations", json={}, headers=auth_user)
    conv_id = created.json()["id"]
    resp = client.post(
        f"/api/chat/conversations/{conv_id}/regenerate", headers=auth_user
    )
    assert resp.status_code == 422


def test_bulk_delete_only_owned(client: TestClient, auth_user, auth_admin):
    ids = []
    for q in ("Bulk one?", "Bulk two?"):
        body = _send(client, auth_user, q)
        ids.append(body["conversation_id"])
    foreign = client.post("/api/chat/conversations", json={}, headers=auth_admin)
    foreign_id = foreign.json()["id"]

    resp = client.post(
        "/api/chat/conversations/bulk-delete",
        json={"ids": [*ids, foreign_id, 99999999]},
        headers=auth_user,
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert sorted(body["deleted"]) == sorted(ids)
    assert body["count"] == 2

    remaining = client.get("/api/chat/conversations", headers=auth_user).json()
    assert not any(c["id"] in ids for c in remaining)
    # The admin's conversation is untouched.
    admin_convs = client.get("/api/chat/conversations", headers=auth_admin).json()
    assert any(c["id"] == foreign_id for c in admin_convs)


def test_bulk_delete_requires_ids(client: TestClient, auth_user):
    resp = client.post(
        "/api/chat/conversations/bulk-delete", json={"ids": []}, headers=auth_user
    )
    assert resp.status_code == 422


def test_export_conversation_markdown(client: TestClient, auth_user):
    body = _send(
        client, auth_user, "What is the stage of extraction in Telangana?"
    )
    conv_id = body["conversation_id"]
    exported = client.get(
        f"/api/chat/conversations/{conv_id}/export", headers=auth_user
    )
    assert exported.status_code == 200, exported.text
    assert "text/markdown" in exported.headers["content-type"]
    assert "attachment" in exported.headers.get("content-disposition", "")
    text = exported.content.decode("utf-8")
    assert body["user_message"]["content"] in text
    assert body["assistant_message"]["content"] in text
    assert "IN-GRES Assistant" in text
