"""Time-series forecasting for groundwater metrics (Phases 19-21).

Statistical, ensemble and (optionally) deep-learning models. Everything except
the deep-learning models is implemented with the standard library plus NumPy —
the only numeric dependency; it ships with the rest of the stack:

- ``linear``: ordinary least-squares trend extrapolation with a 95%
  prediction interval.
- ``moving_average``: trailing-window mean carried forward.
- ``exponential``: simple exponential smoothing carried forward.
- ``arima``: ARIMA(1,1,0) — an autoregressive model on the first differences
  of the series, fitted by least squares with a growing k-step forecast band.
- ``holt``: Holt's linear trend (double exponential smoothing) for series
  that move with a steady drift.
- ``ensemble``: RMSE-weighted blend of the statistical methods (out-of-sample
  weights from walk-forward holdout validation).
- ``lstm`` / ``transformer`` / ``ml``: PyTorch deep-learning models (Phase 21)
  that pre-train basin/state-wide and fine-tune per scope when ``transfer`` is
  enabled. They are optional — when ``torch`` is not installed every ML method
  degrades gracefully to the best statistical model with an explanatory note.
- ``auto``: walk-forward holdout validation across the statistical methods
  (including the ensemble); the model with the lowest out-of-sample RMSE is
  used automatically and reported.

Two confidence-band styles are supported via ``band``: ``normal`` (analytic
95% bands per model) and ``bootstrap`` (an empirical 5-95 percentile fan from
residual block-bootstrap simulation). A forecast can also carry a
``decomposition`` explaining trend / variability / recent acceleration.

Backtesting (``backtest()``) performs a chronological train/test split across
all models and reports RMSE / MAE / MAPE, the continuous ranked probability
score (CRPS), direction accuracy and a skill score versus a persistence
baseline.

Projections are estimates computed from the (synthetic demo or user-imported)
assessment history and are always clearly labelled as such — never official
IN-GRES/CGWB projections.
"""

from __future__ import annotations

import math
import random

import numpy as np
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.groundwater import (
    AssessmentUnit,
    GroundwaterAssessment,
)

METRICS = {"stage", "recharge", "extraction"}
BASE_METHODS = ("linear", "moving_average", "exponential", "arima", "holt")
STAT_METHODS = BASE_METHODS + ("ensemble",)
ML_METHODS = ("lstm", "transformer", "ml")
METHODS = set(STAT_METHODS) | set(ML_METHODS) | {"auto"}
Z = 1.96  # ~95% confidence band

METRIC_LABELS = {
    "stage": "stage of groundwater extraction",
    "recharge": "annual groundwater recharge",
    "extraction": "annual groundwater extraction",
}

METHOD_LABELS = {
    "linear": "Linear trend (OLS)",
    "moving_average": "Moving average",
    "exponential": "Exponential smoothing",
    "arima": "ARIMA(1,1,0)",
    "holt": "Holt's linear trend",
    "ensemble": "Ensemble (RMSE-weighted blend)",
    "lstm": "Deep learning — LSTM",
    "transformer": "Deep learning — Transformer",
    "ml": "Deep learning (best available)",
    "auto": "Auto (best validated model)",
}


def _category_for_stage(stage: float) -> str:
    if stage < 70:
        return "safe"
    if stage < 90:
        return "semi-critical"
    if stage <= 100:
        return "critical"
    return "over-exploited"


def _scope_conditions(
    db: Session,
    state: str | None,
    district: str | None,
    village: str | None,
) -> tuple[list, tuple[int | None, int | None, int | None]]:
    """Resolve scope names to ids and return cheap AssessmentUnit conditions.

    Returns ``(conditions, (state_id, district_id, village_id))`` so callers can
    also apply the effective-dataset filter.
    """
    from app.ingres.queries import resolve_scope_ids

    state_id, district_id, village_id, empty = resolve_scope_ids(db, state, district, village)
    if empty:
        return [AssessmentUnit.id.is_(None)], (None, None, None)
    conds = []
    if state_id is not None:
        conds.append(AssessmentUnit.state_id == state_id)
    if district_id is not None:
        conds.append(AssessmentUnit.district_id == district_id)
    if village_id is not None:
        conds.append(AssessmentUnit.village_id == village_id)
    return conds, (state_id, district_id, village_id)


