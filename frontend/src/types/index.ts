export interface User {
  id: number;
  email: string;
  full_name: string;
  role: "user" | "expert" | "admin";
  language_pref: string;
  is_active: boolean;
}

export type UserRole = User["role"];

export interface HealthResponse {
  status: string;
  app: string;
  version: string;
  environment: string;
  database: string;
}

export interface GroundwaterState {
  id: number;
  name: string;
  code: string;
  region: string | null;
}

export interface GroundwaterDistrict {
  id: number;
  name: string;
  code: string | null;
}

export interface GroundwaterVillage {
  id: number;
  name: string;
  code: string | null;
  population: number | null;
  latitude: number | null;
  longitude: number | null;
}

export interface GroundwaterCategory {
  id: number;
  name: string;
  label: string;
  description: string | null;
  is_official: boolean;
}

export interface GroundwaterAssessment {
  id: number;
  state: string;
  district: string;
  assessment_unit: string;
  assessment_year: number;
  recharge_total: number | null;
  extraction_total: number | null;
  annual_extractable_resource: number | null;
  stage_of_extraction: number | null;
  category: string | null;
  is_demo: boolean;
}

export interface GroundwaterMetric {
  id: number;
  state: string;
  district: string;
  assessment_unit: string;
  year: number;
  metric_type: "recharge" | "extraction";
  value: number | null;
  unit: string;
  is_demo: boolean;
}

export interface CategoryCount {
  category: string;
  count: number;
}

export interface GroundwaterSummary {
  state: string;
  district: string | null;
  village: string | null;
  year: number | null;
  assessment_units: number;
  total_recharge: number | null;
  total_extraction: number | null;
  average_stage_of_extraction: number | null;
  category_counts: CategoryCount[];
  is_demo: boolean;
  source: string | null;
  unit: string;
}