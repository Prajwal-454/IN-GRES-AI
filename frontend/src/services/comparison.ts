import { api } from "./api";

export type ScopeKind = "state" | "district" | "village" | "basin";

export interface ScopeSpec {
  kind: ScopeKind;
  name: string;
}

export interface ComparisonSummary {
  total_recharge: number | null;
  total_extraction: number | null;
  average_stage_of_extraction: number | null;
  assessment_units: number;
  category_counts: { category: string; count: number }[];
  is_demo: boolean;
  source: string | null;
}

export interface ComparisonTrendRow {
  year: number;
  stage_of_extraction: number | null;
  recharge: number | null;
  extraction: number | null;
}

export interface ComparisonScope {
  key: string;
  kind: ScopeKind;
  name: string;
  label: string;
  resolved: boolean;
  summary: ComparisonSummary | null;
  trend: ComparisonTrendRow[];
  latest_year: number | null;
}

export interface ComparisonVerdict {
  metric: string;
  best_key: string;
  best_label: string;
  worst_key: string;
  worst_label: string;
  best_value: number;
  worst_value: number;
}

export interface ComparisonResult {
  scopes: ComparisonScope[];
  count: number;
  verdict: ComparisonVerdict | null;
}

export function scopeKey(scope: ScopeSpec): string {
  return `${scope.kind}:${scope.name}`;
}

export async function compareScopes(scopes: ScopeSpec[]): Promise<ComparisonResult> {
  const { data } = await api.get<ComparisonResult>("/comparison/metrics", {
    params: { scopes: scopes.map(scopeKey).join(",") },
  });
  return data;
}
