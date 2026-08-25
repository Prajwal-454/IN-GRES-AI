"""Prediction & ML endpoints: statistical and deep-learning groundwater forecasting.

Phases 19–21:
- Statistical models (linear / moving_average / exponential / arima / holt /
  ensemble) and auto-selection by walk-forward validation.
- Optional deep-learning models (lstm / transformer / ml) behind the `torch`
  dependency (``requirements-ml.txt``); they degrade gracefully to the best
  statistical model when torch is missing.
- Basin scopes (Indian river basins), bootstrap confidence fans, transfer
  learning, chronological backtesting and forecast metadata.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.database import get_db
from app.ingres import basins, predict
from app.models.user import User
from app.schemas.prediction import (
    BacktestOut,
    BasinOut,
    ForecastCompareOut,
    ForecastMetaOut,
    ForecastOut,
    ScenarioCompareOut,
    ScenarioDeltaOut,
)

router = APIRouter(prefix="/predictions", tags=["predictions"])

_METHOD_PATTERN = (
    r"^(linear|moving_average|exponential|arima|holt|ensemble|auto|lstm|transformer|ml)$"
)


@router.get("/meta", response_model=ForecastMetaOut)
def forecast_meta(
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    """Capabilities exposed to the forecast UI: methods, bands, metrics.

    Deep-learning methods are only advertised when the optional torch
    dependency is installed, so the UI can hide them otherwise.
    """
    from app.ingres import ml_forecast

    return {
        "methods": sorted(predict.METHODS),
        "ml_available": ml_forecast.ml_available(),
        "ml_methods": ml_forecast.ml_methods(),
        "metrics": sorted(predict.METRICS),
        "bands": ["normal", "bootstrap"],
    }


@router.get("/basins", response_model=list[BasinOut])
def list_basins(
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    """Every Indian river basin with its district coverage in this dataset."""
    return basins.list_basins(db)


def _parse_scenario_string(scenario: str | None) -> dict | None:
    """Parse a scenario string like "pumping:-20" into the service dict."""
    if not scenario:
        return None
    try:
        parts = scenario.split(":")
        if len(parts) == 2:
            metric_name = parts[0].strip().lower()
            change_pct = float(parts[1])
            if metric_name in ("pumping", "extraction"):
                metric_name = "extraction"
            elif metric_name == "recharge":
                metric_name = "recharge"
            else:
                return None
            return {"metric": metric_name, "change_pct": change_pct}
    except (ValueError, IndexError):
        pass
    return None


@router.get("/forecast", response_model=ForecastOut)
def forecast(
    state: str | None = Query(default=None),
    district: str | None = Query(default=None),
    village: str | None = Query(default=None),
    basin: str | None = Query(default=None),
    metric: str = Query(default="stage", pattern="^(stage|recharge|extraction)$"),
    horizon: int = Query(default=5, ge=1, le=10),
    method: str = Query(default="linear", pattern=_METHOD_PATTERN),
    band: str = Query(default="normal", pattern="^(normal|bootstrap)$"),
    transfer: bool = Query(default=False),
    epochs: int = Query(default=150, ge=20, le=2000),
    scenario: str | None = Query(default=None, description="What-if scenario, e.g. 'pumping:-20' or 'recharge:-30'"),
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    """Project a metric for a state/district/village or river-basin scope.

    All projections are estimates computed from the current dataset and are
    clearly labelled; they are not official IN-GRES/CGWB forecasts. Deep-learning
    methods (``lstm`` / ``transformer`` / ``ml``) require the optional ``torch``
    dependency and fall back to the best statistical model otherwise.

    What-if scenarios: ``scenario=pumping:-20`` (reduce extraction 20%),
    ``scenario=recharge:-30`` (reduce recharge 30%), ``scenario=extraction:+10``
    (increase extraction 10%), etc. Applied to the historical series before
    fitting the model.
    """
    # Parse scenario string like "pumping:-20" or "recharge:-30"
    scen_dict = _parse_scenario_string(scenario)

    return predict.forecast(
        db,
        state=state,
        district=district,
        village=village,
        basin=basin,
        metric=metric,
        horizon=horizon,
        method=method,
        band=band,
        transfer=transfer,
        epochs=epochs,
        scenario=scen_dict,
    )


@router.get("/backtest", response_model=BacktestOut)
def backtest(
    state: str | None = Query(default=None),
    district: str | None = Query(default=None),
    village: str | None = Query(default=None),
    basin: str | None = Query(default=None),
    metric: str = Query(default="stage", pattern="^(stage|recharge|extraction)$"),
    split: int | None = Query(default=None, ge=3),
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    """Chronological backtest: train on early years, forecast the rest.

    Reports RMSE / MAE / MAPE / CRPS / direction accuracy / skill vs a
    persistence baseline for every statistical model plus the ensemble.
    """
    return predict.backtest(
        db,
        state=state,
        district=district,
        village=village,
        basin=basin,
        metric=metric,
        split=split,
    )


@router.get("/compare", response_model=ForecastCompareOut)
def compare_models(
    state: str | None = Query(default=None),
    district: str | None = Query(default=None),
    village: str | None = Query(default=None),
    basin: str | None = Query(default=None),
    metric: str = Query(default="stage", pattern="^(stage|recharge|extraction)$"),
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    """Walk-forward holdout comparison across all forecast models.

    Returns out-of-sample RMSE / MAE / MAPE for every method plus the
    recommended model for this scope and metric.
    """
    series = predict.get_scope_series(db, state, district, village, metric, basin=basin)
    values = [p["value"] for p in series]
    scope = basin or village or district or state or "India"
    if len(values) < 4:
        return {
            "scope": scope,
            "metric": metric,
            "historical_points": len(values),
            "evaluation": None,
            "best": None,
            "note": "At least four assessment years are required for model comparison.",
        }
    evaluation = predict.evaluate_models(values)
    return {
        "scope": scope,
        "metric": metric,
        "historical_points": len(values),
        "evaluation": evaluation,
        "best": predict.best_method(evaluation),
        "note": None,
    }


@router.get("/scenario-compare", response_model=ScenarioCompareOut)
def scenario_compare(
    state: str | None = Query(default=None),
    district: str | None = Query(default=None),
    village: str | None = Query(default=None),
    basin: str | None = Query(default=None),
    metric: str = Query(default="stage", pattern="^(stage|recharge|extraction)$"),
    horizon: int = Query(default=5, ge=1, le=10),
    method: str = Query(default="auto", pattern=_METHOD_PATTERN),
    band: str = Query(default="normal", pattern="^(normal|bootstrap)$"),
    extraction_change: float = Query(default=0.0, ge=-90, le=300),
    recharge_change: float = Query(default=0.0, ge=-90, le=300),
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    """Run a what-if projection against the unmodified baseline in one call.

    ``extraction_change`` / ``recharge_change`` are percentage changes applied
    to the historical series before fitting (the established scenario
    semantics of this codebase). For the stage metric both changes combine
    multiplicatively (stage ≈ extraction / recharge × 100). When both
    changes are zero the scenario equals the baseline and ``scenario`` is
    still returned for a consistent response shape.
    """
    if metric == "extraction":
        scen: dict | None = {"metric": "extraction", "change_pct": extraction_change}
    elif metric == "recharge":
        scen = {"metric": "recharge", "change_pct": recharge_change}
    else:
        # Stage: combined factor (1 + e) / (1 + r), expressed as one change.
        factor = (1 + extraction_change / 100) / max(1 + recharge_change / 100, 0.1)
        effective_change = round((factor - 1) * 100, 2)
        scen = {"metric": "extraction", "change_pct": effective_change}

    baseline = predict.forecast(
        db,
        state=state,
        district=district,
        village=village,
        basin=basin,
        metric=metric,
        horizon=horizon,
        method=method,
        band=band,
    )
    scenario_result = predict.forecast(
        db,
        state=state,
        district=district,
        village=village,
        basin=basin,
        metric=metric,
        horizon=horizon,
        method=method,
        band=band,
        scenario=scen,
    )

    end_b = baseline.get("end_value")
    end_s = scenario_result.get("end_value")
    delta = end_s - end_b if end_s is not None and end_b is not None else None
    pct = (
        delta * 100 / abs(end_b)
        if delta is not None and end_b not in (None, 0)
        else None
    )

    return ScenarioCompareOut(
        scope=baseline["scope"],
        metric=metric,
        unit=baseline["unit"],
        baseline=ForecastOut.model_validate(baseline),
        scenario=ForecastOut.model_validate(scenario_result),
        delta=ScenarioDeltaOut(
            end_baseline=end_b,
            end_scenario=end_s,
            end_delta=round(delta, 3) if delta is not None else None,
            end_delta_pct=round(pct, 2) if pct is not None else None,
            risk_baseline=baseline.get("risk"),
            risk_scenario=scenario_result.get("risk"),
        ),
    )