import { GitCompareArrows, Loader2, Plus, RefreshCw, Trash2 } from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";

import BarChart from "@/components/BarChart";
import MultiLineChart, {
  SERIES_COLORS,
  type MultiLineSeries,
} from "@/components/MultiLineChart";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Select } from "@/components/ui/select";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { useLanguage } from "@/contexts/LanguageContext";
import { getApiError } from "@/services/api";
import {
  compareScopes,
  type ComparisonResult,
  type ComparisonScope,
  type ScopeKind,
} from "@/services/comparison";
import { fetchDistricts, fetchStates, fetchVillages } from "@/services/groundwater";
import { fetchBasins, type Basin } from "@/services/predictions";
import type {
  GroundwaterDistrict,
  GroundwaterState,
  GroundwaterVillage,
} from "@/types";

const MAX_SLOTS = 4;

const KIND_LABELS: Record<ScopeKind, string> = {
  state: "State",
  district: "District",
  village: "Village",
  basin: "River basin",
};

interface Slot {
  id: number;
  kind: ScopeKind;
  state: string;
  district: string;
  village: string;
  basin: string;
}

function formatNumber(value: number | null | undefined, digits = 1): string {
  if (value === null || value === undefined) return "—";
  return new Intl.NumberFormat("en-IN", { maximumFractionDigits: digits }).format(value);
}

function dominantCategory(scope: ComparisonScope): string | null {
  const counts = scope.summary?.category_counts ?? [];
  let best: { category: string; count: number } | null = null;
  for (const c of counts) {
    if (!best || c.count > best.count) best = c;
  }
  return best?.category ?? null;
}

function categoryVariant(category: string | null) {
  switch ((category ?? "").toLowerCase()) {
    case "safe":
      return "success" as const;
    case "semi-critical":
      return "warning" as const;
    case "critical":
      return "warning" as const;
    case "over-exploited":
    case "overexploited":
      return "destructive" as const;
    default:
      return "secondary" as const;
  }
}

function scopeName(slot: Slot): string | null {
  switch (slot.kind) {
    case "state":
      return slot.state || null;
    case "district":
      return slot.district || null;
    case "village":
      return slot.village || null;
    case "basin":
      return slot.basin || null;
  }
}

function toSeries(scopes: ComparisonScope[], metric: "stage_of_extraction" | "recharge" | "extraction"): MultiLineSeries[] {
  return scopes
    .filter((s) => s.resolved)
    .map((s, i) => ({
      label: s.label,
      color: SERIES_COLORS[i % SERIES_COLORS.length],
      points: s.trend
        .filter((row) => row[metric] !== null)
        .map((row) => ({ label: String(row.year), value: row[metric] as number })),
    }))
    .filter((s) => s.points.length > 0);
}

