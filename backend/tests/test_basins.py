"""Tests for Indian river basin scopes (Phase 21)."""

from app.ingres import basins, predict


def test_list_basins(client, db_session_factory):
    db = db_session_factory()
    try:
        rows = basins.list_basins(db)
    finally:
        db.close()
    assert len(rows) == 20
    names = {r["name"] for r in rows}
    assert {"Ganga", "Godavari", "Krishna", "Cauvery", "Narmada", "Indus"} <= names
    for row in rows:
        assert row["district_count"] >= 0
        assert row["states"]


def test_basin_district_ids(client, db_session_factory):
    db = db_session_factory()
    try:
        godavari = basins.basin_district_ids(db, "Godavari")
        assert len(godavari) > 0
        krishna = basins.basin_district_ids(db, "Krishna")
        assert len(krishna) > 0
        # Telangana splits between Godavari and Krishna.
        telangana_ids = set(godavari) | set(krishna)
        assert telangana_ids
    finally:
        db.close()


def test_unknown_basin_empty(client, db_session_factory):
    db = db_session_factory()
    try:
        assert basins.basin_district_ids(db, "Not a basin") == []
    finally:
        db.close()


def test_basin_scope_series(client, db_session_factory):
    db = db_session_factory()
    try:
        series = predict.get_scope_series(db, basin="Godavari", metric="stage")
        assert len(series) >= 2
        years = [p["year"] for p in series]
        assert years == sorted(years)
    finally:
        db.close()


def test_basin_forecast(client, db_session_factory):
    db = db_session_factory()
    try:
        fc = predict.forecast(db, basin="Godavari", metric="stage", horizon=3, method="linear")
        assert fc["scope"] == "Godavari"
        assert fc["basin"] == "Godavari"
        assert len(fc["forecast"]) == 3
        assert len(fc["historical"]) >= 2
    finally:
        db.close()


def test_basin_backtest(client, db_session_factory):
    db = db_session_factory()
    try:
        result = predict.backtest(db, basin="Krishna", metric="stage")
        assert result["scope"] == "Krishna"
        assert result["evaluation"] is not None
        assert result["best"] in result["evaluation"]
    finally:
        db.close()