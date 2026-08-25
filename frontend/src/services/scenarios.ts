import { api } from "./api";
import type { ForecastMethod, ForecastMetric } from "./predictions";

export interface SavedScenario {
  id: number;
  name: string;
  state: string | null;
  district: string | null;
  village: string | null;
  basin: string | null;
  metric: ForecastMetric;
  horizon: number;
  method: ForecastMethod;
  extraction_change: number;
  recharge_change: number;
  created_at: string | null;
}

export interface CreateScenarioInput {
  name: string;
  state?: string | null;
  district?: string | null;
  village?: string | null;
  basin?: string | null;
  metric: ForecastMetric;
  horizon: number;
  method: ForecastMethod;
  extraction_change: number;
  recharge_change: number;
}

export async function listSavedScenarios(): Promise<SavedScenario[]> {
  const { data } = await api.get<{ scenarios: SavedScenario[]; count: number }>(
    "/scenarios"
  );
  return data.scenarios;
}

export async function createSavedScenario(input: CreateScenarioInput): Promise<SavedScenario> {
  const { data } = await api.post<SavedScenario>("/scenarios", input);
  return data;
}

export async function deleteSavedScenario(id: number): Promise<void> {
  await api.delete(`/scenarios/${id}`);
}
