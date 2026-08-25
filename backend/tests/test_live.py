"""Tests for the live government data sync (NWDP CGWB telemetry + IMD rainfall)."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base
from app.ingres import live
from app.ingres.live import LIVE_DATASET_NAME, match_unit, sync_live_data
from app.models.groundwater import (
    AssessmentUnit,
    Dataset,
    District,
    GroundwaterLevel,
    GroundwaterRainfall,
    State,
    Village,
)


@pytest.fixture()
def live_db():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    TestingSession = sessionmaker(bind=engine, expire_on_commit=False)
    db = TestingSession()
    state = State(name="Test State", code="TS", region="South")
    db.add(state)
    db.flush()
    district = District(state_id=state.id, name="Test District")
    db.add(district)
    db.flush()
    village = Village(
        district_id=district.id,
        name="Test Village A",
        latitude=17.0,
        longitude=79.0,
        is_demo=False,
    )
    db.add(village)
    db.flush()
    db.add(
        AssessmentUnit(
            state_id=state.id,
            district_id=district.id,
            village_id=village.id,
            name="Station A",
            unit_type="station",
            latitude=17.0,
            longitude=79.0,
            is_demo=False,
        )
    )
    db.commit()
    try:
        yield db
    finally:
        db.close()
        engine.dispose()


def _reading(**overrides) -> dict:
    rec = {
        "Station": "Station A",
        "State": "Test State",
        "District": "Test District",
        "Latitude": "17.0",
        "Longitude": "79.0",
        "Data Acquisition Time": "10-08-2026 12:00",
        "Groundwater Level Telemetry 6 Hourly (meter)": "-3.5",
    }
    rec.update(overrides)
    return rec


def test_match_unit_exact_village():
    index = [{"id": 1, "district": "testdistrict", "name": "stationa", "lat": 17.0, "lon": 79.0}]
    assert match_unit(index, "Test District", "Station A", 17.0, 79.0, 15) == 1


def test_match_unit_nearest_within_radius():
    index = [
        {"id": 1, "district": "other", "name": "zzz", "lat": 17.01, "lon": 79.01},
        {"id": 2, "district": "other", "name": "yyy", "lat": 17.5, "lon": 79.5},
    ]
    assert match_unit(index, "Test District", "Station X", 17.01, 79.01, 15) == 1


def test_match_unit_outside_radius_returns_none():
    index = [{"id": 1, "district": "other", "name": "zzz", "lat": 17.0, "lon": 79.0}]
    assert match_unit(index, "Test District", "Station X", 30.0, 79.0, 15) is None


def test_sync_overlays_levels_and_rainfall(live_db, monkeypatch):
    monkeypatch.setattr(
        live, "fetch_nwdp_resources",
        lambda: [{"state": "Test State", "resource_id": "r1", "name": "x"}],
    )
    monkeypatch.setattr(live, "fetch_nwdp_latest", lambda resource_id: [_reading()])
    monkeypatch.setattr(
        live, "fetch_imd_rainfall",
        lambda: [{"state": "Test State", "district": "Test District",
                  "monthly_date": "01-08-2026 To 31-08-2026", "monthly_actual": "45.2"}],
    )
    monkeypatch.setenv("IMD_API_KEY", "test-key")
    from app.config import get_settings

    get_settings.cache_clear()

    result = sync_live_data(live_db)

    assert result["states"] == 1
    assert result["stations"] == 1
    assert result["levels"] == 1
    assert result["rainfall"] == 1

    level = live_db.scalar(select(GroundwaterLevel))
    assert level.depth_bgl == Decimal("3.50")
    assert level.water_level_class == "shallow"
    assert level.measured_date == date(2026, 8, 10)
    assert level.dataset_id == result["dataset_id"]

    rain = live_db.scalar(select(GroundwaterRainfall))
    assert rain.value_mm == Decimal("45.20")
    assert rain.year == 2026
    assert rain.month == 8

    dataset = live_db.scalar(select(Dataset).where(Dataset.name == LIVE_DATASET_NAME))
    assert dataset is not None

    # Idempotent: a second sync replaces, never duplicates.
    sync_live_data(live_db)
    assert len(list(live_db.scalars(select(GroundwaterLevel)))) == 1
    assert len(list(live_db.scalars(select(GroundwaterRainfall)))) == 1


def test_sync_skips_imd_without_key(live_db, monkeypatch):
    monkeypatch.setattr(
        live, "fetch_nwdp_resources",
        lambda: [{"state": "Test State", "resource_id": "r1", "name": "x"}],
    )
    monkeypatch.setattr(live, "fetch_nwdp_latest", lambda resource_id: [_reading()])
    monkeypatch.delenv("IMD_API_KEY", raising=False)
    from app.config import get_settings

    get_settings.cache_clear()

    result = sync_live_data(live_db)
    assert result["levels"] == 1
    assert result["rainfall"] == 0
    assert result["skipped"]["imd"] == "no IMD_API_KEY configured"


def test_sync_skipped_when_lock_held(live_db):
    assert live._LIVE_LOCK.acquire(blocking=False)
    try:
        result = sync_live_data(live_db)
        assert result["skipped"] is True
        assert "already running" in result["reason"]
    finally:
        live._LIVE_LOCK.release()


def test_partial_sync_preserves_other_states(live_db, monkeypatch):
    """Syncing a subset of states must not wipe live rows for other states."""
    from app.models.groundwater import State as StateModel

    db = live_db
    # Second state with its own unit (far away, distinct).
    st2 = StateModel(name="Test State Two", code="T2", region="South")
    db.add(st2)
    db.flush()
    d2 = District(state_id=st2.id, name="Other District")
    db.add(d2)
    db.flush()
    db.add(
        AssessmentUnit(
            state_id=st2.id,
            district_id=d2.id,
            name="Station Two",
            unit_type="station",
            latitude=10.0,
            longitude=77.0,
            is_demo=False,
        )
    )
    db.commit()

    def resources():
        return [
            {"state": "Test State", "resource_id": "r1", "name": "x"},
            {"state": "Test State Two", "resource_id": "r2", "name": "y"},
        ]

    def latest(resource_id):
        if resource_id == "r1":
            return [_reading()]
        return [_reading(
            Station="Station Two",
            State="Test State Two",
            District="Other District",
            Latitude="10.0",
            Longitude="77.0",
            **{
                "Data Acquisition Time": "11-08-2026 06:00",
                "Groundwater Level Telemetry 6 Hourly (meter)": "-6.2",
            },
        )]

    monkeypatch.setattr(live, "fetch_nwdp_resources", resources)
    monkeypatch.setattr(live, "fetch_nwdp_latest", latest)
    monkeypatch.setattr(live, "fetch_imd_rainfall", lambda: [])

    sync_live_data(db)  # full sync: both states
    assert len(list(db.scalars(select(GroundwaterLevel)))) == 2

    # Partial sync of only the first state: the second state's live row stays.
    sync_live_data(db, states=["test state"])
    levels = db.scalars(select(GroundwaterLevel)).all()
    assert len(levels) == 2
    units = {db.get(AssessmentUnit, l.assessment_unit_id).name for l in levels}
    assert units == {"Station A", "Station Two"}


def test_api_sync_live_endpoint(client, auth_admin, auth_user, monkeypatch):
    def fake_sync(db, states=None):
        return {
            "states": 1, "stations": 5, "levels": 5, "rainfall": 3,
            "skipped": {"imd": False}, "errors": [], "dataset_id": 99,
        }

    monkeypatch.setattr(live, "sync_live_data", fake_sync)
    resp = client.post("/api/admin/datasets/sync-live", params=[("states", "Telangana")], headers=auth_admin)
    assert resp.status_code == 200
    body = resp.json()
    assert body["levels"] == 5
    assert body["rainfall"] == 3

    resp = client.post("/api/admin/datasets/sync-live", headers=auth_user)
    assert resp.status_code in (401, 403)