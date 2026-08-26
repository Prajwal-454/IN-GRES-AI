from __future__ import annotations

import random
from decimal import Decimal

from geoalchemy2 import WKTElement
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.groundwater import (
    AssessmentCategory,
    AssessmentUnit,
    Dataset,
    District,
    GroundwaterAssessment,
    GroundwaterExtraction,
    GroundwaterRecharge,
    State,
    Village,
)
from app.ingres.query_cache import invalidate_analytics_cache

DEMO_STATES: dict[str, dict] = {
    "Andhra Pradesh": {
        "code": "AP",
        "region": "South India",
        "districts": {
            "Visakhapatnam": (17.69, 83.22, "normal"),
            "Guntur": (16.31, 80.44, "normal"),
            "Krishna": (16.43, 80.99, "wet"),
            "Chittoor": (13.21, 79.10, "dry"),
            "Anantapur": (14.68, 77.60, "dry"),
            "Kurnool": (15.83, 78.03, "dry"),
            "Nellore": (14.45, 79.99, "wet"),
            "Srikakulam": (18.29, 83.90, "wet"),
            "Vizianagaram": (18.11, 83.41, "wet"),
            "East Godavari": (17.00, 81.80, "wet"),
            "West Godavari": (16.80, 81.20, "wet"),
            "Prakasam": (15.50, 79.70, "normal"),
            "YSR Kadapa": (14.47, 78.82, "dry"),
        },
    },
    "Telangana": {
        "code": "TS",
        "region": "South India",
        "districts": {
            "Hyderabad": (17.38, 78.48, "normal"),
            "Warangal": (17.97, 79.60, "normal"),
            "Karimnagar": (18.44, 79.13, "normal"),
            "Nizamabad": (18.67, 78.09, "dry"),
            "Khammam": (17.25, 80.15, "wet"),
            "Mahbubnagar": (16.74, 77.99, "dry"),
            "Nalgonda": (17.05, 79.27, "normal"),
            "Medak": (17.77, 78.10, "dry"),
            "Adilabad": (19.67, 78.53, "dry"),
        },
    },
}

DEMO_YEARS = [2017, 2018, 2019, 2020, 2021, 2022, 2023, 2024, 2025, 2026]

BASE_STAGE: dict[str, tuple[float, float]] = {
    "wet": (52.0, 78.0),
    "normal": (70.0, 95.0),
    "dry": (98.0, 125.0),
}

DROUGHT_YEARS = {2018, 2019}


def _square_wkt(lat: float, lon: float, size: float = 0.7) -> str:
    h = size / 2
    return (
        f"POLYGON(({lon - h:.4f} {lat - h:.4f},{lon + h:.4f} {lat - h:.4f},"
        f"{lon + h:.4f} {lat + h:.4f},{lon - h:.4f} {lat + h:.4f},{lon - h:.4f} {lat - h:.4f}))"
    )


def _point_wkt(lat: float, lon: float) -> str:
    return f"POINT({lon:.4f} {lat:.4f})"


def _category_for_stage(stage: float) -> str:
    if stage < 70:
        return "safe"
    if stage < 90:
        return "semi-critical"
    if stage <= 100:
        return "critical"
    return "over-exploited"


def _district_profiles() -> dict[str, str]:
    profiles: dict[str, str] = {}
    for info in DEMO_STATES.values():
        for district_name, (_lat, _lon, profile) in info["districts"].items():
            profiles[district_name] = profile
    return profiles


def _topup_missing_years(db: Session, dataset: Dataset) -> bool:
    """Backfill assessment rows for DEMO_YEARS added after the dataset was
    first seeded (e.g. 2023-2026 on databases created earlier)."""
    seeded = set(
        db.scalars(
            select(GroundwaterAssessment.assessment_year).where(
                GroundwaterAssessment.dataset_id == dataset.id
            )
        ).all()
    )
    missing = [year for year in DEMO_YEARS if year not in seeded]
    if not missing:
        return False

    profiles = _district_profiles()
    profile_by_district = {
        d_id: profiles.get(d_name, "normal")
        for d_id, d_name in db.execute(select(District.id, District.name)).all()
    }
    units = db.scalars(select(AssessmentUnit).where(AssessmentUnit.is_demo.is_(True))).all()
    rng = random.Random(1234)

    for unit in units:
        low, high = BASE_STAGE[profile_by_district.get(unit.district_id or 0, "normal")]
        for year in missing:
            year_idx = DEMO_YEARS.index(year)
            base_stage = rng.uniform(low, high)
            drought = -12 if year in DROUGHT_YEARS else 0
            growth = year_idx * 1.5
            stage = max(25.0, min(140.0, base_stage + drought + growth + rng.uniform(-6, 6)))

            recharge_total = round(rng.uniform(90, 260) * (0.9 if year in DROUGHT_YEARS else 1.0), 2)
            annual_extractable = round(recharge_total * rng.uniform(0.85, 0.95), 2)
            extraction_total = round(annual_extractable * (stage / 100), 2)

            db.add(
                GroundwaterAssessment(
                    assessment_unit_id=unit.id,
                    dataset_id=dataset.id,
                    assessment_year=year,
                    recharge_total=Decimal(str(recharge_total)),
                    extraction_total=Decimal(str(extraction_total)),
                    annual_extractable_resource=Decimal(str(annual_extractable)),
                    stage_of_extraction=Decimal(str(round(stage, 2))),
                    category=_category_for_stage(stage),
                    is_demo=True,
                )
            )
            db.add(
                GroundwaterRecharge(
                    assessment_unit_id=unit.id,
                    dataset_id=dataset.id,
                    year=year,
                    recharge_type="total",
                    value=Decimal(str(recharge_total)),
                    is_demo=True,
                )
            )
            db.add(
                GroundwaterExtraction(
                    assessment_unit_id=unit.id,
                    dataset_id=dataset.id,
                    year=year,
                    extraction_type="total",
                    value=Decimal(str(extraction_total)),
                    is_demo=True,
                )
            )

    db.commit()
    invalidate_analytics_cache()
    print(f"Backfilled demo dataset with years: {missing}")
    return True


