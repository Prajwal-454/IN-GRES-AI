import {
  Activity,
  AlertTriangle,
  Bot,
  ClipboardCheck,
  Database,
  Download,
  FileUp,
  LayoutDashboard,
  LineChart,
  Loader2,
  MessageSquareText,
  Plus,
  RefreshCw,
  ScrollText,
  ShieldCheck,
  UserPlus,
  Users as UsersIcon,
} from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";
import { Navigate } from "react-router-dom";

import IngresMap from "@/components/IngresMap";
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
import { useAuth } from "@/contexts/AuthContext";
import { useLanguage } from "@/contexts/LanguageContext";
import { useNotifications } from "@/contexts/NotificationContext";
import {
  createUser,
  getOverview,
  getModelMetrics,
  getQualityFlags,
  getQualitySummary,
  getQueryMonitor,
  listAuditLogs,
  listDatasets,
  listUsers,
  reviewFlag,
  runQualityScan,
  updateUser,
  type AdminOverview,
  type AdminUser,
  type AnomalyFlag,
  type AuditLog,
  type DatasetInfo,
  type FlagStatus,
  type ModelMetrics,
  type QualitySummary,
  type QueryMonitorRow,
} from "@/services/admin";
import {
  downloadImportTemplate,
  importDataset,
  triggerBlobDownload,
} from "@/services/imports";
import { getRagStatus, reindexRag, type RagStatus } from "@/services/rag";

const ROLE_OPTIONS = ["admin", "expert", "user"];

type TabKey =
  | "overview"
  | "data"
  | "quality"
  | "ai"
  | "models"
  | "queries"
  | "users"
  | "audit";

const TABS: { key: TabKey; labelKey: string }[] = [
  { key: "overview", labelKey: "Overview" },
  { key: "data", labelKey: "Data" },
  { key: "quality", labelKey: "Data Quality" },
  { key: "ai", labelKey: "AI / RAG" },
  { key: "models", labelKey: "Models" },
  { key: "queries", labelKey: "Queries" },
  { key: "users", labelKey: "Users" },
  { key: "audit", labelKey: "Audit" },
];

function tabIcon(key: TabKey) {
  const cls = "h-4 w-4";
  switch (key) {
    case "overview":
      return <LayoutDashboard className={cls} />;
    case "data":
      return <Database className={cls} />;
    case "quality":
      return <ClipboardCheck className={cls} />;
    case "ai":
      return <Bot className={cls} />;
    case "models":
      return <LineChart className={cls} />;
    case "queries":
      return <MessageSquareText className={cls} />;
    case "users":
      return <UsersIcon className={cls} />;
    case "audit":
      return <ScrollText className={cls} />;
  }
}

function StatCard({
  label,
  value,
  sub,
  accent,
}: {
  label: string;
  value: string;
  sub?: string;
  accent?: boolean;
}) {
  return (
    <div
      className={
        accent
          ? "rounded-xl border bg-primary/5 p-4"
          : "rounded-xl border bg-card p-4"
      }
    >
      <div className="text-[11px] uppercase tracking-wide text-muted-foreground">
        {label}
      </div>
      <div className="mt-1 text-2xl font-bold leading-tight">{value}</div>
      {sub && <div className="mt-0.5 text-[11px] text-muted-foreground">{sub}</div>}
    </div>
  );
}

const SEVERITY_DOT: Record<string, string> = {
  critical: "bg-red-500",
  warning: "bg-amber-500",
  ok: "bg-emerald-500",
  unknown: "bg-slate-400",
};

const INTENT_LABELS: Record<string, string> = {
  data_query: "Data",
  forecast: "Forecast",
  scenario: "Scenario",
  recommend: "Recommendation",
  terminology: "Terminology",
  knowledge: "Knowledge",
  conversational: "Conversational",
  greeting: "Greeting",
  thanks: "Thanks",
  help: "Help",
  fallback: "Unclear",
  unknown: "Unknown",
};

const LANG_LABELS: Record<string, string> = { en: "EN", te: "TE", hi: "HI" };

function fmtNum(n: number | null | undefined): string {
  if (n === null || n === undefined) return "—";
  return new Intl.NumberFormat("en-IN").format(n);
}

