import { api } from "./api";

export interface AdminUser {
  id: number;
  email: string;
  full_name: string;
  role: string;
  language_pref: string;
  is_active: boolean;
  last_login_at: string | null;
  created_at: string | null;
}

export interface AuditLog {
  id: number;
  action: string;
  resource: string | null;
  resource_id: string | null;
  user: string | null;
  details: Record<string, unknown> | null;
  created_at: string | null;
}

export interface DatasetInfo {
  id: number;
  name: string;
  description: string | null;
  source: string | null;
  publication_year: number | null;
  version: string;
  geographic_level: string | null;
  validation_status: string;
  is_demo: boolean;
}

export async function listUsers(): Promise<AdminUser[]> {
  const { data } = await api.get<AdminUser[]>("/admin/users");
  return data;
}

export async function createUser(data: {
  email: string;
  full_name: string;
  password: string;
  role: string;
}): Promise<AdminUser> {
  const { data: res } = await api.post<AdminUser>("/admin/users", data);
  return res;
}

export async function updateUser(
  id: number,
  data: { role?: string; is_active?: boolean }
): Promise<AdminUser> {
  const { data: res } = await api.patch<AdminUser>(`/admin/users/${id}`, data);
  return res;
}

export async function listAuditLogs(): Promise<AuditLog[]> {
  const { data } = await api.get<AuditLog[]>("/admin/audit-logs", { params: { limit: 200 } });
  return data;
}

export async function listDatasets(): Promise<DatasetInfo[]> {
  const { data } = await api.get<DatasetInfo[]>("/admin/datasets");
  return data;
}

export interface CriticalZone {
  district: string | null;
  state: string | null;
  stage: number | null;
  category: string;
  severity: "critical" | "warning" | "ok" | "unknown";
}

export interface AdminOverview {
  groundwater: {
    latest_year: number | null;
    assessment_units: number;
    total_units_registered: number;
    recharge_hm3: number;
    extraction_hm3: number;
    avg_stage_pct: number;
    category_counts: Record<string, number>;
    monitoring_levels: number;
    rainfall_records: number;
    critical_zones: CriticalZone[];
  };
  alerts: { enabled_rules: number; triggered_last_7d: number };
  datasets: { total: number };
  ai: {
    llm_enabled: boolean;
    llm_provider: string;
    llm_model: string;
    search_model: string | null;
    web_search_enabled: boolean;
    rag_documents: number;
    rag_chunks: number;
  };
  queries: {
    conversations: number;
    messages: number;
    assistant_answers: number;
    intent_counts: Record<string, number>;
    feedback_helpful: number;
    feedback_not_helpful: number;
  };
  users: {
    total: number;
    active: number;
    by_role: Record<string, number>;
  };
  system: {
    database_ok: boolean;
    python_version: string;
    platform: string;
    environment: string;
  };
}

export async function getOverview(): Promise<AdminOverview> {
  const { data } = await api.get<AdminOverview>("/admin/overview");
  return data;
}

export interface QueryMonitorRow {
  id: number;
  conversation_id: number;
  user: string | null;
  question: string | null;
  answer_preview: string;
  intent: string | null;
  response_type: string | null;
  language: string | null;
  is_demo: boolean;
  rating: number | null;
  created_at: string;
}

export async function getQueryMonitor(limit = 50): Promise<QueryMonitorRow[]> {
  const { data } = await api.get<QueryMonitorRow[]>("/admin/queries", {
    params: { limit },
  });
  return data;
}

export interface ModelMetric {
  model: string;
  rmse: number | null;
  mae: number | null;
  mape: number | null;
  direction_accuracy: number | null;
}

export interface ModelMetrics {
  state: string;
  metric: string;
  best_model: string | null;
  models: ModelMetric[];
  error?: string;
}

export async function getModelMetrics(
  state?: string,
  metric?: string
): Promise<ModelMetrics> {
  const { data } = await api.get<ModelMetrics>("/admin/models/metrics", {
    params: { state, metric },
  });
  return data;
}

// ---------------------------------------------------------------------------
// Data quality (anomaly flags)
// ---------------------------------------------------------------------------

export interface QualitySummary {
  total_open: number;
  by_status: Record<string, number>;
  by_severity: Record<string, number>;
  last_scan_at: string | null;
}

export type FlagStatus = "open" | "acknowledged" | "resolved" | "dismissed";

export interface AnomalyFlag {
  id: number;
  kind: string;
  severity: "high" | "medium" | "low";
  metric: string;
  year: number | null;
  state_name: string | null;
  district_name: string | null;
  unit_name: string | null;
  value: number | null;
  expected_min: number | null;
  expected_max: number | null
  detail: string | null;
  status: FlagStatus;
  review_note: string | null;
  created_at: string | null;
}

export interface FlagListResponse {
  total: number;
  count: number;
  limit: number;
  offset: number;
  flags: AnomalyFlag[];
  kinds: string[];
}

export async function getQualitySummary(): Promise<QualitySummary> {
  const { data } = await api.get<QualitySummary>("/quality/summary");
  return data;
}

export async function getQualityFlags(params: {
  status?: FlagStatus | "all";
  kind?: string;
  severity?: "high" | "medium" | "low";
  limit?: number;
}): Promise<FlagListResponse> {
  const { data } = await api.get<FlagListResponse>("/quality/flags", { params });
  return data;
}

export async function runQualityScan(): Promise<{
  scanned: number;
  created: number;
  truncated: boolean;
}> {
  const { data } = await api.post("/quality/scan");
  return data;
}

export async function reviewFlag(
  id: number,
  data: { status?: FlagStatus; review_note?: string }
): Promise<AnomalyFlag> {
  const { data: res } = await api.patch<AnomalyFlag>(`/quality/flags/${id}`, data);
  return res;
}
