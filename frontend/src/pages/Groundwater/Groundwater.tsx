import { Droplets, Filter, Loader2, MapPin, RefreshCw, Waves } from "lucide-react";
import { useEffect, useMemo, useState } from "react";

import BarChart from "@/components/BarChart";
import ExplainStrip from "@/components/ExplainStrip";
import LevelGauge from "@/components/LevelGauge";
import StatCard from "@/components/StatCard";
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
import { useLanguage } from "@/contexts/LanguageContext";
import {
  Table,
  TableBody,
  TableCaption,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  fetchAssessments,
  fetchCategories,
  fetchDistricts,
  fetchExtraction,
  fetchRecharge,
  fetchStates,
  fetchSummary,
  fetchVillages,
} from "@/services/groundwater";
import type {
  GroundwaterAssessment,
  GroundwaterCategory,
  GroundwaterState,
  GroundwaterSummary,
  GroundwaterVillage,
  CategoryCount,
} from "@/types";

const CATEGORY_COLORS: Record<string, string> = {
  Safe: "#16a34a",
  "Semi-critical": "#f59e0b",
  Critical: "#f97316",
  Overexploited: "#dc2626",
};

const YEAR_OPTIONS = [2017, 2018, 2019, 2020, 2021, 2022];

function formatNumber(value: number | null | undefined, digits = 1): string {
  if (value === null || value === undefined) return "—";
  return new Intl.NumberFormat("en-IN", { maximumFractionDigits: digits }).format(value);
}

function categoryVariant(category: string | null) {
  switch (category) {
    case "Safe":
      return "success" as const;
    case "Semi-critical":
      return "warning" as const;
    case "Critical":
      return "warning" as const;
    case "Overexploited":
      return "destructive" as const;
    default:
      return "secondary" as const;
  }
}