def get_scope_series(
    db: Session,
    state: str | None = None,
    district: str | None = None,
    village: str | None = None,
    metric: str = "stage",
    basin: str | None = None,
) -> list[dict]:
    """Annual aggregate series for a scope. Stage is averaged, volumes summed.

    ``basin`` is an Indian river basin (see ``app.ingres.basins``); it resolves
    to the set of districts in the basin and is mutually exclusive with the
    district/village scopes.
    """
    target = "stage_of_extraction" if metric == "stage" else f"{metric}_total"
    fn = func.avg if metric == "stage" else func.sum
    stmt = (
        select(
            GroundwaterAssessment.assessment_year.label("year"),
            fn(getattr(GroundwaterAssessment, target)).label("value"),
        )
        .join(AssessmentUnit, GroundwaterAssessment.assessment_unit_id == AssessmentUnit.id)
        .group_by(GroundwaterAssessment.assessment_year)
        .order_by(GroundwaterAssessment.assessment_year)
    )
    conds, _ids = _scope_conditions(db, state, district, village)
    if basin:
        from app.ingres.basins import basin_district_ids

        ids = basin_district_ids(db, basin)
        conds = [AssessmentUnit.district_id.in_(ids)] if ids else [AssessmentUnit.id.is_(None)]
    for cond in conds:
        stmt = stmt.where(cond)
    return [
        {"year": row.year, "value": float(row.value)}
        for row in db.execute(stmt).all()
        if row.value is not None
    ]


def _linear_model(
    values: list[float], horizon: int
) -> tuple[float, float | None, list[tuple[float, float, float]]]:
    """OLS fit on x = 0..n-1. Returns (slope, r2, [(pred, upper, lower)])."""
    n = len(values)
    xs = list(range(n))
    xm = sum(xs) / n
    ym = sum(values) / n
    sxx = sum((xi - xm) ** 2 for xi in xs)
    sxy = sum((xi - xm) * (yi - ym) for xi, yi in zip(xs, values))
    slope = sxy / sxx if sxx else 0.0
    intercept = ym - slope * xm

    fitted = [intercept + slope * xi for xi in xs]
    resid = [yi - fi for yi, fi in zip(values, fitted)]
    ss = sum(r * r for r in resid)
    resid_std = math.sqrt(ss / max(n - 2, 1))

    sst = sum((yi - ym) ** 2 for yi in values)
    r2 = 1 - ss / sst if sst else 0.0

    points = []
    for k in range(1, horizon + 1):
        xp = n - 1 + k
        yhat = intercept + slope * xp
        se = (
            resid_std * math.sqrt(1 + 1 / n + (xp - xm) ** 2 / sxx)
            if sxx
            else resid_std
        )
        points.append((yhat, yhat + Z * se, yhat - Z * se))
    return slope, r2, points


def _moving_average_model(
    values: list[float], horizon: int, window: int = 3
) -> tuple[float, float | None, list[tuple[float, float, float]]]:
    n = len(values)
    w = min(window, n)
    recent = values[-w:]
    mean = sum(recent) / w
    variance = sum((v - mean) ** 2 for v in recent) / max(w - 1, 1)
    sd = math.sqrt(variance)
    se = sd * math.sqrt(1 + 1 / w) if w else 0.0
    slope = (values[-1] - values[0]) / max(n - 1, 1) if n >= 2 else 0.0
    points = [(mean, mean + Z * se, mean - Z * se) for _ in range(horizon)]
    return slope, None, points


def _exponential_model(
    values: list[float], horizon: int, alpha: float = 0.5
) -> tuple[float, float | None, list[tuple[float, float, float]]]:
    n = len(values)
    smoothed = [values[0]]
    for v in values[1:]:
        smoothed.append(alpha * v + (1 - alpha) * smoothed[-1])
    level = smoothed[-1]
    resid = [v - f for v, f in zip(values, smoothed)]
    sd = math.sqrt(sum(r * r for r in resid) / max(n - 1, 1))
    se = sd * math.sqrt(1 + alpha)
    slope = (smoothed[-1] - smoothed[0]) / max(n - 1, 1) if n >= 2 else 0.0
    points = [(level, level + Z * se, level - Z * se) for _ in range(horizon)]
    return slope, None, points


