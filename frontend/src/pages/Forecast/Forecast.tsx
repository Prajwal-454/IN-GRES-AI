import {
  Activity,
  AlertTriangle,
  BrainCircuit,
  CheckCircle2,
  Cpu,
  TrendingUp,
} from "lucide-react";
import { useEffect, useMemo, useState } from "react";

import ForecastChart from "@/components/ForecastChart";
import IngresLoader from "@/components/IngresLoader";
import IngresNetworkError from "@/components/IngresNetworkError";
import { Badge } from "@/components/ui/badge";
import { getApiError, isNetworkError } from "@/services/api";
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
import {
  fetchDistricts,
  fetchStates,
  fetchVillages,
} from "@/services/groundwater";
import {
  fetchBacktest,
  fetchBasins,
  fetchForecast,
  fetchForecastMeta,
  fetchModelComparison,
  type Basin,
  type ConfidenceBand,
  type ForecastCompare,
  type ForecastMethod,
  type ForecastMeta,
  type ForecastMetric,
  type ForecastResult,
} from "@/services/predictions";
import type { GroundwaterState, GroundwaterVillage } from "@/types";

const RISK_VARIANT: Record<string, "success" | "warning" | "destructive" | "secondary"> = {
  safe: "success",
  "semi-critical": "warning",
  critical: "warning",
  "over-exploited": "destructive",
};

const METHOD_LABELS: Record<ForecastMethod, string> = {
  linear: "Linear trend",
  moving_average: "Moving average",
  exponential: "Exponential smoothing",
  arima: "ARIMA(1,1,0)",
  holt: "Holt's linear trend",
  ensemble: "Ensemble (weighted blend)",
  auto: "Auto (best validated)",
  lstm: "Deep learning — LSTM",
  transformer: "Deep learning — Transformer",
  ml: "Deep learning (best available)",
};

const ALL_METHODS: ForecastMethod[] = [
  "linear",
  "moving_average",
  "exponential",
  "arima",
  "holt",
  "ensemble",
];

function formatNumber(value: number | null | undefined, digits = 1): string {
  if (value === null || value === undefined) return "—";
  return new Intl.NumberFormat("en-IN", { maximumFractionDigits: digits }).format(value);
}

