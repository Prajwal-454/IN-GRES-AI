"""Rich structured sections for assistant answers.

Computes a JSON-serialisable ``sections`` payload (Answer -> Data -> Map ->
Graph -> Prediction -> Explanation -> Recommendation) that the chat frontend
renders as cards under the assistant's text reply. Every number is produced by
the (cached) structured query engine so nothing is hallucinated.

The payload shape consumed by ``frontend/src/components/ChatSections.tsx``::

    {
      "mode": "data" | "forecast" | "scenario" | "recommend",
      "data": {...},          # summary metrics + category counts + ranking
      "map": {...},           # FeatureCollection (district/unit or India states)
      "graph": {...},         # historical series + optional forecast lines
      "prediction": {...},    # forecast points with confidence band
      "explanation": str,
      "recommendation": [str, ...]
    }
"""

from __future__ import annotations

import logging

from sqlalchemy.orm import Session

from app.ai.assistant import (
    _category_label,
    _extract_location,
    _parse_scenario,
    _recommendations_for_stage,
    _village_scope,
    extract_horizon,
    extract_metric,
)
from app.api import analytics
from app.gis import service as gis_service
from app.ingres import predict, queries

logger = logging.getLogger(__name__)

MAP_METRICS = ("stage", "recharge", "extraction", "resource")
SERIES_METRICS = ("stage", "recharge", "extraction")


def _scope(
    db: Session, text: str, context: dict
) -> tuple[str | None, str | None, str | None]:
    state = context.get("state_name")
    district = context.get("district")
    village = context.get("village")
    if state is None and district is None and village is None:
        state, district, village, _display = _extract_location(db, text)
    return state, district, village


def _scope_label(state: str | None, district: str | None, village: str | None) -> str:
    if village:
        label = _village_scope(village)
        if district:
            label = f"{label}, {district}"
        if state:
            label = f"{label}, {state}"
        return label
    if district:
        return f"{district}, {state}" if state else district
    if state:
        return state
    return "All India"


def _series(
    db: Session,
    state: str | None,
    district: str | None,
    village: str | None,
    metric: str,
) -> list[dict]:
    """Yearly series for a scope. Uses the cached national/state aggregate when
    possible and the scoped aggregate otherwise."""
    metric = metric if metric in SERIES_METRICS else "stage"
    if district or village:
        return predict.get_scope_series(db, state, district, village, metric)
    rows = analytics.trends_data(db, state)
    key = "stage_of_extraction" if metric == "stage" else metric
    return [
        {"year": r["year"], "value": r[key]}
        for r in rows
        if r.get(key) is not None
    ]


def _data_section(
    db: Session,
    state: str | None,
    district: str | None,
    village: str | None,
    year: int | None,
) -> dict:
    summary = queries.get_summary(db, state=state, district=district, village=village)
    cat_counts = {c["category"]: c["count"] for c in summary["category_counts"]}
    stage = summary["average_stage_of_extraction"]
    resource = (
        round(summary["total_extraction"] / stage * 100, 2)
        if stage
        else None
    )
    ranking = _ranking(db, state, year)
    return {
        "scope": _scope_label(state, district, village),
        "year": year,
        "assessment_units": summary["assessment_units"],
        "recharge": round(summary["total_recharge"], 2),
        "extraction": round(summary["total_extraction"], 2),
        "stage": round(stage, 2),
        "resource": resource,
        "category": _category_label(stage) if stage else None,
        "category_counts": cat_counts,
        "ranking": ranking,
    }


def _ranking(db: Session, state: str | None, year: int | None) -> list[dict]:
    rows = analytics.district_ranking_data(db, state, year, "stage")
    out = []
    for r in rows[:10]:
        out.append(
            {
                "name": r["district"],
                "stage": r["stage_of_extraction"],
                "category": _category_label(r["stage_of_extraction"]),
            }
        )
    return out


def _map_section(
    db: Session,
    state: str | None,
    district: str | None,
    village: str | None,
    year: int | None,
    metric: str,
) -> dict:
    metric = metric if metric in MAP_METRICS else "stage"
    if state is None and district is None and village is None:
        india = gis_service.build_india_geojson(db, year, metric)
        return {
            "features": [],
            "india": india,
            "metric": metric,
            "year": india["meta"]["year"],
            "state": None,
            "district": None,
            "village": None,
        }
    geo = gis_service.build_geojson(
        db, state=state, district=district, village=village, year=year, metric=metric
    )
    return {
        "features": geo["features"],
        "india": None,
        "metric": metric,
        "year": geo["meta"]["year"],
        "state": state,
        "district": district,
        "village": village,
    }


def _graph_section(
    db: Session,
    state: str | None,
    district: str | None,
    village: str | None,
    metric: str,
    forecast: list[dict] | None = None,
    scenario_forecast: list[dict] | None = None,
) -> dict:
    metric = metric if metric in SERIES_METRICS else "stage"
    unit = "%" if metric == "stage" else "hm³"
    series = _series(db, state, district, village, metric)
    comparison = None
    other = "extraction" if metric in ("stage", "recharge") else "recharge"
    comp = _series(db, state, district, village, other)
    if comp:
        comparison = [{"year": p["year"], "value": round(p["value"], 2)} for p in comp]
    return {
        "metric": metric,
        "unit": unit,
        "series": [{"year": p["year"], "value": round(p["value"], 2)} for p in series],
        "comparison": comparison,
        "forecast": forecast,
        "scenario_forecast": scenario_forecast,
    }


