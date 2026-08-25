from __future__ import annotations

from datetime import date
from decimal import Decimal

from geoalchemy2 import Geometry
from sqlalchemy import Boolean, Date, Float, ForeignKey, Index, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.base import TimestampMixin
from app.config import get_settings

_ENABLE_GEOMETRY = get_settings().ENABLE_GEOMETRY


class State(Base):
    __tablename__ = "states"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120), unique=True, index=True, nullable=False)
    code: Mapped[str] = mapped_column(String(10), unique=True, index=True, nullable=False)
    region: Mapped[str | None] = mapped_column(String(120))


class District(Base):
    __tablename__ = "districts"

    id: Mapped[int] = mapped_column(primary_key=True)
    state_id: Mapped[int] = mapped_column(ForeignKey("states.id"), index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(120), index=True, nullable=False)
    code: Mapped[str | None] = mapped_column(String(20))


class Mandal(Base):
    __tablename__ = "mandals"

    id: Mapped[int] = mapped_column(primary_key=True)
    district_id: Mapped[int] = mapped_column(ForeignKey("districts.id"), index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(120), index=True, nullable=False)
    code: Mapped[str | None] = mapped_column(String(20))


class Village(Base):
    __tablename__ = "villages"

    id: Mapped[int] = mapped_column(primary_key=True)
    district_id: Mapped[int] = mapped_column(ForeignKey("districts.id"), index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(120), index=True, nullable=False)
    code: Mapped[str | None] = mapped_column(String(30), index=True)
    population: Mapped[int | None] = mapped_column(Integer)
    latitude: Mapped[float | None] = mapped_column(Float)
    longitude: Mapped[float | None] = mapped_column(Float)
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False)


class AssessmentUnit(Base):
    __tablename__ = "assessment_units"

    id: Mapped[int] = mapped_column(primary_key=True)
    state_id: Mapped[int] = mapped_column(ForeignKey("states.id"), index=True, nullable=False)
    district_id: Mapped[int | None] = mapped_column(ForeignKey("districts.id"), index=True)
    village_id: Mapped[int | None] = mapped_column(ForeignKey("villages.id"), index=True)
    name: Mapped[str] = mapped_column(String(255), index=True, nullable=False)
    code: Mapped[str | None] = mapped_column(String(50))
    unit_type: Mapped[str | None] = mapped_column(String(50))
    latitude: Mapped[float | None] = mapped_column(Float)
    longitude: Mapped[float | None] = mapped_column(Float)
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False)
    if _ENABLE_GEOMETRY:
        geom: Mapped[object | None] = mapped_column(Geometry("POLYGON", srid=4326))
        centroid: Mapped[object | None] = mapped_column(Geometry("POINT", srid=4326))


class AssessmentCategory(Base):
    __tablename__ = "assessment_categories"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    label: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    is_official: Mapped[bool] = mapped_column(Boolean, default=False)


class Dataset(TimestampMixin, Base):
    __tablename__ = "datasets"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    source: Mapped[str | None] = mapped_column(String(255))
    source_url: Mapped[str | None] = mapped_column(String(500))
    publication_year: Mapped[int | None] = mapped_column(Integer)
    version: Mapped[str] = mapped_column(String(50), default="1.0")
    geographic_level: Mapped[str | None] = mapped_column(String(50))
    unit: Mapped[str | None] = mapped_column(String(50))
    validation_status: Mapped[str] = mapped_column(String(50), default="pending")
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False)
    file_path: Mapped[str | None] = mapped_column(String(500))
    uploaded_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"))


class GroundwaterAssessment(Base):
    __tablename__ = "groundwater_assessments"
    __table_args__ = (
        Index("ix_groundwater_assessments_year_category", "assessment_year", "category"),
        Index("ix_groundwater_assessments_unit_year", "assessment_unit_id", "assessment_year"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    assessment_unit_id: Mapped[int] = mapped_column(ForeignKey("assessment_units.id"), index=True, nullable=False)
    dataset_id: Mapped[int | None] = mapped_column(ForeignKey("datasets.id"), index=True)
    assessment_year: Mapped[int] = mapped_column(Integer, index=True, nullable=False)
    recharge_total: Mapped[Decimal | None] = mapped_column(Numeric(14, 3))
    extraction_total: Mapped[Decimal | None] = mapped_column(Numeric(14, 3))
    annual_extractable_resource: Mapped[Decimal | None] = mapped_column(Numeric(14, 3))
    stage_of_extraction: Mapped[Decimal | None] = mapped_column(Numeric(6, 2))
    category: Mapped[str | None] = mapped_column(String(50), index=True)
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False)


class GroundwaterRecharge(Base):
    __tablename__ = "groundwater_recharge"

    id: Mapped[int] = mapped_column(primary_key=True)
    assessment_unit_id: Mapped[int] = mapped_column(ForeignKey("assessment_units.id"), index=True, nullable=False)
    dataset_id: Mapped[int | None] = mapped_column(ForeignKey("datasets.id"), index=True)
    year: Mapped[int] = mapped_column(Integer, index=True, nullable=False)
    recharge_type: Mapped[str | None] = mapped_column(String(50))
    value: Mapped[Decimal | None] = mapped_column(Numeric(14, 3))
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False)


class GroundwaterExtraction(Base):
    __tablename__ = "groundwater_extraction"

    id: Mapped[int] = mapped_column(primary_key=True)
    assessment_unit_id: Mapped[int] = mapped_column(ForeignKey("assessment_units.id"), index=True, nullable=False)
    dataset_id: Mapped[int | None] = mapped_column(ForeignKey("datasets.id"), index=True)
    year: Mapped[int] = mapped_column(Integer, index=True, nullable=False)
    extraction_type: Mapped[str | None] = mapped_column(String(50))
    value: Mapped[Decimal | None] = mapped_column(Numeric(14, 3))
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False)


class GroundwaterLevel(Base):
    __tablename__ = "groundwater_levels"

    id: Mapped[int] = mapped_column(primary_key=True)
    assessment_unit_id: Mapped[int] = mapped_column(ForeignKey("assessment_units.id"), index=True, nullable=False)
    dataset_id: Mapped[int | None] = mapped_column(ForeignKey("datasets.id"), index=True)
    measured_date: Mapped[date | None] = mapped_column(Date)
    depth_bgl: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))
    water_level_class: Mapped[str | None] = mapped_column(String(50))
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False)


class GroundwaterRainfall(Base):
    __tablename__ = "groundwater_rainfall"

    id: Mapped[int] = mapped_column(primary_key=True)
    assessment_unit_id: Mapped[int] = mapped_column(ForeignKey("assessment_units.id"), index=True, nullable=False)
    dataset_id: Mapped[int | None] = mapped_column(ForeignKey("datasets.id"), index=True)
    year: Mapped[int] = mapped_column(Integer, index=True, nullable=False)
    month: Mapped[int | None] = mapped_column(Integer)
    value_mm: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False)


class DatasetFileState(Base):
    """Content fingerprint of each source file imported into a dataset.

    Used to detect when a real-data CSV has been updated so the next refresh can
    re-import only the states whose files actually changed.
    """

    __tablename__ = "dataset_file_state"

    dataset_id: Mapped[int] = mapped_column(ForeignKey("datasets.id"), primary_key=True)
    filename: Mapped[str] = mapped_column(String(255), primary_key=True)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)