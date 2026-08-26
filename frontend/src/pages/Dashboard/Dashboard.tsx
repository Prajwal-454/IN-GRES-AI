import {
  AlertTriangle,
  ArrowRight,
  CloudRain,
  Droplets,
  FileText,
  Map as MapIcon,
  MapPin,
  Sparkles,
  TrendingUp,
  Waves,
} from "lucide-react";
import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import BarChart from "@/components/BarChart";
import LineChart from "@/components/LineChart";
import ExplainStrip from "@/components/ExplainStrip";
import LevelGauge from "@/components/LevelGauge";
import StatCard from "@/components/StatCard";
import TrendChip, { type TrendDirection } from "@/components/TrendChip";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { useAuth } from "@/contexts/AuthContext";
import { useLanguage } from "@/contexts/LanguageContext";
import { getInsights, getTrends, type Insight } from "@/services/analytics";
import { fetchSummary, fetchStates } from "@/services/groundwater";
import type { GroundwaterSummary, GroundwaterState } from "@/types";

const CATEGORY_COLORS: Record<string, string> = {
  Safe: "#16a34a",
  "Semi-critical": "#f59e0b",
  Critical: "#f97316",
  Overexploited: "#dc2626",
};

const INSIGHT_ICONS: Record<string, typeof TrendingUp> = {
  trend: TrendingUp,
  stress: AlertTriangle,
  top: MapPin,
  recharge: CloudRain,
};

function formatNumber(value: number | null | undefined): string {
  if (value === null || value === undefined) return "—";
  return new Intl.NumberFormat("en-IN", { maximumFractionDigits: 1 }).format(value);
}

