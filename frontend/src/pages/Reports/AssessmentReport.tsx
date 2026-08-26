import { Download, FileText, Loader2 } from "lucide-react";
import { useEffect, useState } from "react";

import ForecastChart from "@/components/ForecastChart";
import LineChart from "@/components/LineChart";
import ReportMap from "@/components/ReportMap";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Select } from "@/components/ui/select";
import { useLanguage } from "@/contexts/LanguageContext";
import { fetchDistricts, fetchStates } from "@/services/groundwater";
import {
  downloadAssessmentPdf,
  downloadAssessmentXlsx,
  getAssessmentReport,
  type AssessmentReport,
} from "@/services/reports";
import type { GroundwaterDistrict, GroundwaterState } from "@/types";

const FROM_YEARS = [2017, 2018, 2019, 2020, 2021, 2022, 2023, 2024, 2025, 2026];
const TO_YEARS = [2023, 2024, 2025, 2026, 2027, 2028, 2029, 2030, 2031, 2032, 2033, 2034, 2035];

const CATEGORY_COLORS: Record<string, string> = {
  safe: "#16a34a",
  "semi-critical": "#eab308",
  critical: "#f97316",
  "over-exploited": "#dc2626",
};

const RISK_BADGE: Record<string, string> = {
  Low: "bg-green-100 text-green-800",
  Medium: "bg-amber-100 text-amber-800",
  High: "bg-orange-100 text-orange-800",
  Critical: "bg-red-100 text-red-800",
};

function formatNumber(value: number | null | undefined, digits = 1): string {
  if (value === null || value === undefined) return "—";
  return new Intl.NumberFormat("en-IN", { maximumFractionDigits: digits }).format(value);
}

