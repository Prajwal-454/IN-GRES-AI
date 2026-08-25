import { api } from "./api";
import type {
  GroundwaterAssessment,
  GroundwaterCategory,
  GroundwaterDistrict,
  GroundwaterMetric,
  GroundwaterState,
  GroundwaterSummary,
  GroundwaterVillage,
} from "@/types";

export interface GroundwaterFilters {
  state?: string;
  district?: string;
  village?: string;
  year?: number;
  category?: string;
}

function query(params: GroundwaterFilters): string {
  const qs = new URLSearchParams();
  if (params.state) qs.set("state", params.state);
  if (params.district) qs.set("district", params.district);
  if (params.village) qs.set("village", params.village);
  if (params.year) qs.set("year", String(params.year));
  if (params.category) qs.set("category", params.category);
  const s = qs.toString();
  return s ? `?${s}` : "";
}

export async function fetchStates(): Promise<GroundwaterState[]> {
  const { data } = await api.get<GroundwaterState[]>("/groundwater/states");
  return data;
}

export async function fetchDistricts(state: string): Promise<GroundwaterDistrict[]> {
  const { data } = await api.get<GroundwaterDistrict[]>("/groundwater/districts", {
    params: { state },
  });
  return data;
}

export async function fetchVillages(
  state: string,
  district: string
): Promise<GroundwaterVillage[]> {
  const { data } = await api.get<GroundwaterVillage[]>("/groundwater/villages", {
    params: { state, district },
  });
  return data;
}

export async function fetchCategories(): Promise<GroundwaterCategory[]> {
  const { data } = await api.get<GroundwaterCategory[]>("/groundwater/categories");
  return data;
}

export async function fetchAssessments(
  filters: GroundwaterFilters
): Promise<GroundwaterAssessment[]> {
  const { data } = await api.get<GroundwaterAssessment[]>(
    `/groundwater/assessment${query(filters)}`
  );
  return data;
}

export async function fetchRecharge(
  filters: GroundwaterFilters
): Promise<GroundwaterMetric[]> {
  const { data } = await api.get<GroundwaterMetric[]>(`/groundwater/recharge${query(filters)}`);
  return data;
}

export async function fetchExtraction(
  filters: GroundwaterFilters
): Promise<GroundwaterMetric[]> {
  const { data } = await api.get<GroundwaterMetric[]>(
    `/groundwater/extraction${query(filters)}`
  );
  return data;
}

export async function fetchSummary(
  filters: GroundwaterFilters
): Promise<GroundwaterSummary> {
  const { data } = await api.get<GroundwaterSummary>(`/groundwater/summary${query(filters)}`);
  return data;
}