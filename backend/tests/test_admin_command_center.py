"""Admin command centre: overview, query monitor and model metrics."""

from fastapi.testclient import TestClient


def test_overview_requires_admin(client: TestClient, auth_user):
    resp = client.get("/api/admin/overview", headers=auth_user)
    assert resp.status_code == 403


def test_overview_payload_shape(client: TestClient, auth_admin):
    # Make sure at least one exchange exists for the queries section.
    client.post(
        "/api/chat/messages",
        json={"message": "What is an aquifer?"},
        headers=auth_admin,
    )
    resp = client.get("/api/admin/overview", headers=auth_admin)
    assert resp.status_code == 200, resp.text
    body = resp.json()

    gw = body["groundwater"]
    assert gw["assessment_units"] > 0
    assert gw["recharge_hm3"] > 0
    assert gw["extraction_hm3"] > 0
    assert isinstance(gw["category_counts"], dict) and gw["category_counts"]
    assert isinstance(gw["critical_zones"], list)

    ai = body["ai"]
    assert "llm_enabled" in ai and "rag_documents" in ai

    q = body["queries"]
    assert q["messages"] > 0
    assert isinstance(q["intent_counts"], dict)
    assert body["users"]["total"] >= 2

    sysinfo = body["system"]
    assert sysinfo["database_ok"] is True


def test_query_monitor_lists_answers(client: TestClient, auth_user, auth_admin):
    # Ensure at least one exchange exists.
    client.post(
        "/api/chat/messages",
        json={"message": "What is an aquifer?"},
        headers=auth_user,
    )
    resp = client.get("/api/admin/queries?limit=5", headers=auth_admin)
    assert resp.status_code == 200, resp.text
    rows = resp.json()
    assert rows, "expected at least one assistant answer"
    top = rows[0]
    for field in ("intent", "response_type", "language", "question"):
        assert field in top


def test_model_metrics_cached(client: TestClient, auth_admin):
    resp = client.get("/api/admin/models/metrics", headers=auth_admin)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["state"] == "Telangana"
    if not body.get("error"):
        assert isinstance(body["models"], list)
        assert body["models"], "expected backtest metrics"
        first = body["models"][0]
        for field in ("model", "rmse", "mae", "mape"):
            assert field in first
        # Cached second call returns the same payload shape.
        again = client.get("/api/admin/models/metrics", headers=auth_admin).json()
        assert again["best_model"] == body["best_model"]