export default function Forecast() {
  const { t } = useLanguage();
  const [states, setStates] = useState<GroundwaterState[]>([]);
  const [districts, setDistricts] = useState<{ id: number; name: string }[]>([]);
  const [villages, setVillages] = useState<GroundwaterVillage[]>([]);
  const [basins, setBasins] = useState<Basin[]>([]);
  const [meta, setMeta] = useState<ForecastMeta | null>(null);

  const [stateFilter, setStateFilter] = useState("");
  const [districtFilter, setDistrictFilter] = useState("");
  const [villageFilter, setVillageFilter] = useState("");
  const [basinFilter, setBasinFilter] = useState("");
  const [metric, setMetric] = useState<ForecastMetric>("stage");
  const [method, setMethod] = useState<ForecastMethod>("linear");
  const [horizon, setHorizon] = useState(5);
  const [band, setBand] = useState<ConfidenceBand>("normal");
  const [transfer, setTransfer] = useState(false);

  const [result, setResult] = useState<ForecastResult | null>(null);
  const [comparison, setComparison] = useState<ForecastCompare | null>(null);
  const [backtest, setBacktest] = useState<Awaited<ReturnType<typeof fetchBacktest>> | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [lastError, setLastError] = useState<unknown>(null);

  const mlAvailable = meta?.ml_available ?? false;

  const availableMethods = useMemo<ForecastMethod[]>(() => {
    if (!meta) return ALL_METHODS;
    const methods = meta.methods.filter(
      (m) => !["lstm", "transformer", "ml"].includes(m) || mlAvailable
    ) as ForecastMethod[];
    return methods.length ? methods : ALL_METHODS;
  }, [meta, mlAvailable]);

  const filters = useMemo(
    () => ({
      state: stateFilter || undefined,
      district: districtFilter || undefined,
      village: villageFilter || undefined,
      basin: basinFilter || undefined,
      metric,
      method,
      horizon,
      band,
      transfer: transfer && method !== "linear",
    }),
    [stateFilter, districtFilter, villageFilter, basinFilter, metric, method, horizon, band, transfer]
  );

  const scopeParams = useMemo(
    () => ({
      state: stateFilter || undefined,
      district: districtFilter || undefined,
      village: villageFilter || undefined,
      basin: basinFilter || undefined,
      metric,
    }),
    [stateFilter, districtFilter, villageFilter, basinFilter, metric]
  );

  useEffect(() => {
    let active = true;
    fetchStates()
      .then((rows) => active && setStates(rows))
      .catch(() => undefined);
    fetchBasins()
      .then((rows) => active && setBasins(rows))
      .catch(() => undefined);
    fetchForecastMeta()
      .then((m) => active && setMeta(m))
      .catch(() => undefined);
    return () => {
      active = false;
    };
  }, []);

  useEffect(() => {
    if (!stateFilter || basinFilter) {
      setDistricts([]);
      setVillages([]);
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

  useEffect(() => {
    let active = true;
    setLoading(true);
    setError(null);
    setLastError(null);
    fetchForecast(filters)
      .then((data) => {
        if (active) setResult(data);
      })
      .catch((err) => {
        if (!active) return;
        setLastError(err);
        setError(getApiError(err));
      })
      .finally(() => active && setLoading(false));
    return () => {
      active = false;
    };
  }, [filters]);

  useEffect(() => {
    let active = true;
    setComparison(null);
    fetchModelComparison(scopeParams)
      .then((data) => active && setComparison(data))
      .catch(() => active && setComparison(null));
    return () => {
      active = false;
    };
  }, [scopeParams]);

  useEffect(() => {
    let active = true;
    setBacktest(null);
    fetchBacktest(scopeParams)
      .then((data) => active && setBacktest(data))
      .catch(() => active && setBacktest(null));
    return () => {
      active = false;
    };
  }, [scopeParams]);

  const combined =
    result &&
    [...result.historical, ...result.forecast].map((p) => ({
      year: p.year,
      value: p.value,
      upper: p.upper ?? null,
      lower: p.lower ?? null,
    }));

  const unitLabel = metric === "stage" ? "%" : result?.unit ?? "hm³";
  const isMl = result && ["lstm", "transformer", "ml"].includes(result.method);

  const statCards = [
    {
      label: t("Latest ({year})", { year: result?.historical.at(-1)?.year ?? "—" }),
      value: formatNumber(result?.historical.at(-1)?.value),
      hint: t("Observed value"),
    },
    {
      label: t("Projected {year}", { year: result?.forecast.at(-1)?.year ?? "—" }),
      value: formatNumber(result?.end_value),
      hint: t("End of forecast horizon"),
    },
    {
      label: t("Change"),
      value: result?.pct_change != null ? `${result.pct_change >= 0 ? "+" : ""}${result.pct_change.toFixed(1)}%` : "—",
      hint: t("Over the forecast horizon"),
    },
    {
      label: t("Annual trend"),
      value: result?.slope != null ? `${result.slope >= 0 ? "+" : ""}${result.slope.toFixed(2)}` : "—",
      hint: `${unitLabel} ${t("per year")} · ${t(result?.direction ?? "stable")}`,
    },
  ];

  const backtestRows = backtest?.evaluation
    ? (Object.entries(backtest.evaluation) as [string, { rmse: number | null; mae: number | null; mape: number | null; crps: number | null; skill: number | null; n: number }][])
    : [];

  return (
    <div className="mx-auto max-w-6xl space-y-6">
      <section className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="flex items-center gap-2 text-2xl font-bold">
            <BrainCircuit className="h-6 w-6 text-primary" />
            {t("Forecast")}
          </h2>
          <p className="mt-1 text-muted-foreground">
            {t(
              "Project groundwater metrics with time-series models — linear trend, moving average, exponential smoothing, ARIMA(1,1,0), Holt's trend, ensemble, auto-selection, or deep-learning LSTM/Transformer models."
            )}
          </p>
        </div>
        <div className="flex items-center gap-2">
          {mlAvailable && (
            <Badge variant="secondary">
              <Cpu className="mr-1 h-3 w-3" />
              {t("Deep learning ready")}
            </Badge>
          )}
          <Badge variant="warning">{t("Statistical projection · not official data")}</Badge>
        </div>
      </section>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <TrendingUp className="h-4 w-4" />
            {t("Forecast settings")}
          </CardTitle>
        </CardHeader>
        <CardContent className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
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
                  {b.name} ({b.district_count} {t("districts")})
                </option>
              ))}
            </Select>
          </div>
          <div className="space-y-1.5">
            <label className="text-sm font-medium">{t("state")}</label>
            <Select
              value={stateFilter}
              onChange={(e) => {
                setStateFilter(e.target.value);
                setDistrictFilter("");
                setVillageFilter("");
              }}
              disabled={!!basinFilter}
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
              disabled={!stateFilter || !!basinFilter}
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
              disabled={!districtFilter || !!basinFilter}
            >
              <option value="">{t("All villages")}</option>
              {villages.map((v) => (
                <option key={v.id} value={v.name}>
                  {v.name}
                </option>
              ))}
            </Select>
          </div>
          <div className="space-y-1.5">
            <label className="text-sm font-medium">{t("metric")}</label>
            <Select value={metric} onChange={(e) => setMetric(e.target.value as ForecastMetric)}>
              <option value="stage">{t("Stage of extraction")} (%)</option>
              <option value="recharge">{t("Recharge")} (hm³)</option>
              <option value="extraction">{t("Extraction")} (hm³)</option>
            </Select>
          </div>
          <div className="space-y-1.5">
            <label className="text-sm font-medium">{t("Model")}</label>
            <Select value={method} onChange={(e) => setMethod(e.target.value as ForecastMethod)}>
              {availableMethods.map((k) => (
                <option key={k} value={k}>
                  {t(METHOD_LABELS[k] ?? k)}
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
          <div className="space-y-1.5">
            <label className="text-sm font-medium">{t("Horizon (years)")}</label>
            <Select value={horizon} onChange={(e) => setHorizon(Number(e.target.value))}>
              {[3, 5, 10].map((h) => (
                <option key={h} value={h}>
                  {h}
                </option>
              ))}
            </Select>
          </div>
        </CardContent>
        {(["lstm", "transformer", "ml"] as ForecastMethod[]).includes(method) && (
          <CardContent className="border-t pt-4">
            <label className="flex items-center gap-2 text-sm">
              <input
                type="checkbox"
                checked={transfer}
                onChange={(e) => setTransfer(e.target.checked)}
                disabled={!districtFilter && !villageFilter && !basinFilter}
              />
              {t("Transfer learning — pre-train on the containing state/basin, then fine-tune this scope")}
            </label>
            {!mlAvailable && (
              <p className="mt-2 text-xs text-warning">
                {t(
                  "Deep-learning models need the optional torch dependency. Without it the forecast falls back to the best statistical model. Install with: pip install -r requirements-ml.txt"
                )}
              </p>
            )}
          </CardContent>
        )}
      </Card>

      {error && isNetworkError(lastError) ? (
        <IngresNetworkError detail={error} onRetry={() => window.location.reload()} />
      ) : error ? (
        <div className="rounded-md border border-destructive/30 bg-destructive/10 p-4 text-sm text-destructive">
          {error}
        </div>
      ) : null}

      {loading ? (
        <IngresLoader
          variant="inline"
          size="sm"
          message={t("Loading forecast…")}
          submessage="Projecting groundwater metrics"
        />
      ) : result ? (
        <>
          <section className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            {statCards.map((stat) => (
              <Card key={stat.label}>
                <CardHeader>
                  <CardDescription>{stat.label}</CardDescription>
                  <CardTitle className="text-3xl">{stat.value}</CardTitle>
                </CardHeader>
                <CardContent>
                  <p className="text-xs text-muted-foreground">{stat.hint}</p>
                </CardContent>
              </Card>
            ))}
          </section>

          <Card>
            <CardHeader className="flex-row items-start justify-between space-y-0">
              <div>
                <CardTitle>{t("Projected trend")}</CardTitle>
                <CardDescription>
                  {t("{scope} · {metric} · {method}", {
                    scope: result.scope,
                    metric: metric === "stage" ? t("Stage of extraction") : t(metric),
                    method: t(result.method_label ?? METHOD_LABELS[method]),
                  })}
                </CardDescription>
              </div>
              <div className="flex items-center gap-2">
                {isMl && (
                  <Badge variant="secondary">
                    <Cpu className="mr-1 h-3 w-3" />
                    {t("ML")}
                  </Badge>
                )}
                {result.risk && (
                  <Badge variant={RISK_VARIANT[result.risk] ?? "secondary"}>
                    {t("Projected category")}: {t(result.risk)}
                  </Badge>
                )}
              </div>
            </CardHeader>
            <CardContent>
              {combined ? (
                <ForecastChart
                  points={combined}
                  forecastFrom={result.forecast[0]?.year}
                  metric={metric}
                  formatValue={(v) =>
                    `${formatNumber(v, 1)}${metric === "stage" ? "%" : ""}`
                  }
                />
              ) : (
                <div className="text-sm text-muted-foreground">{t("No data.")}</div>
              )}
            </CardContent>
          </Card>

          {isMl && result.ml && (
            <Card>
              <CardContent className="flex flex-wrap items-center gap-3 pt-4 text-sm">
                <Cpu className="mt-0.5 h-4 w-4 shrink-0 text-primary" />
                <p className="flex flex-wrap items-center gap-2">
                  <span className="font-medium">{t("Deep-learning model")}:</span>
                  {result.ml.model ? t(result.ml.model) : t("LSTM")}
                  {result.ml.transfer && (
                    <Badge variant="secondary">
                      {t("Pre-trained on")} {result.ml.pretrained_scope ?? "pool"} · {t("fine-tuned")}
                    </Badge>
                  )}
                  {result.ml.epochs != null && (
                    <span className="text-muted-foreground">
                      {result.ml.epochs} {t("epochs")} · window {result.ml.window}
                    </span>
                  )}
                </p>
              </CardContent>
            </Card>
          )}

          {result.decomposition && (
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <Activity className="h-4 w-4" />
                  {t("Series decomposition")}
                </CardTitle>
                <CardDescription>
                  {t("Statistical character of the historical series that drives the projection.")}
                </CardDescription>
              </CardHeader>
              <CardContent>
                <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
                  {[
                    {
                      label: t("Trend / year"),
                      value: result.decomposition.trend_per_year != null
                        ? `${result.decomposition.trend_per_year >= 0 ? "+" : ""}${result.decomposition.trend_per_year.toFixed(2)}`
                        : "—",
                    },
                    {
                      label: t("Volatility"),
                      value: result.decomposition.volatility != null
                        ? result.decomposition.volatility.toFixed(2)
                        : "—",
                    },
                    {
                      label: t("Residual σ"),
                      value: result.decomposition.residual_std != null
                        ? result.decomposition.residual_std.toFixed(2)
                        : "—",
                    },
                    {
                      label: t("Acceleration"),
                      value: result.decomposition.acceleration != null
                        ? `${result.decomposition.acceleration >= 0 ? "+" : ""}${result.decomposition.acceleration.toFixed(3)}`
                        : "—",
                    },
                  ].map((cell) => (
                    <div key={cell.label} className="space-y-1">
                      <div className="text-xs text-muted-foreground">{cell.label}</div>
                      <div className="text-xl font-semibold">{cell.value}</div>
                    </div>
                  ))}
                </div>
                {result.decomposition.summary && (
                  <p className="mt-3 text-xs text-muted-foreground">{result.decomposition.summary}</p>
                )}
              </CardContent>
            </Card>
          )}

          {result.note && (
            <Card>
              <CardContent className="flex items-start gap-3 pt-4 text-sm">
                <BrainCircuit className="mt-0.5 h-4 w-4 shrink-0 text-primary" />
                <p>
                  <span className="font-medium">{t("Model explanation")}: </span>
                  {result.note}
                </p>
              </CardContent>
            </Card>
          )}

          {comparison?.evaluation && result.validation && (
            <Card>
              <CardHeader className="flex-row items-start justify-between space-y-0">
                <div>
                  <CardTitle>{t("Model comparison")}</CardTitle>
                  <CardDescription>
                    {t(
                      "Out-of-sample walk-forward validation scores (lower is better). {n} forecasts tested.",
                      { n: comparison.historical_points - 3 }
                    )}
                  </CardDescription>
                </div>
                {comparison.best && (
                  <Badge variant="success">
                    <CheckCircle2 className="mr-1 h-3 w-3" />
                    {t("Recommended")}: {t(METHOD_LABELS[comparison.best as ForecastMethod] ?? comparison.best)}
                  </Badge>
                )}
              </CardHeader>
              <CardContent>
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>{t("Model")}</TableHead>
                      <TableHead className="text-right">{t("RMSE")}</TableHead>
                      <TableHead className="text-right">{t("MAE")}</TableHead>
                      <TableHead className="text-right">{t("MAPE")}</TableHead>
                      <TableHead className="text-right">{t("Tests")}</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {ALL_METHODS.map((m) => {
                      const metrics = comparison.evaluation?.[m];
                      const isBest = comparison.best === m;
                      return (
                        <TableRow key={m} className={isBest ? "bg-success/10" : undefined}>
                          <TableCell className="font-medium">
                            {t(METHOD_LABELS[m])}
                            {isBest && (
                              <Badge variant="success" className="ml-2">
                                {t("best")}
                              </Badge>
                            )}
                          </TableCell>
                          <TableCell className="text-right">
                            {metrics?.rmse != null ? metrics.rmse.toFixed(3) : "—"}
                          </TableCell>
                          <TableCell className="text-right">
                            {metrics?.mae != null ? metrics.mae.toFixed(3) : "—"}
                          </TableCell>
                          <TableCell className="text-right">
                            {metrics?.mape != null ? `${metrics.mape.toFixed(2)}%` : "—"}
                          </TableCell>
                          <TableCell className="text-right">{metrics?.n ?? "—"}</TableCell>
                        </TableRow>
                      );
                    })}
                  </TableBody>
                </Table>
                {result.best_method && method !== "auto" && (
                  <p className="mt-3 text-xs text-muted-foreground">
                    {t(
                      "The best validated model for this scope is {method}. Switch the model dropdown to Auto to use it automatically.",
                      {
                        method: t(
                          METHOD_LABELS[result.best_method as ForecastMethod] ?? result.best_method
                        ),
                      }
                    )}
                  </p>
                )}
              </CardContent>
            </Card>
          )}

          {backtestRows.length > 0 && (
            <Card>
              <CardHeader>
                <CardTitle>{t("Backtest")}</CardTitle>
                <CardDescription>
                  {t(
                    "Chronological train/test split — forecast the held-out years with each model and compare (lower is better)."
                  )}
                  {backtest?.best && ` ${t("Best")}: ${t(METHOD_LABELS[backtest.best as ForecastMethod] ?? backtest.best)}`}
                </CardDescription>
              </CardHeader>
              <CardContent>
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>{t("Model")}</TableHead>
                      <TableHead className="text-right">{t("RMSE")}</TableHead>
                      <TableHead className="text-right">{t("MAE")}</TableHead>
                      <TableHead className="text-right">{t("CRPS")}</TableHead>
                      <TableHead className="text-right">{t("Skill")}</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {backtestRows.map(([m, metrics]) => (
                      <TableRow key={m}>
                        <TableCell className="font-medium">{t(METHOD_LABELS[m as ForecastMethod] ?? m)}</TableCell>
                        <TableCell className="text-right">{metrics.rmse != null ? metrics.rmse.toFixed(3) : "—"}</TableCell>
                        <TableCell className="text-right">{metrics.mae != null ? metrics.mae.toFixed(3) : "—"}</TableCell>
                        <TableCell className="text-right">{metrics.crps != null ? metrics.crps.toFixed(3) : "—"}</TableCell>
                        <TableCell className="text-right">
                          {metrics.skill != null ? `${(metrics.skill * 100).toFixed(1)}%` : "—"}
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </CardContent>
            </Card>
          )}

          {result.years_to_threshold && (
            <div className="flex items-start gap-3 rounded-md border border-warning/40 bg-warning/10 p-4 text-sm">
              <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-warning" />
              <p>
                {t(
                  "At the projected trend, {scope} crosses the over-exploited threshold (100% stage of extraction) in about {count} year(s).",
                  { scope: result.scope, count: result.years_to_threshold }
                )}
              </p>
            </div>
          )}

          <Card>
            <CardHeader>
              <CardTitle>{t("Forecast points")}</CardTitle>
              <CardDescription>
                {band === "bootstrap"
                  ? t("Point estimates with a bootstrap 5–95% confidence fan.")
                  : t("Point estimates with a 95% confidence band.")}
              </CardDescription>
            </CardHeader>
            <CardContent>
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>{t("year")}</TableHead>
                    <TableHead className="text-right">{t("Lower")}</TableHead>
                    <TableHead className="text-right">{t("Value")}</TableHead>
                    <TableHead className="text-right">{t("Upper")}</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {result.forecast.map((p) => (
                    <TableRow key={p.year}>
                      <TableCell className="font-medium">{p.year}</TableCell>
                      <TableCell className="text-right">{formatNumber(p.lower)}</TableCell>
                      <TableCell className="text-right">
                        {formatNumber(p.value)}
                        {metric === "stage" ? "%" : ""}
                      </TableCell>
                      <TableCell className="text-right">{formatNumber(p.upper)}</TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </CardContent>
          </Card>
        </>
      ) : (
        <div className="text-sm text-muted-foreground">{t("No data.")}</div>
      )}
    </div>
  );
}