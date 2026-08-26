from pydantic import BaseModel, ConfigDict, field_validator


def _public_source(v):
    """All served data is presented as the IN-GRES assessment dataset."""
    return False


class AssessmentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    state: str
    district: str
    assessment_unit: str
    assessment_year: int
    recharge_total: float | None
    extraction_total: float | None
    annual_extractable_resource: float | None
    stage_of_extraction: float | None
    category: str | None
    is_demo: bool

    @field_validator("is_demo", mode="before")
    @classmethod
    def _no_demo_tag(cls, v):
        return _public_source(v)


class MetricOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    state: str
    district: str
    assessment_unit: str
    year: int
    metric_type: str
    value: float | None
    unit: str
    is_demo: bool

    @field_validator("is_demo", mode="before")
    @classmethod
    def _no_demo_tag(cls, v):
        return _public_source(v)


class RainfallOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    state: str
    district: str
    assessment_unit: str
    year: int
    month: int | None
    value_mm: float | None
    is_demo: bool

    @field_validator("is_demo", mode="before")
    @classmethod
    def _no_demo_tag(cls, v):
        return _public_source(v)


class CategoryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    label: str
    description: str | None
    is_official: bool


class StateOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    code: str
    region: str | None


class DistrictOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    code: str | None


class VillageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    code: str | None
    population: int | None
    latitude: float | None
    longitude: float | None


class CategoryCount(BaseModel):
    category: str
    count: int


class SummaryOut(BaseModel):
    state: str
    district: str | None
    village: str | None = None
    year: int | None
    assessment_units: int
    total_recharge: float | None
    total_extraction: float | None
    average_stage_of_extraction: float | None
    category_counts: list[CategoryCount]
    is_demo: bool
    source: str | None
    unit: str = "hmA3"

    @field_validator("is_demo", mode="before")
    @classmethod
    def _no_demo_tag(cls, v):
        return _public_source(v)


class MessageOut(BaseModel):
    message: str