export default function Dashboard() {
  const { user } = useAuth();
  const { t } = useLanguage();
  const [states, setStates] = useState<GroundwaterState[]>([]);
  const [summary, setSummary] = useState<GroundwaterSummary | null>(null);
  const [trends, setTrends] = useState<{ label: string; value: number }[]>([]);
  const [insights, setInsights] = useState<Insight[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let active = true;
    Promise.all([
      fetchStates(),
      fetchSummary({}),
      getTrends(),
      getInsights(),
    ])
      .then(([stateRows, summaryData, trendRows, insightData]) => {
        if (!active) return;
        setStates(stateRows);
        setSummary(summaryData);
        setTrends(
          trendRows.map((r) => ({ label: String(r.year), value: r.stage_of_extraction }))
        );
        setInsights(insightData.insights);
      })
      .catch(() => undefined)
      .finally(() => active && setLoading(false));
    return () => {
      active = false;
    };
  }, []);

  const stage = summary?.average_stage_of_extraction ?? null;

  // Plain-language condition summary from the real category counts.
  const counts = summary?.category_counts ?? [];
  const totalAreas = counts.reduce((sum, c) => sum + c.count, 0);
  const dominant = counts.reduce<{ category: string; count: number } | null>(
    (best, c) => (!best || c.count > best.count ? c : best),
    null,
  );
  const STRESSED = new Set(["Semi-critical", "Critical", "Overexploited"]);
  const stressedCount = counts
    .filter((c) => STRESSED.has(c.category))
    .reduce((sum, c) => sum + c.count, 0);

  // Usage-direction sentence from the first/last observed years.
  const firstTrend = trends[0];
  const lastTrend = trends[trends.length - 1];
  const delta =
    firstTrend && lastTrend ? lastTrend.value - firstTrend.value : null;
  const direction: TrendDirection | null =
    delta == null ? null : delta > 1 ? "rising" : delta < -1 ? "falling" : "stable";

  const categoryData = counts.map((c) => ({
    label: c.category,
    value: c.count,
    color: CATEGORY_COLORS[c.category] ?? "#64748b",
  }));

  return (
    <div className="mx-auto max-w-6xl space-y-8">
      <section>
        <h2 className="text-2xl font-bold">
          {t("Welcome, {name}", { name: user?.full_name.split(" ")[0] ?? "" })}
        </h2>
        <p className="mt-1 text-muted-foreground">
          {t("A quick picture of the groundwater near you.")}
        </p>
      </section>

      {summary?.is_demo && (
        <Badge variant="warning">{t("Demo data · {source}", { source: summary.source })}</Badge>
      )}

      <section className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard
          icon={MapPin}
          label={t("Areas tracked")}
          value={summary ? String(summary.assessment_units) : "—"}
          sub={summary ? t("{count} states monitored", { count: states.length }) : undefined}
          loading={loading}
        />
        <StatCard
          icon={Droplets}
          label={t("Water refilling the ground")}
          value={formatNumber(summary?.total_recharge)}
          sub={t("Each year")}
          loading={loading}
        />
        <StatCard
          icon={Waves}
          label={t("Water pumped out")}
          value={formatNumber(summary?.total_extraction)}
          sub={t("Each year")}
          loading={loading}
        />
        <div className="rounded-xl border bg-card p-5">
          <div className="text-sm font-medium text-muted-foreground">
            {t("How much water do we use?")}
          </div>
          <div className="mt-3">
            <LevelGauge value={loading ? null : stage} />
          </div>
          <div className="mt-2 text-sm text-muted-foreground">
            {t("Share of the fresh water that gets pumped up each year.")}
          </div>
        </div>
      </section>

      <section className="grid gap-4 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>{t("Condition of the areas")}</CardTitle>
            <CardDescription>
              {t("Every area is marked Safe, Needs Care or Critical.")}
            </CardDescription>
          </CardHeader>
          <CardContent>
            {loading ? (
              <div className="text-sm text-muted-foreground">{t("loading")}</div>
            ) : categoryData.length ? (
              <>
                <BarChart data={categoryData} />
                <ExplainStrip>
                  {stressedCount > 0 ? (
                    <>
                      {t(
                        "{count} of {total} areas are using more water than is safe.",
                        { count: stressedCount, total: totalAreas },
                      )}
                      {dominant && (
                        <>
                          {" "}
                          {t("The largest group is {category} ({count} areas).", {
                            category: dominant.category,
                            count: dominant.count,
                          })}
                        </>
                      )}
                    </>
                  ) : (
                    dominant &&
                    t("Good news: all {total} areas are in the Safe group.", {
                      total: totalAreas,
                    })
                  )}
                </ExplainStrip>
              </>
            ) : (
              <div className="text-sm text-muted-foreground">{t("No data available.")}</div>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row flex-wrap items-center justify-between gap-2">
            <div>
              <CardTitle>{t("Water use over the years")}</CardTitle>
              <CardDescription>
                {t("Share of fresh water pumped up, year by year.")}
              </CardDescription>
            </div>
            {direction && !loading && (
              <TrendChip
                direction={direction}
                good={direction === "falling"}
                label={
                  direction === "rising"
                    ? t("Going up")
                    : direction === "falling"
                      ? t("Coming down")
                      : t("Steady")
                }
              />
            )}
          </CardHeader>
          <CardContent>
            {loading ? (
              <div className="text-sm text-muted-foreground">{t("loading")}</div>
            ) : trends.length ? (
              <>
                <LineChart data={trends} formatValue={(v) => `${v.toFixed(0)}%`} />
                <ExplainStrip>
                  {lastTrend &&
                    t("In {year}, people used about {pct}% of the fresh water.", {
                      year: lastTrend.label,
                      pct: Math.round(lastTrend.value),
                    })}
                  {direction === "rising" && <> {t("Use keeps increasing — water needs care.")}</>}
                  {direction === "falling" && <> {t("Use is coming down — a good sign.")}</>}
                  {direction === "stable" && <> {t("Use has stayed about the same.")}</>}
                </ExplainStrip>
              </>
            ) : (
              <div className="text-sm text-muted-foreground">{t("No data available.")}</div>
            )}
          </CardContent>
        </Card>
      </section>

      <section className="grid gap-4 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Sparkles className="h-4 w-4 text-primary" />
              {t("What your village should know")}
            </CardTitle>
            <CardDescription>
              {t("Short answers from the latest data.")}
            </CardDescription>
          </CardHeader>
          <CardContent>
            {loading ? (
              <div className="text-sm text-muted-foreground">{t("loading")}</div>
            ) : insights.length ? (
              <ul className="space-y-3">
                {insights.map((ins, i) => {
                  const Icon = INSIGHT_ICONS[ins.type] ?? TrendingUp;
                  return (
                    <li key={i} className="flex items-start gap-3">
                      <span
                        aria-hidden
                        className={
                          ins.type === "stress"
                            ? "mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-amber-100 text-amber-700 dark:bg-amber-950 dark:text-amber-300"
                            : "mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-sky-100 text-sky-700 dark:bg-sky-950 dark:text-sky-300"
                        }
                      >
                        <Icon className="h-4 w-4" />
                      </span>
                      <span className="text-[15px] leading-relaxed">{ins.text}</span>
                    </li>
                  );
                })}
              </ul>
            ) : (
              <div className="text-sm text-muted-foreground">{t("No insights available.")}</div>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>{t("Explore groundwater data")}</CardTitle>
            <CardDescription>
              {t("Analytics, maps and reports across India.")}
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="flex flex-wrap gap-2">
              {(states.length ? states : []).slice(0, 8).map((s) => (
                <Badge key={s.id} variant="outline">
                  {s.name}
                </Badge>
              ))}
              {states.length > 8 && (
                <Badge variant="secondary">
                  {t("+{count} more", { count: states.length - 8 })}
                </Badge>
              )}
            </div>
            <div className="grid grid-cols-2 gap-3">
              <Button asChild variant="outline" size="lg" className="justify-start">
                <Link to="/assistant">
                  <Sparkles className="h-4 w-4" />
                  {t("Ask a question")}
                </Link>
              </Button>
              <Button asChild variant="outline" size="lg" className="justify-start">
                <Link to="/gis">
                  <MapIcon className="h-4 w-4" />
                  {t("GIS Map")}
                </Link>
              </Button>
              <Button asChild variant="outline" size="lg" className="justify-start">
                <Link to="/reports">
                  <FileText className="h-4 w-4" />
                  {t("nav_reports")}
                </Link>
              </Button>
              <Button asChild size="lg" className="justify-start">
                <Link to="/groundwater">
                  <ArrowRight className="h-4 w-4" />
                  {t("Analytics")}
                </Link>
              </Button>
            </div>
          </CardContent>
        </Card>
      </section>
    </div>
  );
}
