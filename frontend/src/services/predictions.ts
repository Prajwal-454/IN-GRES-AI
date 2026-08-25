import { api } from "./api";

export type ForecastMetric = "stage" | "recharge" | "extraction";
export type ForecastMethod =
  | "linear"
  | "moving_average"
  | "exponential"
  | "arima"
  | "holt"
  | "ensemble"
  | "lstm"
  | "transformer"
  | "ml"
  | "auto";
export type ConfidenceBand = "normal" | "bootstrap";

export interface ForecastPoint {
  year: number;
  value: number;
  upper: number | null;
  lower: number | null;
}

export interface ModelMetrics {
  rmse: number | null;
  mae: number | null;
  mape: number | null;
  crps?: number | null;
  direction_accuracy?: number | null;
  skill?: number | null;
  n: number;
}

export interface DecompositionInfo {
  trend_per_year: number | null;
  volatility: number | null;
  residual_std: number | null;
  acceleration: number | null;
  summary: string | null;
}

export interface MlInfo {
  available: boolean;
  note: string | null;
  model: string | null;
  transfer: boolean | null;
  pretrained_scope: string | null;
  epochs: number | null;
  window: number | null;
  residual_std: number | null;
}

export interface ForecastResult {
  scope: string;
  state: string | null;
  district: string | null;
  village: string | null;
  basin: string | null;
  metric: ForecastMetric;
  method: ForecastMethod;
  method_label: string;
  unit: string;
  historical: ForecastPoint[];
  forecast: ForecastPoint[];
  slope: number | null;
  r2: number | null;
  direction: "rising" | "falling" | "stable";
  pct_change: number | null;
  end_value: number | null;
  risk: string | null;
  years_to_threshold: number | null;
  note: string;
  validation: Record<string, ModelMetrics> | null;
  best_method: string | null;
  is_demo: boolean;
  band: ConfidenceBand;
  decomposition: DecompositionInfo | null;
  ml: MlInfo | null;
}

export interface ForecastCompare {
  scope: string;
  metric: ForecastMetric;
  historical_points: number;
  evaluation: Record<string, ModelMetrics> | null;
  best: string | null;
  note: string | null;
}

export interface Basin {
  code: string;
  name: string;
  label: string;
  states: string[];
  description: string;
  state_count: number;
  district_count: number;
  district_ids: number[];
  latest: { year: number | null; stage: number | null; unit_count: number } | null;
}

export interface BacktestResult {
  scope: string;
  metric: ForecastMetric;
  historical_points: number;
  split_index: number | null;
  train_years: number[];
  test_years: number[];
  evaluation: Record<string, ModelMetrics> | null;
  baseline: { model: string; rmse: number | null; skill: number | null } | null;
  best: string | null;
  note: string | null;
}

export interface ForecastMeta {
  methods: ForecastMethod[];
  ml_available: boolean;
  ml_methods: ForecastMethod[];
  metrics: ForecastMetric[];
  bands: ConfidenceBand[];
}

export interface ForecastFilters {
  state?: string;
  district?: string;
  village?: string;
  basin?: string;
  metric: ForecastMetric;
  horizon: number;
  method: ForecastMethod;
  band?: ConfidenceBand;
  transfer?: boolean;
  epochs?: number;
}

export async function fetchForecast(filters: ForecastFilters): Promise<ForecastResult> {
  const { data } = await api.get<ForecastResult>("/predictions/forecast", {
    params: filters,
  });
  return data;
}

export async function fetchModelComparison(
  filters: Pick<ForecastFilters, "state" | "district" | "village" | "basin" | "metric">
): Promise<ForecastCompare> {
  const { data } = await api.get<ForecastCompare>("/predictions/compare", {
    params: filters,
  });
  return data;
}

export async function fetchBacktest(
  filters: Pick<ForecastFilters, "state" | "district" | "village" | "basin" | "metric"> & {
    split?: number;
  }
): Promise<BacktestResult> {
  const { data } = await api.get<BacktestResult>("/predictions/backtest", {
    params: filters,
  });
  return data;
}

export async function fetchForecastMeta(): Promise<ForecastMeta> {
  const { data } = await api.get<ForecastMeta>("/predictions/meta");
  return data;
}

export async function fetchBasins(): Promise<Basin[]> {
  const { data } = await api.get<Basin[]>("/predictions/basins");
  return data;
}

// ---------------------------------------------------------------------------
// Scenario Studio
// ---------------------------------------------------------------------------

export interface ScenarioDelta {
  end_baseline: number | null;
  end_scenario: number | null;
  end_delta: number | null;
  end_delta_pct: number | null;
  risk_baseline: string | null;
  risk_scenario: string | null;
}

export interface ScenarioCompare {
  scope: string;
  metric: ForecastMetric;
  unit: string;
  baseline: ForecastResult;
  scenario: ForecastResult | null;
  delta: ScenarioDelta;
}

export interface ScenarioFilters extends Omit<ForecastFilters, "transfer" | "epochs"> {
  extraction_change: number;
  recharge_change: number;
}

export async function fetchScenarioCompare(filters: ScenarioFilters): Promise<ScenarioCompare> {
  const { data } = await api.get<ScenarioCompare>("/predictions/scenario-compare", {
    params: filters,
  });
  return data;
}