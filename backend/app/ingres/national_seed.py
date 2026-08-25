"""National all-India synthetic groundwater seed.

Creates every Indian state/union territory, its real districts, a deterministic
synthetic village layer (default target ~600,000 villages), and per-village
groundwater assessments for a set of years. All rows are labelled as demo
data and are not official IN-GRES/CGWB numbers.

The seed is idempotent: it refuses to run twice for the same dataset and uses
bulk (executemany) inserts with batched commits so the full national run stays
fast enough to use on both SQLite and Postgres.
"""

from __future__ import annotations

from decimal import Decimal

from sqlalchemy import insert, select, text
from sqlalchemy.orm import Session

from app.ingres.demo_data import BASE_STAGE, DEMO_YEARS, DROUGHT_YEARS, _category_for_stage
from app.ingres.query_cache import invalidate_analytics_cache
from app.ingres.india_data import (
    DISTRICTS_BY_STATE,
    INDIA_STATES,
    district_centroid,
    generate_population,
    generate_village_coords,
    generate_village_names,
    random_for,
    state_info,
    village_count_for,
)
from app.gis.geo import india_polygons
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

NATIONAL_DATASET_NAME = "National Synthetic Groundwater Assessment Dataset"
_BATCH = 20_000

_STAGE_LOW = {"wet": 45.0, "normal": 65.0, "dry": 90.0}
_STAGE_HIGH = {"wet": 70.0, "normal": 95.0, "dry": 120.0}


def _insert_many(db: Session, model, rows: list[dict]) -> None:
    """Bulk insert a list of row dicts via executemany (respects bind-param limits)."""
    for start in range(0, len(rows), _BATCH):
        chunk = rows[start : start + _BATCH]
        db.execute(insert(model), chunk)


def _tune_for_bulk(db: Session) -> None:
    """Speed up the bulk seed (SQLite journal/sync settings; no-op on Postgres)."""
    if db.bind.dialect.name != "sqlite":
        return
    db.execute(text("PRAGMA journal_mode=WAL"))
    db.execute(text("PRAGMA synchronous=OFF"))
    db.execute(text("PRAGMA cache_size=-64000"))
    db.execute(text("PRAGMA temp_store=MEMORY"))
    db.commit()


def _village_assessment_rows(
    unit_ids: list[int],
    names: list[str],
    populations: list[int],
    coords: list[tuple[float, float]],
    district_id: int,
    state_id: int,
    dataset_id: int,
    profile: str,
    code_prefix: str,
) -> tuple[list[dict], list[dict], list[dict]]:
    """Build assessment, recharge and extraction rows for a set of villages."""
    assessments: list[dict] = []
    recharges: list[dict] = []
    extractions: list[dict] = []

    low = _STAGE_LOW[profile]
    high = _STAGE_HIGH[profile]

    for idx, unit_id in enumerate(unit_ids):
        name = names[idx]
        population = populations[idx]
        lat, lon = coords[idx]
        seed_key = f"{district_id}:{idx}"

        for year in DEMO_YEARS:
            rng = random_for(f"{seed_key}:{year}")
            year_idx = DEMO_YEARS.index(year)
            base_stage = rng.uniform(low, high)
            drought = -10 if year in DROUGHT_YEARS else 0
            growth = year_idx * 1.2
            stage = max(25.0, min(140.0, base_stage + drought + growth + rng.uniform(-6, 6)))

            pop_factor = max(0.25, min(3.0, (population or 1500) / 1500))
            recharge_total = round(rng.uniform(0.8, 7.0) * pop_factor * (0.9 if year in DROUGHT_YEARS else 1.0), 3)
            annual_extractable = round(recharge_total * rng.uniform(0.82, 0.95), 3)
            extraction_total = round(annual_extractable * (stage / 100), 3)
            category = _category_for_stage(stage)

            assessments.append(
                {
                    "assessment_unit_id": unit_id,
                    "dataset_id": dataset_id,
                    "assessment_year": year,
                    "recharge_total": Decimal(str(recharge_total)),
                    "extraction_total": Decimal(str(extraction_total)),
                    "annual_extractable_resource": Decimal(str(annual_extractable)),
                    "stage_of_extraction": Decimal(str(round(stage, 2))),
                    "category": category,
                    "is_demo": True,
                }
            )
            recharges.append(
                {
                    "assessment_unit_id": unit_id,
                    "dataset_id": dataset_id,
                    "year": year,
                    "recharge_type": "total",
                    "value": Decimal(str(recharge_total)),
                    "is_demo": True,
                }
            )
            extractions.append(
                {
                    "assessment_unit_id": unit_id,
                    "dataset_id": dataset_id,
                    "year": year,
                    "extraction_type": "total",
                    "value": Decimal(str(extraction_total)),
                    "is_demo": True,
                }
            )

    return assessments, recharges, extractions