def seed_demo_groundwater(db: Session) -> None:
    existing = db.scalar(select(Dataset).where(Dataset.name == "Synthetic Groundwater Assessment Dataset"))
    if existing:
        _topup_missing_years(db, existing)
        return

    dataset = Dataset(
        name="Synthetic Groundwater Assessment Dataset",
        description=(
            "Clearly synthetic development data for demo purposes only. "
            "Not official IN-GRES or CGWB data."
        ),
        source="Synthetic Development Dataset",
        source_url=None,
        publication_year=2023,
        version="1.0",
        geographic_level="assessment unit",
        unit="hm³",
        validation_status="demo",
        is_demo=True,
    )
    db.add(dataset)
    db.flush()

    for name, label, description in [
        ("safe", "Safe", "Stage of groundwater extraction below 70%."),
        ("semi-critical", "Semi-critical", "Stage of groundwater extraction between 70% and 90%."),
        ("critical", "Critical", "Stage of groundwater extraction between 90% and 100%."),
        ("over-exploited", "Over-exploited", "Stage of groundwater extraction above 100%."),
    ]:
        db.add(AssessmentCategory(name=name, label=label, description=description, is_official=False))

    has_geom = "geom" in AssessmentUnit.__table__.columns
    rng = random.Random(42)

    for state_name, info in DEMO_STATES.items():
        state = State(name=state_name, code=info["code"], region=info["region"])
        db.add(state)
        db.flush()

        for district_name, (lat, lon, profile) in info["districts"].items():
            district = District(state_id=state.id, name=district_name)
            db.add(district)
            db.flush()

            village = Village(
                district_id=district.id,
                name=f"{district_name} Village",
                code=f"{info['code']}-{district_name[:3].upper()}-V",
                population=int(rng.uniform(5_000, 150_000)),
                latitude=lat,
                longitude=lon,
                is_demo=True,
            )
            db.add(village)
            db.flush()

            unit = AssessmentUnit(
                state_id=state.id,
                district_id=district.id,
                village_id=village.id,
                name=f"{district_name} Village",
                code=f"{info['code']}-{district_name[:3].upper()}",
                unit_type="assessment_unit",
                latitude=lat,
                longitude=lon,
                is_demo=True,
            )
            if has_geom:
                unit.geom = WKTElement(_square_wkt(lat, lon), srid=4326)
                unit.centroid = WKTElement(_point_wkt(lat, lon), srid=4326)
            db.add(unit)
            db.flush()

            low, high = BASE_STAGE[profile]
            for year in DEMO_YEARS:
                year_idx = DEMO_YEARS.index(year)
                base_stage = rng.uniform(low, high)
                drought = -12 if year in DROUGHT_YEARS else 0
                growth = year_idx * 1.5
                stage = max(25.0, min(140.0, base_stage + drought + growth + rng.uniform(-6, 6)))

                recharge_total = round(rng.uniform(90, 260) * (0.9 if year in DROUGHT_YEARS else 1.0), 2)
                annual_extractable = round(recharge_total * rng.uniform(0.85, 0.95), 2)
                extraction_total = round(annual_extractable * (stage / 100), 2)
                category = _category_for_stage(stage)

                db.add(
                    GroundwaterAssessment(
                        assessment_unit_id=unit.id,
                        dataset_id=dataset.id,
                        assessment_year=year,
                        recharge_total=Decimal(str(recharge_total)),
                        extraction_total=Decimal(str(extraction_total)),
                        annual_extractable_resource=Decimal(str(annual_extractable)),
                        stage_of_extraction=Decimal(str(round(stage, 2))),
                        category=category,
                        is_demo=True,
                    )
                )
                db.add(
                    GroundwaterRecharge(
                        assessment_unit_id=unit.id,
                        dataset_id=dataset.id,
                        year=year,
                        recharge_type="total",
                        value=Decimal(str(recharge_total)),
                        is_demo=True,
                    )
                )
                db.add(
                    GroundwaterExtraction(
                        assessment_unit_id=unit.id,
                        dataset_id=dataset.id,
                        year=year,
                        extraction_type="total",
                        value=Decimal(str(extraction_total)),
                        is_demo=True,
                    )
                )

    db.commit()
    invalidate_analytics_cache()
    print("Seeded synthetic groundwater demo dataset")