def _arima_model(
    values: list[float], horizon: int
) -> tuple[float, float | None, list[tuple[float, float, float]]]:
    """ARIMA(1,1,0): AR(1) on the first differences, then integrate back."""
    n = len(values)
    diffs = [values[i] - values[i - 1] for i in range(1, n)]
    if len(diffs) >= 2:
        y = np.asarray(diffs[1:], dtype=float)
        x = np.asarray(diffs[:-1], dtype=float)
        xx = float(x @ x)
        phi = float(x @ y / xx) if xx else 0.0
        phi = max(-1.0, min(1.0, phi))  # keep the fitted process stable
        resid = y - phi * x
        sigma = float(np.std(resid, ddof=1)) if len(resid) > 1 else 0.0
    else:
        phi, sigma = 0.0, 0.0

    level = values[-1]
    last_d = diffs[-1] if diffs else 0.0
    points: list[tuple[float, float, float]] = []
    for k in range(1, horizon + 1):
        last_d = phi * last_d
        level = level + last_d
        # k-step forecast error variance of an AR(1) with innovations sigma.
        if abs(phi) < 1.0:
            var = sigma * sigma * (1 - phi ** (2 * k)) / (1 - phi * phi)
        else:
            var = sigma * sigma * k
        se = math.sqrt(max(var, 0.0))
        points.append((level, level + Z * se, level - Z * se))
    slope = (values[-1] - values[0]) / max(n - 1, 1)
    return slope, None, points


def _holt_model(
    values: list[float], horizon: int, alpha: float = 0.5, beta: float = 0.3
) -> tuple[float, float | None, list[tuple[float, float, float]]]:
    """Holt's linear trend: level + trend double exponential smoothing."""
    n = len(values)
    level = float(values[0])
    trend = float(values[1] - values[0]) if n > 1 else 0.0
    fitted = [level]
    for v in values[1:]:
        last_level = level
        level = alpha * v + (1 - alpha) * (level + trend)
        trend = beta * (level - last_level) + (1 - beta) * trend
        fitted.append(level)
    resid = [v - f for v, f in zip(values, fitted)]
    sd = math.sqrt(sum(r * r for r in resid) / max(n - 1, 1))
    points: list[tuple[float, float, float]] = []
    for k in range(1, horizon + 1):
        yhat = level + k * trend
        se = sd * math.sqrt(k)
        points.append((yhat, yhat + Z * se, yhat - Z * se))
    return trend, None, points


def _model_fns() -> dict[str, callable]:
    return {
        "linear": _linear_model,
        "moving_average": _moving_average_model,
        "exponential": _exponential_model,
        "arima": _arima_model,
        "holt": _holt_model,
    }


def _bootstrap_fan(
    values: list[float],
    horizon: int,
    n_iter: int = 300,
    seed: int = 42,
) -> tuple[list[float], list[float], list[float]]:
    """Empirical 5/50/95 percentile fan via residual block bootstrap.

    Fits a simple exponential-smoothing level path, draws block-bootstrapped
    residual paths around it and simulates ``n_iter`` futures out to
    ``horizon``. Returns ``(median, lower, upper)`` per horizon step. This is
    the ``band="bootstrap"`` confidence band used by the forecast API.
    """
    n = len(values)
    if n < 2:
        return list(values), list(values), list(values)

    smoothed = [float(values[0])]
    for v in values[1:]:
        smoothed.append(0.5 * v + 0.5 * smoothed[-1])
    resid = [v - f for v, f in zip(values, smoothed)]

    rng = random.Random(seed)
    block = max(1, min(n, 3))
    paths: list[list[float]] = []
    for _ in range(n_iter):
        level = smoothed[-1]
        path = []
        for _ in range(horizon):
            start = rng.randrange(0, n - block + 1)
            level = level + resid[start + rng.randrange(0, block)]
            path.append(level)
        paths.append(path)

    med, low, high = [], [], []
    for k in range(horizon):
        column = sorted(p[k] for p in paths)
        idx = len(column) - 1
        med.append(column[int(0.5 * idx)])
        low.append(column[int(0.05 * idx)])
        high.append(column[int(0.95 * idx)])
    return med, low, high


def _ensemble_weights(evaluation: dict[str, dict] | None) -> dict[str, float]:
    """Inverse-RMSE weights over the base methods (equal when untested)."""
    if not evaluation:
        return {m: 1.0 for m in BASE_METHODS}
    rmse = {m: evaluation[m].get("rmse") for m in BASE_METHODS}
    usable = {m: v for m, v in rmse.items() if v is not None and v > 0}
    if not usable:
        return {m: 1.0 for m in BASE_METHODS}
    inv = {m: 1.0 / v for m, v in usable.items()}
    total = sum(inv.values())
    return {m: (inv[m] / total if m in inv else 0.0) for m in BASE_METHODS}