def seed_national_groundwater(
    db: Session,
    states: list[str] | None = None,
    per_district: int | None = None,
) -> dict:
    """Seed the full national demo dataset. Returns summary counters."""
    existing = db.scalar(select(Dataset).where(Dataset.name == NATIONAL_DATASET_NAME))
    if existing:
        return {"skipped": True, "dataset_id": existing.id}

    _tune_for_bulk(db)

    dataset = Dataset(
        name=NATIONAL_DATASET_NAME,
        description=(
            "Clearly synthetic national development data covering all states, "
            "union territories, districts and a generated village layer. "
            "Not official IN-GRES or CGWB data."
        ),
        source="Synthetic National Development Dataset",
        source_url=None,
        publication_year=2023,
        version="1.0",
        geographic_level="village",
        unit="hm³",
        validation_status="demo",
        is_demo=True,
    )
    db.add(dataset)
    db.flush()
    dataset_id = dataset.id

    for name, label, description in [
        ("safe", "Safe", "Stage of groundwater extraction below 70%."),
        ("semi-critical", "Semi-critical", "Stage of groundwater extraction between 70% and 90%."),
        ("critical", "Critical", "Stage of groundwater extraction between 90% and 100%."),
        ("over-exploited", "Over-exploited", "Stage of groundwater extraction above 100%."),
    ]:
        if db.scalar(select(AssessmentCategory).where(AssessmentCategory.name == name)) is None:
            db.add(AssessmentCategory(name=name, label=label, description=description, is_official=False))

    target_states = states or [s["name"] for s in INDIA_STATES]

    stats = {
        "states": 0,
        "districts": 0,
        "villages": 0,
        "units": 0,
        "assessments": 0,
    }

    for state_name in target_states:
        info = state_info(state_name)
        if info is None:
            continue

        state = db.scalar(select(State).where(State.code == info["code"]))
        if state is None:
            state = State(name=state_name, code=info["code"], region=info["region"])
            db.add(state)
            db.flush()
        stats["states"] += 1

        for district_name in DISTRICTS_BY_STATE.get(state_name, []):
            district = db.scalar(
                select(District).where(District.state_id == state.id, District.name == district_name)
            )
            if district is None:
                district = District(state_id=state.id, name=district_name)
                db.add(district)
                db.flush()
            stats["districts"] += 1

            dlat, dlon = district_centroid(info, district_name)
            state_geom = india_polygons().get(state_name)
            count = village_count_for(district_name, info["density"], per_district=per_district)
            names = generate_village_names(district_name, count, info["suffix"])

            village_rows = []
            for i, name in enumerate(names):
                lat, lon = generate_village_coords(
                    dlat, dlon, f"{district.id}:{i}", geom=state_geom
                )
                village_rows.append(
                    {
                        "district_id": district.id,
                        "name": name,
                        "code": f"{info['code']}-{district.id}-{i + 1}",
                        "population": generate_population(f"{district.id}:{i}"),
                        "latitude": lat,
                        "longitude": lon,
                        "is_demo": True,
                    }
                )
            _insert_many(db, Village, village_rows)
            db.flush()

            village_ids = db.scalars(
                select(Village.id)
                .where(Village.district_id == district.id, Village.is_demo == True)  # noqa: E712
                .order_by(Village.id)
            ).all()

            unit_rows = []
            for i, (vid, name) in enumerate(zip(village_ids, names)):
                lat, lon = village_rows[i]["latitude"], village_rows[i]["longitude"]
                unit_rows.append(
                    {
                        "state_id": state.id,
                        "district_id": district.id,
                        "village_id": vid,
                        "name": name,
                        "code": f"{info['code']}-{district.id}-U{i + 1}",
                        "unit_type": "village",
                        "latitude": lat,
                        "longitude": lon,
                        "is_demo": True,
                    }
                )
            _insert_many(db, AssessmentUnit, unit_rows)
            db.flush()

            unit_ids = db.scalars(
                select(AssessmentUnit.id)
                .where(
                    AssessmentUnit.district_id == district.id,
                    AssessmentUnit.village_id.is_not(None),
                    AssessmentUnit.is_demo == True,  # noqa: E712
                )
                .order_by(AssessmentUnit.id)
            ).all()

            populations = [village_rows[i]["population"] for i in range(len(names))]
            coords = [(village_rows[i]["latitude"], village_rows[i]["longitude"]) for i in range(len(names))]
            assessments, recharges, extractions = _village_assessment_rows(
                unit_ids=unit_ids,
                names=names,
                populations=populations,
                coords=coords,
                district_id=district.id,
                state_id=state.id,
                dataset_id=dataset_id,
                profile=info["profile"],
                code_prefix=info["code"],
            )

            _insert_many(db, GroundwaterAssessment, assessments)
            _insert_many(db, GroundwaterRecharge, recharges)
            _insert_many(db, GroundwaterExtraction, extractions)

            stats["villages"] += len(names)
            stats["units"] += len(unit_ids)
            stats["assessments"] += len(assessments)

        db.commit()
        print(f"  [{state_name}] villages={stats['villages']} assessments={stats['assessments']}")

    print(
        f"Seeded national synthetic dataset: {stats['states']} states/UTs, "
        f"{stats['districts']} districts, {stats['villages']} villages, "
        f"{stats['assessments']} assessment records"
    )
    invalidate_analytics_cache()
    return {"skipped": False, "dataset_id": dataset_id, **stats}
