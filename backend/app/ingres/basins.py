"""Indian river basins (Phase 21) — approximate basin -> district resolution.

India's surface water is organised into the 20 major river basins used by the
Central Water Commission (CWC) and the WRIS portal. This module maps each basin
to the states (and, where a state drains into more than one basin, the specific
districts) that make up its catchment.

The mapping is an **approximation for analytics and forecasting scopes** — it is
derived from the standard basin definitions, not from official IN-GRES/CGWB
catchment boundaries. Basins resolve to the *districts already present in the
database*, so a basin query only ever aggregates assessment data that exists.

Functions
---------
- :func:`list_basins` — every basin with the states it covers and, where known,
  the district-level split inside those states.
- :func:`basin_district_ids` — the district ids belonging to a basin
  (or ``[]`` when the basin is unknown / has no districts in the database).
"""

from __future__ import annotations

import re

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.groundwater import AssessmentUnit, District, GroundwaterAssessment

# A basin whose states are listed in ``BASIN_STATES`` covers *all* districts of
# those states. A state listed under ``BASIN_DISTRICTS[basin]`` is only partly
# in the basin, so only the named districts are counted.
BASIN_STATES: dict[str, tuple[str, ...]] = {
    "Indus": ("Jammu and Kashmir", "Ladakh", "Punjab"),
    "Ganga": (
        "Uttarakhand",
        "Uttar Pradesh",
        "Bihar",
        "Delhi",
        "Haryana",
        "Jharkhand",
        "Rajasthan",
        "Madhya Pradesh",
        "Chhattisgarh",
        "West Bengal",
    ),
    "Brahmaputra": (
        "Arunachal Pradesh",
        "Assam",
        "Sikkim",
        "Nagaland",
        "Manipur",
        "Meghalaya",
        "Tripura",
    ),
    "Barak and Others": ("Mizoram",),
    "Godavari": (
        "Maharashtra",
        "Telangana",
        "Andhra Pradesh",
        "Odisha",
        "Karnataka",
    ),
    "Krishna": (
        "Maharashtra",
        "Karnataka",
        "Telangana",
        "Andhra Pradesh",
    ),
    "Cauvery": ("Tamil Nadu", "Kerala", "Puducherry", "Karnataka"),
    "Pennar": ("Andhra Pradesh",),
    "Mahanadi": ("Chhattisgarh", "Odisha"),
    "Brahmani-Baitarani": ("Odisha", "Jharkhand"),
    "Subarnarekha": ("West Bengal", "Jharkhand", "Odisha"),
    "Narmada": ("Gujarat", "Madhya Pradesh", "Maharashtra"),
    "Tapi": ("Gujarat", "Maharashtra", "Madhya Pradesh"),
    "Sabarmati": ("Rajasthan", "Gujarat"),
    "Mahi": ("Rajasthan", "Gujarat", "Madhya Pradesh"),
    "West Flowing Rivers of Kutch and Saurashtra": ("Gujarat",),
    "West Flowing Rivers South of Tapi": ("Maharashtra", "Karnataka", "Kerala", "Goa"),
    "East Flowing Rivers between Mahanadi and Pennar": ("Odisha", "Andhra Pradesh"),
    "East Flowing Rivers between Pennar and Kanyakumari": ("Tamil Nadu", "Andhra Pradesh"),
    "Minor Rivers Draining into Bangladesh": ("West Bengal", "Tripura", "Meghalaya", "Assam"),
}

