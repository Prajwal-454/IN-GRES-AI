"""Web-search fallback: when the knowledge base has nothing, search the web."""

from fastapi.testclient import TestClient

from app.ai.assistant import AnswerResult


GENERAL_QUESTION = "Who wrote Romeo and Juliet?"

WEB_HIT = {
    "title": "Example news",
    "url": "https://example.org/article",
    "snippet": "The answer is 42.",
}


def _enable_llm(monkeypatch):
    from app.config import get_settings

    settings = get_settings()
    monkeypatch.setattr(settings, "LLM_ENABLED", True)
    monkeypatch.setattr(settings, "WEB_SEARCH_ENABLED", True)


def test_dataset_miss_triggers_web_search(client: TestClient, auth_user, monkeypatch):
    """A data question the dataset cannot answer falls back to web + LLM."""
    _enable_llm(monkeypatch)
    captured: dict = {}

    def fake_answer(text, db, language, context=None):
        return AnswerResult(
            content="I could not find any groundwater assessment data to rank.",
            response_type="data",
            intent="data_query",
            language=language or "en",
            location=None,
            sources=[],
            is_demo=False,
        )

    def fake_generate(text, language, chunks=None, history=None, web_results=None):
        captured["web_results"] = web_results
        return AnswerResult(
            content="The Ganga basin is the largest in India.",
            response_type="conversational",
            intent="fallback",
            language="en",
            sources=["Web search", WEB_HIT["url"]],
            is_demo=False,
        )

    monkeypatch.setattr("app.ai.orchestrator.answer", fake_answer)
    monkeypatch.setattr("app.ai.orchestrator.llm_generate", fake_generate)

    import app.rag.websearch as websearch_module

    monkeypatch.setattr(
        websearch_module, "search", lambda q, max_results=None: [dict(WEB_HIT)]
    )

    resp = client.post(
        "/api/chat/messages",
        json={"message": "Which districts are over-exploited?"},
        headers=auth_user,
    )
    assert resp.status_code == 201, resp.text
    msg = resp.json()["assistant_message"]
    assert "Ganga basin" in msg["content"]
    assert "not covered" not in msg["content"].lower(), "no disclaimer prefix"
    assert captured["web_results"] == [dict(WEB_HIT)]
    assert any("example.org" in s for s in (msg["sources"] or []))


def test_dataset_hit_skips_web_and_llm(client: TestClient, auth_user, monkeypatch):
    """A normal data answer must never trigger a web round-trip."""
    from app.config import get_settings

    settings = get_settings()
    monkeypatch.setattr(settings, "WEB_SEARCH_ENABLED", True)
    calls = {"web": 0, "llm": 0}

    def fake_answer(text, db, language, context=None):
        return AnswerResult(
            content="Stage of extraction in Telangana is about 63% (demo).",
            response_type="data",
            intent="data_query",
            language="en",
            location="Telangana",
            sources=[],
            is_demo=True,
        )

    def fail_generate(*a, **kwargs):
        calls["llm"] += 1
        raise AssertionError("LLM must not be called for answered data queries")

    monkeypatch.setattr("app.ai.orchestrator.answer", fake_answer)
    monkeypatch.setattr("app.ai.orchestrator.llm_generate", fail_generate)

    import app.rag.websearch as websearch_module

    def fail_search(q, max_results=None):
        calls["web"] += 1
        return []

    monkeypatch.setattr(websearch_module, "search", fail_search)

    resp = client.post(
        "/api/chat/messages",
        json={"message": "What is the stage of extraction in Telangana?"},
        headers=auth_user,
    )
    assert resp.status_code == 201, resp.text
    msg = resp.json()["assistant_message"]
    assert "63%" in msg["content"]
    assert calls == {"web": 0, "llm": 0}


def test_search_model_answers_general_questions(client: TestClient, auth_user, monkeypatch):
    """With a search-native model available, general questions use it (no ddgs)."""
    _enable_llm(monkeypatch)
    calls = {"ddgs": 0, "plain_llm": 0}

    def fake_search_model(text, language, history=None):
        return AnswerResult(
            content="Compound searched the web for you.",
            response_type="conversational",
            intent="fallback",
            language="en",
            sources=["Web search", "https://example.org/a"],
            is_demo=False,
        )

    monkeypatch.setattr("app.ai.orchestrator.rag_search", lambda db, t, top_k=3: [])
    monkeypatch.setattr(
        "app.ai.orchestrator.llm_generate_search", fake_search_model
    )

    def fail_plain_llm(*a, **kwargs):
        calls["plain_llm"] += 1
        return None

    import app.rag.websearch as websearch_module

    def fail_ddgs(q, max_results=None):
        calls["ddgs"] += 1
        return []

    monkeypatch.setattr(websearch_module, "search", fail_ddgs)
    monkeypatch.setattr("app.ai.orchestrator.llm_generate", fail_plain_llm)

    resp = client.post(
        "/api/chat/messages",
        json={"message": GENERAL_QUESTION},
        headers=auth_user,
    )
    assert resp.status_code == 201, resp.text
    msg = resp.json()["assistant_message"]
    assert msg["content"] == "Compound searched the web for you."
    assert any("example.org" in s for s in (msg["sources"] or []))
    assert calls == {"ddgs": 0, "plain_llm": 0}