def _ensemble_model(
    values: list[float],
    horizon: int,
    weights: dict[str, float] | None = None,
    band: str = "normal",
) -> tuple[float, float | None, list[tuple[float, float, float]]]:
    """RMSE-weighted blend of the base statistical models' point forecasts.

    The 95% band is a blend of the component bands when ``band="normal"``, or
    an empirical bootstrap fan when ``band="bootstrap"``.
    """
    n = len(values)
    weight = weights or {m: 1.0 for m in BASE_METHODS}
    points: dict[str, list[tuple[float, float, float]]] = {}
    for name, fn in _model_fns().items():
        try:
            points[name] = fn(values, horizon)[2]
        except (ValueError, ZeroDivisionError, IndexError):
            points[name] = [(values[-1], values[-1], values[-1])] * horizon

    if band == "bootstrap":
        med, low, high = _bootstrap_fan(values, horizon)
        preds = [(m, h, l) for m, l, h in zip(med, low, high)]
    else:
        preds = []
        for k in range(horizon):
            val = sum(weight[m] * points[m][k][0] for m in weight if weight[m] > 0)
            ups = [points[m][k][1] for m in weight if weight[m] > 0]
            lows = [points[m][k][2] for m in weight if weight[m] > 0]
            preds.append((val, max(ups), min(lows)))
    slope = (values[-1] - values[0]) / max(n - 1, 1) if n >= 2 else 0.0
    return slope, None, preds


def explain_series(values: list[float]) -> dict:
    """Explainability for an annual series: trend, variability, acceleration.

    Computes the overall trend, recent-vs-earlier acceleration, year-to-year
    volatility and residual scatter around a linear fit, then summarises the
    dominant behaviour as a short human-readable text.
    """
    n = len(values)
    if n < 3:
        return {
            "trend_per_year": round(values[-1] - values[0], 2) if n >= 2 else None,
            "volatility": None,
            "acceleration": None,
            "summary": "Not enough observations to explain the series.",
        }
    xs = list(range(n))
    xm = sum(xs) / n
    ym = sum(values) / n
    sxx = sum((xi - xm) ** 2 for xi in xs)
    sxy = sum((xi - xm) * (yi - ym) for xi, yi in zip(xs, values))
    slope = sxy / sxx if sxx else 0.0
    intercept = ym - slope * xm
    fitted = [intercept + slope * xi for xi in xs]
    resid = [yi - fi for yi, fi in zip(values, fitted)]
    resid_std = math.sqrt(sum(r * r for r in resid) / max(n - 2, 1))

    half = n // 2
    early_slope = (values[half - 1] - values[0]) / max(half - 1, 1) if half >= 2 else slope
    recent_slope = (values[-1] - values[n - half]) / max(half - 1, 1) if half >= 2 else slope
    accel = recent_slope - early_slope
    diffs = [values[i] - values[i - 1] for i in range(1, n)]
    volatility = math.sqrt(sum(d * d for d in diffs) / len(diffs))

    if resid_std and abs(slope) > 0 and abs(slope) / resid_std < 0.5:
        summary = "The series is dominated by year-to-year variability rather than a steady trend."
    elif accel > 0.02 * (abs(slope) + 1e-9):
        summary = "The recent trend is accelerating (change per year is growing)."
    elif accel < -0.02 * (abs(slope) + 1e-9):
        summary = "The recent trend is decelerating (change per year is slowing)."
    else:
        summary = "The series moves at a broadly steady pace with modest variability."
    return {
        "trend_per_year": round(slope, 4),
        "volatility": round(volatility, 4),
        "residual_std": round(resid_std, 4),
        "acceleration": round(accel, 4),
        "summary": summary,
    }


def _crps_normal(mu: float, sigma: float, obs: float) -> float:
    """CRPS of a normal predictive distribution N(mu, sigma^2) at obs."""
    from math import erf, exp, sqrt, pi

    if sigma <= 0:
        return abs(mu - obs)
    z = (obs - mu) / sigma
    phi = exp(-0.5 * z * z) / sqrt(2 * pi)
    phi_z = 0.5 * (1 + erf(z / sqrt(2)))
    return sigma * (z * (2 * phi_z - 1) + 2 * phi - 1 / sqrt(pi))


