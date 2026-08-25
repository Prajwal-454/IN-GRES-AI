"""CSV / XLSX groundwater dataset import with validation.

Imports uploaded assessment data into the structured tables (State, District,
AssessmentUnit, Dataset, GroundwaterAssessment, GroundwaterRecharge,
GroundwaterExtraction). The pipeline validates headers, parses numbers,
normalises assessment categories and reports every issue instead of silently
dropping rows. Imported data is tagged ``is_demo=False`` so it can be told
apart from the synthetic development dataset.
"""

from __future__ import annotations

import csv
import io
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.ingres.query_cache import invalidate_analytics_cache
from app.models.groundwater import (
    AssessmentUnit,
    Dataset,
    District,
    GroundwaterAssessment,
    GroundwaterExtraction,
    GroundwaterRecharge,
    State,
)

MAX_ROWS = 100_000

CATEGORY_NORMALISATION = {
    "safe": "Safe",
    "semi-critical": "Semi-critical",
    "sem-critical": "Semi-critical",
    "semi critical": "Semi-critical",
    "semi": "Semi-critical",
    "critical": "Critical",
    "over-exploited": "Over-exploited",
    "overexploited": "Over-exploited",
    "over exploited": "Over-exploited",
}

# header name -> canonical field (headers are normalised: lower, no spaces)
_FIELD_MAP = {
    "state": "state",
    "statename": "state",
    "district": "district",
    "districtname": "district",
    "assessmentunit": "assessment_unit",
    "assessment_unit": "assessment_unit",
    "unit": "assessment_unit",
    "block": "assessment_unit",
    "mandal": "assessment_unit",
    "year": "year",
    "assessmentyear": "year",
    "recharge": "recharge",
    "rechargetotal": "recharge",
    "annualrecharge": "recharge",
    "extraction": "extraction",
    "extractiontotal": "extraction",
    "annualextraction": "extraction",
    "extractable": "extractable",
    "extractableresource": "extractable",
    "annualextractableresource": "extractable",
    "resource": "extractable",
    "stage": "stage",
    "stageofextraction": "stage",
    "soe": "stage",
    "category": "category",
    "stagecategory": "category",
    "classification": "category",
}

_REQUIRED = {"state", "year", "assessment_unit"}


@dataclass
class ImportResult:
    dataset_id: int | None = None
    rows_parsed: int = 0
    rows_imported: int = 0
    states_created: list[str] = field(default_factory=list)
    districts_created: list[str] = field(default_factory=list)
    units_created: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def _normalise_header(name: str) -> str:
    return "".join(ch for ch in name.strip().lower() if ch.isalnum())


def _parse_number(value, field_name: str) -> float | None:
    if value is None:
        return None
    text = str(value).strip().replace(",", "")
    if not text:
        return None
    try:
        return float(Decimal(text))
    except (InvalidOperation, ValueError):
        raise ValueError(f"{field_name} is not a number: {value!r}")


def _normalise_category(value) -> str | None:
    if value is None:
        return None
    key = " ".join(str(value).strip().lower().split())
    if not key:
        return None
    if key in CATEGORY_NORMALISATION:
        return CATEGORY_NORMALISATION[key]
    # Accept the display forms directly.
    return str(value).strip()


def _rows_from_csv(content: bytes) -> list[list[str]]:
    text = content.decode("utf-8-sig", errors="replace")
    reader = csv.reader(io.StringIO(text))
    return [row for row in reader if any(cell.strip() for cell in row)]


def _rows_from_xlsx(content: bytes) -> list[list]:
    from openpyxl import load_workbook

    wb = load_workbook(io.BytesIO(content), read_only=True, data_only=True)
    ws = wb.active
    rows = []
    for row in ws.iter_rows(values_only=True):
        if any(cell is not None and str(cell).strip() for cell in row):
            rows.append(list(row))
    wb.close()
    return rows


def _build_field_index(headers: list) -> tuple[dict[str, int], list[str]]:
    index: dict[str, int] = {}
    errors: list[str] = []
    for col, raw in enumerate(headers):
        canonical = _FIELD_MAP.get(_normalise_header(str(raw)))
        if canonical is None:
            continue
        if canonical in index:
            errors.append(f"Duplicate column for {canonical!r}; ignoring column {col + 1}")
            continue
        index[canonical] = col
    return index, errors


