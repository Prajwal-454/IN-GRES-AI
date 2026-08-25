"""Multi-scope comparison endpoints.

Compares any set of states, districts, villages and river basins
side-by-side: latest-year summary metrics, full annual trend series and an
overall better/worse verdict based on the stage of extraction.
"""

from __future__ import annotations

import re

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.database import get_db
from app.ingres.basins import basin_district_ids
from app.ingres.predict import get_scope_series
from app.ingres.query_cache import cache_get, cache_set
from app.ingres.queries import (
    find_village,
    get_summary,
    resolve_state,
)
from app.models.groundwater import District, State
from app.models.user import User

router = APIRouter(prefix="/comparison", tags=["comparison"])

_SCOPE_TOKEN = re.compile(r"^(state|district|village|basin):(.+)$", re.IGNORECASE)
_MAX_SCOPES = 6


def _resolve_district_anywhere(db: Session, name: str) -> District | None:
    return db.query(District).filter(func.lower(District.name) == name.strip().lower()).first()


def _parse_scope_token(db: Session, token: str) -> dict:
    """Resolve one ``kind:name`` token into a canonical scope dict."""
    match = _SCOPE_TOKEN.match(token.strip())
    if not match:
        raise HTTPException(
            400,
            f"Invalid scope '{token}'. Use kind:name with kind in "
            "state|district|village|basin.",
        )
    kind, name = match.group(1).lower(), match.group(2).strip()
    if not name:
        raise HTTPException(400, f"Invalid scope '{token}': missing name.")
    if len(name) > 120:
        raise HTTPException(400, f"Scope name too long: '{name[:40]}…'.")

    scope = {
        "key": f"{kind}:{name}",
        "kind": kind,
        "name": name,
        "label": name,
        "state": None,
        "district": None,
        "village": None,
        "basin": None,
        "resolved": False,
    }

    if kind == "state":
        state_obj = resolve_state(db, name)
        if state_obj is None:
            return scope
        scope.update(state=state_obj.name, label=state_obj.name, resolved=True)
        return scope

    if kind == "basin":
        if not basin_district_ids(db, name):
            # Accept the canonical casing of a known basin even when it has
            # no districts in the DB yet, so labels still resolve sensibly.
            from app.ingres.basins import BASIN_LABELS

            for canonical, label in BASIN_LABELS.items():
                if canonical.lower() == name.lower():
                    scope.update(basin=canonical, label=label, resolved=False)
                    return scope
            return scope
        scope.update(basin=name, resolved=True)
        return scope

    if kind == "district":
        district_obj = _resolve_district_anywhere(db, name)
        if district_obj is None:
            return scope
        state_obj = db.get(State, district_obj.state_id)
        scope.update(
            state=state_obj.name if state_obj else None,
            district=district_obj.name,
            label=f"{district_obj.name} ({state_obj.name})" if state_obj else district_obj.name,
            resolved=True,
        )
        return scope

    village_obj = find_village(db, name)
    if village_obj is None:
        return scope
    district_obj = db.get(District, village_obj.district_id)
    state_obj = db.get(State, district_obj.state_id) if district_obj else None
    scope.update(
        state=state_obj.name if state_obj else None,
        district=district_obj.name if district_obj else None,
        village=village_obj.name,
        label=village_obj.name,
        resolved=True,
    )
    return scope


def _scope_trend(db: Session, scope: dict) -> list[dict]:
    """Merged {year, recharge, extraction, stage} rows for one scope."""
    kwargs = dict(
        state=scope["state"],
        district=scope["district"],
        village=scope["village"],
        basin=scope["basin"],
    )
    series = {
        metric: {row["year"]: row["value"] for row in get_scope_series(db, metric=metric, **kwargs)}
        for metric in ("stage", "recharge", "extraction")
    }
    years = sorted(set().union(*(s.keys() for s in series.values())))
    return [
        {
            "year": year,
            "stage_of_extraction": round(series["stage"][year], 2) if year in series["stage"] else None,
            "recharge": round(series["recharge"][year], 2) if year in series["recharge"] else None,
            "extraction": round(series["extraction"][year], 2) if year in series["extraction"] else None,
        }
        for year in years
    ]


def compare_scopes_data(db: Session, scopes_param: str) -> dict:
    cache_key = ("comparison", tuple(sorted(s.strip().lower() for s in scopes_param.split(","))))
    cached = cache_get(cache_key)
    if isinstance(cached, dict):
        return cached

    tokens = [t for t in (s.strip() for s in scopes_param.split(",")) if t]
    if not tokens:
        raise HTTPException(400, "Provide at least one scope.")
    if len(tokens) > _MAX_SCOPES:
        raise HTTPException(400, f"Compare at most {_MAX_SCOPES} scopes at once.")

    results: list[dict] = []
    for token in tokens:
        scope = _parse_scope_token(db, token)
        entry = dict(scope)
        entry.pop("key")
        payload = {"key": scope["key"], **entry}
        if not scope["resolved"]:
            payload.update(summary=None, trend=[], latest_year=None)
            results.append(payload)
            continue

        summary = get_summary(
            db,
            state=scope["state"],
            district=scope["district"],
            village=scope["village"],
            basin=scope["basin"],
        )
        trend = _scope_trend(db, scope)
        payload.update(
            summary=summary,
            trend=trend,
            latest_year=trend[-1]["year"] if trend else None,
        )
        results.append(payload)

    # Verdict: lower final-year stage of extraction is better.
    verdict = None
    staged = [
        r
        for r in results
        if r["resolved"]
        and r["trend"]
        and r["trend"][-1]["stage_of_extraction"] is not None
    ]
    if len(staged) >= 2:
        ranked = sorted(staged, key=lambda r: r["trend"][-1]["stage_of_extraction"])
        verdict = {
            "metric": "stage_of_extraction",
            "best_key": ranked[0]["key"],
            "best_label": ranked[0]["label"],
            "worst_key": ranked[-1]["key"],
            "worst_label": ranked[-1]["label"],
            "best_value": ranked[0]["trend"][-1]["stage_of_extraction"],
            "worst_value": ranked[-1]["trend"][-1]["stage_of_extraction"],
        }

    out = {"scopes": results, "count": len(results), "verdict": verdict}
    cache_set(cache_key, out)
    return out


@router.get("/metrics")
def compare_scopes(
    scopes: str = Query(..., description="Comma-separated kind:name tokens, e.g. state:Telangana,basin:Krishna"),
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    """Compare up to six states/districts/villages/basins side-by-side."""
    return compare_scopes_data(db, scopes)