def _persistence(values: list[float], steps: int) -> float:
    """Mean absolute one-step error of a persistence (naive) baseline."""
    if len(values) < 2:
        return float("nan")
    diffs = [abs(values[i] - values[i - 1]) for i in range(1, len(values))]
    return sum(diffs) / len(diffs)


def _skill_score(err_forecast: float, err_baseline: float) -> float | None:
    """Skill vs a baseline: 1 - forecast_err / baseline_err (NaN-safe)."""
    if err_baseline is None or math.isnan(err_baseline) or err_baseline == 0:
        return None
    return 1.0 - err_forecast / err_baseline


def evaluate_models(values: list[float]) -> dict[str, dict]:
    """Walk-forward one-step holdout validation for every method.

    For each method the series is refit on ``values[:i]`` and scored against
    the next observation, producing out-of-sample RMSE / MAE / MAPE. The
    ensemble is weighted by the base methods' holdout scores and evaluated on
    the same split. Used by ``auto`` selection and surfaced to the user on the
    comparison endpoint.
    """
    out: dict[str, dict] = {}
    for name, fn in _model_fns().items():
        pairs: list[tuple[float, float]] = []
        for i in range(3, len(values)):
            train = values[:i]
            try:
                yhat = fn(train, 1)[2][0][0]
            except (ValueError, ZeroDivisionError, IndexError):
                continue
            pairs.append((yhat, values[i]))
        if len(pairs) < 2:
            out[name] = {"rmse": None, "mae": None, "mape": None, "n": len(pairs)}
            continue
        mae = sum(abs(p - a) for p, a in pairs) / len(pairs)
        rmse = math.sqrt(sum((p - a) ** 2 for p, a in pairs) / len(pairs))
        mape_vals = [abs(p - a) / abs(a) * 100 for p, a in pairs if a != 0]
        mape = sum(mape_vals) / len(mape_vals) if mape_vals else None
        out[name] = {
            "rmse": round(rmse, 3),
            "mae": round(mae, 3),
            "mape": round(mape, 2) if mape is not None else None,
            "n": len(pairs),
        }

    # Ensemble holdout (weights from the base evals above).
    pairs: list[tuple[float, float]] = []
    for i in range(3, len(values)):
        train = values[:i]
        weights = _ensemble_weights({m: out[m] for m in BASE_METHODS})
        try:
            yhat = _ensemble_model(train, 1, weights=weights)[2][0][0]
        except (ValueError, ZeroDivisionError, IndexError):
            continue
        pairs.append((yhat, values[i]))
    if len(pairs) >= 2:
        mae = sum(abs(p - a) for p, a in pairs) / len(pairs)
        rmse = math.sqrt(sum((p - a) ** 2 for p, a in pairs) / len(pairs))
        mape_vals = [abs(p - a) / abs(a) * 100 for p, a in pairs if a != 0]
        mape = sum(mape_vals) / len(mape_vals) if mape_vals else None
        out["ensemble"] = {
            "rmse": round(rmse, 3),
            "mae": round(mae, 3),
            "mape": round(mape, 2) if mape is not None else None,
            "n": len(pairs),
        }
    else:
        out["ensemble"] = {"rmse": None, "mae": None, "mape": None, "n": len(pairs)}
    return out


def best_method(evaluation: dict[str, dict]) -> str | None:
    """Method with the lowest out-of-sample RMSE, or None when untested."""
    ranked = sorted(
        (name for name, m in evaluation.items() if m.get("rmse") is not None),
        key=lambda name: evaluation[name]["rmse"],
    )
    return ranked[0] if ranked else None


