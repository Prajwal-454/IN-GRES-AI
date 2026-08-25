import { api } from "./api";

export interface TrendPoint {
  year: number;
  recharge: number;
  extraction: number;
  stage_of_extraction: number;
  categories: Record<string, number>;
}

export interface DistrictRanking {
  district: string;
  value: number;
  stage_of_extraction: number;
  year: number | null;
}

export interface Insight {
  type: string;
  text: string;
}

export interface InsightsResponse {
  insights: Insight[];
  state: string | null;
  latest_year: number | null;
}

export async function getTrends(state?: string): Promise<TrendPoint[]> {
  const { data } = await api.get<TrendPoint[]>("/analytics/trends", {
    params: { state },
  });
  return data;
}

export async function getDistrictRanking(params: {
  state?: string;
  year?: number;
  metric?: "recharge" | "extraction" | "stage";
}): Promise<DistrictRanking[]> {
  const { data } = await api.get<DistrictRanking[]>("/analytics/district-ranking", {
    params,
  });
  return data;
}

export async function getInsights(state?: string): Promise<InsightsResponse> {
  const { data } = await api.get<InsightsResponse>("/analytics/insights", {
    params: { state },
  });
  return data;
}