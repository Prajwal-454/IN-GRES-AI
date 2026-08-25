"""Tests for the real (CGWB/IMD) state-CSV import and dataset preference."""

from __future__ import annotations

import csv
from decimal import Decimal
from pathlib import Path

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base
from app.ingres import queries
from app.ingres.real_import import REAL_DATASET_NAME, import_real_dataset, refresh_real_dataset
from app.models.groundwater import (
    AssessmentUnit,
    Dataset,
    DatasetFileState,
    District,
    GroundwaterAssessment,
    GroundwaterLevel,
    GroundwaterRainfall,
    State,
    Village,
)

_HEADER = (
    "state_name,district_name,block_name,mandal_name,village_name,location_name,"
    "latitude,longitude,observation_year,observation_month,observation_period,"
    "groundwater_depth_m,gwra_year,gwra_category,annual_groundwater_recharge_bcm,"
    "annual_extractable_groundwater_resource_bcm,annual_groundwater_extraction_bcm,"
    "stage_of_groundwater_extraction_percent,rainfall_mm,rainfall_period,"
    "geography_match_type,confidence_score,data_quality_status,"
    "data_source_groundwater,data_source_gwra,data_source_rainfall,"
    "groundwater_source_type,gwra_source_type,rainfall_source_type,"
    "groundwater_extraction_method,gwra_extraction_method,rainfall_extraction_method,"
    "groundwater_source_page,gwra_source_page,rainfall_source_page,source_url"
)


def _row(**overrides) -> list[str]:
    values = {
        "state_name": "test state",
        "district_name": "Test District",
        "block_name": "Block A",
        "mandal_name": "Block A",
        "village_name": "Test Village A",
        "location_name": "Test Station A",
        "latitude": "17.0",
        "longitude": "79.0",
        "observation_year": "2025",
        "observation_month": "8",
        "observation_period": "August",
        "groundwater_depth_m": "4.5",
        "gwra_year": "2025",
        "gwra_category": "Safe",
        "annual_groundwater_recharge_bcm": "0.5",
        "annual_extractable_groundwater_resource_bcm": "0.45",
        "annual_groundwater_extraction_bcm": "0.2",
        "stage_of_groundwater_extraction_percent": "44.44",
        "rainfall_mm": "120.5",
        "rainfall_period": "monthly",
        "geography_match_type": "normalized_exact",
        "confidence_score": "0.9",
        "data_quality_status": "valid",
        "data_source_groundwater": "August_WL_1994-2025.pdf",
        "data_source_gwra": "GWRA_2025.pdf",
        "data_source_rainfall": "IMD Gridded Rainfall (0.25x0.25 deg)",
        "groundwater_source_type": "local_pdf",
        "gwra_source_type": "local_pdf",
        "rainfall_source_type": "official_web_fallback",
        "groundwater_extraction_method": "pdf_text",
        "gwra_extraction_method": "pdf_table",
        "rainfall_extraction_method": "netcdf_spatial_lookup",
        "groundwater_source_page": "1",
        "gwra_source_page": "NULL",
        "rainfall_source_page": "NULL",
        "source_url": "https://cgwb.gov.in",
    }
    values.update(overrides)
    return [values[k] for k in _HEADER.split(",")]