def backtest(
    db: Session,
    state: str | None = None,
    district: str | None = None,
    village: str | None = None,
    basin: str | None = None,
    metric: str = "stage",
    split: int | None = None,
) -> dict:
    """Chronological backtest: train on early years, forecast the rest.

    Splits the series so the first ``split`` observations (default ~60%) are
    used to fit each model and the remaining years are forecast one step at a
    time in expanding-window fashion. Every method is scored with RMSE, MAE,
    MAPE, CRPS, direction accuracy and a skill score versus the persistence
    (naive) baseline.
    """
    series = get_scope_series(db, state, district, village, metric, basin=basin)
    values = [p["value"] for p in series]
    years = [p["year"] for p in series]
    scope = basin or village or district or state or "India"

    if len(values) < 6:
        return {
            "scope": scope,
            "metric": metric,
            "historical_points": len(values),
            "split_index": None,
            "train_years": [],
            "test_years": [],
            "evaluation": None,
            "baseline": None,
            "note": "At least six assessment years are required for a train/test backtest.",
        }

    n_split = split or max(3, int(len(values) * 0.6))
    n_split = min(max(n_split, 3), len(values) - 2)
    train_years = years[:n_split]
    test_years = years[n_split:]

    results: dict[str, dict] = {}
    for name, fn in _model_fns().items():
        preds, obs = [], []
        for i in range(n_split, len(values)):
            train = values[:i]
            try:
                yhat = fn(train, 1)[2][0][0]
            except (ValueError, ZeroDivisionError, IndexError):
                continue
            preds.append(yhat)
            obs.append(values[i])
        results[name] = _score_backtest(preds, obs, values[:n_split])

    # Ensemble.
    ens_preds, ens_obs = [], []
    for i in range(n_split, len(values)):
        train = values[:i]
        weights = _ensemble_weights(None)
        try:
            yhat = _ensemble_model(train, 1, weights=weights)[2][0][0]
        except (ValueError, ZeroDivisionError, IndexError):
            continue
        ens_preds.append(yhat)
        ens_obs.append(values[i])
    results["ensemble"] = _score_backtest(ens_preds, ens_obs, values[:n_split])

    baseline_mae = _persistence(values[: len(values)], 1)
    best = best_method({k: v for k, v in results.items() if v["n"] > 0})
    return {
        "scope": scope,
        "metric": metric,
        "historical_points": len(values),
        "split_index": n_split,
        "train_years": train_years,
        "test_years": test_years,
        "evaluation": results,
        "baseline": {
            "label": "Persistence (naive)",
            "mae": round(baseline_mae, 3) if baseline_mae == baseline_mae else None,
        },
        "best": best,
        "note": None,
    }


def _score_backtest(preds: list[float], obs: list[float], train: list[float]) -> dict:
    """RMSE / MAE / MAPE / CRPS / direction accuracy / skill for one model."""
    if len(preds) < 1:
        return {"rmse": None, "mae": None, "mape": None, "crps": None, "direction_accuracy": None, "skill": None, "n": 0}
    n = len(preds)
    errors = [abs(p - a) for p, a in zip(preds, obs)]
    mae = sum(errors) / n
    rmse = math.sqrt(sum(e * e for e in errors) / n)
    mape_vals = [abs(p - a) / abs(a) * 100 for p, a in zip(preds, obs) if a != 0]
    mape = sum(mape_vals) / len(mape_vals) if mape_vals else None

    # Normal-approximation CRPS per step, averaged.
    spread = max(1e-9, (sum(train) / len(train)) * 0.05 if train else 1e-9)
    crps = sum(_crps_normal(p, max(spread, abs(p - a) * 0.5), a) for p, a in zip(preds, obs)) / n

    # Direction accuracy vs. last observed value.
    last = obs[0] if obs else 0.0
    direction_hits = sum(1 for p, a in zip(preds, obs) if (p - last) * (a - last) > 0)
    direction_acc = direction_hits / n

    baseline_mae = _persistence(train + obs, 1)
    skill = _skill_score(mae, baseline_mae)
    return {
        "rmse": round(rmse, 3),
        "mae": round(mae, 3),
        "mape": round(mape, 2) if mape is not None else None,
        "crps": round(crps, 3),
        "direction_accuracy": round(direction_acc, 3),
        "skill": round(skill, 3) if skill is not None else None,
        "n": n,
    }


