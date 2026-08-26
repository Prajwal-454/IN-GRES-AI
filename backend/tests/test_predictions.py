from fastapi.testclient import TestClient

from app.ingres import predict


def test_forecast_requires_auth(client: TestClient):
    resp = client.get("/api/predictions/forecast")
    assert resp.status_code == 401


def test_forecast_stage_all_india(client: TestClient, auth_user):
    resp = client.get(
        "/api/predictions/forecast",
        params={"metric": "stage", "horizon": 5, "method": "linear"},
        headers=auth_user,
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["metric"] == "stage"
    assert body["unit"] == "%"
    assert body["is_demo"] is False
    assert len(body["historical"]) >= 2
    assert len(body["forecast"]) == 5
    assert body["forecast"][0]["year"] == body["historical"][-1]["year"] + 1
    for pt in body["forecast"]:
        assert pt["lower"] <= pt["value"] <= pt["upper"]
    assert body["direction"] in ("rising", "falling", "stable")


def test_forecast_by_scope(client: TestClient, auth_user):
    resp = client.get(
        "/api/predictions/forecast",
        params={"state": "Telangana", "district": "Warangal", "metric": "recharge"},
        headers=auth_user,
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["state"] == "Telangana"
    assert body["district"] == "Warangal"
    assert body["unit"] == "hm³"
    assert body["forecast"]


def test_forecast_by_village(client: TestClient, auth_user):
    resp = client.get(
        "/api/predictions/forecast",
        params={
            "state": "Andhra Pradesh",
            "district": "Guntur",
            "village": "Guntur Village",
            "metric": "extraction",
            "method": "moving_average",
        },
        headers=auth_user,
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["village"] == "Guntur Village"


def test_forecast_methods(client: TestClient, auth_user):
    for method in ("linear", "moving_average", "exponential"):
        resp = client.get(
            "/api/predictions/forecast",
            params={"metric": "stage", "horizon": 3, "method": method},
            headers=auth_user,
        )
        assert resp.status_code == 200, resp.text
        assert resp.json()["method"] == method
        assert len(resp.json()["forecast"]) == 3


def test_forecast_ml_methods(client: TestClient, auth_user):
    for method in ("arima", "holt", "auto"):
        resp = client.get(
            "/api/predictions/forecast",
            params={"metric": "stage", "horizon": 3, "method": method},
            headers=auth_user,
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert len(body["forecast"]) == 3
        if method == "auto":
            assert body["method"] in (
                "linear",
                "moving_average",
                "exponential",
                "arima",
                "holt",
                "ensemble",
            )
            assert body["best_method"] == body["method"]
            assert body["validation"] is not None
        else:
            assert body["method"] == method
            assert body["method_label"]


def test_forecast_validation_present(client: TestClient, auth_user):
    resp = client.get(
        "/api/predictions/forecast",
        params={"metric": "stage", "horizon": 5, "method": "linear"},
        headers=auth_user,
    )
    assert resp.status_code == 200
    validation = resp.json()["validation"]
    assert validation is not None
    for model in ("linear", "moving_average", "exponential", "arima", "holt", "ensemble"):
        assert model in validation
        assert "rmse" in validation[model]


def test_forecast_ensemble(client: TestClient, auth_user):
    resp = client.get(
        "/api/predictions/forecast",
        params={"metric": "stage", "horizon": 4, "method": "ensemble"},
        headers=auth_user,
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["method"] == "ensemble"
    assert len(body["forecast"]) == 4
    for pt in body["forecast"]:
        assert pt["lower"] <= pt["value"] <= pt["upper"]


def test_forecast_bootstrap_band(client: TestClient, auth_user):
    resp = client.get(
        "/api/predictions/forecast",
        params={"metric": "stage", "horizon": 4, "method": "ensemble", "band": "bootstrap"},
        headers=auth_user,
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["band"] == "bootstrap"
    assert len(body["forecast"]) == 4
    for pt in body["forecast"]:
        assert pt["lower"] <= pt["value"] <= pt["upper"]


def test_forecast_decomposition_present(client: TestClient, auth_user):
    resp = client.get(
        "/api/predictions/forecast",
        params={"metric": "stage", "method": "linear"},
        headers=auth_user,
    )
    assert resp.status_code == 200
    dec = resp.json()["decomposition"]
    assert dec is not None
    assert "trend_per_year" in dec
    assert "summary" in dec
    assert dec["summary"]


def test_forecast_basin_scope(client: TestClient, auth_user):
    resp = client.get(
        "/api/predictions/forecast",
        params={"basin": "Krishna", "metric": "stage", "method": "linear"},
        headers=auth_user,
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["basin"] == "Krishna"
    assert body["scope"] == "Krishna"
    assert len(body["historical"]) >= 2


def test_forecast_unknown_basin(client: TestClient, auth_user):
    resp = client.get(
        "/api/predictions/forecast",
        params={"basin": "NonexistentBasin", "metric": "stage"},
        headers=auth_user,
    )
    assert resp.status_code == 200
    assert not resp.json()["forecast"]
    assert "Not enough historical data" in resp.json()["note"]


def test_forecast_ml_fallback(client: TestClient, auth_user):
    """When torch is missing, deep-learning methods fall back to statistics."""
    resp = client.get(
        "/api/predictions/forecast",
        params={"metric": "stage", "horizon": 3, "method": "lstm"},
        headers=auth_user,
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["ml"]["available"] is False
    assert body["method"] in ("linear", "moving_average", "exponential", "arima", "holt", "ensemble")
    assert len(body["forecast"]) == 3
    assert "torch" in body["note"]


def test_forecast_meta(client: TestClient, auth_user):
    resp = client.get("/api/predictions/meta", headers=auth_user)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert "ensemble" in body["methods"]
    assert "lstm" in body["methods"]
    assert "bootstrap" in body["bands"]
    assert isinstance(body["ml_available"], bool)


def test_backtest(client: TestClient, auth_user):
    resp = client.get(
        "/api/predictions/backtest",
        params={"state": "Telangana", "metric": "stage"},
        headers=auth_user,
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["evaluation"] is not None
    assert body["split_index"] >= 3
    assert body["test_years"]
    assert body["best"] in body["evaluation"]
    for model in ("linear", "moving_average", "exponential", "arima", "holt", "ensemble"):
        m = body["evaluation"][model]
        for key in ("rmse", "mae", "crps", "direction_accuracy", "skill", "n"):
            assert key in m
    assert body["baseline"]["label"] == "Persistence (naive)"


def test_backtest_too_few_points(client: TestClient, auth_user):
    resp = client.get(
        "/api/predictions/backtest",
        params={"state": "NonexistentState", "metric": "stage"},
        headers=auth_user,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["evaluation"] is None
    assert "six" in body["note"]


def test_list_basins(client: TestClient, auth_user):
    resp = client.get("/api/predictions/basins", headers=auth_user)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert len(body) >= 10
    by_name = {b["name"]: b for b in body}
    assert "Ganga" in by_name
    assert "Krishna" in by_name
    assert by_name["Krishna"]["district_count"] > 0
    assert by_name["Ganga"]["states"]


def test_model_comparison(client: TestClient, auth_user):
    resp = client.get(
        "/api/predictions/compare",
        params={"state": "Telangana", "metric": "stage"},
        headers=auth_user,
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["evaluation"] is not None
    assert body["best"] in body["evaluation"]
    assert body["historical_points"] >= 4


def test_model_comparison_too_few_points(client: TestClient, auth_user):
    resp = client.get(
        "/api/predictions/compare",
        params={"state": "NonexistentState", "metric": "stage"},
        headers=auth_user,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["evaluation"] is None
    assert body["best"] is None


def test_forecast_stage_risk(client: TestClient, auth_user):
    resp = client.get(
        "/api/predictions/forecast",
        params={"state": "Telangana", "metric": "stage", "horizon": 10},
        headers=auth_user,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["risk"] in ("safe", "semi-critical", "critical", "over-exploited")


def test_forecast_invalid_params(client: TestClient, auth_user):
    resp = client.get(
        "/api/predictions/forecast",
        params={"metric": "bogus", "horizon": 99},
        headers=auth_user,
    )
    assert resp.status_code == 422


def test_linear_model_exact():
    values = [1.0, 2.0, 3.0, 4.0]
    slope, r2, points = predict._linear_model(values, horizon=1)
    assert round(slope, 6) == 1.0
    assert round(r2, 6) == 1.0
    assert round(points[0][0], 6) == 5.0


def test_category_mapping():
    assert predict._category_for_stage(65) == "safe"
    assert predict._category_for_stage(75) == "semi-critical"
    assert predict._category_for_stage(95) == "critical"
    assert predict._category_for_stage(105) == "over-exploited"


def test_forecast_too_few_points(db_session_factory):
    db = db_session_factory()
    try:
        body = predict.forecast(db, state="NonexistentState", metric="stage")
    finally:
        db.close()
    assert not body["forecast"]
    assert "Not enough historical data" in body["note"]