# District-level splits for states whose catchment straddles more than one
# basin. Only districts listed here are counted for the basin; the rest of the
# state belongs to its other basin(s).
BASIN_DISTRICTS: dict[str, dict[str, tuple[str, ...]]] = {
    "Godavari": {
        "Maharashtra": (
            "Nashik",
            "Aurangabad",
            "Nanded",
            "Wardha",
            "Nagpur",
            "Gadchiroli",
            "Chandrapur",
            "Yavatmal",
            "Akola",
            "Amravati",
            "Buldhana",
            "Washim",
            "Hingoli",
            "Parbhani",
            "Beed",
            "Latur",
            "Osmanabad",
            "Solapur",
            "Ahmednagar",
            "Jalgaon",
        ),
        "Telangana": (
            "Adilabad",
            "Nizamabad",
            "Karimnagar",
            "Warangal",
            "Khammam",
            "Mancherial",
            "Nirmal",
            "Jagtial",
            "Peddapalli",
            "Jayashankar",
            "Bhadradri",
            "Kothagudem",
            "Mulugu",
            "Siddipet",
            "Kamareddy",
        ),
        "Andhra Pradesh": (
            "East Godavari",
            "West Godavari",
            "Vizianagaram",
            "Visakhapatnam",
            "Srikakulam",
            "Krishna",
            "Guntur",
            "Prakasam",
        ),
        "Karnataka": ("Gulbarga", "Bidar", "Raichur", "Koppal", "Bellary"),
        "Odisha": ("Koraput", "Malkangiri", "Nabarangpur", "Rayagada"),
    },
    "Krishna": {
        "Maharashtra": (
            "Satara",
            "Sangli",
            "Kolhapur",
            "Pune",
            "Solapur",
            "Aurangabad",
            "Beed",
            "Latur",
            "Osmanabad",
            "Nanded",
        ),
        "Karnataka": (
            "Belgaum",
            "Bijapur",
            "Bagalkot",
            "Gadag",
            "Dharwad",
            "Haveri",
            "Chitradurga",
            "Bellary",
            "Raichur",
            "Koppal",
        ),
        "Telangana": (
            "Medak",
            "Hyderabad",
            "Rangareddy",
            "Nalgonda",
            "Mahabubnagar",
            "Nagarkurnool",
            "Wanaparthy",
            "Jogulamba",
            "Vikarabad",
            "Sangareddy",
        ),
        "Andhra Pradesh": (
            "Kurnool",
            "Guntur",
            "Prakasam",
            "Krishna",
            "Nellore",
            "Cuddapah",
        ),
    },
    "Cauvery": {
        "Karnataka": (
            "Kodagu",
            "Mysore",
            "Chamarajanagar",
            "Mandya",
            "Hassan",
            "Tumkur",
            "Ramanagara",
            "Bangalore",
            "Chikkaballapur",
        )
    },
    "Indus": {
        "Himachal Pradesh": (
            "Kinnaur",
            "Lahaul and Spiti",
            "Chamba",
            "Kangra",
            "Hamirpur",
            "Una",
        ),
        "Haryana": ("Ambala", "Yamunanagar", "Panchkula", "Kurukshetra"),
        "Rajasthan": ("Ganganagar", "Hanumangarh", "Jaisalmer", "Bikaner", "Churu"),
    },
    "Ganga": {
        "Himachal Pradesh": ("Sirmaur", "Bilaspur", "Solan", "Shimla"),
        "Rajasthan": (
            "Alwar",
            "Bharatpur",
            "Dholpur",
            "Karauli",
            "Sawai Madhopur",
            "Tonk",
        ),
        "Madhya Pradesh": (
            "Rewa",
            "Satna",
            "Panna",
            "Chhatarpur",
            "Tikamgarh",
            "Sidhi",
            "Singrauli",
            "Shahdol",
            "Umaria",
            "Katni",
        ),
        "Chhattisgarh": ("Koriya", "Surguja", "Balrampur", "Jashpur", "Korea"),
    },
    "Narmada": {
        "Maharashtra": ("Nandurbar", "Dhule", "Jalgaon", "Nashik"),
    },
    "Tapi": {
        "Maharashtra": ("Nandurbar", "Dhule", "Jalgaon", "Nashik", "Akola", "Buldhana"),
        "Madhya Pradesh": ("Betul", "Burhanpur", "Khargone", "Khandwa"),
    },
    "Mahi": {
        "Madhya Pradesh": ("Ratlam", "Jhabua", "Dhar", "Mandsaur", "Neemuch"),
        "Rajasthan": ("Banswara", "Dungarpur", "Pratapgarh", "Chittorgarh", "Udaipur"),
    },
    "Sabarmati": {
        "Rajasthan": ("Udaipur", "Sirohi", "Pali", "Jalore", "Pratapgarh"),
    },
    "Subarnarekha": {
        "West Bengal": ("Purulia", "Bankura", "Midnapore", "Paschim Medinipur"),
        "Jharkhand": ("Ranchi", "East Singhbhum", "West Singhbhum", "Seraikela"),
    },
    "Brahmani-Baitarani": {
        "Odisha": (
            "Sundargarh",
            "Deogarh",
            "Keonjhar",
            "Bhadrak",
            "Jajpur",
            "Mayurbhanj",
            "Balasore",
        ),
        "Jharkhand": ("West Singhbhum", "East Singhbhum"),
    },
    "Mahanadi": {
        "Madhya Pradesh": ("Amarpatan", "Shahdol", "Dindori", "Mandla"),
    },
}