def _write_state_csv(dir_path: Path, filename: str, rows: list[list[str]]) -> Path:
    path = dir_path / filename
    with open(path, "w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(_HEADER.split(","))
        writer.writerows(rows)
    return path


@pytest.fixture()
def real_csv_dir(tmp_path: Path) -> Path:
    rows = [
        _row(),  # full GWRA assessment + level + rainfall
        _row(
            village_name="Test Village B",
            location_name="Test Station B",
            groundwater_depth_m="12.3",
            gwra_year="NULL",
            gwra_category="NULL",
            annual_groundwater_recharge_bcm="NULL",
            annual_extractable_groundwater_resource_bcm="NULL",
            annual_groundwater_extraction_bcm="NULL",
            stage_of_groundwater_extraction_percent="NULL",
            rainfall_mm="80.0",
        ),  # level + rainfall only, no assessment
    ]
    _write_state_csv(tmp_path, "test_state.csv", rows)
    return tmp_path


@pytest.fixture()
def real_db(real_csv_dir: Path):
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    TestingSession = sessionmaker(bind=engine, expire_on_commit=False)
    db = TestingSession()
    try:
        yield db
    finally:
        db.close()
        engine.dispose()


def test_import_creates_real_dataset(real_db, real_csv_dir: Path):
    result = import_real_dataset(real_db, states_dir=real_csv_dir)

    assert result["skipped"] is False
    assert result["states"] == 1
    assert result["rows"] == 2
    assert result["villages"] == 2
    assert result["units"] == 2

    dataset = real_db.scalar(select(Dataset).where(Dataset.name == REAL_DATASET_NAME))
    assert dataset is not None
    assert dataset.is_demo is False

    units = list(real_db.scalars(select(AssessmentUnit)))
    assert len(units) == 2
    assert all(u.is_demo is False for u in units)
    assert all(u.unit_type == "station" for u in units)
    villages = list(real_db.scalars(select(Village)))
    assert len(villages) == 2
    assert all(v.is_demo is False for v in villages)

    assessments = list(real_db.scalars(select(GroundwaterAssessment)))
    assert len(assessments) == 1  # only the row with GWRA data
    a = assessments[0]
    assert a.assessment_year == 2025
    assert float(a.recharge_total) == 500.0  # 0.5 bcm -> hm³
    assert float(a.annual_extractable_resource) == 450.0
    assert float(a.extraction_total) == 200.0
    assert float(a.stage_of_extraction) == 44.44
    assert a.category == "safe"
    assert a.is_demo is False

    levels = list(real_db.scalars(select(GroundwaterLevel)))
    assert len(levels) == 2
    assert levels[0].water_level_class == "shallow"
    assert levels[1].water_level_class == "deep"

    rainfall = list(real_db.scalars(select(GroundwaterRainfall)))
    assert len(rainfall) == 2
    assert float(rainfall[0].value_mm) == 120.5


def test_import_is_idempotent(real_db, real_csv_dir: Path):
    first = import_real_dataset(real_db, states_dir=real_csv_dir)
    second = import_real_dataset(real_db, states_dir=real_csv_dir)
    assert second["skipped"] is True
    assert second["dataset_id"] == first["dataset_id"]
    assert len(list(real_db.scalars(select(AssessmentUnit)))) == 2


def test_real_data_preferred_over_demo(real_db, real_csv_dir: Path):
    import_real_dataset(real_db, states_dir=real_csv_dir)

    mode = queries.resolve_dataset_mode(real_db)
    assert mode == "real"

    summary = queries.get_summary(real_db)
    assert summary["is_demo"] is False
    assert "CGWB" in summary["source"]
    assert summary["assessment_units"] == 1  # only the row with GWRA data

    rows = queries.get_assessments(real_db)
    assert len(rows) == 1
    assert all(r.is_demo is False for r in rows)

    # Forced dataset selections.
    assert len(queries.get_assessments(real_db, data_source="demo")) == 0
    assert len(queries.get_assessments(real_db, data_source="all")) == 1


def test_real_units_without_assessments_fall_back_to_demo(real_db, real_csv_dir: Path):
    import_real_dataset(real_db, states_dir=real_csv_dir)

    state = real_db.scalar(select(State).where(State.name == "Test State"))
    district = District(state_id=state.id, name="Empty District")
    real_db.add(district)
    real_db.flush()

    real_db.add_all(
        [
            AssessmentUnit(
                state_id=state.id,
                district_id=district.id,
                name="Empty Station",
                code="TS-EMPTY",
                unit_type="station",
                is_demo=False,
            ),
            AssessmentUnit(
                state_id=state.id,
                district_id=district.id,
                name="Demo Village",
                code="TS-DEMO",
                unit_type="village",
                is_demo=True,
            ),
        ]
    )
    real_db.flush()

    demo_unit = real_db.scalar(
        select(AssessmentUnit).where(
            AssessmentUnit.district_id == district.id, AssessmentUnit.is_demo.is_(True)
        )
    )
    real_db.add(
        GroundwaterAssessment(
            assessment_unit_id=demo_unit.id,
            assessment_year=2023,
            recharge_total=Decimal("10"),
            extraction_total=Decimal("5"),
            annual_extractable_resource=Decimal("8"),
            stage_of_extraction=Decimal("62.5"),
            category="safe",
            is_demo=True,
        )
    )
    real_db.commit()

    assert queries.resolve_dataset_mode(real_db, district_id=district.id) == "demo"

    summary = queries.get_summary(real_db, state="test state", district="Empty District")
    assert summary["is_demo"] is True
    assert summary["assessment_units"] == 1


def test_refresh_imports_when_dataset_missing(real_db, real_csv_dir: Path):
    result = refresh_real_dataset(real_db, states_dir=real_csv_dir)
    assert result["skipped"] is False
    assert result["states"] == 1
    assert result["updated"] == ["test_state"]

    fingerprints = real_db.scalars(select(DatasetFileState)).all()
    assert len(fingerprints) == 1
    assert fingerprints[0].filename == "test_state.csv"


def test_refresh_skips_unchanged_files(real_db, real_csv_dir: Path):
    import_real_dataset(real_db, states_dir=real_csv_dir)

    result = refresh_real_dataset(real_db, states_dir=real_csv_dir)
    assert result["skipped"] is False
    assert result["updated"] == []
    assert result["unchanged"] == ["test_state"]
    assert result["states"] == 0

    assert len(list(real_db.scalars(select(AssessmentUnit)))) == 2
    assert len(list(real_db.scalars(select(Village)))) == 2


def test_refresh_reimports_changed_state(real_db, real_csv_dir: Path):
    import_real_dataset(real_db, states_dir=real_csv_dir)
    summary = queries.get_summary(real_db, state="test state")
    assert summary["total_recharge"] == 500.0

    _write_state_csv(
        real_csv_dir,
        "test_state.csv",
        [
            _row(annual_groundwater_recharge_bcm="0.7"),
            _row(
                village_name="Test Village B",
                location_name="Test Station B",
                groundwater_depth_m="12.3",
                gwra_year="NULL",
                gwra_category="NULL",
                annual_groundwater_recharge_bcm="NULL",
                annual_extractable_groundwater_resource_bcm="NULL",
                annual_groundwater_extraction_bcm="NULL",
                stage_of_groundwater_extraction_percent="NULL",
                rainfall_mm="80.0",
            ),
        ],
    )

    result = refresh_real_dataset(real_db, states_dir=real_csv_dir)
    assert result["updated"] == ["test_state"]
    assert result["states"] == 1

    summary = queries.get_summary(real_db, state="test state")
    assert summary["total_recharge"] == 700.0

    # Old real rows were replaced, not duplicated.
    assert len(list(real_db.scalars(select(AssessmentUnit)))) == 2
    assert len(list(real_db.scalars(select(Village)))) == 2
    assert len(list(real_db.scalars(select(GroundwaterAssessment)))) == 1

    fingerprint = real_db.scalar(
        select(DatasetFileState).where(DatasetFileState.filename == "test_state.csv")
    )
    assert fingerprint is not None


def test_refresh_force_reimports_all(real_db, real_csv_dir: Path):
    import_real_dataset(real_db, states_dir=real_csv_dir)

    result = refresh_real_dataset(real_db, states_dir=real_csv_dir, force=True)
    assert result["updated"] == ["test_state"]
    assert result["unchanged"] == []
    assert result["states"] == 1


def test_api_import_real_endpoint(client, auth_admin, auth_user, monkeypatch):
    import app.ingres.real_import as real_import

    called = {}

    def fake_import(db, states=None):
        called["states"] = states
        return {
            "skipped": False,
            "dataset_id": 42,
            "states": 1,
            "rows": 2,
            "villages": 2,
            "units": 2,
            "districts": 1,
        }

    monkeypatch.setattr(real_import, "import_real_dataset", fake_import)
    resp = client.post(
        "/api/admin/datasets/import-real",
        params=[("states", "telangana"), ("states", "karnataka")],
        headers=auth_admin,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["dataset_id"] == 42
    assert body["units"] == 2
    assert called["states"] == ["telangana", "karnataka"]

    resp = client.post("/api/admin/datasets/import-real", headers=auth_user)
    assert resp.status_code in (401, 403)


def test_api_import_real_refresh_endpoint(client, auth_admin, auth_user, monkeypatch):
    import app.ingres.real_import as real_import

    called = {}

    def fake_refresh(db, states=None, force=False):
        called["states"] = states
        called["force"] = force
        return {
            "skipped": False,
            "dataset_id": 42,
            "states": 1,
            "rows": 2,
            "villages": 2,
            "units": 2,
            "districts": 1,
            "updated": ["telangana"],
            "unchanged": [],
        }

    monkeypatch.setattr(real_import, "refresh_real_dataset", fake_refresh)
    resp = client.post(
        "/api/admin/datasets/import-real",
        params=[("states", "telangana"), ("refresh", "true")],
        headers=auth_admin,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["updated"] == ["telangana"]
    assert called["states"] == ["telangana"]

    resp = client.post("/api/admin/datasets/import-real", headers=auth_user)
    assert resp.status_code in (401, 403)


def test_api_rainfall_endpoint(client, auth_user):
    resp = client.get("/api/groundwater/rainfall", headers=auth_user)
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


def test_api_summary_data_source(client, auth_user):
    resp = client.get(
        "/api/groundwater/summary", params={"data_source": "real"}, headers=auth_user
    )
    assert resp.status_code == 200
    body = resp.json()
    assert "is_demo" in body and "source" in body