export default function Compare() {
  const { t } = useLanguage();
  const [states, setStates] = useState<GroundwaterState[]>([]);
  const [basins, setBasins] = useState<Basin[]>([]);
  const [districtOptions, setDistrictOptions] = useState<Record<number, GroundwaterDistrict[]>>({});
  const [villageOptions, setVillageOptions] = useState<Record<number, GroundwaterVillage[]>>({});

  const [slots, setSlots] = useState<Slot[]>([
    { id: 1, kind: "state", state: "", district: "", village: "", basin: "" },
    { id: 2, kind: "state", state: "", district: "", village: "", basin: "" },
  ]);
  const nextId = useMemo(() => Math.max(0, ...slots.map((s) => s.id)) + 1, [slots]);

  const [result, setResult] = useState<ComparisonResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [bootstrapped, setBootstrapped] = useState(false);

  useEffect(() => {
    let active = true;
    Promise.all([fetchStates(), fetchBasins()])
      .then(([stateRows, basinRows]) => {
        if (!active) return;
        setStates(stateRows);
        setBasins(basinRows.filter((b) => b.district_count > 0));
      })
      .catch(() => undefined);
    return () => {
      active = false;
    };
  }, []);

  // Preselect two states once the option lists arrive.
  useEffect(() => {
    if (bootstrapped || states.length < 2) return;
    setBootstrapped(true);
    setSlots((prev) =>
      prev.map((slot, i) => ({ ...slot, state: states[Math.min(i, states.length - 1)].name }))
    );
  }, [bootstrapped, states]);

  useEffect(() => {
    for (const slot of slots) {
      if (!slot.state || districtOptions[slot.id]) continue;
      const key = slot.id;
      fetchDistricts(slot.state)
        .then((rows) => setDistrictOptions((prev) => ({ ...prev, [key]: rows })))
        .catch(() => undefined);
    }
  }, [slots, districtOptions]);

  useEffect(() => {
    for (const slot of slots) {
      if (!slot.state || !slot.district || villageOptions[slot.id]) continue;
      const key = slot.id;
      fetchVillages(slot.state, slot.district)
        .then((rows) => setVillageOptions((prev) => ({ ...prev, [key]: rows })))
        .catch(() => undefined);
    }
  }, [slots, villageOptions]);

  const updateSlot = (id: number, patch: Partial<Slot>) => {
    setSlots((prev) =>
      prev.map((s) => {
        if (s.id !== id) return s;
        const merged = { ...s, ...patch };
        if (patch.kind !== undefined && patch.kind !== s.kind) {
          merged.state = "";
          merged.district = "";
          merged.village = "";
          merged.basin = "";
          setDistrictOptions((opts) => {
            const copy = { ...opts };
            delete copy[id];
            return copy;
          });
          setVillageOptions((opts) => {
            const copy = { ...opts };
            delete copy[id];
            return copy;
          });
        }
        if (patch.state !== undefined && patch.state !== s.state) {
          merged.district = "";
          merged.village = "";
          setDistrictOptions((opts) => {
            const copy = { ...opts };
            delete copy[id];
            return copy;
          });
          setVillageOptions((opts) => {
            const copy = { ...opts };
            delete copy[id];
            return copy;
          });
        }
        if (patch.district !== undefined && patch.district !== s.district) {
          merged.village = "";
          setVillageOptions((opts) => {
            const copy = { ...opts };
            delete copy[id];
            return copy;
          });
        }
        return merged;
      })
    );
  };

  const runCompare = useCallback(
    async (current: Slot[]) => {
      const specs = current
        .map((s) => ({ kind: s.kind, name: scopeName(s) }))
        .filter((s): s is { kind: ScopeKind; name: string } => Boolean(s.name));
      if (specs.length === 0) {
        setError(t("Pick at least one location to compare."));
        return;
      }
      setLoading(true);
      setError(null);
      try {
        const data = await compareScopes(specs);
        setResult(data);
      } catch (err) {
        setError(getApiError(err));
      } finally {
        setLoading(false);
      }
    },
    [t]
  );

  // Auto-compare the initial preselection.
  useEffect(() => {
    if (!bootstrapped) return;
    const ready = slots.every((s) => scopeName(s));
    if (ready) void runCompare(slots);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [bootstrapped, slots]);

  const scopes = result?.scopes ?? [];
  const hasUnresolved = scopes.some((s) => !s.resolved);

  const latestStageBars = scopes
    .filter((s) => s.resolved && s.trend.length > 0 && s.trend[s.trend.length - 1].stage_of_extraction !== null)
    .map((s, i) => ({
      label: s.label,
      value: s.trend[s.trend.length - 1].stage_of_extraction as number,
      color: SERIES_COLORS[i % SERIES_COLORS.length],
    }));

  return (
    <div className="mx-auto max-w-6xl space-y-6">
      <section className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="text-2xl font-bold">{t("Comparison workspace")}</h2>
          <p className="mt-1 text-muted-foreground">
            {t("Compare states, districts, villages or river basins side-by-side.")}
          </p>
        </div>
        {scopes.some((s) => s.summary?.is_demo) && (
          <Badge variant="warning">{t("Synthetic demo data")}</Badge>
        )}
      </section>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <GitCompareArrows className="h-4 w-4" />
            {t("Scopes")}
          </CardTitle>
          <CardDescription>
            {t("Choose up to {count} locations. Each column becomes one comparison series.", {
              count: MAX_SLOTS,
            })}
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          {slots.map((slot) => (
            <div key={slot.id} className="grid gap-2 sm:grid-cols-[9rem_1fr_1fr_1fr_auto] sm:items-end">
              <div className="space-y-1.5">
                <label className="text-xs font-medium text-muted-foreground">{t("Type")}</label>
                <Select
                  value={slot.kind}
                  onChange={(e) => updateSlot(slot.id, { kind: e.target.value as ScopeKind })}
                  className="h-8 w-full"
                >
                  {(Object.keys(KIND_LABELS) as ScopeKind[]).map((k) => (
                    <option key={k} value={k}>
                      {t(KIND_LABELS[k])}
                    </option>
                  ))}
                </Select>
              </div>
              {slot.kind !== "basin" && (
                <div className="space-y-1.5">
                  <label className="text-xs font-medium text-muted-foreground">{t("state")}</label>
                  <Select
                    value={slot.state}
                    onChange={(e) => updateSlot(slot.id, { state: e.target.value })}
                    className="h-8 w-full"
                  >
                    <option value="">{t("all_states")}</option>
                    {states.map((s) => (
                      <option key={s.id} value={s.name}>
                        {s.name}
                      </option>
                    ))}
                  </Select>
                </div>
              )}
              {(slot.kind === "district" || slot.kind === "village") && (
                <div className="space-y-1.5">
                  <label className="text-xs font-medium text-muted-foreground">{t("district")}</label>
                  <Select
                    value={slot.district}
                    onChange={(e) => updateSlot(slot.id, { district: e.target.value })}
                    disabled={!slot.state}
                    className="h-8 w-full"
                  >
                    <option value="">{t("all_districts")}</option>
                    {(districtOptions[slot.id] ?? []).map((d) => (
                      <option key={d.id} value={d.name}>
                        {d.name}
                      </option>
                    ))}
                  </Select>
                </div>
              )}
              {slot.kind === "village" && (
                <div className="space-y-1.5">
                  <label className="text-xs font-medium text-muted-foreground">{t("village")}</label>
                  <Select
                    value={slot.village}
                    onChange={(e) => updateSlot(slot.id, { village: e.target.value })}
                    disabled={!slot.district}
                    className="h-8 w-full"
                  >
                    <option value="">{t("All villages")}</option>
                    {(villageOptions[slot.id] ?? []).map((v) => (
                      <option key={v.id} value={v.name}>
                        {v.name}
                      </option>
                    ))}
                  </Select>
                </div>
              )}
              {slot.kind === "basin" && (
                <div className="space-y-1.5 sm:col-span-2">
                  <label className="text-xs font-medium text-muted-foreground">
                    {t("River basin")}
                  </label>
                  <Select
                    value={slot.basin}
                    onChange={(e) => updateSlot(slot.id, { basin: e.target.value })}
                    className="h-8 w-full"
                  >
                    <option value="">{t("Select a basin")}</option>
                    {basins.map((b) => (
                      <option key={b.code} value={b.name}>
                        {b.label}
                      </option>
                    ))}
                  </Select>
                </div>
              )}
              <Button
                variant="ghost"
                size="icon"
                aria-label={t("Remove")}
                onClick={() =>
                  setSlots((prev) =>
                    prev.length > 1 ? prev.filter((s) => s.id !== slot.id) : prev
                  )
                }
              >
                <Trash2 className="h-4 w-4" />
              </Button>
            </div>
          ))}
          <div className="flex flex-wrap gap-2">
            <Button size="sm" onClick={() => void runCompare(slots)} disabled={loading}>
              {loading ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <GitCompareArrows className="h-3.5 w-3.5" />}
              {t("Compare")}
            </Button>
            {slots.length < MAX_SLOTS && (
              <Button
                size="sm"
                variant="outline"
                onClick={() =>
                  setSlots((prev) => [
                    ...prev,
                    { id: nextId, kind: "state", state: "", district: "", village: "", basin: "" },
                  ])
                }
              >
                <Plus className="h-3.5 w-3.5" />
                {t("Add location")}
              </Button>
            )}
            <Button size="sm" variant="ghost" onClick={() => void runCompare(slots)} disabled={loading}>
              <RefreshCw className="h-3.5 w-3.5" />
              {t("Refresh")}
            </Button>
          </div>
        </CardContent>
      </Card>

      {error && (
        <div className="rounded-md border border-destructive/30 bg-destructive/10 p-4 text-sm text-destructive">
          {error}
        </div>
      )}

      {loading && !result && (
        <div className="flex items-center justify-center gap-2 py-16 text-muted-foreground">
          <Loader2 className="h-4 w-4 animate-spin" />
          {t("Loading comparison…")}
        </div>
      )}

      {result && (
        <>
          {result.verdict && (
            <Card>
              <CardContent className="flex flex-wrap items-center gap-x-6 gap-y-2 py-4 text-sm">
                <span>
                  <span className="font-medium">{t("Better position:")}</span>{" "}
                  {result.verdict.best_label} ({result.verdict.best_value.toFixed(1)}%{" "}
                  {t("stage of extraction")})
                </span>
                <span>
                  <span className="font-medium">{t("Most stressed:")}</span>{" "}
                  {result.verdict.worst_label} ({result.verdict.worst_value.toFixed(1)}%{" "}
                  {t("stage of extraction")})
                </span>
                <Badge variant="outline">{t("Lower stage is better")}</Badge>
              </CardContent>
            </Card>
          )}

          {hasUnresolved && (
            <div className="rounded-md border border-warning/40 bg-warning/10 p-3 text-sm">
              {t("Some selected locations could not be resolved in the dataset and were skipped.")}
            </div>
          )}

          <Card>
            <CardHeader>
              <CardTitle>{t("Latest-year metrics")}</CardTitle>
              <CardDescription>{t("Side-by-side summary of the most recent assessment year.")}</CardDescription>
            </CardHeader>
            <CardContent className="overflow-x-auto">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead className="w-44">{t("Metric")}</TableHead>
                    {scopes.map((s) => (
                      <TableHead key={s.key}>
                        <div className="flex items-center gap-1.5">
                          {s.label}
                          {!s.resolved && <Badge variant="secondary">{t("unresolved")}</Badge>}
                        </div>
                      </TableHead>
                    ))}
                  </TableRow>
                </TableHeader>
                <TableBody>
                  <TableRow>
                    <TableCell className="font-medium">{t("Assessment Units")}</TableCell>
                    {scopes.map((s) => (
                      <TableCell key={s.key}>
                        {s.summary ? s.summary.assessment_units : "—"}
                      </TableCell>
                    ))}
                  </TableRow>
                  <TableRow>
                    <TableCell className="font-medium">{t("Recharge (hm³)")}</TableCell>
                    {scopes.map((s) => (
                      <TableCell key={s.key}>{formatNumber(s.summary?.total_recharge, 0)}</TableCell>
                    ))}
                  </TableRow>
                  <TableRow>
                    <TableCell className="font-medium">{t("Extraction (hm³)")}</TableCell>
                    {scopes.map((s) => (
                      <TableCell key={s.key}>{formatNumber(s.summary?.total_extraction, 0)}</TableCell>
                    ))}
                  </TableRow>
                  <TableRow>
                    <TableCell className="font-medium">{t("Avg Stage of Extraction")}</TableCell>
                    {scopes.map((s) => (
                      <TableCell key={s.key}>
                        {s.summary?.average_stage_of_extraction != null
                          ? `${s.summary.average_stage_of_extraction.toFixed(1)}%`
                          : "—"}
                      </TableCell>
                    ))}
                  </TableRow>
                  <TableRow>
                    <TableCell className="font-medium">{t("Dominant category")}</TableCell>
                    {scopes.map((s) => {
                      const cat = dominantCategory(s);
                      return (
                        <TableCell key={s.key}>
                          {cat ? <Badge variant={categoryVariant(cat)}>{cat}</Badge> : "—"}
                        </TableCell>
                      );
                    })}
                  </TableRow>
                </TableBody>
              </Table>
            </CardContent>
          </Card>

          <div className="grid gap-6 lg:grid-cols-2">
            <Card>
              <CardHeader>
                <CardTitle>{t("Stage of extraction trend")}</CardTitle>
                <CardDescription>{t("% of recharge extracted, per year.")}</CardDescription>
              </CardHeader>
              <CardContent>
                <MultiLineChart series={toSeries(scopes, "stage_of_extraction")} formatValue={(v) => `${v.toFixed(1)}%`} />
              </CardContent>
            </Card>
            <Card>
              <CardHeader>
                <CardTitle>{t("Recharge trend")}</CardTitle>
                <CardDescription>{t("Total annual recharge (hm³), per year.")}</CardDescription>
              </CardHeader>
              <CardContent>
                <MultiLineChart series={toSeries(scopes, "recharge")} formatValue={(v) => formatNumber(v, 0)} />
              </CardContent>
            </Card>
            <Card>
              <CardHeader>
                <CardTitle>{t("Extraction trend")}</CardTitle>
                <CardDescription>{t("Total annual extraction (hm³), per year.")}</CardDescription>
              </CardHeader>
              <CardContent>
                <MultiLineChart series={toSeries(scopes, "extraction")} formatValue={(v) => formatNumber(v, 0)} />
              </CardContent>
            </Card>
            <Card>
              <CardHeader>
                <CardTitle>{t("Latest stage comparison")}</CardTitle>
                <CardDescription>{t("Most recent year, side-by-side.")}</CardDescription>
              </CardHeader>
              <CardContent>
                {latestStageBars.length > 0 ? (
                  <BarChart data={latestStageBars} formatValue={(v) => `${v.toFixed(1)}%`} />
                ) : (
                  <div className="text-sm text-muted-foreground">
                    {t("No data for the current filters.")}
                  </div>
                )}
              </CardContent>
            </Card>
          </div>
        </>
      )}
    </div>
  );
}