def _state_code(name: str, db: Session) -> str:
    """A stable, unique state code derived from the name."""
    base = "".join(ch for ch in name.upper() if ch.isalnum())[:10] or "ST"
    code = base
    suffix = 1
    while db.scalar(select(State).where(State.code == code)) is not None:
        code = f"{base[:7]}{suffix}"
        suffix += 1
    return code


def _get_or_create_state(db: Session, name: str) -> State:
    state = db.scalar(select(State).where(State.name.ilike(name.strip())))
    if state:
        return state
    state = State(name=name.strip(), code=_state_code(name, db), region=None)
    db.add(state)
    db.flush()
    return state


def _get_or_create_district(db: Session, state: State, name: str) -> District:
    district = db.scalar(
        select(District).where(District.state_id == state.id, District.name.ilike(name.strip()))
    )
    if district:
        return district
    district = District(state_id=state.id, name=name.strip())
    db.add(district)
    db.flush()
    return district


def _get_or_create_unit(db: Session, district: District, state: State, name: str) -> AssessmentUnit:
    unit = db.scalar(
        select(AssessmentUnit)
        .where(
            AssessmentUnit.state_id == state.id,
            AssessmentUnit.district_id == district.id,
            AssessmentUnit.name.ilike(name.strip()),
        )
    )
    if unit:
        return unit
    unit = AssessmentUnit(state_id=state.id, district_id=district.id, name=name.strip())
    db.add(unit)
    db.flush()
    return unit


def _normalise_fieldname(s: str) -> str:
    return "".join(ch for ch in s.strip().lower() if ch.isalnum())