def _describe(
    metric: str,
    method: str,
    direction: str,
    slope: float | None,
    pct_change: float | None,
    last_value: float,
    end_value: float,
    years_to_threshold: int | None,
    unit: str,
    band: str = "normal",
    ml_available: bool | None = None,
) -> str:
    label = METRIC_LABELS[metric]
    model_words = {
        "linear": "a linear least-squares trend",
        "moving_average": "a trailing moving average",
        "exponential": "simple exponential smoothing",
        "arima": "an ARIMA(1,1,0) autoregressive model",
        "holt": "Holt's linear trend (double exponential smoothing)",
        "ensemble": "an RMSE-weighted ensemble of the statistical models",
        "lstm": "a deep-learning LSTM (long short-term memory) network",
        "transformer": "a deep-learning transformer with self-attention",
        "ml": "the best available deep-learning model",
    }
    words = model_words.get(method, "a time-series model")
    if band == "bootstrap":
        words += " with a residual block-bootstrap 5–95% confidence fan"
    else:
        words += " with a 95% confidence band"
    if ml_available is False:
        words = "the best available statistical model (deep-learning forecast requires the optional torch dependency; see requirements-ml.txt)"

    parts = [
        f"Projection using {words} over {last_value:.2f} {unit} "
        f"({label}) and extrapolating to {end_value:.2f} {unit}."
    ]
    if metric == "stage" and slope is not None and abs(slope) >= 0.01:
        verb = "rising" if slope > 0 else "falling"
        parts.append(
            f"The trend is {verb} by about {abs(slope):.1f} percentage points per year "
            f"({direction})."
        )
    elif pct_change is not None:
        parts.append(f"That is a {direction} of about {abs(pct_change):.1f}%.")
    if years_to_threshold:
        parts.append(
            f"At this pace the projected stage reaches the over-exploited threshold "
            f"(100%) in about {years_to_threshold} year(s)."
        )
    return " ".join(parts)