export default function Groundwater() {
  const { t } = useLanguage();
  const [states, setStates] = useState<GroundwaterState[]>([]);
  const [categories, setCategories] = useState<GroundwaterCategory[]>([]);
  const [districts, setDistricts] = useState<{ id: number; name: string }[]>([]);
  const [villages, setVillages] = useState<GroundwaterVillage[]>([]);

  const [stateFilter, setStateFilter] = useState("");
  const [districtFilter, setDistrictFilter] = useState("");
  const [villageFilter, setVillageFilter] = useState("");
  const [yearFilter, setYearFilter] = useState("");
  const [categoryFilter, setCategoryFilter] = useState("");

  const [summary, setSummary] = useState<GroundwaterSummary | null>(null);
  const [assessments, setAssessments] = useState<GroundwaterAssessment[]>([]);
  const [rechargeByYear, setRechargeByYear] = useState<{ label: string; value: number }[]>([]);
  const [extractionByYear, setExtractionByYear] = useState<{ label: string; value: number }[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const filters = useMemo(
    () => ({
      state: stateFilter || undefined,
      district: districtFilter || undefined,
      village: villageFilter || undefined,
      year: yearFilter ? Number(yearFilter) : undefined,
      category: categoryFilter || undefined,
    }),
    [stateFilter, districtFilter, villageFilter, yearFilter, categoryFilter]
  );

  useEffect(() => {
    let active = true;
    Promise.all([fetchStates(), fetchCategories()])
      .then(([stateRows, categoryRows]) => {
        if (!active) return;
        setStates(stateRows);
        setCategories(categoryRows);
      })
      .catch(() => undefined);
    return () => {
      active = false;
    };
  }, []);

  useEffect(() => {
    if (!stateFilter) {
      setDistricts([]);
      setVillages([]);
      return;
    }
    let active = true;
    fetchDistricts(stateFilter)
      .then((rows) => {
        if (!active) return;
        setDistricts(rows);
      })
      .catch(() => active && setDistricts([]));
    return () => {
      active = false;
    };
  }, [stateFilter]);

  useEffect(() => {
    if (!stateFilter || !districtFilter) {
      setVillages([]);
      return;
    }
    let active = true;
    fetchVillages(stateFilter, districtFilter)
      .then((rows) => {
        if (!active) return;
        setVillages(rows);
      })
      .catch(() => active && setVillages([]));
    return () => {
      active = false;
    };
  }, [stateFilter, districtFilter]);

  useEffect(() => {
    let active = true;
    setLoading(true);
    setError(null);

    function aggregate(rows: { year: number; value: number | null }[]) {
      const byYear = new Map<number, number>();
      for (const row of rows) {
        if (row.value === null) continue;
        byYear.set(row.year, (byYear.get(row.year) ?? 0) + row.value);
      }
      return [...byYear.entries()]
        .sort((a, b) => a[0] - b[0])
        .map(([year, value]) => ({ label: String(year), value }));
    }

    Promise.all([
      fetchSummary(filters),
      fetchAssessments(filters),
      fetchRecharge(filters),
      fetchExtraction(filters),
    ])
      .then(([summaryData, assessmentRows, rechargeRows, extractionRows]) => {
        if (!active) return;
        setSummary(summaryData);
        setAssessments(assessmentRows);
        setRechargeByYear(aggregate(rechargeRows));
        setExtractionByYear(aggregate(extractionRows));
      })
      .catch((err) => {
        if (!active) return;
        setError(
          typeof err === "object" && err !== null && "message" in err
            ? String((err as { message: string }).message)
            : t("Failed to load groundwater data.")
        );
      })
      .finally(() => active && setLoading(false));

    return () => {
      active = false;
    };
  }, [filters]);

  const categoryData =
    summary?.category_counts.map((c) => ({
      label: c.category,
      value: c.count,
      color: CATEGORY_COLORS[c.category] ?? "#64748b",
    })) ?? [];

  const hasFilters = Boolean(
    stateFilter || districtFilter || villageFilter || yearFilter || categoryFilter
  );

  // Plain-language condition summary from the real category counts.
  const totalAreas =
    summary?.category_counts.reduce((sum, c) => sum + c.count, 0) ?? 0;
  const dominantCategory = summary?.category_counts.reduce<CategoryCount | null>(
    (best, c) => (!best || c.count > best.count ? c : best),
    null,
  );
  const STRESSED = new Set(["Semi-critical", "Critical", "Overexploited"]);
  const stressedCount =
    summary?.category_counts
      .filter((c) => STRESSED.has(c.category))
      .reduce((sum, c) => sum + c.count, 0) ?? 0;

  // Year-over-year change for the recharge/extraction explain strips.
  function firstLastChange(rows: { label: string; value: number }[]) {
    if (rows.length < 2) return null;
    return { from: rows[0], to: rows[rows.length - 1] };
  }
  const rechargeChange = firstLastChange(rechargeByYear);
  const extractionChange = firstLastChange(extractionByYear);

  return (
    <div className="mx-auto max-w-6xl space-y-6">
      <section className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="text-2xl font-bold">{t("Groundwater Analytics")}</h2>
          <p className="mt-1 text-muted-foreground">
            {t("See the water situation for any state, district or village.")}
          </p>
        </div>
        {summary?.is_demo && (
          <Badge variant="warning">
            {t("Demo data · {source}", { source: summary.source })}
          </Badge>
        )}
      </section>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Filter className="h-4 w-4" />
            {t("Filters")}
          </CardTitle>
        </CardHeader>
        <CardContent className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
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
          <div className="space-y-1.5">
            <label className="text-sm font-medium">{t("Assessment Year")}</label>
            <Select value={yearFilter} onChange={(e) => setYearFilter(e.target.value)}>
              <option value="">{t("all_years")}</option>
              {YEAR_OPTIONS.map((y) => (
                <option key={y} value={y}>
                  {y}
                </option>
              ))}
            </Select>
          </div>
          <div className="space-y-1.5">
            <label className="text-sm font-medium">{t("category")}</label>
            <Select value={categoryFilter} onChange={(e) => setCategoryFilter(e.target.value)}>
              <option value="">{t("All categories")}</option>
              {categories.map((c) => (
                <option key={c.id} value={c.name}>
                  {c.label}
                </option>
              ))}
            </Select>
          </div>
        </CardContent>
      </Card>

      {error && (
        <div className="rounded-md border border-destructive/30 bg-destructive/10 p-4 text-sm text-destructive">
          {error}
        </div>
      )}

      {loading ? (
        <div className="flex items-center justify-center gap-2 py-16 text-sm text-muted-foreground">
          <Loader2 className="h-4 w-4 animate-spin" />
          {t("Loading groundwater data…")}
        </div>
      ) : (
        <>
          <section className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <StatCard
              icon={MapPin}
              label={t("Areas tracked")}
              value={summary ? String(summary.assessment_units) : "—"}
              sub={t("Units in scope")}
            />
            <StatCard
              icon={Droplets}
              label={t("Water refilling the ground")}
              value={formatNumber(summary?.total_recharge)}
              sub={t("Total annual recharge")}
            />
            <StatCard
              icon={Waves}
              label={t("Water pumped out")}
              value={formatNumber(summary?.total_extraction)}
              sub={t("Total annual extraction")}
            />
            <div className="rounded-xl border bg-card p-5">
              <div className="text-sm font-medium text-muted-foreground">
                {t("How much water do we use?")}
              </div>
              <div className="mt-3">
                <LevelGauge value={summary?.average_stage_of_extraction ?? null} />
              </div>
              <div className="mt-2 text-sm text-muted-foreground">
                {t("Share of the fresh water that gets pumped up each year.")}
              </div>
            </div>
          </section>

          <section className="grid gap-4 lg:grid-cols-2">
            <Card>
              <CardHeader>
                <CardTitle>{t("Category distribution")}</CardTitle>
                <CardDescription>
                  {t("Assessment units by stage-of-extraction category.")}
                </CardDescription>
              </CardHeader>
              <CardContent>
                {categoryData.length ? (
                  <>
                    <BarChart data={categoryData} />
                    <ExplainStrip>
                      {stressedCount > 0 ? (
                        <>
                          {t(
                            "{count} of {total} areas are using more water than is safe.",
                            { count: stressedCount, total: totalAreas },
                          )}
                          {dominantCategory && (
                            <>
                              {" "}
                              {t("The largest group is {category} ({count} areas).", {
                                category: dominantCategory.category,
                                count: dominantCategory.count,
                              })}
                            </>
                          )}
                        </>
                      ) : (
                        dominantCategory &&
                        t("Good news: all {total} areas are in the Safe group.", {
                          total: totalAreas,
                        })
                      )}
                    </ExplainStrip>
                  </>
                ) : (
                  <div className="text-sm text-muted-foreground">
                    {t("No data for the current filters.")}
                  </div>
                )}
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle>{t("Recharge by year")}</CardTitle>
                <CardDescription>
                  {t("Water that refills the ground each year, in {unit}.", {
                    unit: summary?.unit ?? "hm³",
                  })}
                </CardDescription>
              </CardHeader>
              <CardContent>
                {rechargeByYear.length ? (
                  <>
                    <BarChart
                      data={rechargeByYear.map((d) => ({ ...d, color: "#0ea5e9" }))}
                      formatValue={(v) => formatNumber(v, 0)}
                    />
                    {rechargeChange && (
                      <ExplainStrip>
                        {t(
                          "In {from}, {valueA} went into the ground; in {to}, it was {valueB}.",
                          {
                            from: rechargeChange.from.label,
                            to: rechargeChange.to.label,
                            valueA: formatNumber(rechargeChange.from.value, 0),
                            valueB: formatNumber(rechargeChange.to.value, 0),
                          },
                        )}
                      </ExplainStrip>
                    )}
                  </>
                ) : (
                  <div className="text-sm text-muted-foreground">
                    {t("No data for the current filters.")}
                  </div>
                )}
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle>{t("Extraction by year")}</CardTitle>
                <CardDescription>
                  {t("Water pumped out each year, in {unit}.", { unit: summary?.unit ?? "hm³" })}
                </CardDescription>
              </CardHeader>
              <CardContent>
                {extractionByYear.length ? (
                  <>
                    <BarChart
                      data={extractionByYear.map((d) => ({ ...d, color: "#8b5cf6" }))}
                      formatValue={(v) => formatNumber(v, 0)}
                    />
                    {extractionChange && (
                      <ExplainStrip>
                        {t(
                          "In {from}, {valueA} was pumped out; in {to}, it was {valueB}.",
                          {
                            from: extractionChange.from.label,
                            to: extractionChange.to.label,
                            valueA: formatNumber(extractionChange.from.value, 0),
                            valueB: formatNumber(extractionChange.to.value, 0),
                          },
                        )}
                      </ExplainStrip>
                    )}
                  </>
                ) : (
                  <div className="text-sm text-muted-foreground">
                    {t("No data for the current filters.")}
                  </div>
                )}
              </CardContent>
            </Card>

            <Card>
              <CardHeader className="flex-row items-start justify-between space-y-0">
                <div>
                  <CardTitle>{t("Assessment records")}</CardTitle>
                  <CardDescription>{t("Detailed stage-of-extraction data.")}</CardDescription>
                </div>
                <Button
                  variant="outline"
                  size="sm"
                  disabled={!hasFilters}
                  onClick={() => {
                    setStateFilter("");
                    setDistrictFilter("");
                    setVillageFilter("");
                    setYearFilter("");
                    setCategoryFilter("");
                  }}
                >
                  <RefreshCw className="h-3.5 w-3.5" />
                  {t("Reset")}
                </Button>
              </CardHeader>
              <CardContent>
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>{t("Village / Unit")}</TableHead>
                      <TableHead>{t("district")}</TableHead>
                      <TableHead>{t("year")}</TableHead>
                      <TableHead className="text-right">{t("recharge")}</TableHead>
                      <TableHead className="text-right">{t("extraction")}</TableHead>
                      <TableHead className="text-right">{t("SoE %")}</TableHead>
                      <TableHead>{t("category")}</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {assessments.slice(0, 25).map((a) => (
                      <TableRow key={a.id}>
                        <TableCell className="font-medium">{a.assessment_unit}</TableCell>
                        <TableCell>{a.district || "—"}</TableCell>
                        <TableCell>{a.assessment_year}</TableCell>
                        <TableCell className="text-right">{formatNumber(a.recharge_total)}</TableCell>
                        <TableCell className="text-right">{formatNumber(a.extraction_total)}</TableCell>
                        <TableCell className="text-right">
                          {a.stage_of_extraction != null ? `${a.stage_of_extraction.toFixed(1)}%` : "—"}
                        </TableCell>
                        <TableCell>
                          <Badge variant={categoryVariant(a.category)}>{a.category ?? "—"}</Badge>
                        </TableCell>
                      </TableRow>
                    ))}
                    {assessments.length === 0 && (
                      <TableRow>
                        <TableCell colSpan={7} className="h-24 text-center text-muted-foreground">
                          {t("No assessment records for the current filters.")}
                        </TableCell>
                      </TableRow>
                    )}
                  </TableBody>
                  {assessments.length > 25 && (
                    <TableCaption>
                      {t("Showing 25 of {count} records.", { count: assessments.length })}
                    </TableCaption>
                  )}
                </Table>
              </CardContent>
            </Card>
          </section>
        </>
      )}
    </div>
  );
}