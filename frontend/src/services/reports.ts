import { api } from "./api";
import type { GroundwaterAssessment, GroundwaterSummary } from "@/types";

export interface ReportData {
  rows: GroundwaterAssessment[];
  summary: GroundwaterSummary;
  count: number;
}

export async function getReportData(params: {
  state?: string;
  district?: string;
  village?: string;
  year?: number;
}): Promise<ReportData> {
  const { data } = await api.get<ReportData>("/reports/data", { params });
  return data;
}

export async function downloadReport(
  type: "assessment" | "recharge" | "extraction",
  params: { state?: string; district?: string; village?: string; year?: number }
): Promise<void> {
  const { data } = await api.get(`/reports/export.csv`, {
    params: { type, ...params },
    responseType: "blob",
  });
  triggerDownload(data, `ingres-${type}-report.csv`);
}

export async function downloadPdf(params: {
  state?: string;
  district?: string;
  village?: string;
  year?: number;
}): Promise<void> {
  const { data } = await api.get(`/reports/export.pdf`, {
    params,
    responseType: "blob",
  });
  triggerDownload(data, "ingres-report.pdf");
}

export function triggerDownload(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}

export interface AssessmentReportParams {
  state?: string;
  district?: string;
  year_from?: number;
  year_to?: number;
}

export interface TrendPoint {
  year: number;
  stage: number;
  recharge: number;
  extraction: number;
}

export interface ForecastPoint {
  year: number;
  value: number;
  upper: number | null;
  lower: number | null;
}

export interface AssessmentReport {
  scope: { state: string | null; district: string | null; display: string };
  period: { from: number; to: number; requested_to: number; latest: number };
  is_demo: boolean;
  generated_at: string;
  executive_summary: string[];
  status: {
    assessment_units: number;
    recharge: number;
    extraction: number;
    resource: number | null;
    stage: number;
    category: string | null;
    water_level: { value: number | null; unit: string; trend_per_year: number | null };
    category_counts: { category: string; count: number }[];
  };
  trend: {
    metric: string;
    unit: string;
    series: TrendPoint[];
    direction: "rising" | "falling" | "stable";
    slope: number | null;
    pct_change: number | null;
  };
  prediction: {
    metric: string;
    unit: string;
    method: string | null;
    method_label: string | null;
    best_method: string | null;
    direction: "rising" | "falling" | "stable";
    pct_change: number | null;
    r2: number | null;
    slope: number | null;
    risk: string | null;
    years_to_threshold: number | null;
    end_value: number | null;
    end_year: number;
    historical: ForecastPoint[];
    forecast: ForecastPoint[];
    note: string;
  };
  risk: {
    current: string | null;
    predicted: string | null;
    level: string;
    current_category: string | null;
    predicted_category: string | null;
    summary: string;
  };
  map: {
    type: "FeatureCollection";
    features: { type: string; properties: Record<string, unknown>; geometry: unknown }[];
    meta: { metric: string; year: number; target_year: number };
  };
  recommendations: string[];
  sources: string[];
}

export async function getAssessmentReport(
  params: AssessmentReportParams
): Promise<AssessmentReport> {
  const { data } = await api.get<AssessmentReport>("/reports/assessment", { params });
  return data;
}

export async function downloadAssessmentPdf(params: AssessmentReportParams): Promise<void> {
  const { data } = await api.get(`/reports/assessment.pdf`, {
    params,
    responseType: "blob",
  });
  triggerDownload(data, "ingres-assessment-report.pdf");
}

export async function downloadAssessmentXlsx(params: AssessmentReportParams): Promise<void> {
  const { data } = await api.get(`/reports/assessment.xlsx`, {
    params,
    responseType: "blob",
  });
  triggerDownload(data, "ingres-assessment-report.xlsx");
}

// ---------------------------------------------------------------------------
// Scheduled reports (digests)
// ---------------------------------------------------------------------------

export type ScheduleFrequency = "weekly" | "monthly";

export interface ReportSchedule {
  id: number;
  name: string;
  state: string | null;
  district: string | null;
  village: string | null;
  scope_label: string;
  frequency: ScheduleFrequency;
  recipients: string[];
  enabled: boolean;
  next_run_at: string | null;
  last_run_at: string | null;
  last_status: string | null;
  last_error: string | null;
  has_file: boolean;
}

export interface CreateScheduleInput {
  name: string;
  state?: string | null;
  district?: string | null;
  village?: string | null;
  frequency: ScheduleFrequency;
  recipients: string[];
  enabled?: boolean;
}

export async function listSchedules(all = false): Promise<ReportSchedule[]> {
  const { data } = await api.get<{ schedules: ReportSchedule[]; count: number }>(
    "/reports/schedules",
    { params: { all } }
  );
  return data.schedules;
}

export async function createSchedule(input: CreateScheduleInput): Promise<ReportSchedule> {
  const { data } = await api.post<ReportSchedule>("/reports/schedules", input);
  return data;
}

export async function updateSchedule(
  id: number,
  patch: { name?: string; frequency?: ScheduleFrequency; recipients?: string[]; enabled?: boolean }
): Promise<ReportSchedule> {
  const { data } = await api.patch<ReportSchedule>(`/reports/schedules/${id}`, patch);
  return data;
}

export async function deleteSchedule(id: number): Promise<void> {
  await api.delete(`/reports/schedules/${id}`);
}

export async function runScheduleNow(
  id: number
): Promise<{ id: number; status: string; emailed: boolean; file: string | null; error: string | null }> {
  const { data } = await api.post(`/reports/schedules/${id}/run`);
  return data;
}

export async function downloadLatestDigest(id: number, filename: string): Promise<void> {
  const { data } = await api.get(`/reports/schedules/${id}/download-latest`, {
    responseType: "blob",
  });
  triggerDownload(data, filename);
}