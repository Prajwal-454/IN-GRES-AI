import {
  FlaskConical,
  Loader2,
  Play,
  Save,
  SlidersHorizontal,
  Trash2,
} from "lucide-react";
import { useEffect, useMemo, useState } from "react";

import ForecastChart from "@/components/ForecastChart";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Input } from "@/components/ui/input";
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
import { useNotifications } from "@/contexts/NotificationContext";
import { getApiError } from "@/services/api";
import { fetchDistricts, fetchStates, fetchVillages } from "@/services/groundwater";
import {
  fetchBasins,
  fetchScenarioCompare,
  type ConfidenceBand,
  type ForecastMethod,
  type ForecastMetric,
  type ForecastPoint,
  type ForecastResult,
  type ScenarioCompare,
} from "@/services/predictions";
import {
  createSavedScenario,
  deleteSavedScenario,
  listSavedScenarios,
  type SavedScenario,
} from "@/services/scenarios";
import type { GroundwaterDistrict, GroundwaterState, GroundwaterVillage } from "@/types";

const METHODS: ForecastMethod[] = [
  "auto",
  "linear",
  "moving_average",
  "exponential",
  "arima",
  "holt",
  "ensemble",
];

const CHANGE_MIN = -50;
const CHANGE_MAX = 100;

function formatNumber(value: number | null | undefined, digits = 1): string {
  if (value === null || value === undefined) return "—";
  return new Intl.NumberFormat("en-IN", { maximumFractionDigits: digits }).format(value);
}

function toChartPoints(result: ForecastResult | null): ForecastPoint[] {
  if (!result) return [];
  return [...result.historical, ...result.forecast].map((p) => ({
    year: p.year,
    value: p.value,
    upper: p.upper ?? null,
    lower: p.lower ?? null,
  }));
}