export default function AssessmentReport() {
  const { t } = useLanguage();
  const [states, setStates] = useState<GroundwaterState[]>([]);
  const [districts, setDistricts] = useState<GroundwaterDistrict[]>([]);
  const [state, setState] = useState("");
  const [district, setDistrict] = useState("");
  const [yearFrom, setYearFrom] = useState("2020");
  const [yearTo, setYearTo] = useState("2030");
  const [report, setReport] = useState<AssessmentReport | null>(null);
  const [loading, setLoading] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchStates()
      .then(setStates)
      .catch(() => undefined);
  }, []);

  useEffect(() => {
    setDistrict("");
    if (!state) {
      setDistricts([]);
      return;
    }
    let active = true;
    fetchDistricts(state)
      .then((rows) => active && setDistricts(rows))
      .catch(() => active && setDistricts([]));
    return () => {
      active = false;
    };
  }, [state]);

  async function generate() {
    setLoading(true);
    setError(null);
    try {
      setReport(
        await getAssessmentReport({
          state: state || undefined,
          district: district || undefined,
          year_from: yearFrom ? Number(yearFrom) : undefined,
          year_to: yearTo ? Number(yearTo) : undefined,
        })
      );
    } catch {
      setError(t("Failed to generate the assessment report."));
    } finally {
      setLoading(false);
    }
  }

  async function handleDownloadPdf() {
    setBusy(true);
    try {
      await downloadAssessmentPdf({
        state: state || undefined,
        district: district || undefined,
        year_from: yearFrom ? Number(yearFrom) : undefined,
        year_to: yearTo ? Number(yearTo) : undefined,
      });
    } finally {
      setBusy(false);
    }
  }

  async function handleDownloadXlsx() {
    setBusy(true);
    try {
      await downloadAssessmentXlsx({
        state: state || undefined,
        district: district || undefined,
        year_from: yearFrom ? Number(yearFrom) : undefined,
        year_to: yearTo ? Number(yearTo) : undefined,
      });
    } finally {
      setBusy(false);
    }
  }

  const trendPoints = (report?.trend.series ?? []).map((s) => ({
    label: String(s.year),
    value: s.stage,
  }));
  const predPoints = report
    ? [
        ...report.prediction.historical
          .filter((p) => p.year >= report.period.from)
          .map((p) => ({ year: p.year, value: p.value, upper: null, lower: null })),
        ...report.prediction.forecast,
      ]
    : [];
  const forecastFrom = report?.prediction.forecast[0]?.year;

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader>
          <CardTitle className="text-sm">{t("generate")}</CardTitle>
          <CardDescription>
            {t(
              "Generate an AI-written report for a state, district and period, with status, trend, prediction, risk, map, graphs, recommendations and data sources, exportable as PDF or Excel."
            )}
          </CardDescription>
        </CardHeader>
        <CardContent className="flex flex-wrap items-end gap-4">
          <div className="space-y-1.5">
            <label className="text-sm font-medium">{t("state")}</label>
            <Select
              value={state}
              onChange={(e) => setState(e.target.value)}
              className="min-w-44"
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
              value={district}
              onChange={(e) => setDistrict(e.target.value)}
              disabled={!state}
              className="min-w-44"
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
            <label className="text-sm font-medium">{t("Period from")}</label>
            <Select value={yearFrom} onChange={(e) => setYearFrom(e.target.value)}>
              {FROM_YEARS.map((y) => (
                <option key={y} value={y}>
                  {y}
                </option>
              ))}
            </Select>
          </div>
          <div className="space-y-1.5">
            <label className="text-sm font-medium">{t("Period to")}</label>
            <Select value={yearTo} onChange={(e) => setYearTo(e.target.value)}>
              {TO_YEARS.map((y) => (
                <option key={y} value={y}>
                  {y}
                </option>
              ))}
            </Select>
          </div>
          <Button onClick={generate} disabled={loading}>
            {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : <FileText className="h-4 w-4" />}
            {t("Generate report")}
          </Button>
        </CardContent>
      </Card>

      {error && (
        <div className="rounded-md border border-destructive/30 bg-destructive/10 p-4 text-sm text-destructive">
          {error}
        </div>
      )}

      {loading && (
        <div className="flex items-center justify-center gap-2 py-16 text-sm text-muted-foreground">
          <Loader2 className="h-4 w-4 animate-spin" />
          {t("Generating assessment report…")}
        </div>
      )}

      {!report && !loading && !error && (
        <Card>
          <CardContent className="py-12 text-center text-sm text-muted-foreground">
            {t("No report yet. Choose a scope and period, then click Generate report.")}
          </CardContent>
        </Card>
      )}

      {report && (
        <>
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div className="flex items-center gap-2">
              <h3 className="text-lg font-semibold">{report.scope.display}</h3>
            </div>
            <div className="flex flex-wrap gap-2">
              <Button variant="outline" onClick={handleDownloadXlsx} disabled={busy}>
                {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <Download className="h-4 w-4" />}
                {t("Download Excel")}
              </Button>
              <Button onClick={handleDownloadPdf} disabled={busy}>
                {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <Download className="h-4 w-4" />}
                {t("Download PDF")}
              </Button>
            </div>
          </div>

          <Card>
            <CardHeader>
              <CardTitle className="text-sm">{t("Executive summary")}</CardTitle>
              <CardDescription>
                {report.scope.display} · {report.period.from}–{report.period.to} ·{" "}
                {t("latest data {year}", { year: report.period.latest })}
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-3 text-sm">
              {report.executive_summary.map((line, i) => (
                <p key={i} className="leading-relaxed">
                  {line}
                </p>
              ))}
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle className="text-sm">{t("Groundwater status")}</CardTitle>
            </CardHeader>
            <CardContent className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
              <div>
                <p className="text-sm text-muted-foreground">{t("units")}</p>
                <p className="text-2xl font-semibold">{report.status.assessment_units}</p>
              </div>
              <div>
                <p className="text-sm text-muted-foreground">{t("recharge")} (hm³)</p>
                <p className="text-2xl font-semibold">{formatNumber(report.status.recharge)}</p>
              </div>
              <div>
                <p className="text-sm text-muted-foreground">{t("extraction")} (hm³)</p>
                <p className="text-2xl font-semibold">{formatNumber(report.status.extraction)}</p>
              </div>
              <div>
                <p className="text-sm text-muted-foreground">{t("stage_of_extraction")}</p>
                <p className="text-2xl font-semibold">
                  {formatNumber(report.status.stage)}% · {report.status.category}
                </p>
              </div>
            </CardContent>
          </Card>

          <div className="grid gap-4 lg:grid-cols-2">
            <Card>
              <CardHeader>
                <CardTitle className="text-sm">{t("Historical trend")}</CardTitle>
                <CardDescription>
                  {t("Stage of extraction, {from}–{latest}", {
                    from: report.period.from,
                    latest: report.period.latest,
                  })}
                </CardDescription>
              </CardHeader>
              <CardContent>
                <LineChart
                  data={trendPoints}
                  formatValue={(v) => `${v.toFixed(1)}%`}
                  height={230}
                />
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle className="text-sm">{t("Prediction")}</CardTitle>
                <CardDescription>
                  {report.prediction.method_label ?? report.prediction.method} ·{" "}
                  {report.prediction.direction} ·{" "}
                  {report.prediction.r2 !== null && `R² ${report.prediction.r2.toFixed(3)} · `}
                  {t("to {year}", { year: report.prediction.end_year })}
                </CardDescription>
              </CardHeader>
              <CardContent>
                <ForecastChart
                  points={predPoints}
                  forecastFrom={forecastFrom}
                  metric="stage"
                  formatValue={(v) => `${v.toFixed(1)}%`}
                  height={230}
                />
              </CardContent>
            </Card>
          </div>

          <Card>
            <CardHeader>
              <CardTitle className="text-sm">{t("Risk analysis")}</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="flex flex-wrap items-center gap-2 text-sm">
                <span
                  className={`rounded-full px-3 py-1 text-xs font-semibold ${
                    RISK_BADGE[report.risk.level] ?? "bg-slate-100 text-slate-700"
                  }`}
                >
                  {t("Risk")}: {report.risk.level}
                </span>
                <span className="text-muted-foreground">
                  {t("Current")}: {report.risk.current_category} ({report.risk.current}) →{" "}
                  {t("Projected")}: {report.risk.predicted_category} ({report.risk.predicted})
                </span>
              </div>
              <p className="text-sm leading-relaxed text-muted-foreground">{report.risk.summary}</p>
            </CardContent>
          </Card>

          <div className="grid gap-4 lg:grid-cols-3">
            <Card className="lg:col-span-2">
              <CardHeader>
                <CardTitle className="text-sm">{t("Map")}</CardTitle>
              </CardHeader>
              <CardContent>
                <ReportMap
                  features={report.map.features}
                  title={`${report.scope.display} — ${t("status {year}", { year: report.map.meta.year })}`}
                />
              </CardContent>
            </Card>
            <Card>
              <CardHeader>
                <CardTitle className="text-sm">{t("Legend")}</CardTitle>
              </CardHeader>
              <CardContent className="space-y-2 text-sm">
                {[
                  ["safe", "Safe (<70%)"],
                  ["semi-critical", "Semi-critical (70–90%)"],
                  ["critical", "Critical (90–100%)"],
                  ["over-exploited", "Over-exploited (>100%)"],
                ].map(([key, label]) => (
                  <div key={key} className="flex items-center gap-2">
                    <span className="h-3 w-3 rounded-sm" style={{ backgroundColor: CATEGORY_COLORS[key] }} />
                    <span className="text-muted-foreground">{t(label)}</span>
                  </div>
                ))}
              </CardContent>
            </Card>
          </div>

          <Card>
            <CardHeader>
              <CardTitle className="text-sm">{t("Recommendations")}</CardTitle>
            </CardHeader>
            <CardContent>
              <ul className="space-y-2 text-sm">
                {report.recommendations.map((r, i) => (
                  <li key={i} className="flex gap-2">
                    <span className="text-primary">•</span>
                    <span>{r}</span>
                  </li>
                ))}
              </ul>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle className="text-sm">{t("Data sources")}</CardTitle>
            </CardHeader>
            <CardContent>
              <ul className="space-y-2 text-sm text-muted-foreground">
                {report.sources.map((s, i) => (
                  <li key={i} className="flex gap-2">
                    <span className="text-primary">•</span>
                    <span>{s}</span>
                  </li>
                ))}
              </ul>
            </CardContent>
          </Card>
        </>
      )}
    </div>
  );
}