def _prediction_section(fc: dict) -> dict | None:
    if not fc or not fc.get("forecast"):
        return None
    last = fc["historical"][-1] if fc["historical"] else {}
    return {
        "scope": fc["scope"],
        "metric": fc["metric"],
        "unit": fc["unit"],
        "direction": fc["direction"],
        "pct_change": fc["pct_change"],
        "r2": fc["r2"],
        "method": fc.get("best_method") or fc.get("method"),
        "risk": fc.get("risk"),
        "years_to_threshold": fc.get("years_to_threshold"),
        "last_value": last.get("value"),
        "last_year": last.get("year"),
        "end_value": fc["end_value"],
        "points": fc["forecast"],
    }


def _explanation(
    db: Session,
    state: str | None,
    district: str | None,
    village: str | None,
    metric: str,
) -> str:
    metric = metric if metric in SERIES_METRICS else "stage"
    stage_series = _series(db, state, district, village, "stage")
    if not stage_series:
        return (
            "The stage of extraction is the ratio of annual groundwater extraction to "
            "the annual extractable resource, expressed as a percentage. Values below "
            "70% are Safe, 70–90% Semi-critical, 90–100% Critical and above 100% "
            "Over-exploited."
        )

    current = stage_series[-1]["value"]
    lines = [
        f"Stage of extraction is the ratio of annual groundwater extraction to the "
        f"annual extractable resource. For this area the average stage is "
        f"{current:.1f}%, which is {_category_label(current)}."
    ]

    if len(stage_series) >= 2:
        first, last = stage_series[0], stage_series[-1]
        diff = last["value"] - first["value"]
        span = f"{first['year']}–{last['year']}"
        if diff > 1:
            lines.append(
                f"Stage rose from {first['value']:.1f}% in {first['year']} to "
                f"{last['value']:.1f}% in {last['year']} (+{diff:.1f} points), showing "
                f"rising pressure on groundwater over {span}."
            )
        elif diff < -1:
            lines.append(
                f"Stage fell from {first['value']:.1f}% in {first['year']} to "
                f"{last['value']:.1f}% in {last['year']} ({diff:.1f} points), suggesting "
                f"pressure is easing over {span}."
            )
        else:
            lines.append(
                f"Stage stayed roughly flat around {last['value']:.1f}% across {span}."
            )

    recharge = _series(db, state, district, village, "recharge")
    extraction = _series(db, state, district, village, "extraction")
    if len(recharge) >= 2 and len(extraction) >= 2:
        rec_growth = recharge[-1]["value"] - recharge[0]["value"]
        ext_growth = extraction[-1]["value"] - extraction[0]["value"]
        if ext_growth > rec_growth + 0.01:
            lines.append(
                f"Over the same period extraction grew by about {ext_growth:,.0f} hm³ "
                f"while recharge changed by {rec_growth:,.0f} hm³ — extraction rising "
                f"faster than recharge is the main driver of declining groundwater."
            )
        elif rec_growth < -0.01:
            lines.append(
                f"Recharge fell by about {abs(rec_growth):,.0f} hm³ while extraction "
                f"stayed relatively steady — reduced recharge (e.g. lower rainfall) is "
                f"the main driver of declining groundwater."
            )
    return " ".join(lines)


def build_sections(
    db: Session, text: str, result, context: dict | None = None
) -> dict | None:
    """Build the rich sections payload for an assistant result, or None."""
    context = context or {}
    intent = result.intent
    if intent not in ("data_query", "forecast", "scenario", "recommend"):
        return None
    try:
        return _build_sections_uncached(db, text, result, context)
    except Exception:  # pragma: no cover - defensive; never break the chat flow
        logger.exception("failed to build rich sections")
        return None


def _build_sections_uncached(
    db: Session, text: str, result, context: dict
) -> dict:
    intent = result.intent
    mode = {
        "recommend": "recommend",
        "scenario": "scenario",
        "forecast": "forecast",
        "data_query": "data",
    }[intent]

    state, district, village = _scope(db, text, context)
    metric = context.get("metric") or extract_metric(text) or "stage"
    year = context.get("year")
    if year is None:
        year = queries.get_latest_year(db, state=state, district=district, village=village)

    sections: dict = {"mode": mode, "data": _data_section(db, state, district, village, year)}
    sections["explanation"] = _explanation(db, state, district, village, metric)
    sections["recommendation"] = _recommendations_for_stage(sections["data"]["stage"])

    if mode in ("data", "forecast", "scenario"):
        sections["map"] = _map_section(db, state, district, village, year, metric)

        forecast_points = None
        scenario_points = None
        prediction = None
        if mode in ("forecast", "scenario") or len(
            _series(db, state, district, village, metric)
        ) >= 2:
            horizon = extract_horizon(text)
            if mode == "scenario":
                base_fc = predict.forecast(
                    db, state=state, district=district, village=village,
                    metric=metric, horizon=horizon, method="auto",
                )
                scen_fc = predict.forecast(
                    db, state=state, district=district, village=village,
                    metric=metric, horizon=horizon, method="auto",
                    scenario=_parse_scenario(text),
                )
                prediction = _prediction_section(scen_fc)
                forecast_points = base_fc["forecast"]
                scenario_points = scen_fc["forecast"]
            else:
                fc = predict.forecast(
                    db, state=state, district=district, village=village,
                    metric=metric, horizon=horizon, method="auto",
                )
                prediction = _prediction_section(fc)
                forecast_points = fc["forecast"]

        sections["graph"] = _graph_section(
            db, state, district, village, metric,
            forecast=forecast_points, scenario_forecast=scenario_points,
        )
        if prediction:
            sections["prediction"] = prediction

    return sections