export default function Studio() {
  const { t } = useLanguage();
  const { toast } = useNotifications();

  const [states, setStates] = useState<GroundwaterState[]>([]);
  const [districts, setDistricts] = useState<GroundwaterDistrict[]>([]);
  const [villages, setVillages] = useState<GroundwaterVillage[]>([]);
  const [basins, setBasins] = useState<{ code: string; name: string; label: string }[]>([]);

  const [stateFilter, setStateFilter] = useState("");
  const [districtFilter, setDistrictFilter] = useState("");
  const [villageFilter, setVillageFilter] = useState("");
  const [basinFilter, setBasinFilter] = useState("");
  const [metric, setMetric] = useState<ForecastMetric>("stage");
  const [horizon, setHorizon] = useState(5);
  const [method, setMethod] = useState<ForecastMethod>("auto");
  const [band, setBand] = useState<ConfidenceBand>("normal");

  const [extractionChange, setExtractionChange] = useState(-20);
  const [rechargeChange, setRechargeChange] = useState(0);

  const [result, setResult] = useState<ScenarioCompare | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [saved, setSaved] = useState<SavedScenario[] | null>(null);
  const [scenarioName, setScenarioName] = useState("");
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    let active = true;
    fetchStates()
      .then((rows) => active && setStates(rows))
      .catch(() => undefined);
    fetchBasins()
      .then((rows) => active && setBasins(rows.filter((b) => b.district_count > 0)))
      .catch(() => undefined);
    listSavedScenarios()
      .then((rows) => active && setSaved(rows))
      .catch(() => active && setSaved([]));
    return () => {
      active = false;
    };
  }, []);

  // Preselect the first state so the studio has something to show on arrival.
  useEffect(() => {
    if (!states.length || stateFilter || basinFilter) return;
    setStateFilter(states[0].name);
  }, [states, stateFilter, basinFilter]);

  useEffect(() => {
    if (!stateFilter || basinFilter) {
      setDistricts([]);
      return;
    }
    let active = true;
    fetchDistricts(stateFilter)
      .then((rows) => active && setDistricts(rows))
      .catch(() => active && setDistricts([]));
    return () => {
      active = false;
    };
  }, [stateFilter, basinFilter]);

  useEffect(() => {
    if (!stateFilter || !districtFilter || basinFilter) {
      setVillages([]);
      return;
    }
    let active = true;
    fetchVillages(stateFilter, districtFilter)
      .then((rows) => active && setVillages(rows))
      .catch(() => active && setVillages([]));
    return () => {
      active = false;
    };
  }, [stateFilter, districtFilter, basinFilter]);

  const runPayload = useMemo(
    () => ({
      state: stateFilter || undefined,
      district: districtFilter || undefined,
      village: villageFilter || undefined,
      basin: basinFilter || undefined,
      metric,
      horizon,
      method,
      band,
      extraction_change: extractionChange,
      recharge_change: rechargeChange,
    }),
    [stateFilter, districtFilter, villageFilter, basinFilter, metric, horizon, method, band, extractionChange, rechargeChange]
  );

  async function run(payload = runPayload) {
    setLoading(true);
    setError(null);
    try {
      setResult(await fetchScenarioCompare(payload));
    } catch (err) {
      setError(getApiError(err));
    } finally {
      setLoading(false);
    }
  }

  const scopeLabel =
    result?.scope ??
    (basinFilter ||
      villageFilter ||
      districtFilter ||
      stateFilter ||
      t("India"));

  async function handleSave() {
    if (!scenarioName.trim()) {
      toast(t("Give this scenario a name."), "error");
      return;
    }
    setSaving(true);
    try {
      await createSavedScenario({
        name: scenarioName.trim(),
        state: stateFilter || null,
        district: districtFilter || null,
        village: villageFilter || null,
        basin: basinFilter || null,
        metric,
        horizon,
        method,
        extraction_change: extractionChange,
        recharge_change: rechargeChange,
      });
      setScenarioName("");
      toast(t("Scenario saved."), "success");
      setSaved(await listSavedScenarios());
    } catch (err) {
      toast(getApiError(err), "error");
    } finally {
      setSaving(false);
    }
  }

  function loadSaved(s: SavedScenario) {
    setBasinFilter(s.basin ?? "");
    setStateFilter(s.state ?? "");
    setDistrictFilter(s.district ?? "");
    setVillageFilter(s.village ?? "");
    setMetric(s.metric);
    setHorizon(s.horizon);
    setMethod(s.method);
    setExtractionChange(s.extraction_change);
    setRechargeChange(s.recharge_change);
    void run({
      state: s.state ?? undefined,
      district: s.district ?? undefined,
      village: s.village ?? undefined,
      basin: s.basin ?? undefined,
      metric: s.metric,
      horizon: s.horizon,
      method: s.method,
      band,
      extraction_change: s.extraction_change,
      recharge_change: s.recharge_change,
    });
  }

  async function handleDelete(id: number) {
    try {
      await deleteSavedScenario(id);
      setSaved((prev) => (prev ?? []).filter((s) => s.id !== id));
    } catch (err) {
      toast(getApiError(err), "error");
    }
  }

  const delta = result?.delta;
  const improvement =
    delta?.end_delta != null
      ? metric === "stage" || metric === "extraction"
        ? delta.end_delta < 0
        : metric === "recharge"
          ? delta.end_delta > 0
          : delta.end_delta < 0
      : null;

  return (
    <div className="mx-auto max-w-6xl space-y-6">
      <section className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="flex items-center gap-2 text-2xl font-bold">
            <FlaskConical className="h-6 w-6 text-primary" />
            {t("Scenario Studio")}
          </h2>
          <p className="mt-1 text-muted-foreground">
            {t(
              "Ask what-if: change pumping or recharge and compare the projection against the unmodified baseline."
            )}
          </p>
        </div>
        {result?.baseline.is_demo && (
          <Badge variant="warning">{t("Statistical estimate · demo data")}</Badge>
        )}
      </section>

      <Card>
        <CardHeader>
          <CardTitle className="text-sm">{t("Scope & model")}</CardTitle>
        </CardHeader>
        <CardContent className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          <div className="space-y-1.5">
            <label className="text-sm font-medium">{t("River basin")}</label>
            <Select
              value={basinFilter}
              onChange={(e) => {
                setBasinFilter(e.target.value);
                setStateFilter("");
                setDistrictFilter("");
                setVillageFilter("");
              }}
            >
              <option value="">{t("No basin (state/district/village)")}</option>
              {basins.map((b) => (
                <option key={b.code} value={b.name}>
                  {b.label}
                </option>
              ))}
            </Select>
          </div>
          {!basinFilter && (
            <>
              <div className="space-y-1.5">
                <label className="text-sm font-medium">{t("state")}</label>
                <Select
                  value={stateFilter}
                  onChange={(e) => {
                    setStateFilter(e.target.value);
                    setDistrictFilter("");
                    setVillageFilter("");
                  }}
                >
                  <option value="">{t("all_states")}</option>
                  {states.map((s) => (
                    <option key={s.id} value={s.name}>
                      {s.name}
                    </option>
                  ))}
                </Select>
              </div>
              <div className="space-y-1.5">
                <label className="text-sm font-medium">{t("district")}</label>
                <Select
                  value={districtFilter}
                  onChange={(e) => {
                    setDistrictFilter(e.target.value);
                    setVillageFilter("");
                  }}
                  disabled={!stateFilter}
                >
                  <option value="">{t("all_districts")}</option>
                  {districts.map((d) => (
                    <option key={d.id} value={d.name}>
                      {d.name}
                    </option>
                  ))}
                </Select>
              </div>
              <div className="space-y-1.5">
                <label className="text-sm font-medium">{t("Village")}</label>
                <Select
                  value={villageFilter}
                  onChange={(e) => setVillageFilter(e.target.value)}
                  disabled={!districtFilter}
                >
                  <option value="">{t("All villages")}</option>
                  {villages.map((v) => (
                    <option key={v.id} value={v.name}>
                      {v.name}
                    </option>
                  ))}
                </Select>
              </div>
            </>
          )}
          <div className="space-y-1.5">
            <label className="text-sm font-medium">{t("metric")}</label>
            <Select value={metric} onChange={(e) => setMetric(e.target.value as ForecastMetric)}>
              <option value="stage">{t("Stage of extraction")}</option>
              <option value="recharge">{t("recharge")}</option>
              <option value="extraction">{t("extraction")}</option>
            </Select>
          </div>
          <div className="space-y-1.5">
            <label className="text-sm font-medium">{t("Model")}</label>
            <Select value={method} onChange={(e) => setMethod(e.target.value as ForecastMethod)}>
              {METHODS.map((m) => (
                <option key={m} value={m}>
                  {m}
                </option>
              ))}
            </Select>
          </div>
          <div className="space-y-1.5">
            <label className="text-sm font-medium">{t("Confidence band")}</label>
            <Select value={band} onChange={(e) => setBand(e.target.value as ConfidenceBand)}>
              <option value="normal">{t("Normal (95%)")}</option>
              <option value="bootstrap">{t("Bootstrap fan (5–95%)")}</option>
            </Select>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-sm">
            <SlidersHorizontal className="h-4 w-4" />
            {t("What-if changes")}
          </CardTitle>
          <CardDescription>
            {t(
              "Applied to the historical series before fitting the model, exactly like assistant what-if answers."
            )}
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-5">
          <div className="grid gap-5 sm:grid-cols-2">
            <div>
              <div className="mb-2 flex items-center justify-between text-sm">
                <span className="font-medium">{t("Extraction (pumping) change")}</span>
                <Badge variant={extractionChange < 0 ? "success" : extractionChange > 0 ? "destructive" : "secondary"}>
                  {extractionChange > 0 ? "+" : ""}
                  {extractionChange}%
                </Badge>
              </div>
              <input
                type="range"
                min={CHANGE_MIN}
                max={CHANGE_MAX}
                step={5}
                value={extractionChange}
                onChange={(e) => setExtractionChange(Number(e.target.value))}
                className="w-full accent-teal-700"
                aria-label={t("Extraction (pumping) change")}
              />
              <div className="mt-1 flex justify-between text-[10px] text-muted-foreground">
                <span>{CHANGE_MIN}%</span>
                <span>{CHANGE_MAX}%</span>
              </div>
            </div>
            <div>
              <div className="mb-2 flex items-center justify-between text-sm">
                <span className="font-medium">{t("Recharge change")}</span>
                <Badge variant={rechargeChange > 0 ? "success" : rechargeChange < 0 ? "destructive" : "secondary"}>
                  {rechargeChange > 0 ? "+" : ""}
                  {rechargeChange}%
                </Badge>
              </div>
              <input
                type="range"
                min={CHANGE_MIN}
                max={CHANGE_MAX}
                step={5}
                value={rechargeChange}
                onChange={(e) => setRechargeChange(Number(e.target.value))}
                className="w-full accent-sky-600"
                aria-label={t("Recharge change")}
              />
              <div className="mt-1 flex justify-between text-[10px] text-muted-foreground">
                <span>{CHANGE_MIN}%</span>
                <span>{CHANGE_MAX}%</span>
              </div>
            </div>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <Button onClick={() => void run()} disabled={loading}>
              {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : <Play className="h-4 w-4" />}
              {t("Run projection")}
            </Button>
            <Button
              variant="outline"
              size="sm"
              onClick={() => {
                setExtractionChange(-20);
                setRechargeChange(0);
              }}
            >
              {t("-20% pumping")}
            </Button>
            <Button
              variant="outline"
              size="sm"
              onClick={() => {
                setExtractionChange(10);
                setRechargeChange(-25);
              }}
            >
              {t("+10% pumping · drier recharge")}
            </Button>
            <Button
              variant="ghost"
              size="sm"
              onClick={() => {
                setExtractionChange(0);
                setRechargeChange(0);
              }}
            >
              {t("Reset")}
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
          {t("Loading forecast…")}
        </div>
      )}

      {delta && (
        <section className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <Card>
            <CardHeader>
              <CardDescription>{t("Baseline end value")}</CardDescription>
              <CardTitle className="text-2xl">
                {formatNumber(delta.end_baseline)}
                {metric === "stage" ? "%" : ` ${result?.unit ?? "hm³"}`}
              </CardTitle>
            </CardHeader>
          </Card>
          <Card>
            <CardHeader>
              <CardDescription>{t("Scenario end value")}</CardDescription>
              <CardTitle className="text-2xl">
                {formatNumber(delta.end_scenario)}
                {metric === "stage" ? "%" : ` ${result?.unit ?? "hm³"}`}
              </CardTitle>
            </CardHeader>
          </Card>
          <Card>
            <CardHeader>
              <CardDescription>{t("Difference at horizon end")}</CardDescription>
              <CardTitle
                className={
                  improvement === null
                    ? "text-2xl"
                    : improvement
                      ? "text-2xl text-emerald-600"
                      : "text-2xl text-red-600"
                }
              >
                {delta.end_delta != null
                  ? `${delta.end_delta > 0 ? "+" : ""}${formatNumber(delta.end_delta)}${
                      delta.end_delta_pct != null
                        ? ` (${delta.end_delta_pct > 0 ? "+" : ""}${delta.end_delta_pct.toFixed(1)}%)`
                        : ""
                    }`
                  : "—"}
              </CardTitle>
            </CardHeader>
          </Card>
          <Card>
            <CardHeader>
              <CardDescription>{t("Projected risk category")}</CardDescription>
              <CardTitle className="text-base leading-snug">
                {delta.risk_baseline ?? "—"} <span className="text-muted-foreground">→</span>{" "}
                {delta.risk_scenario ?? "—"}
              </CardTitle>
            </CardHeader>
          </Card>
        </section>
      )}

      {result && (
        <div className="grid gap-6 lg:grid-cols-2">
          <Card>
            <CardHeader>
              <CardTitle>{t("Baseline projection")}</CardTitle>
              <CardDescription>
                {scopeLabel} · {result.baseline.method_label}
              </CardDescription>
            </CardHeader>
            <CardContent>
              <ForecastChart points={toChartPoints(result.baseline)} metric={metric} formatValue={(v) => `${formatNumber(v)}`} />
            </CardContent>
          </Card>
          <Card>
            <CardHeader>
              <CardTitle>{t("Scenario projection")}</CardTitle>
              <CardDescription>
                {extractionChange !== 0 && (
                  <>
                    {t("Extraction {sign}{pct}%", {
                      sign: extractionChange > 0 ? "+" : "",
                      pct: Math.abs(extractionChange),
                    })}
                    {" · "}
                  </>
                )}
                {rechargeChange !== 0 && (
                  <>
                    {t("Recharge {sign}{pct}%", {
                      sign: rechargeChange > 0 ? "+" : "",
                      pct: Math.abs(rechargeChange),
                    })}
                    {" · "}
                  </>
                )}
                {t("{method}", { method: result.scenario?.method_label ?? "" })}
              </CardDescription>
            </CardHeader>
            <CardContent>
              <ForecastChart points={toChartPoints(result.scenario)} metric={metric} formatValue={(v) => `${formatNumber(v)}`} />
            </CardContent>
          </Card>
        </div>
      )}

      <Card>
        <CardHeader>
          <CardTitle className="text-sm">{t("Saved scenarios")}</CardTitle>
          <CardDescription>
            {t("Store the current inputs and reload them later — they always recompute on the latest data.")}
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex flex-wrap items-end gap-3">
            <div className="min-w-56 flex-1 space-y-1.5">
              <label className="text-sm font-medium">{t("Name")}</label>
              <Input
                value={scenarioName}
                onChange={(e) => setScenarioName(e.target.value)}
                placeholder={t("Cut pumping 20% by 2030") ?? ""}
              />
            </div>
            <Button variant="outline" onClick={() => void handleSave()} disabled={saving}>
              {saving ? <Loader2 className="h-4 w-4 animate-spin" /> : <Save className="h-4 w-4" />}
              {t("Save current setup")}
            </Button>
          </div>

          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>{t("Name")}</TableHead>
                <TableHead>{t("Scope")}</TableHead>
                <TableHead>{t("Changes")}</TableHead>
                <TableHead>{t("Actions")}</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {(saved ?? []).map((s) => (
                <TableRow key={s.id}>
                  <TableCell className="font-medium">
                    {s.name}
                    <div className="mt-0.5 text-[11px] text-muted-foreground">
                      {s.metric} · {s.horizon}y · {s.method}
                    </div>
                  </TableCell>
                  <TableCell className="text-xs text-muted-foreground">
                    {[s.village, s.district, s.state, s.basin].filter(Boolean).join(", ") ||
                      t("All India")}
                  </TableCell>
                  <TableCell className="whitespace-nowrap text-xs">
                    <Badge variant={s.extraction_change < 0 ? "success" : s.extraction_change > 0 ? "destructive" : "secondary"}>
                      E {s.extraction_change > 0 ? "+" : ""}
                      {s.extraction_change}%
                    </Badge>{" "}
                    <Badge variant={s.recharge_change > 0 ? "success" : s.recharge_change < 0 ? "destructive" : "secondary"}>
                      R {s.recharge_change > 0 ? "+" : ""}
                      {s.recharge_change}%
                    </Badge>
                  </TableCell>
                  <TableCell>
                    <div className="flex gap-1">
                      <Button size="sm" variant="outline" onClick={() => loadSaved(s)}>
                        {t("Load")}
                      </Button>
                      <Button size="sm" variant="ghost" onClick={() => void handleDelete(s.id)}>
                        <Trash2 className="h-3.5 w-3.5" />
                      </Button>
                    </div>
                  </TableCell>
                </TableRow>
              ))}
              {saved?.length === 0 && (
                <TableRow>
                  <TableCell colSpan={4} className="h-16 text-center text-muted-foreground">
                    {t("No saved scenarios yet.")}
                  </TableCell>
                </TableRow>
              )}
            </TableBody>
          </Table>
        </CardContent>
      </Card>
    </div>
  );
}