def import_dataset(
    db: Session,
    filename: str,
    content: bytes,
    user_id: int,
    name: str | None = None,
    source: str | None = None,
    year: int | None = None,
) -> ImportResult:
    """Validate and import an uploaded CSV/XLSX assessment dataset."""
    result = ImportResult()

    if len(content) > 50 * 1024 * 1024:
        result.errors.append("File exceeds the 50 MB upload limit.")
        return result

    lower = filename.lower()
    if lower.endswith(".xlsx") or lower.endswith(".xlsm"):
        try:
            rows = _rows_from_xlsx(content)
        except Exception as exc:  # noqa: BLE001
            result.errors.append(f"Could not read the spreadsheet: {exc}")
            return result
    elif lower.endswith(".csv"):
        rows = _rows_from_csv(content)
    else:
        result.errors.append("Unsupported file type. Upload a .csv or .xlsx file.")
        return result

    if len(rows) < 2:
        result.errors.append("File must contain a header row and at least one data row.")
        return result

    headers = rows[0]
    field_index, header_errors = _build_field_index(headers)
    result.errors.extend(header_errors)

    missing = _REQUIRED - set(field_index)
    if missing:
        result.errors.append(f"Missing required column(s): {', '.join(sorted(missing))}.")
        return result

    data_rows = rows[1:]
    if len(data_rows) > get_settings().IMPORT_MAX_ROWS:
        result.errors.append(
            f"File has {len(data_rows)} data rows; the limit is {get_settings().IMPORT_MAX_ROWS}."
        )
        return result

    dataset = Dataset(
        name=name or (source or "Imported dataset"),
        description=f"Imported from {filename}",
        source=source,
        publication_year=year,
        version="1.0",
        geographic_level="assessment_unit",
        validation_status="VALIDATED",
        is_demo=False,
        file_path=filename,
        uploaded_by=user_id,
    )
    db.add(dataset)
    db.flush()

    result.rows_parsed = len(data_rows)

    for row_no, row in enumerate(data_rows, start=2):
        def field_value(canonical: str) -> str | None:
            col = field_index.get(canonical)
            if col is None or col >= len(row):
                return None
            cell = row[col]
            return None if cell is None else str(cell).strip()

        state_name = field_value("state")
        unit_name = field_value("assessment_unit")
        year_text = field_value("year")
        if not state_name or not unit_name or not year_text:
            result.errors.append(f"Row {row_no}: state, assessment unit and year are required.")
            continue

        try:
            row_year = int(float(year_text))
        except ValueError:
            result.errors.append(f"Row {row_no}: year is not a valid integer: {year_text!r}.")
            continue

        recharge = field_value("recharge")
        extraction = field_value("extraction")
        extractable = field_value("extractable")
        stage = field_value("stage")
        category = _normalise_category(field_value("category"))

        try:
            recharge_val = _parse_number(recharge, "recharge") if recharge else None
            extraction_val = _parse_number(extraction, "extraction") if extraction else None
            extractable_val = _parse_number(extractable, "extractable") if extractable else None
            stage_val = _parse_number(stage, "stage") if stage else None
        except ValueError as exc:
            result.errors.append(f"Row {row_no}: {exc}")
            continue

        if stage_val is not None and not (0 <= stage_val <= 1000):
            result.warnings.append(
                f"Row {row_no}: stage of extraction {stage_val} looks out of range."
            )

        state = db.scalar(select(State).where(State.name.ilike(state_name.strip())))
        if state is None:
            state = _get_or_create_state(db, state_name)
            result.states_created.append(state.name)

        district_name = field_value("district") or state_name
        district = db.scalar(
            select(District).where(
                District.state_id == state.id,
                District.name.ilike(district_name.strip()),
            )
        )
        if district is None:
            district = _get_or_create_district(db, state, district_name)
            result.districts_created.append(f"{district.name} ({state.name})")

        unit = db.scalar(
            select(AssessmentUnit).where(
                AssessmentUnit.state_id == state.id,
                AssessmentUnit.district_id == district.id,
                AssessmentUnit.name.ilike(unit_name.strip()),
            )
        )
        if unit is None:
            unit = _get_or_create_unit(db, district, state, unit_name)
            result.units_created.append(f"{unit.name} ({state.name})")

        assessment = GroundwaterAssessment(
            assessment_unit_id=unit.id,
            dataset_id=dataset.id,
            assessment_year=row_year,
            recharge_total=Decimal(recharge_val) if recharge_val is not None else None,
            extraction_total=Decimal(extraction_val) if extraction_val is not None else None,
            annual_extractable_resource=Decimal(extractable_val) if extractable_val is not None else None,
            stage_of_extraction=Decimal(stage_val) if stage_val is not None else None,
            category=category,
            is_demo=False,
        )
        db.add(assessment)
        if recharge_val is not None:
            db.add(
                GroundwaterRecharge(
                    assessment_unit_id=unit.id,
                    dataset_id=dataset.id,
                    year=row_year,
                    recharge_type="total",
                    value=Decimal(recharge_val),
                    is_demo=False,
                )
            )
        if extraction_val is not None:
            db.add(
                GroundwaterExtraction(
                    assessment_unit_id=unit.id,
                    dataset_id=dataset.id,
                    year=row_year,
                    extraction_type="total",
                    value=Decimal(extraction_val),
                    is_demo=False,
                )
            )
        result.rows_imported += 1

    if result.errors:
        db.rollback()
        result.dataset_id = None
        result.rows_imported = 0
        result.states_created = []
        result.districts_created = []
        result.units_created = []
        return result

    db.commit()
    invalidate_analytics_cache()
    result.dataset_id = dataset.id
    return result


def import_template_rows() -> list[dict]:
    """A few example rows for the downloadable import template."""
    return [
        {
            "state": "Telangana",
            "district": "Hyderabad",
            "assessment_unit": "Hyderabad Block 1",
            "year": 2021,
            "recharge": 210.5,
            "extraction": 240.0,
            "extractable": 220.0,
            "stage": 109.1,
            "category": "Over-exploited",
        },
        {
            "state": "Andhra Pradesh",
            "district": "Guntur",
            "assessment_unit": "Guntur Block 1",
            "year": 2021,
            "recharge": 320.0,
            "extraction": 180.0,
            "extractable": 300.0,
            "stage": 60.0,
            "category": "Safe",
        },
    ]