export default function Admin() {
  const { user } = useAuth();
  const { toast } = useNotifications();
  const { t } = useLanguage();
  const [tab, setTab] = useState<TabKey>("overview");
  const [users, setUsers] = useState<AdminUser[]>([]);
  const [logs, setLogs] = useState<AuditLog[]>([]);
  const [datasets, setDatasets] = useState<DatasetInfo[]>([]);
  const [overview, setOverview] = useState<AdminOverview | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [email, setEmail] = useState("");
  const [fullName, setFullName] = useState("");
  const [password, setPassword] = useState("");
  const [role, setRole] = useState("user");
  const [creating, setCreating] = useState(false);

  const [rag, setRag] = useState<RagStatus | null>(null);
  const [reindexing, setReindexing] = useState(false);

  const [importName, setImportName] = useState("");
  const [importSource, setImportSource] = useState("");
  const [importFile, setImportFile] = useState<File | null>(null);
  const [importing, setImporting] = useState(false);
  const [importResult, setImportResult] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  // Models tab
  const [modelMetrics, setModelMetrics] = useState<ModelMetrics | null>(null);
  const [loadingModels, setLoadingModels] = useState(false);
  const [metricsState, setMetricsState] = useState("Telangana");
  const [metricsMetric, setMetricsMetric] = useState("stage");

  // Queries tab
  const [queryRows, setQueryRows] = useState<QueryMonitorRow[] | null>(null);
  const [loadingQueries, setLoadingQueries] = useState(false);

  // Data Quality tab
  const [qualitySummary, setQualitySummary] = useState<QualitySummary | null>(null);
  const [qualityFlags, setQualityFlags] = useState<AnomalyFlag[] | null>(null);
  const [qualityStatusFilter, setQualityStatusFilter] = useState<FlagStatus | "all">("open");
  const [loadingQuality, setLoadingQuality] = useState(false);
  const [scanningQuality, setScanningQuality] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [u, l, d, o] = await Promise.all([
        listUsers(),
        listAuditLogs(),
        listDatasets(),
        getOverview().catch(() => null),
      ]);
      setUsers(u);
      setLogs(l);
      setDatasets(d);
      setOverview(o);
    } catch {
      setError(t("Failed to load admin data (admin role required)."));
    } finally {
      setLoading(false);
    }
  }, []);

  const loadRag = useCallback(async () => {
    try {
      setRag(await getRagStatus());
    } catch {
      /* ignore */
    }
  }, []);

  const loadModels = useCallback(
    async (state: string, metric: string) => {
      setLoadingModels(true);
      try {
        setModelMetrics(await getModelMetrics(state, metric));
      } catch {
        setModelMetrics(null);
      } finally {
        setLoadingModels(false);
      }
    },
    []
  );

  const loadQueries = useCallback(async () => {
    setLoadingQueries(true);
    try {
      setQueryRows(await getQueryMonitor(50));
    } catch {
      setQueryRows([]);
    } finally {
      setLoadingQueries(false);
    }
  }, []);

  const loadQuality = useCallback(
    async (status: FlagStatus | "all" = qualityStatusFilter) => {
      setLoadingQuality(true);
      try {
        const [summary, list] = await Promise.all([
          getQualitySummary(),
          getQualityFlags({ status, limit: 200 }),
        ]);
        setQualitySummary(summary);
        setQualityFlags(list.flags);
      } catch {
        setQualityFlags([]);
      } finally {
        setLoadingQuality(false);
      }
    },
    [qualityStatusFilter]
  );

  const scanQuality = useCallback(async () => {
    setScanningQuality(true);
    try {
      const res = await runQualityScan();
      toast(
        t("Anomaly scan finished: {count} new issue(s) found.", { count: res.created }),
        res.created > 0 ? "info" : "success"
      );
      await loadQuality();
    } catch {
      toast(t("Failed to run the anomaly scan."), "error");
    } finally {
      setScanningQuality(false);
    }
  }, [loadQuality, t, toast]);

  const handleReviewFlag = useCallback(
    async (id: number, status: FlagStatus) => {
      try {
        await reviewFlag(id, { status });
        setQualityFlags((prev) =>
          (prev ?? []).map((f) => (f.id === id ? { ...f, status } : f))
        );
        getQualitySummary()
          .then(setQualitySummary)
          .catch(() => undefined);
      } catch {
        toast(t("Failed to update the flag."), "error");
      }
    },
    [t, toast]
  );

  useEffect(() => {
    if (user?.role !== "admin") return;
    load();
    loadRag();
  }, [load, loadRag, user?.role]);

  useEffect(() => {
    if (user?.role !== "admin") return;
    if (tab === "queries" && queryRows === null && !loadingQueries) {
      void loadQueries();
    }
    if (tab === "models" && modelMetrics === null && !loadingModels) {
      void loadModels(metricsState, metricsMetric);
    }
    if (tab === "quality" && qualityFlags === null && !loadingQuality) {
      void loadQuality();
    }
  }, [
    tab,
    user?.role,
    queryRows,
    loadingQueries,
    modelMetrics,
    loadingModels,
    metricsState,
    metricsMetric,
    qualityFlags,
    loadingQuality,
    loadQueries,
    loadModels,
    loadQuality,
  ]);

  if (user?.role !== "admin") {
    return <Navigate to="/dashboard" replace />;
  }

  async function handleCreate() {
    if (!email.trim() || !password.trim()) return;
    setCreating(true);
    try {
      await createUser({
        email: email.trim(),
        full_name: fullName.trim() || email.trim(),
        password,
        role,
      });
      setEmail("");
      setFullName("");
      setPassword("");
      setRole("user");
      await load();
    } catch {
      setError(t("Failed to create user."));
    } finally {
      setCreating(false);
    }
  }

  async function handleToggle(id: number, is_active: boolean) {
    try {
      await updateUser(id, { is_active });
      await load();
    } catch {
      setError(t("Failed to update user."));
    }
  }

  async function handleRole(id: number, nextRole: string) {
    try {
      await updateUser(id, { role: nextRole });
      await load();
    } catch {
      setError(t("Failed to update role."));
    }
  }

  async function handleDownloadTemplate() {
    try {
      const blob = await downloadImportTemplate();
      triggerBlobDownload(blob, "ingres-import-template.csv");
    } catch {
      toast(t("Could not download the import template."), "error");
    }
  }

  async function handleImport() {
    if (!importFile) return;
    setImporting(true);
    setImportResult(null);
    try {
      const res = await importDataset(importFile, {
        name: importName.trim() || undefined,
        source: importSource.trim() || undefined,
      });
      setImportResult(
        t(
          "{rows} row(s) imported ({parsed} parsed). {states} state(s), {districts} district(s), {units} unit(s) created.",
          {
            rows: res.rows_imported,
            parsed: res.rows_parsed,
            states: res.states_created.length,
            districts: res.districts_created.length,
            units: res.units_created.length,
          }
        ) +
          (res.alerts_triggered
            ? ` ${t("{alerts} alert(s) triggered.", { alerts: res.alerts_triggered })}`
            : "")
      );
      toast(t("Dataset imported successfully."), "success");
      setImportFile(null);
      if (fileInputRef.current) fileInputRef.current.value = "";
      await Promise.all([load(), loadRag()]);
    } catch (err) {
      const detail = (err as { response?: { data?: { detail?: { errors?: string[] } } } })
        ?.response?.data?.detail;
      const message = detail?.errors?.slice(0, 5).join(" ") ?? t("Failed to import dataset.");
      setImportResult(message);
      toast(t("Import failed. See the message below."), "error");
    } finally {
      setImporting(false);
    }
  }

  async function handleReindex() {
    setReindexing(true);
    try {
      const res = await reindexRag();
      toast(t("Re-embedded {updated} knowledge chunks.", { updated: res.updated }), "success");
      await loadRag();
    } catch {
      toast(t("Could not re-index embeddings."), "error");
    } finally {
      setReindexing(false);
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center gap-2 py-16 text-sm text-muted-foreground">
        <Loader2 className="h-4 w-4 animate-spin" />
        {t("Loading admin panel…")}
      </div>
    );
  }

  const gw = overview?.groundwater;
  const intentEntries = Object.entries(overview?.queries.intent_counts ?? {}).sort(
    (a, b) => b[1] - a[1]
  );
  const maxIntent = Math.max(1, ...intentEntries.map(([, n]) => n));

  return (
    <div className="mx-auto max-w-7xl space-y-6">
      <section>
        <h2 className="flex items-center gap-2 text-2xl font-bold">
          <ShieldCheck className="h-6 w-6 text-primary" />
          {t("Groundwater Command Center")}
        </h2>
        <p className="mt-1 text-muted-foreground">
          {t("Data, AI/RAG, models, queries, users and system health — at a glance.")}
        </p>
      </section>

      {/* Tabs */}
      <div className="flex flex-wrap gap-1.5 rounded-xl border bg-card p-1.5">
        {TABS.map((tb) => (
          <button
            key={tb.key}
            onClick={() => setTab(tb.key)}
            className={
              tab === tb.key
                ? "inline-flex items-center gap-1.5 rounded-lg bg-primary px-3 py-1.5 text-sm font-medium text-primary-foreground"
                : "inline-flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-sm font-medium text-muted-foreground transition-colors hover:bg-accent hover:text-foreground"
            }
          >
            {tabIcon(tb.key)}
            {t(tb.labelKey)}
          </button>
        ))}
      </div>

      {error && (
        <div className="rounded-md border border-destructive/30 bg-destructive/10 p-4 text-sm text-destructive">
          {error}
        </div>
      )}

      {/* ------------------------------------------------ Overview */}
      {tab === "overview" && (
        <div className="space-y-6">
          <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
            <StatCard
              label={t("Assessment units")}
              value={fmtNum(gw?.assessment_units)}
              sub={`${fmtNum(gw?.total_units_registered)} ${t("registered")}`}
              accent
            />
            <StatCard
              label={t("Total recharge")}
              value={`${fmtNum(gw?.recharge_hm3)}`}
              sub="hm³"
            />
            <StatCard
              label={t("Total extraction")}
              value={`${fmtNum(gw?.extraction_hm3)}`}
              sub="hm³"
            />
            <StatCard
              label={t("Avg stage of extraction")}
              value={gw ? `${gw.avg_stage_pct}%` : "—"}
              sub={t("Year {year}", { year: gw?.latest_year ?? "—" })}
            />
            <StatCard
              label={t("Alerts triggered (7d)")}
              value={fmtNum(overview?.alerts.triggered_last_7d)}
              sub={`${fmtNum(overview?.alerts.enabled_rules)} ${t("active rules")}`}
            />
            <StatCard
              label={t("Assistant answers")}
              value={fmtNum(overview?.queries.assistant_answers)}
              sub={`${fmtNum(overview?.queries.conversations)} ${t("conversations")}`}
            />
            <StatCard
              label={t("Knowledge chunks")}
              value={fmtNum(overview?.ai.rag_chunks)}
              sub={`${fmtNum(overview?.ai.rag_documents)} ${t("documents")}`}
            />
            <StatCard
              label={t("Users")}
              value={fmtNum(overview?.users.total)}
              sub={`${fmtNum(overview?.users.active)} ${t("active")}`}
            />
          </div>

          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm">{t("India groundwater map")}</CardTitle>
              <CardDescription>
                {t("Interactive layers: level, recharge, extraction, critical areas.")}
              </CardDescription>
            </CardHeader>
            <CardContent>
              <div className="h-[420px] overflow-hidden rounded-lg border">
                <IngresMap />
              </div>
            </CardContent>
          </Card>

          <div className="grid gap-6 lg:grid-cols-2">
            <Card>
              <CardHeader className="flex-row items-center gap-2 pb-2">
                <AlertTriangle className="h-4 w-4 text-amber-500" />
                <CardTitle className="text-sm">{t("Critical groundwater zones")}</CardTitle>
              </CardHeader>
              <CardContent>
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>{t("District")}</TableHead>
                      <TableHead>{t("State")}</TableHead>
                      <TableHead className="text-right">{t("Stage")}</TableHead>
                      <TableHead>{t("Severity")}</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {(gw?.critical_zones ?? []).map((z) => (
                      <TableRow key={`${z.state}-${z.district}`}>
                        <TableCell className="font-medium">{z.district}</TableCell>
                        <TableCell className="text-muted-foreground">{z.state}</TableCell>
                        <TableCell className="text-right font-semibold">
                          {z.stage != null ? `${z.stage.toFixed(1)}%` : "—"}
                        </TableCell>
                        <TableCell>
                          <span className="flex items-center gap-1.5 text-xs">
                            <span
                              className={`h-2 w-2 rounded-full ${SEVERITY_DOT[z.severity] ?? SEVERITY_DOT.unknown}`}
                            />
                            {t(z.category)}
                          </span>
                        </TableCell>
                      </TableRow>
                    ))}
                    {!gw?.critical_zones.length && (
                      <TableRow>
                        <TableCell colSpan={4} className="h-16 text-center text-muted-foreground">
                          {t("No ranking data available.")}
                        </TableCell>
                      </TableRow>
                    )}
                  </TableBody>
                </Table>
              </CardContent>
            </Card>

            <div className="space-y-6">
              <Card>
                <CardHeader className="pb-2">
                  <CardTitle className="text-sm">{t("Category distribution")}</CardTitle>
                </CardHeader>
                <CardContent className="flex flex-wrap gap-2">
                  {Object.entries(gw?.category_counts ?? {}).map(([cat, count]) => (
                    <Badge
                      key={cat}
                      variant={
                        cat === "Safe"
                          ? "success"
                          : cat === "Semi-critical"
                            ? "warning"
                            : "destructive"
                      }
                    >
                      {cat}: {fmtNum(count)}
                    </Badge>
                  ))}
                  {!gw && <span className="text-sm text-muted-foreground">—</span>}
                </CardContent>
              </Card>

              <Card>
                <CardHeader className="pb-2">
                  <CardTitle className="flex items-center gap-2 text-sm">
                    <Activity className="h-4 w-4 text-emerald-500" />
                    {t("System")}
                  </CardTitle>
                </CardHeader>
                <CardContent className="flex flex-wrap gap-2 text-xs">
                  <Badge variant={overview?.system.database_ok ? "success" : "destructive"}>
                    {t("Database")}: {overview?.system.database_ok ? t("Healthy") : t("Down")}
                  </Badge>
                  <Badge variant="outline">Python {overview?.system.python_version}</Badge>
                  <Badge variant="outline">{overview?.system.platform}</Badge>
                  <Badge variant="outline">{overview?.system.environment}</Badge>
                  <Badge variant="outline">
                    {t("{count} datasets", { count: overview?.datasets.total ?? 0 })}
                  </Badge>
                  <Badge variant="outline">
                    {t("{count} monitoring levels", {
                      count: fmtNum(gw?.monitoring_levels),
                    })}
                  </Badge>
                </CardContent>
              </Card>
            </div>
          </div>
        </div>
      )}

      {/* ------------------------------------------------ Data */}
      {tab === "data" && (
        <div className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2 text-sm">
                <FileUp className="h-4 w-4" />
                {t("Import dataset (CSV / XLSX)")}
              </CardTitle>
              <CardDescription>
                {t(
                  "Upload assessment data (state, district, assessment_unit, year, recharge, extraction, stage, category). Imported rows are tagged as real data, not demo."
                )}
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="grid gap-4 sm:grid-cols-2">
                <Input
                  value={importName}
                  onChange={(e) => setImportName(e.target.value)}
                  placeholder={t("Dataset name")}
                />
                <Input
                  value={importSource}
                  onChange={(e) => setImportSource(e.target.value)}
                  placeholder={t("Source (e.g. CGWB, State dept.)")}
                />
              </div>
              <div className="flex flex-wrap items-center gap-3">
                <Input
                  ref={fileInputRef}
                  type="file"
                  accept=".csv,.xlsx,.xlsm"
                  onChange={(e) => setImportFile(e.target.files?.[0] ?? null)}
                  className="max-w-xs"
                />
                <Button onClick={handleImport} disabled={importing || !importFile}>
                  {importing ? <Loader2 className="h-4 w-4 animate-spin" /> : <FileUp className="h-4 w-4" />}
                  {t("Import")}
                </Button>
                <Button variant="outline" onClick={handleDownloadTemplate}>
                  <Download className="h-4 w-4" />
                  {t("Template")}
                </Button>
              </div>
              {importResult && (
                <p className="rounded-md border bg-muted px-3 py-2 text-sm text-muted-foreground">
                  {importResult}
                </p>
              )}
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm">{t("Datasets ({count})", { count: datasets.length })}</CardTitle>
            </CardHeader>
            <CardContent>
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>{t("Name")}</TableHead>
                    <TableHead>{t("Source")}</TableHead>
                    <TableHead>{t("Version")}</TableHead>
                    <TableHead>{t("Level")}</TableHead>
                    <TableHead>{t("Status")}</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {datasets.map((d) => (
                    <TableRow key={d.id}>
                      <TableCell className="font-medium">
                        {d.name}
                        {d.is_demo && (
                          <Badge variant="warning" className="ml-2 text-[10px]">
                            demo
                          </Badge>
                        )}
                      </TableCell>
                      <TableCell>{d.source ?? "—"}</TableCell>
                      <TableCell>{d.version}</TableCell>
                      <TableCell>{d.geographic_level ?? "—"}</TableCell>
                      <TableCell>
                        <Badge variant={d.validation_status === "VALIDATED" ? "success" : "secondary"}>
                          {d.validation_status}
                        </Badge>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </CardContent>
          </Card>
        </div>
      )}

      {/* ------------------------------------------------ Data Quality */}
      {tab === "quality" && (
        <div className="space-y-6">
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            <StatCard
              label={t("Open issues")}
              value={fmtNum(qualitySummary?.total_open ?? 0)}
              accent={(qualitySummary?.total_open ?? 0) > 0}
            />
            <StatCard
              label={t("High severity (open)")}
              value={fmtNum(qualitySummary?.by_severity?.high ?? 0)}
            />
            <StatCard
              label={t("Resolved")}
              value={fmtNum(qualitySummary?.by_status?.resolved ?? 0)}
            />
            <StatCard
              label={t("Last scan")}
              value={
                qualitySummary?.last_scan_at
                  ? new Date(qualitySummary.last_scan_at).toLocaleString()
                  : t("Never")
              }
            />
          </div>

          <Card>
            <CardHeader className="flex-row items-center justify-between pb-2">
              <CardTitle className="text-sm">{t("Anomaly scan")}</CardTitle>
              <Button size="sm" onClick={() => void scanQuality()} disabled={scanningQuality}>
                {scanningQuality ? (
                  <Loader2 className="h-4 w-4 animate-spin" />
                ) : (
                  <RefreshCw className="h-4 w-4" />
                )}
                {t("Scan now")}
              </Button>
            </CardHeader>
            <CardContent className="text-xs text-muted-foreground">
              {t(
                "Checks for impossible values, negative volumes, category mismatches, inconsistent extraction/recharge ratios and statistical outliers. Re-running never duplicates known issues."
              )}
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="flex-row items-center justify-between gap-3 pb-2">
              <CardTitle className="text-sm">{t("Flags")}</CardTitle>
              <Select
                value={qualityStatusFilter}
                onChange={(e) => {
                  const next = e.target.value as FlagStatus | "all";
                  setQualityStatusFilter(next);
                  void loadQuality(next);
                }}
                className="h-8 w-40"
              >
                <option value="open">{t("Open")}</option>
                <option value="acknowledged">{t("Acknowledged")}</option>
                <option value="resolved">{t("Resolved")}</option>
                <option value="dismissed">{t("Dismissed")}</option>
                <option value="all">{t("All")}</option>
              </Select>
            </CardHeader>
            <CardContent className="max-h-[560px] overflow-auto">
              {loadingQuality && !qualityFlags ? (
                <div className="flex items-center justify-center gap-2 py-10 text-sm text-muted-foreground">
                  <Loader2 className="h-4 w-4 animate-spin" />
                  {t("Loading…")}
                </div>
              ) : (
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>{t("Issue")}</TableHead>
                      <TableHead>{t("Severity")}</TableHead>
                      <TableHead>{t("Location")}</TableHead>
                      <TableHead>{t("Value")}</TableHead>
                      <TableHead>{t("Status")}</TableHead>
                      <TableHead className="w-28">{t("Actions")}</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {(qualityFlags ?? []).map((f) => (
                      <TableRow key={f.id}>
                        <TableCell className="max-w-[280px]">
                          <div className="font-medium">{t(f.kind.replaceAll("_", " "))}</div>
                          {f.detail && (
                            <div className="mt-0.5 line-clamp-2 text-xs text-muted-foreground" title={f.detail}>
                              {f.detail}
                            </div>
                          )}
                        </TableCell>
                        <TableCell>
                          <Badge
                            variant={
                              f.severity === "high"
                                ? "destructive"
                                : f.severity === "medium"
                                  ? "warning"
                                  : "secondary"
                            }
                          >
                            {f.severity}
                          </Badge>
                        </TableCell>
                        <TableCell className="text-xs text-muted-foreground">
                          {[f.unit_name, f.district_name, f.state_name].filter(Boolean).join(", ") ||
                            "—"}
                          {f.year ? ` · ${f.year}` : ""}
                        </TableCell>
                        <TableCell className="whitespace-nowrap text-xs">
                          {f.value !== null ? f.value.toFixed(2) : "—"}
                          {f.expected_min !== null && f.expected_max !== null && (
                            <div className="text-[10px] text-muted-foreground">
                              {f.expected_min}–{f.expected_max}
                            </div>
                          )}
                        </TableCell>
                        <TableCell>
                          <Badge variant={f.status === "open" ? "outline" : "secondary"}>
                            {f.status}
                          </Badge>
                          {f.review_note && (
                            <div className="mt-0.5 max-w-[160px] truncate text-[10px] text-muted-foreground" title={f.review_note}>
                              {f.review_note}
                            </div>
                          )}
                        </TableCell>
                        <TableCell className="space-x-1 whitespace-nowrap">
                          {f.status === "open" && (
                            <>
                              <Button
                                size="sm"
                                variant="outline"
                                onClick={() => void handleReviewFlag(f.id, "acknowledged")}
                              >
                                {t("Ack")}
                              </Button>
                              <Button
                                size="sm"
                                variant="ghost"
                                onClick={() => void handleReviewFlag(f.id, "dismissed")}
                              >
                                {t("Dismiss")}
                              </Button>
                            </>
                          )}
                          {(f.status === "acknowledged" || f.status === "dismissed") && (
                            <Button
                              size="sm"
                              variant="outline"
                              onClick={() => void handleReviewFlag(f.id, "resolved")}
                            >
                              {t("Resolve")}
                            </Button>
                          )}
                          {f.status === "resolved" && (
                            <span className="text-xs text-muted-foreground">—</span>
                          )}
                        </TableCell>
                      </TableRow>
                    ))}
                    {qualityFlags?.length === 0 && (
                      <TableRow>
                        <TableCell colSpan={6} className="h-16 text-center text-muted-foreground">
                          {t("No flags for this filter. Run a scan to check the data.")}
                        </TableCell>
                      </TableRow>
                    )}
                  </TableBody>
                </Table>
              )}
            </CardContent>
          </Card>
        </div>
      )}

      {/* ------------------------------------------------ AI / RAG */}
      {tab === "ai" && (
        <div className="grid gap-6 lg:grid-cols-2">
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="flex items-center gap-2 text-sm">
                <Bot className="h-4 w-4" />
                {t("LLM status")}
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-2 text-sm">
              <div className="flex items-center gap-2">
                <Badge variant={overview?.ai.llm_enabled ? "success" : "secondary"}>
                  {overview?.ai.llm_enabled ? t("Online") : t("Disabled")}
                </Badge>
                <span className="font-mono text-xs">{overview?.ai.llm_model ?? "—"}</span>
              </div>
              <p className="text-muted-foreground">
                {t("Provider")}: <span className="font-medium">{overview?.ai.llm_provider ?? "—"}</span>
              </p>
              {overview?.ai.search_model && (
                <p className="text-muted-foreground">
                  {t("Web-search agent")}:{" "}
                  <span className="font-medium">{overview.ai.search_model}</span>
                </p>
              )}
              <p className="text-muted-foreground">
                {t("Internet fallback")}:{" "}
                {overview?.ai.web_search_enabled ? t("Enabled") : t("Disabled")}
              </p>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="flex-row items-center justify-between pb-2">
              <CardTitle className="flex items-center gap-2 text-sm">
                <RefreshCw className="h-4 w-4" />
                {t("Semantic RAG")}
              </CardTitle>
              <Button variant="outline" size="sm" onClick={handleReindex} disabled={reindexing}>
                {reindexing ? (
                  <Loader2 className="h-4 w-4 animate-spin" />
                ) : (
                  <RefreshCw className="h-4 w-4" />
                )}
                {t("Re-embed")}
              </Button>
            </CardHeader>
            <CardContent className="space-y-2 text-sm">
              {rag ? (
                <>
                  <div className="flex flex-wrap items-center gap-2">
                    <Badge variant={rag.available ? "success" : "secondary"}>
                      {rag.available ? t("Online") : t("Unavailable")}
                    </Badge>
                    <span className="text-muted-foreground">
                      {t("{indexed} / {chunks} chunks indexed", {
                        indexed: rag.indexed,
                        chunks: rag.chunks,
                      })}
                    </span>
                  </div>
                  <p className="text-muted-foreground">
                    mode: {rag.mode} · model: {rag.embedding_model}
                  </p>
                </>
              ) : (
                <p className="text-muted-foreground">{t("RAG status unavailable.")}</p>
              )}
              <p className="text-muted-foreground">
                {t("{docs} documents · {chunks} chunks", {
                  docs: fmtNum(overview?.ai.rag_documents),
                  chunks: fmtNum(overview?.ai.rag_chunks),
                })}
              </p>
            </CardContent>
          </Card>
        </div>
      )}

      {/* ------------------------------------------------ Models */}
      {tab === "models" && (
        <Card>
          <CardHeader className="flex-row items-center justify-between gap-3 pb-2">
            <div>
              <CardTitle className="text-sm">{t("Forecast model validation")}</CardTitle>
              <CardDescription>
                {t("Walk-forward backtest metrics per statistical model.")}
              </CardDescription>
            </div>
            <div className="flex items-center gap-2">
              <Select
                value={metricsState}
                onChange={(e) => setMetricsState(e.target.value)}
                className="h-8 w-44"
              >
                {["Telangana", "Andhra Pradesh", "Karnataka", "Maharashtra", "Punjab", "Uttar Pradesh"].map(
                  (s) => (
                    <option key={s} value={s}>
                      {s}
                    </option>
                  )
                )}
              </Select>
              <Select
                value={metricsMetric}
                onChange={(e) => setMetricsMetric(e.target.value)}
                className="h-8 w-32"
              >
                <option value="stage">stage</option>
                <option value="recharge">recharge</option>
                <option value="extraction">extraction</option>
              </Select>
              <Button
                size="sm"
                onClick={() => loadModels(metricsState, metricsMetric)}
                disabled={loadingModels}
              >
                {loadingModels ? (
                  <Loader2 className="h-4 w-4 animate-spin" />
                ) : (
                  <RefreshCw className="h-4 w-4" />
                )}
                {t("Run")}
              </Button>
            </div>
          </CardHeader>
          <CardContent>
            {modelMetrics?.best_model && (
              <p className="mb-3 text-sm text-muted-foreground">
                {t("Recommended model")}:{" "}
                <Badge variant="success">{modelMetrics.best_model}</Badge>
              </p>
            )}
            {modelMetrics?.error && (
              <p className="mb-3 text-sm text-destructive">{modelMetrics.error}</p>
            )}
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>{t("Model")}</TableHead>
                  <TableHead className="text-right">RMSE</TableHead>
                  <TableHead className="text-right">MAE</TableHead>
                  <TableHead className="text-right">MAPE %</TableHead>
                  <TableHead className="text-right">{t("Direction acc.")}</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {(modelMetrics?.models ?? []).map((m) => (
                  <TableRow key={m.model}>
                    <TableCell className="font-medium">
                      <span className="flex items-center gap-2">
                        {m.model}
                        {m.model === modelMetrics?.best_model && (
                          <Badge variant="success" className="text-[10px]">
                            best
                          </Badge>
                        )}
                      </span>
                    </TableCell>
                    <TableCell className="text-right">{m.rmse?.toFixed(2) ?? "—"}</TableCell>
                    <TableCell className="text-right">{m.mae?.toFixed(2) ?? "—"}</TableCell>
                    <TableCell className="text-right">{m.mape?.toFixed(1) ?? "—"}</TableCell>
                    <TableCell className="text-right">
                      {m.direction_accuracy != null
                        ? `${(m.direction_accuracy * 100).toFixed(0)}%`
                        : "—"}
                    </TableCell>
                  </TableRow>
                ))}
                {!modelMetrics && (
                  <TableRow>
                    <TableCell colSpan={5} className="h-20 text-center text-muted-foreground">
                      {t("Run a backtest to see model metrics.")}
                    </TableCell>
                  </TableRow>
                )}
              </TableBody>
            </Table>
          </CardContent>
        </Card>
      )}

      {/* ------------------------------------------------ Queries */}
      {tab === "queries" && (
        <div className="space-y-6">
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm">{t("What users are asking")}</CardTitle>
            </CardHeader>
            <CardContent className="space-y-2">
              {intentEntries.map(([intent, count]) => (
                <div key={intent} className="flex items-center gap-3 text-xs">
                  <span className="w-28 shrink-0 truncate text-muted-foreground">
                    {t(INTENT_LABELS[intent] ?? intent)}
                  </span>
                  <div className="h-2 flex-1 overflow-hidden rounded-full bg-muted">
                    <div
                      className="h-full rounded-full bg-primary"
                      style={{ width: `${Math.round((count / maxIntent) * 100)}%` }}
                    />
                  </div>
                  <span className="w-10 shrink-0 text-right font-medium">{fmtNum(count)}</span>
                </div>
              ))}
              {!intentEntries.length && (
                <p className="text-sm text-muted-foreground">{t("No assistant activity yet.")}</p>
              )}
              <div className="pt-1 text-xs text-muted-foreground">
                👍 {fmtNum(overview?.queries.feedback_helpful)} · 👎{" "}
                {fmtNum(overview?.queries.feedback_not_helpful)}
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="flex-row items-center justify-between pb-2">
              <CardTitle className="text-sm">{t("Recent AI answers")}</CardTitle>
              <Button variant="outline" size="sm" onClick={() => void loadQueries()} disabled={loadingQueries}>
                {loadingQueries ? (
                  <Loader2 className="h-4 w-4 animate-spin" />
                ) : (
                  <RefreshCw className="h-4 w-4" />
                )}
                {t("Refresh")}
              </Button>
            </CardHeader>
            <CardContent className="max-h-[480px] overflow-auto">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>{t("Question")}</TableHead>
                    <TableHead>{t("User")}</TableHead>
                    <TableHead>{t("Intent")}</TableHead>
                    <TableHead>{t("Lang")}</TableHead>
                    <TableHead>{t("Feedback")}</TableHead>
                    <TableHead>{t("Time")}</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {(queryRows ?? []).map((r) => (
                    <TableRow key={r.id}>
                      <TableCell className="max-w-[280px] truncate" title={r.question ?? ""}>
                        {r.question ?? "—"}
                      </TableCell>
                      <TableCell className="text-muted-foreground">{r.user ?? "—"}</TableCell>
                      <TableCell>
                        <Badge variant="outline">{t(INTENT_LABELS[r.intent ?? "unknown"])}</Badge>
                      </TableCell>
                      <TableCell className="text-muted-foreground">
                        {LANG_LABELS[r.language ?? ""] ?? r.language ?? "—"}
                      </TableCell>
                      <TableCell>
                        {r.rating === 1 ? (
                          <Badge variant="success">👍</Badge>
                        ) : r.rating === -1 ? (
                          <Badge variant="destructive">👎</Badge>
                        ) : (
                          <span className="text-muted-foreground">—</span>
                        )}
                      </TableCell>
                      <TableCell className="whitespace-nowrap text-muted-foreground">
                        {r.created_at ? new Date(r.created_at).toLocaleString() : "—"}
                      </TableCell>
                    </TableRow>
                  ))}
                  {queryRows?.length === 0 && (
                    <TableRow>
                      <TableCell colSpan={6} className="h-16 text-center text-muted-foreground">
                        {t("No assistant activity yet.")}
                      </TableCell>
                    </TableRow>
                  )}
                </TableBody>
              </Table>
            </CardContent>
          </Card>
        </div>
      )}

      {/* ------------------------------------------------ Users */}
      {tab === "users" && (
        <div className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2 text-sm">
                <UserPlus className="h-4 w-4" />
                {t("Create user")}
              </CardTitle>
            </CardHeader>
            <CardContent className="grid gap-4 sm:grid-cols-2 lg:grid-cols-5">
              <Input value={fullName} onChange={(e) => setFullName(e.target.value)} placeholder={t("Full name")} />
              <Input value={email} onChange={(e) => setEmail(e.target.value)} placeholder={t("Email")} type="email" />
              <Input
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder={t("Password")}
                type="password"
              />
              <Select value={role} onChange={(e) => setRole(e.target.value)}>
                {ROLE_OPTIONS.map((r) => (
                  <option key={r} value={r}>
                    {r}
                  </option>
                ))}
              </Select>
              <Button onClick={handleCreate} disabled={creating || !email.trim() || !password.trim()}>
                {creating ? <Loader2 className="h-4 w-4 animate-spin" /> : <Plus className="h-4 w-4" />}
                {t("Create")}
              </Button>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm">{t("Users ({count})", { count: users.length })}</CardTitle>
            </CardHeader>
            <CardContent>
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>{t("Name")}</TableHead>
                    <TableHead>{t("Email")}</TableHead>
                    <TableHead>{t("Role")}</TableHead>
                    <TableHead>{t("Status")}</TableHead>
                    <TableHead>{t("Last login")}</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {users.map((u) => (
                    <TableRow key={u.id}>
                      <TableCell className="font-medium">{u.full_name}</TableCell>
                      <TableCell>{u.email}</TableCell>
                      <TableCell>
                        <Select
                          value={u.role}
                          onChange={(e) => handleRole(u.id, e.target.value)}
                          className="h-8 w-28"
                          disabled={u.id === user.id}
                        >
                          {ROLE_OPTIONS.map((r) => (
                            <option key={r} value={r}>
                              {r}
                            </option>
                          ))}
                        </Select>
                      </TableCell>
                      <TableCell>
                        <Button
                          variant={u.is_active ? "outline" : "destructive"}
                          size="sm"
                          onClick={() => handleToggle(u.id, !u.is_active)}
                          disabled={u.id === user.id}
                        >
                          {u.is_active ? t("Active") : t("Disabled")}
                        </Button>
                      </TableCell>
                      <TableCell className="text-muted-foreground">
                        {u.last_login_at ? new Date(u.last_login_at).toLocaleString() : t("never")}
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </CardContent>
          </Card>
        </div>
      )}

      {/* ------------------------------------------------ Audit */}
      {tab === "audit" && (
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm">{t("Audit log")}</CardTitle>
          </CardHeader>
          <CardContent className="max-h-[560px] overflow-auto">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>{t("Time")}</TableHead>
                  <TableHead>{t("Action")}</TableHead>
                  <TableHead>{t("Resource")}</TableHead>
                  <TableHead>{t("User")}</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {logs.map((l) => (
                  <TableRow key={l.id}>
                    <TableCell className="whitespace-nowrap text-muted-foreground">
                      {l.created_at ? new Date(l.created_at).toLocaleString() : "—"}
                    </TableCell>
                    <TableCell className="font-mono text-xs">{l.action}</TableCell>
                    <TableCell className="text-muted-foreground">
                      {l.resource}
                      {l.resource_id ? ` #${l.resource_id}` : ""}
                    </TableCell>
                    <TableCell className="text-muted-foreground">{l.user ?? "—"}</TableCell>
                  </TableRow>
                ))}
                {logs.length === 0 && (
                  <TableRow>
                    <TableCell colSpan={4} className="h-20 text-center text-muted-foreground">
                      {t("No audit events yet.")}
                    </TableCell>
                  </TableRow>
                )}
              </TableBody>
            </Table>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
