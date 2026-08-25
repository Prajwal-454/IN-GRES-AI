"""Tests for rich structured assistant sections (Answer/Data/Map/Graph/
Prediction/Explanation/Recommendation)."""

from fastapi.testclient import TestClient


def test_classify_recommend_and_why():
    from app.ai.assistant import classify_intent

    assert classify_intent("What measures can reduce groundwater extraction?") == "recommend"
    assert classify_intent("How can we conserve groundwater?") == "recommend"
    assert classify_intent("Which districts are over-exploited?") == "data_query"
    assert classify_intent("Why is groundwater declining in Andhra Pradesh?") == "data_query"
    assert classify_intent("Predict groundwater availability for the next 5 years") == "forecast"


def test_data_query_returns_sections(client: TestClient, auth_user):
    resp = client.post(
        "/api/chat/messages",
        json={"message": "What is the stage of extraction in Telangana?"},
        headers=auth_user,
    )
    assert resp.status_code == 201, resp.text
    msg = resp.json()["assistant_message"]
    assert msg["sections"] is not None
    sec = msg["sections"]
    assert sec["mode"] == "data"
    assert "data" in sec and "map" in sec and "graph" in sec
    assert sec["data"]["scope"] == "Telangana"
    assert sec["data"]["stage"] is not None
    assert sec["map"]["state"] == "Telangana"
    assert sec["map"]["district"] is None
    assert sec["explanation"]
    assert sec["recommendation"]


def test_over_exploited_districts_returns_ranking(client: TestClient, auth_user):
    resp = client.post(
        "/api/chat/messages",
        json={"message": "Which districts are over-exploited in Andhra Pradesh?"},
        headers=auth_user,
    )
    assert resp.status_code == 201, resp.text
    sec = resp.json()["assistant_message"]["sections"]
    assert sec["mode"] == "data"
    assert sec["data"]["ranking"]
    assert any(r["category"] == "Over-exploited" for r in sec["data"]["ranking"])


def test_forecast_returns_prediction(client: TestClient, auth_user):
    resp = client.post(
        "/api/chat/messages",
        json={
            "message": "Predict groundwater availability for the next 5 years in Telangana"
        },
        headers=auth_user,
    )
    assert resp.status_code == 201, resp.text
    msg = resp.json()["assistant_message"]
    assert msg["intent"] == "forecast"
    sec = msg["sections"]
    assert sec["mode"] == "forecast"
    assert sec["prediction"] and sec["prediction"]["points"]
    assert sec["graph"]["forecast"]


def test_scenario_returns_prediction(client: TestClient, auth_user):
    resp = client.post(
        "/api/chat/messages",
        json={"message": "What if pumping increases 10% in Telangana?"},
        headers=auth_user,
    )
    assert resp.status_code == 201, resp.text
    sec = resp.json()["assistant_message"]["sections"]
    assert sec["mode"] == "scenario"
    assert sec["prediction"] and sec["prediction"]["points"]
    assert sec["graph"]["scenario_forecast"]


def test_recommend_returns_recommendations(client: TestClient, auth_user):
    resp = client.post(
        "/api/chat/messages",
        json={"message": "What measures can reduce groundwater extraction?"},
        headers=auth_user,
    )
    assert resp.status_code == 201, resp.text
    msg = resp.json()["assistant_message"]
    assert msg["intent"] == "recommend"
    sec = msg["sections"]
    assert sec["mode"] == "recommend"
    assert len(sec["recommendation"]) > 0
    assert sec["explanation"]
    assert "map" not in sec


def test_why_returns_sections(client: TestClient, auth_user):
    resp = client.post(
        "/api/chat/messages",
        json={"message": "Why is groundwater declining in Andhra Pradesh?"},
        headers=auth_user,
    )
    assert resp.status_code == 201, resp.text
    sec = resp.json()["assistant_message"]["sections"]
    assert sec is not None
    assert sec["mode"] == "data"
    assert "explanation" in sec


def test_terminology_has_no_sections(client: TestClient, auth_user):
    resp = client.post(
        "/api/chat/messages",
        json={"message": "What is an aquifer?"},
        headers=auth_user,
    )
    assert resp.status_code == 201, resp.text
    assert resp.json()["assistant_message"]["sections"] is None