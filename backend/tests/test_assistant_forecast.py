"""Tests for the assistant forecast & scenario features (Phase 20)."""

from fastapi.testclient import TestClient

from app.ai.assistant import (
    _extract_basin,
    _parse_scenario,
    classify_intent,
    extract_horizon,
)
from app.ingres import predict


def test_extract_basin():
    assert _extract_basin("What is the trend in the Godavari basin?") == "Godavari"
    assert _extract_basin("forecast stage for Krishna river basin") == "Krishna"
    assert _extract_basin("Ganga basin outlook") == "Ganga"
    assert _extract_basin("how about Telangana?") is None
    assert _extract_basin("explain recharge") is None


def test_forecast_basin(client: TestClient, db_session_factory):
    db = db_session_factory()
    try:
        fc = predict.forecast(db, basin="Godavari", metric="stage", horizon=3)
    finally:
        db.close()
    assert fc["forecast"]
    assert fc["basin"] == "Godavari"
    assert fc["scope"] == "Godavari"
    assert fc["unit"] == "%"


def test_chat_basin_forecast_answer(client: TestClient, auth_user):
    resp = client.post(
        "/api/chat/messages",
        json={"message": "What is the predicted trend in the Krishna river basin next 3 years?"},
        headers=auth_user,
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["intent"] == "forecast"
    content = body["assistant_message"]["content"]
    assert "Krishna river basin" in content


def test_classify_forecast_intent():
    assert classify_intent("What is the predicted trend in Telangana next 5 years?") == "forecast"
    assert classify_intent("Forecast stage of extraction in Punjab by 2030") == "forecast"
    assert classify_intent("What will the groundwater outlook be in 2030?") == "forecast"


def test_classify_scenario_intent():
    assert classify_intent("What if pumping increases 10%?") == "scenario"
    assert classify_intent("what if recharge decreases 20% in Telangana?") == "scenario"
    assert classify_intent("Show me the effect of reduced extraction in Guntur") == "scenario"


def test_classify_not_scenario():
    assert classify_intent("How much recharge is in Telangana?") == "data_query"
    assert classify_intent("Recharge in Guntur district") == "data_query"


def test_extract_horizon():
    assert extract_horizon("next 5 years") == 5
    assert extract_horizon("next 3 years") == 3
    assert extract_horizon("over the next 2 years") == 2
    assert extract_horizon("by 2030") == 8
    assert extract_horizon("what is the trend?") == 5


def test_parse_scenario():
    assert _parse_scenario("what if extraction decreases 20%") == {
        "metric": "extraction",
        "change_pct": -20,
    }
    assert _parse_scenario("what if recharge increases 10%") == {
        "metric": "recharge",
        "change_pct": 10,
    }
    assert _parse_scenario("what if pumping goes up") == {
        "metric": "extraction",
        "change_pct": 10,
    }
    assert _parse_scenario("recharge in Telangana") is None
    assert _parse_scenario("extraction increased from 2018") is None


def test_forecast_scenario_shifts_stage(client: TestClient, db_session_factory):
    db = db_session_factory()
    try:
        baseline = predict.forecast(db, state="Telangana", metric="stage", horizon=3)
        raised = predict.forecast(
            db,
            state="Telangana",
            metric="stage",
            horizon=3,
            scenario={"metric": "extraction", "change_pct": 20},
        )
        reduced = predict.forecast(
            db,
            state="Telangana",
            metric="stage",
            horizon=3,
            scenario={"metric": "recharge", "change_pct": -20},
        )
    finally:
        db.close()

    assert baseline["scenario"] is None
    assert raised["scenario"]["change_pct"] == 20
    assert reduced["scenario"]["change_pct"] == -20
    assert raised["forecast"]
    assert raised["end_value"] > baseline["end_value"]
    assert reduced["end_value"] > baseline["end_value"]


def test_chat_forecast_answer(client: TestClient, auth_user):
    resp = client.post(
        "/api/chat/messages",
        json={"message": "What is the predicted groundwater trend in Telangana next 3 years?"},
        headers=auth_user,
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["intent"] == "forecast"
    content = body["assistant_message"]["content"]
    assert "Projection" in content
    assert "95% forecast band" in content
    assert "⚠️" in content


def test_chat_scenario_answer(client: TestClient, auth_user):
    resp = client.post(
        "/api/chat/messages",
        json={"message": "What if pumping increases 10% in Telangana?"},
        headers=auth_user,
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["intent"] == "scenario"
    content = body["assistant_message"]["content"]
    assert "Scenario" in content
    assert "compared with" in content