def test_web_search_used_when_kb_empty(client: TestClient, auth_user, monkeypatch):
    _enable_llm(monkeypatch)
    captured: dict = {}

    def fake_generate(text, language, chunks=None, history=None, web_results=None):
        captured["chunks"] = chunks
        captured["web_results"] = web_results
        return AnswerResult(
            content="42, according to Example news.",
            response_type="conversational",
            intent="fallback",
            language="en",
            sources=["Web search", WEB_HIT["url"]],
            is_demo=False,
        )

    monkeypatch.setattr("app.ai.orchestrator.rag_search", lambda db, t, top_k=3: [])
    monkeypatch.setattr("app.ai.orchestrator.llm_generate", fake_generate)

    import app.rag.websearch as websearch_module

    def fake_search(query, max_results=None):
        captured["query"] = query
        return [dict(WEB_HIT)]

    monkeypatch.setattr(websearch_module, "search", fake_search)

    resp = client.post(
        "/api/chat/messages", json={"message": GENERAL_QUESTION}, headers=auth_user
    )
    assert resp.status_code == 201, resp.text
    msg = resp.json()["assistant_message"]
    assert msg["content"] == "42, according to Example news."
    assert captured["query"] == GENERAL_QUESTION
    # The web hit reached the LLM as context and its URL is cited on the message.
    assert captured["web_results"] == [dict(WEB_HIT)]
    assert any("example.org" in s for s in (msg["sources"] or []))


def test_no_web_search_when_kb_has_hits(client: TestClient, auth_user, monkeypatch):
    _enable_llm(monkeypatch)
    calls = {"search": 0}

    def fake_generate(text, language, chunks=None, history=None, web_results=None):
        return AnswerResult(
            content="kb answer",
            response_type="knowledge",
            intent="fallback",
            language="en",
            sources=["IN-GRES AI knowledge base"],
            is_demo=False,
        )

    monkeypatch.setattr(
        "app.ai.orchestrator.rag_search",
        lambda db, t, top_k=3: [("Solid knowledge chunk about aquifers.", 10.0)],
    )
    monkeypatch.setattr("app.ai.orchestrator.llm_generate", fake_generate)

    import app.rag.websearch as websearch_module

    def fail_search(query, max_results=None):
        calls["search"] += 1
        return []

    monkeypatch.setattr(websearch_module, "search", fail_search)

    resp = client.post(
        "/api/chat/messages",
        json={"message": "What is an aquifer exactly?"},
        headers=auth_user,
    )
    assert resp.status_code == 201, resp.text
    assert calls["search"] == 0, "KB hits should prevent a web round-trip"


def test_web_search_disabled_never_called(client: TestClient, auth_user, monkeypatch):
    from app.config import get_settings

    settings = get_settings()
    # Web search OFF (as conftest sets it) even though the LLM is available.
    monkeypatch.setattr(settings, "LLM_ENABLED", True)
    assert settings.WEB_SEARCH_ENABLED is False

    import app.rag.websearch as websearch_module

    def fail_search(query, max_results=None):
        raise AssertionError("network must not be touched when disabled")

    monkeypatch.setattr(websearch_module, "search", fail_search)
    # With web search off and an empty KB, the answer comes from the heuristic
    # assistant; the point of this test is that search() above never runs.
    resp = client.post(
        "/api/chat/messages",
        json={"message": GENERAL_QUESTION},
        headers=auth_user,
    )
    assert resp.status_code == 201, resp.text


def test_search_returns_empty_when_disabled():
    from app.config import get_settings
    from app.rag.websearch import search

    settings = get_settings()
    original = settings.WEB_SEARCH_ENABLED
    settings.WEB_SEARCH_ENABLED = False
    try:
        assert search("anything") == []
    finally:
        settings.WEB_SEARCH_ENABLED = original


def test_search_parses_ddgs_rows(monkeypatch):
    import sys
    import types

    from app.config import get_settings
    from app.rag.websearch import search

    settings = get_settings()
    original = settings.WEB_SEARCH_ENABLED
    settings.WEB_SEARCH_ENABLED = True

    class FakeDDGS:
        def __init__(self, timeout=None):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def text(self, query, max_results=5):
            yield {"title": "T", "href": "https://a.example/x", "body": "b"}
            yield {"title": "row without url"}

    fake_mod = types.ModuleType("ddgs")
    fake_mod.DDGS = FakeDDGS  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "ddgs", fake_mod)
    try:
        assert search("test query") == [
            {"title": "T", "url": "https://a.example/x", "snippet": "b"}
        ]
    finally:
        settings.WEB_SEARCH_ENABLED = original
