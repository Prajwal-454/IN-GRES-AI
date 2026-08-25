import { Download, FileDown, Loader2 } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
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
import {
  fetchDistricts,
  fetchStates,
  fetchVillages,
} from "@/services/groundwater";
import {
  downloadPdf,
  downloadReport,
  getReportData,
  type ReportData,
} from "@/services/reports";
import type { GroundwaterDistrict, GroundwaterState, GroundwaterVillage } from "@/types";

import AssessmentReport from "./AssessmentReport";
import ScheduledReports from "./ScheduledReports";

function formatNumber(value: number | null | undefined, digits = 1): string {
  if (value === null || value === undefined) return "—";
  return new Intl.NumberFormat("en-IN", { maximumFractionDigits: digits }).format(value);
}

const YEAR_OPTIONS = [2017, 2018, 2019, 2020, 2021, 2022];

export default function Reports() {
  const { t } = useLanguage();
  const [states, setStates] = useState<GroundwaterState[]>([]);
  const [districts, setDistricts] = useState<GroundwaterDistrict[]>([]);
  const [villages, setVillages] = useState<GroundwaterVillage[]>([]);
  const [state, setState] = useState("");
  const [district, setDistrict] = useState("");
  const [village, setVillage] = useState("");
  const [year, setYear] = useState("");
  const reportType = "assessment";
  const [mode, setMode] = useState<"data" | "assessment" | "schedules">("data");
  const [data, setData] = useState<ReportData | null>(null);
  const [loading, setLoading] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchStates()
      .then(setStates)
      .catch(() => undefined);
  }, []);

  useEffect(() => {
    if (!state) {
      setDistricts([]);
      setVillages([]);
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

  useEffect(() => {
    if (!state || !district) {
      setVillages([]);
      return;
    }
    let active = true;
    fetchVillages(state, district)
      .then((rows) => active && setVillages(rows))
      .catch(() => active && setVillages([]));
    return () => {
      active = false;
    };
  }, [state, district]);

  const params = useMemo(
    () => ({
      state: state || undefined,
      district: district || undefined,
      village: village || undefined,
      year: year ? Number(year) : undefined,
    }),
    [state, district, village, year]
  );

  async function generate() {
    setLoading(true);
    setError(null);
    try {
      setData(await getReportData(params));
    } catch {
      setError(t("Failed to generate the report."));
    } finally {
      setLoading(false);
    }
  }

  async function handleDownload() {
    setBusy(true);
    try {
      await downloadReport(reportType, params);
    } finally {
      setBusy(false);
    }
  }

  const summary = data?.summary;

  return (
    <div className="mx-auto max-w-6xl space-y-6">
      <section className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="flex items-center gap-2 text-2xl font-bold">
            <FileDown className="h-6 w-6 text-primary" />
            {t("nav_reports")}
          </h2>
          <p className="mt-1 text-muted-foreground">
            {t(
              "Generate and export groundwater reports (CSV / PDF / Excel) from the demo dataset."
            )}
          </p>
        </div>
        <div className="flex items-center gap-3">
          {summary?.is_demo && <Badge variant="warning">{t("demo_data")}</Badge>}
          <div className="flex overflow-hidden rounded-md border">
            <button
              type="button"
              onClick={() => setMode("data")}
              className={`px-3 py-1.5 text-sm ${
                mode === "data"
                  ? "bg-primary text-primary-foreground"
                  : "bg-background text-muted-foreground hover:bg-accent"
              }`}
            >
              {t("Data report")}
            </button>
            <button
              type="button"
              onClick={() => setMode("assessment")}
              className={`px-3 py-1.5 text-sm ${
                mode === "assessment"
                  ? "bg-primary text-primary-foreground"
                  : "bg-background text-muted-foreground hover:bg-accent"
              }`}
            >
              {t("Assessment report")}
            </button>
            <button
              type="button"
              onClick={() => setMode("schedules")}
              className={`px-3 py-1.5 text-sm ${
                mode === "schedules"
                  ? "bg-primary text-primary-foreground"
                  : "bg-background text-muted-foreground hover:bg-accent"
              }`}
            >
              {t("Scheduled reports")}
            </button>
          </div>
        </div>
      </section>

      {mode === "assessment" ? (
        <AssessmentReport />
      ) : mode === "schedules" ? (
        <ScheduledReports />
      ) : (
        <>

      <Card>
        <CardHeader>
          <CardTitle className="text-sm">{t("generate")}</CardTitle>
        </CardHeader>
        <CardContent className="flex flex-wrap items-end gap-4">
          <div className="space-y-1.5">
            <label className="text-sm font-medium">{t("state")}</label>
            <Select
              value={state}
              onChange={(e) => {
                setState(e.target.value);
                setDistrict("");
                setVillage("");
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
              value={district}
              onChange={(e) => {
                setDistrict(e.target.value);
                setVillage("");
              }}
              disabled={!state}
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
              value={village}
              onChange={(e) => setVillage(e.target.value)}
              disabled={!district}
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
            <label className="text-sm font-medium">{t("year")}</label>
            <Select value={year} onChange={(e) => setYear(e.target.value)}>
              <option value="">{t("all_years")}</option>
              {YEAR_OPTIONS.map((y) => (
                <option key={y} value={y}>
                  {y}
                </option>
              ))}
            </Select>
          </div>
          <Button onClick={generate} disabled={loading}>
            {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : <FileDown className="h-4 w-4" />}
            {t("generate")}
          </Button>
        </CardContent>
      </Card>

      {error && (
        <div className="rounded-md border border-destructive/30 bg-destructive/10 p-4 text-sm text-destructive">
          {error}
        </div>
      )}

      {summary && (
        <>
          <section className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <Card>
              <CardHeader>
                <CardDescription>{t("units")}</CardDescription>
                <CardTitle className="text-3xl">{summary.assessment_units}</CardTitle>
              </CardHeader>
            </Card>
            <Card>
              <CardHeader>
                <CardDescription>{t("recharge")}</CardDescription>
                <CardTitle className="text-3xl">{formatNumber(summary.total_recharge)}</CardTitle>
              </CardHeader>
            </Card>
            <Card>
              <CardHeader>
                <CardDescription>{t("extraction")}</CardDescription>
                <CardTitle className="text-3xl">{formatNumber(summary.total_extraction)}</CardTitle>
              </CardHeader>
            </Card>
            <Card>
              <CardHeader>
                <CardDescription>{t("stage_of_extraction")}</CardDescription>
                <CardTitle className="text-3xl">
                  {summary.average_stage_of_extraction != null
                    ? `${summary.average_stage_of_extraction.toFixed(1)}%`
                    : "—"}
                </CardTitle>
              </CardHeader>
            </Card>
          </section>

          <div className="flex flex-wrap gap-2">
            <Button onClick={handleDownload} disabled={busy}>
              {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <Download className="h-4 w-4" />}
              {t("download_csv")}
            </Button>
            <Button
              variant="outline"
              onClick={async () => {
                setBusy(true);
                try {
                  await downloadPdf(params);
                } finally {
                  setBusy(false);
                }
              }}
              disabled={busy}
            >
              {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <Download className="h-4 w-4" />}
              {t("download_pdf")}
            </Button>
          </div>

          <Card>
            <CardHeader>
              <CardTitle>{t("Assessment unit detail")}</CardTitle>
              <CardDescription>
                {t("{count} records", { count: data?.count ?? 0 })} ·{" "}
                {reportType === "assessment"
                  ? t("all metrics")
                  : t("{type} only", { type: reportType })}{" "}
                · {state || t("both demo states")}
                {district ? ` · ${district}` : ""}
                {village ? ` · ${village}` : ""}
              </CardDescription>
            </CardHeader>
            <CardContent>
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>{t("Unit")}</TableHead>
                    <TableHead>{t("district")}</TableHead>
                    <TableHead>{t("year")}</TableHead>
                    <TableHead className="text-right">{t("recharge")}</TableHead>
                    <TableHead className="text-right">{t("extraction")}</TableHead>
                    <TableHead className="text-right">{t("SoE %")}</TableHead>
                    <TableHead>{t("category")}</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {(data?.rows ?? []).slice(0, 50).map((r) => (
                    <TableRow key={r.id}>
                      <TableCell className="font-medium">{r.assessment_unit}</TableCell>
                      <TableCell>{r.district || "—"}</TableCell>
                      <TableCell>{r.assessment_year}</TableCell>
                      <TableCell className="text-right">{formatNumber(r.recharge_total)}</TableCell>
                      <TableCell className="text-right">{formatNumber(r.extraction_total)}</TableCell>
                      <TableCell className="text-right">
                        {r.stage_of_extraction != null ? `${r.stage_of_extraction.toFixed(1)}%` : "—"}
                      </TableCell>
                      <TableCell>{r.category ?? "—"}</TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </CardContent>
          </Card>
        </>
      )}

      {!summary && !loading && !error && (
        <Card>
          <CardContent className="py-12 text-center text-sm text-muted-foreground">
            {t("Choose a scope and click Generate to preview a report.")}
          </CardContent>
        </Card>
      )}
        </>
      )}
    </div>
  );
}