# Human label per basin for the UI / assistant.
BASIN_LABELS: dict[str, str] = {
    "Indus": "Indus river basin",
    "Ganga": "Ganga river basin",
    "Brahmaputra": "Brahmaputra river basin",
    "Barak and Others": "Barak and other rivers of the north-east",
    "Godavari": "Godavari river basin",
    "Krishna": "Krishna river basin",
    "Cauvery": "Cauvery river basin",
    "Pennar": "Pennar river basin",
    "Mahanadi": "Mahanadi river basin",
    "Brahmani-Baitarani": "Brahmani–Baitarani river basin",
    "Subarnarekha": "Subarnarekha river basin",
    "Narmada": "Narmada river basin",
    "Tapi": "Tapi river basin",
    "Sabarmati": "Sabarmati river basin",
    "Mahi": "Mahi river basin",
    "West Flowing Rivers of Kutch and Saurashtra": "West-flowing rivers of Kutch and Saurashtra",
    "West Flowing Rivers South of Tapi": "West-flowing rivers south of the Tapi",
    "East Flowing Rivers between Mahanadi and Pennar": "East-flowing rivers between Mahanadi and Pennar",
    "East Flowing Rivers between Pennar and Kanyakumari": "East-flowing rivers between Pennar and Kanyakumari",
    "Minor Rivers Draining into Bangladesh": "Minor rivers draining into Bangladesh",
}

BASIN_ORDER: tuple[str, ...] = tuple(BASIN_LABELS.keys())


def _slug(name: str) -> str:
    """URL-friendly basin code, e.g. ``"Godavari"`` -> ``"godavari"``."""
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return slug or name.lower()


def _description(name: str) -> str:
    """One-line basin description with its primary states."""
    states = set(BASIN_STATES.get(name, ())) | set(BASIN_DISTRICTS.get(name, {}).keys())
    primary = sorted(states)
    if not primary:
        return BASIN_LABELS.get(name, name)
    joined = ", ".join(primary[:4])
    more = f" and {len(primary) - 4} more" if len(primary) > 4 else ""
    return f"{BASIN_LABELS.get(name, name)} (primary states: {joined}{more})."


def _latest_scope(db: Session, district_ids: list[int]) -> dict | None:
    """Latest-year summary for a set of districts (stage avg, categories)."""
    if not district_ids:
        return None
    row = db.execute(
        select(
            GroundwaterAssessment.assessment_year,
            func.avg(GroundwaterAssessment.stage_of_extraction).label("stage"),
            func.count(GroundwaterAssessment.id).label("records"),
        )
        .join(AssessmentUnit, GroundwaterAssessment.assessment_unit_id == AssessmentUnit.id)
        .where(AssessmentUnit.district_id.in_(district_ids))
        .group_by(GroundwaterAssessment.assessment_year)
        .order_by(GroundwaterAssessment.assessment_year.desc())
        .limit(1)
    ).first()
    if row is None:
        return None
    return {
        "year": row.assessment_year,
        "stage": round(float(row.stage), 2) if row.stage is not None else None,
        "unit_count": int(row.records or 0),
    }


def list_basins(db: Session) -> list[dict]:
    """Every basin with metadata, district coverage and latest-year summary.

    Returns a list of ``{"code", "name", "description", "state_count",
    "district_count", "district_ids", "latest"}`` sorted by the standard CWC
    basin order. ``district_count`` is the number of districts *actually
    present in the database* for the basin, so the UI can show which basins
    have data without an extra query per basin.
    """
    rows: list[dict] = []
    for name in BASIN_ORDER:
        states = sorted(
            set(BASIN_STATES.get(name, ())) | set(BASIN_DISTRICTS.get(name, {}).keys())
        )
        ids = basin_district_ids(db, name)
        rows.append(
            {
                "code": _slug(name),
                "name": name,
                "label": BASIN_LABELS.get(name, name),
                "states": states,
                "description": _description(name),
                "state_count": len(states),
                "district_count": len(ids),
                "district_ids": ids,
                "latest": _latest_scope(db, ids),
            }
        )
    return rows


def basin_district_ids(db: Session, basin: str) -> list[int]:
    """District ids for a basin (unknown basin -> ``[]``).

    States listed in ``BASIN_STATES`` contribute every one of their districts;
    a state under ``BASIN_DISTRICTS`` contributes only the named districts.
    """
    if basin not in BASIN_LABELS:
        return []
    states = BASIN_STATES.get(basin, ())
    split = BASIN_DISTRICTS.get(basin, {})

    ids: list[int] = []
    if states:
        from app.ingres.queries import resolve_state

        for name in states:
            state_obj = resolve_state(db, name)
            if state_obj is None:
                continue
            ids.extend(
                list(
                    db.scalars(
                        select(District.id).where(District.state_id == state_obj.id)
                    ).all()
                )
            )
    for state, districts in split.items():
        state_obj = _resolve_state_or_none(db, state)
        if state_obj is None:
            continue
        ids.extend(
            list(
                db.scalars(
                    select(District.id).where(
                        District.state_id == state_obj.id,
                        District.name.in_(districts),
                    )
                ).all()
            )
        )
    return ids


def _resolve_state_or_none(db: Session, state: str):
    """Case-insensitive state lookup (None when unknown)."""
    from sqlalchemy import func

    from app.models.groundwater import State

    return db.scalar(
        select(State).where(func.lower(State.name) == state.strip().lower())
    )