def forecast(
    db: Session,
    state: str | None = None,
    district: str | None = None,
    village: str | None = None,
    basin: str | None = None,
    metric: str = "stage",
    horizon: int = 5,
    method: str = "linear",
    alpha: float = 0.5,
    window: int = 3,
    scenario: dict | None = None,
    band: str = "normal",
    transfer: bool = False,
    epochs: int = 150,
) -> dict:
    metric = metric if metric in METRICS else "stage"
    method = method if method in METHODS else "linear"
    horizon = max(1, min(int(horizon), 10))
    unit = "%" if metric == "stage" else "hm³"

    series = get_scope_series(db, state, district, village, metric, basin=basin)
    scope = basin or village or district or state or "India"

    scenario_desc = None
    if scenario:
        scen_metric = scenario.get("metric")
        pct = float(scenario.get("change_pct") or 0)
        factor = max(1 + pct / 100, 0.05)
        if scen_metric in METRICS and series:
            series = [
                {
                    "year": p["year"],
                    "value": (
                        p["value"] * factor
                        if scen_metric == metric
                        else p["value"] * factor
                        if metric == "stage" and scen_metric == "extraction"
                        else p["value"] / factor
                        if metric == "stage" and scen_metric == "recharge"
                        else p["value"]
                    ),
                }
                for p in series
            ]
            scenario_desc = {
                "metric": scen_metric,
                "change_pct": round(pct, 1),
                "applied_to": metric,
            }

    base = {
        "scope": scope,
        "state": state,
        "district": district,
        "village": village,
        "basin": basin,
        "metric": metric,
        "method": method,
        "method_label": METHOD_LABELS[method],
        "unit": unit,
        "historical": [
            {"year": p["year"], "value": round(p["value"], 2)} for p in series
        ],
        "forecast": [],
        "slope": None,
        "r2": None,
        "direction": "stable",
        "pct_change": None,
        "end_value": None,
        "risk": None,
        "years_to_threshold": None,
        "note": "",
        "validation": None,
        "best_method": None,
        "scenario": scenario_desc,
        "is_demo": True,
        "band": band if band in ("normal", "bootstrap") else "normal",
        "decomposition": None,
        "ml": {"available": False},
    }

    if len(series) < 2:
        base["note"] = (
            f"Not enough historical data to project {METRIC_LABELS[metric]} "
            f"for {scope}. At least two assessment years are required."
        )
        return base

    values = [p["value"] for p in series]
    years = [p["year"] for p in series]
    validation = evaluate_models(values) if len(values) >= 4 else None
    base["validation"] = validation
    base["decomposition"] = explain_series(values)

    ml_available = False
    from app.ingres import ml_forecast

    ml_available = ml_forecast.ml_available()
    base["ml"] = {
        "available": ml_available,
        "note": None if ml_available else "torch not installed; install requirements-ml.txt to enable deep-learning forecasting.",
    }

    ml_degraded = False
    if method in ML_METHODS and not ml_available:
        ml_degraded = True
        fallback = best_method(validation) if validation else None
        fallback = fallback or "linear"
        base["best_method"] = fallback
        base["ml"]["note"] = (
            "Deep-learning forecast requested but torch is not installed. "
            "Falling back to the best validated statistical model "
            f"({METHOD_LABELS[fallback]}). Install requirements-ml.txt to "
            "enable LSTM/Transformer forecasting."
        )
        method = fallback
        base["method"] = method
        base["method_label"] = METHOD_LABELS[method]

    if method == "auto":
        best = best_method(validation) if validation else None
        if best is None:
            best = "linear"
        base["best_method"] = best
        method = best
        base["method"] = method
        base["method_label"] = METHOD_LABELS[method]

    if method in ML_METHODS and ml_available:
        model_type = "transformer" if method == "ml" else method
        pool_values = None
        if transfer and (district or village or basin):
            pool_series = get_scope_series(db, state=state, metric=metric)
            pool_values = [p["value"] for p in pool_series]
            if len(pool_values) < 4:
                pool_values = None
        info: dict = {}
        try:
            slope, r2, preds = ml_forecast.fit_predict(
                values,
                horizon=horizon,
                model_type=model_type,
                epochs=epochs,
                transfer=pool_values,
                metric_name=metric,
                scope=scope,
                seed=42,
                band=band,
                info=info,
            )
            base["ml"].update(info)
        except Exception as exc:  # defensive: never let ML break a forecast
            base["ml"]["note"] = f"Deep-learning model failed ({exc}); using best statistical model."
            method = base["best_method"] or "linear"
            base["method"] = method
            base["method_label"] = METHOD_LABELS[method]
            slope, r2, preds = _run_stat_model(values, method, horizon, alpha, window, band, validation)
    elif method == "ensemble":
        weights = _ensemble_weights(validation)
        slope, r2, preds = _ensemble_model(values, horizon, weights=weights, band=band)
    else:
        slope, r2, preds = _run_stat_model(values, method, horizon, alpha, window, band, validation)

    last_value = values[-1]
    forecast_points = []
    for k, (val, up, low) in enumerate(preds, start=1):
        forecast_points.append(
            {
                "year": years[-1] + k,
                "value": round(val, 2),
                "upper": round(up, 2),
                "lower": round(max(low, 0.0), 2),
            }
        )

    end_value = forecast_points[-1]["value"] if forecast_points else last_value
    direction = (
        "rising"
        if slope is not None and slope > 0.01
        else "falling"
        if slope is not None and slope < -0.01
        else "stable"
    )
    pct_change = ((end_value - last_value) / last_value * 100) if last_value else None

    risk = None
    years_to_threshold = None
    if metric == "stage":
        risk = _category_for_stage(end_value)
        if slope and slope > 0 and end_value > last_value:
            delta = 100.0 - last_value
            if delta > 0:
                t = math.ceil(delta / slope)
                if 0 < t <= horizon:
                    years_to_threshold = t

    base.update(
        {
            "forecast": forecast_points,
            "slope": round(slope, 4) if slope is not None else None,
            "r2": round(r2, 4) if r2 is not None else None,
            "direction": direction,
            "pct_change": round(pct_change, 2) if pct_change is not None else None,
            "end_value": round(end_value, 2),
            "risk": risk,
            "years_to_threshold": years_to_threshold,
            "note": _describe(
                metric,
                method,
                direction,
                slope,
                pct_change,
                last_value,
                end_value,
                years_to_threshold,
                unit,
                band=base["band"],
                ml_available=(None if method not in ML_METHODS else ml_available),
            ),
        }
    )
    if ml_degraded:
        base["note"] += (
            " Note: the requested deep-learning model needs the optional torch "
            "dependency (requirements-ml.txt), so the best validated statistical "
            "model was used instead."
        )
    return base


def _run_stat_model(
    values: list[float],
    method: str,
    horizon: int,
    alpha: float,
    window: int,
    band: str,
    validation: dict | None,
) -> tuple[float, float | None, list[tuple[float, float, float]]]:
    """Dispatch a statistical method with the requested confidence band."""
    if method == "moving_average":
        slope, r2, preds = _moving_average_model(values, horizon, window)
    elif method == "exponential":
        slope, r2, preds = _exponential_model(values, horizon, alpha)
    elif method == "arima":
        slope, r2, preds = _arima_model(values, horizon)
    elif method == "holt":
        slope, r2, preds = _holt_model(values, horizon)
    else:
        slope, r2, preds = _linear_model(values, horizon)
    if band == "bootstrap":
        med, low, high = _bootstrap_fan(values, horizon)
        preds = [(m, h, l) for m, l, h in zip(med, low, high)]
    return slope, r2, preds
