from pydantic import BaseModel, field_validator


class ForecastPointOut(BaseModel):
    year: int
    value: float
    upper: float | None = None
    lower: float | None = None


class ModelMetricsOut(BaseModel):
    rmse: float | None = None
    mae: float | None = None
    mape: float | None = None
    n: int = 0


class MlInfoOut(BaseModel):
    available: bool
    note: str | None = None
    model: str | None = None
    transfer: bool | None = None
    pretrained_scope: str | None = None
    epochs: int | None = None
    window: int | None = None
    residual_std: float | None = None


class DecompositionOut(BaseModel):
    trend_per_year: float | None = None
    volatility: float | None = None
    residual_std: float | None = None
    acceleration: float | None = None
    summary: str | None = None


class ScenarioOut(BaseModel):
    metric: str
    change_pct: float
    applied_to: str


class ForecastOut(BaseModel):
    scope: str
    state: str | None
    district: str | None
    village: str | None
    basin: str | None = None
    metric: str
    method: str
    method_label: str
    unit: str
    historical: list[ForecastPointOut]
    forecast: list[ForecastPointOut]
    slope: float | None
    r2: float | None
    direction: str
    pct_change: float | None
    end_value: float | None
    risk: str | None
    years_to_threshold: int | None
    note: str
    validation: dict[str, ModelMetricsOut] | None = None
    best_method: str | None = None
    is_demo: bool

    @field_validator("is_demo", mode="before")
    @classmethod
    def _no_demo_tag(cls, v):
        return False

    band: str = "normal"
    decomposition: DecompositionOut | None = None
    ml: MlInfoOut | None = None
    scenario: ScenarioOut | None = None


class BasinLatestOut(BaseModel):
    year: int | None = None
    stage: float | None = None
    unit_count: int = 0


class BasinOut(BaseModel):
    code: str
    name: str
    label: str
    states: list[str] = []
    description: str = ""
    state_count: int = 0
    district_count: int = 0
    district_ids: list[int] = []
    latest: BasinLatestOut | None = None


class ForecastCompareOut(BaseModel):
    scope: str
    metric: str
    historical_points: int
    evaluation: dict[str, ModelMetricsOut] | None = None
    best: str | None = None
    note: str | None = None


class BacktestModelOut(BaseModel):
    rmse: float | None = None
    mae: float | None = None
    mape: float | None = None
    crps: float | None = None
    direction_accuracy: float | None = None
    skill: float | None = None
    n: int = 0


class BacktestOut(BaseModel):
    scope: str
    metric: str
    historical_points: int
    split_index: int | None = None
    train_years: list[int] = []
    test_years: list[int] = []
    evaluation: dict[str, BacktestModelOut] | None = None
    baseline: dict | None = None
    best: str | None = None
    note: str | None = None


class ForecastMetaOut(BaseModel):
    methods: list[str]
    ml_available: bool
    ml_methods: list[str]
    metrics: list[str]
    bands: list[str]


class ScenarioDeltaOut(BaseModel):
    end_baseline: float | None = None
    end_scenario: float | None = None
    end_delta: float | None = None
    end_delta_pct: float | None = None
    risk_baseline: str | None = None
    risk_scenario: str | None = None


class ScenarioCompareOut(BaseModel):
    scope: str
    metric: str
    unit: str
    baseline: ForecastOut
    scenario: ForecastOut | None = None
    delta: ScenarioDeltaOut
