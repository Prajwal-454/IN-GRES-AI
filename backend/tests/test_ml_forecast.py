"""Tests for deep-learning groundwater forecasting (Phase 21).

PyTorch is an optional dependency (``requirements-ml.txt``). These tests assert:

- graceful degradation when ``torch`` is missing: ``ml_available()`` is
  ``False``, ML methods are not advertised, and ``predict.forecast`` falls back
  to the best validated statistical model with an explanatory note; and
- the full LSTM/Transformer training path when ``torch`` IS installed
  (skipped otherwise).
"""

import pytest

from app.ingres import predict


def test_ml_available_flag_matches_torch():
    try:
        import torch  # noqa: F401

        expected = True
    except Exception:
        expected = False
    from app.ingres import ml_forecast

    assert ml_forecast.ml_available() is expected
    if not expected:
        assert ml_forecast.ml_methods() == []


def test_fit_predict_raises_without_torch():
    from app.ingres import ml_forecast

    if ml_forecast.ml_available():
        pytest.skip("torch installed; graceful-degradation path not exercised")
    with pytest.raises(RuntimeError):
        ml_forecast.fit_predict([1.0, 2.0, 3.0, 4.0, 5.0], horizon=2)


def test_forecast_lstm_falls_back_without_torch(db_session_factory):
    from app.ingres import ml_forecast

    if ml_forecast.ml_available():
        pytest.skip("torch installed; fallback path not exercised")
    db = db_session_factory()
    try:
        fc = predict.forecast(db, state="Telangana", metric="stage", horizon=3, method="lstm")
    finally:
        db.close()
    assert len(fc["forecast"]) == 3
    assert fc["method"] != "lstm"
    assert fc["method"] in ("linear", "moving_average", "exponential", "arima", "holt")
    assert fc["ml"]["available"] is False
    assert fc["ml"]["note"]


def test_forecast_transformer_falls_back_without_torch(db_session_factory):
    from app.ingres import ml_forecast

    if ml_forecast.ml_available():
        pytest.skip("torch installed; fallback path not exercised")
    db = db_session_factory()
    try:
        fc = predict.forecast(db, metric="stage", horizon=3, method="transformer")
    finally:
        db.close()
    assert len(fc["forecast"]) == 3
    assert fc["method"] != "transformer"
    assert "torch" in fc["ml"]["note"].lower()


def test_forecast_ml_falls_back_without_torch(db_session_factory):
    from app.ingres import ml_forecast

    if ml_forecast.ml_available():
        pytest.skip("torch installed; fallback path not exercised")
    db = db_session_factory()
    try:
        fc = predict.forecast(db, metric="stage", horizon=3, method="ml")
    finally:
        db.close()
    assert len(fc["forecast"]) == 3
    assert fc["method"] not in ("lstm", "transformer", "ml")


@pytest.mark.skipif(
    not __import__("importlib").util.find_spec("torch"),
    reason="torch not installed (requirements-ml.txt)",
)
def test_forecast_lstm_with_torch(db_session_factory):
    from app.ingres import ml_forecast

    db = db_session_factory()
    try:
        fc = predict.forecast(
            db, state="Telangana", metric="stage", horizon=3, method="lstm", epochs=60
        )
    finally:
        db.close()
    assert len(fc["forecast"]) == 3
    assert fc["method"] == "lstm"
    assert fc["ml"]["available"] is True
    assert fc["ml"]["model"] == "lstm"
    assert fc["ml"]["epochs"] >= 20
    for pt in fc["forecast"]:
        assert pt["lower"] <= pt["value"] <= pt["upper"]


@pytest.mark.skipif(
    not __import__("importlib").util.find_spec("torch"),
    reason="torch not installed (requirements-ml.txt)",
)
def test_transfer_learning_with_torch(db_session_factory):
    from app.ingres import ml_forecast

    db = db_session_factory()
    try:
        fc = predict.forecast(
            db,
            state="Telangana",
            district="Warangal",
            metric="stage",
            horizon=3,
            method="lstm",
            transfer=True,
            epochs=40,
        )
    finally:
        db.close()
    assert fc["method"] == "lstm"
    assert fc["ml"]["available"] is True
    assert fc["ml"]["transfer"] is True
    assert fc["ml"]["pretrained_scope"] == "pool"


@pytest.mark.skipif(
    not __import__("importlib").util.find_spec("torch"),
    reason="torch not installed (requirements-ml.txt)",
)
def test_ml_bootstrap_band_with_torch(db_session_factory):
    db = db_session_factory()
    try:
        fc = predict.forecast(
            db, metric="stage", horizon=3, method="transformer", band="bootstrap", epochs=60
        )
    finally:
        db.close()
    assert fc["band"] == "bootstrap"
    assert len(fc["forecast"]) == 3
    for pt in fc["forecast"]:
        assert pt["lower"] <= pt["value"] <= pt["upper"]


def test_ml_forecast_too_few_points(db_session_factory):
    from app.ingres import ml_forecast

    db = db_session_factory()
    try:
        fc = predict.forecast(
            db, state="NonexistentState", metric="stage", horizon=3, method="lstm"
        )
    finally:
        db.close()
    assert not fc["forecast"]
    assert "Not enough historical data" in fc["note"]


def test_forecast_api_meta(client, auth_user):
    resp = client.get("/api/predictions/meta", headers=auth_user)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert "linear" in body["methods"]
    assert "lstm" in body["methods"]
    assert body["metrics"] == ["extraction", "recharge", "stage"]
    assert body["bands"] == ["normal", "bootstrap"]


def test_forecast_api_ml_method(client, auth_user):
    """API accepts ML methods and degrades gracefully without torch."""
    from app.ingres import ml_forecast

    resp = client.get(
        "/api/predictions/forecast",
        params={"metric": "stage", "horizon": 3, "method": "lstm"},
        headers=auth_user,
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert len(body["forecast"]) == 3
    if not ml_forecast.ml_available():
        assert body["method"] != "lstm"
        assert body["ml"]["available"] is False


def test_forecast_api_basin(client, auth_user):
    resp = client.get(
        "/api/predictions/forecast",
        params={"basin": "Godavari", "metric": "stage", "horizon": 3},
        headers=auth_user,
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["basin"] == "Godavari"
    assert body["scope"] == "Godavari"
    assert len(body["forecast"]) == 3


def test_forecast_api_basins_list(client, auth_user):
    resp = client.get("/api/predictions/basins", headers=auth_user)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert len(body) == 20
    names = {b["name"] for b in body}
    assert "Godavari" in names
    for basin in body:
        assert basin["label"]
        assert basin["states"]


def test_forecast_api_backtest(client, auth_user):
    resp = client.get(
        "/api/predictions/backtest",
        params={"basin": "Krishna", "metric": "stage"},
        headers=auth_user,
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["scope"] == "Krishna"
    assert body["evaluation"] is not None
    for name, scores in body["evaluation"].items():
        assert "rmse" in scores
        assert "crps" in scores
        assert "skill" in scores


def test_forecast_api_band_and_transfer_params(client, auth_user):
    resp = client.get(
        "/api/predictions/forecast",
        params={
            "metric": "stage",
            "horizon": 3,
            "method": "linear",
            "band": "bootstrap",
            "transfer": "true",
        },
        headers=auth_user,
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["band"] == "bootstrap"
    for pt in body["forecast"]:
        assert pt["lower"] <= pt["value"] <= pt["upper"]