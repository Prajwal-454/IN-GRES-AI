"""LLM_FULL_CONTROL: Groq composes every reply from verified dataset facts."""

from fastapi.testclient import TestClient


def _enable_full_control(monkeypatch):
    from app.config import get_settings

    s = get_settings()
    monkeypatch.setattr(s, "LLM_ENABLED", True)
    monkeypatch.setattr(s, "LLM_FULL_CONTROL", True)


def test_data_answer_composed_by_llm(client: TestClient, auth_user, monkeypatch):
    captured: dict = {}

    def fake_compose(text, language, facts, history=None):
        captured["facts"] = facts
        return "COMPOSED REPLY ABOUT TELANGANA"

    monkeypatch.setattr("app.ai.orchestrator.compose_answer", fake_compose)
    _enable_full_control(monkeypatch)

    resp = client.post(
        "/api/chat/messages",
        json={"message": "What is the stage of extraction in Telangana?"},
        headers=auth_user,
    )
    assert resp.status_code == 201, resp.text
    msg = resp.json()["assistant_message"]
    assert msg["content"].startswith("COMPOSED REPLY")
    # The verified dataset facts reached the composer...
    assert "Telangana" in captured["facts"]
    assert "%" in captured["facts"]
    # ...and the structured cards still render (intent preserved).
    assert msg["intent"] == "data_query"
    assert msg["response_type"] == "data"
    assert msg["is_demo"] is True


def test_falls_back_to_template_when_llm_fails(client: TestClient, auth_user, monkeypatch):
    def fail_compose(text, language, facts, history=None):
        return None

    monkeypatch.setattr("app.ai.orchestrator.compose_answer", fail_compose)
    _enable_full_control(monkeypatch)

    resp = client.post(
        "/api/chat/messages",
        json={"message": "What is the recharge in Guntur district?"},
        headers=auth_user,
    )
    assert resp.status_code == 201, resp.text
    msg = resp.json()["assistant_message"]
    # Template answer survives untouched.
    assert "COMPOSED" not in msg["content"]
    assert "recharge" in msg["content"].lower()


def test_disabled_keeps_hybrid_behaviour(client: TestClient, auth_user, monkeypatch):
    from app.config import get_settings

    settings = get_settings()
    monkeypatch.setattr(settings, "LLM_ENABLED", True)
    monkeypatch.setattr(settings, "LLM_FULL_CONTROL", False)

    def fail_compose(text, language, facts, history=None):
        raise AssertionError("composer must not run when full control is off")

    monkeypatch.setattr("app.ai.orchestrator.compose_answer", fail_compose)

    resp = client.post(
        "/api/chat/messages",
        json={"message": "What is the groundwater status of Punjab?"},
        headers=auth_user,
    )
    assert resp.status_code == 201, resp.text
