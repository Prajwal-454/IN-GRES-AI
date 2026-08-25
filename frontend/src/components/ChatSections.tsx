import {
  ArrowDownRight,
  ArrowRight,
  ArrowUpRight,
  CheckSquare,
  Lightbulb,
  LineChart,
  ListChecks,
  Map as MapIcon,
  Square,
  Table2,
  TrendingUp,
} from "lucide-react";
import { useEffect, useState } from "react";

import LayersMap, { type ActiveLayer } from "@/components/LayersMap";
import MiniChart from "@/components/MiniChart";
import { Badge } from "@/components/ui/badge";
import { useLanguage } from "@/contexts/LanguageContext";
import {
  analyzeLocation,
  getPrediction,
  getStations,
  type MapData,
  type Station,
} from "@/services/gis";
import type { RichSections } from "@/services/chat";

const METRIC_LABELS: Record<string, string> = {
  stage: "Stage of extraction",
  recharge: "Recharge",
  extraction: "Extraction",
  resource: "Annual extractable resource",
};

const CATEGORY_ORDER = ["Safe", "Semi-critical", "Critical", "Over-exploited"];

const MAP_LAYERS: { key: ActiveLayer; label: string }[] = [
  { key: "waterlevel", label: "Groundwater Level" },
  { key: "recharge", label: "Recharge" },
  { key: "extraction", label: "Extraction" },
  { key: "critical", label: "Critical Areas" },
  { key: "prediction", label: "Prediction" },
];

function Section({
  title,
  icon,
  children,
}: {
  title: string;
  icon: React.ReactNode;
  children: React.ReactNode;
}) {
  return (
    <div className="overflow-hidden rounded-xl border bg-muted/20">
      <div className="flex items-center gap-1.5 border-b bg-background/60 px-3 py-1.5 text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">
        {icon}
        {title}
      </div>
      <div className="p-3">{children}</div>
    </div>
  );
}

function Stat({
  label,
  value,
  unit,
  accent,
}: {
  label: string;
  value: string;
  unit?: string;
  accent?: boolean;
}) {
  return (
    <div
      className={
        accent
          ? "rounded-lg bg-primary/10 px-3 py-2"
          : "rounded-lg border bg-card px-3 py-2"
      }
    >
      <div className="text-[10px] uppercase tracking-wide text-muted-foreground">
        {label}
      </div>
      <div className="text-sm font-semibold text-foreground">
        {value}
        {unit && <span className="ml-1 text-[11px] font-normal text-muted-foreground">{unit}</span>}
      </div>
    </div>
  );
}

function fmt(value: number | null | undefined, decimals = 1): string {
  if (value === null || value === undefined) return "—";
  return value.toLocaleString(undefined, {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  });
}

function DirectionIcon({ direction }: { direction: string }) {
  if (direction === "rising") return <ArrowUpRight className="h-3.5 w-3.5 text-red-500" />;
  if (direction === "falling") return <ArrowDownRight className="h-3.5 w-3.5 text-emerald-500" />;
  return <ArrowRight className="h-3.5 w-3.5 text-muted-foreground" />;
}

export default function ChatSections({ sections }: { sections: RichSections }) {
  const { t } = useLanguage();
  const d = sections.data;
  const graph = sections.graph;
  const metricLabel = METRIC_LABELS[graph?.metric ?? "stage"] ?? "Stage of extraction";

  const map = sections.map;
  const [layer, setLayer] = useState<ActiveLayer>("waterlevel");
  const [stationsOn, setStationsOn] = useState(false);
  const [heatOn, setHeatOn] = useState(false);
  const [prediction, setPrediction] = useState<MapData | null>(null);
  const [stations, setStations] = useState<Station[]>([]);

  useEffect(() => {
    if (!map || layer !== "prediction" || prediction) return;
    let active = true;
    getPrediction({
      state: map.state ?? undefined,
      district: map.district ?? undefined,
      village: map.village ?? undefined,
      target_year: (map.year ?? 2022) + 5,
    })
      .then((d) => active && setPrediction(d))
      .catch(() => undefined);
    return () => {
      active = false;
    };
  }, [map, layer, prediction]);

  useEffect(() => {
    if (!map || !stationsOn || stations.length) return;
    let active = true;
    getStations({
      state: map.state ?? undefined,
      district: map.district ?? undefined,
      village: map.village ?? undefined,
    })
      .then((s) => active && setStations(s))
      .catch(() => undefined);
    return () => {
      active = false;
    };
  }, [map, stationsOn, stations]);

  const hasRanking = d.ranking && d.ranking.length > 0;

  return (
    <div className="mt-3 space-y-3">
      {d && (
        <Section title={t("Data")} icon={<Table2 className="h-3 w-3" />}>
          <div className="mb-1 text-[11px] text-muted-foreground">
            {d.scope}
            {d.year ? ` · ${d.year}` : ""}
          </div>
          <div className="grid grid-cols-2 gap-2 sm:grid-cols-3">
            <Stat label={t("recharge")} value={fmt(d.recharge)} unit="hm³" />
            <Stat label={t("extraction")} value={fmt(d.extraction)} unit="hm³" />
            <Stat label={t("stage_of_extraction")} value={fmt(d.stage)} unit="%" accent />
            <Stat label={t("annual_extractable_resource")} value={fmt(d.resource)} unit="hm³" />
            <Stat label={t("category")} value={d.category ?? "—"} />
            <Stat
              label={t("assessment_units")}
              value={d.assessment_units ? d.assessment_units.toLocaleString() : "—"}
            />
          </div>
          {Object.keys(d.category_counts ?? {}).length > 0 && (
            <div className="mt-2 flex flex-wrap gap-1.5">
              {CATEGORY_ORDER.filter((c) => d.category_counts?.[c]).map((c) => (
                <Badge key={c} variant="outline" className="text-[10px]">
                  {c}: {d.category_counts![c]}
                </Badge>
              ))}
            </div>
          )}
          {hasRanking && (
            <div className="mt-3">
              <div className="mb-1 text-[11px] font-semibold text-muted-foreground">
                {t("top_districts_by_stage")}
              </div>
              <div className="space-y-1">
                {d.ranking.map((r, i) => (
                  <div
                    key={r.name}
                    className="flex items-center justify-between gap-2 rounded-lg bg-card px-3 py-1.5 text-sm"
                  >
                    <span className="flex min-w-0 items-center gap-2">
                      <span className="w-4 shrink-0 text-right text-[11px] text-muted-foreground">
                        {i + 1}
                      </span>
                      <span className="truncate">{r.name}</span>
                    </span>
                    <span className="flex shrink-0 items-center gap-2">
                      <span className="text-xs font-semibold">{fmt(r.stage)}%</span>
                      <Badge
                        variant="outline"
                        className="text-[10px]"
                      >
                        {r.category ?? "—"}
                      </Badge>
                    </span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </Section>
      )}

      {map && (
        <Section title={t("Layers")} icon={<MapIcon className="h-3 w-3" />}>
          <div className="flex flex-wrap gap-1">
            {MAP_LAYERS.map((l) => (
              <button
                key={l.key}
                type="button"
                onClick={() => setLayer(l.key)}
                className="inline-flex items-center gap-1 rounded-md px-2 py-1 text-xs text-muted-foreground transition-colors hover:bg-accent hover:text-foreground"
              >
                {layer === l.key ? (
                  <CheckSquare className="h-3.5 w-3.5 shrink-0 text-primary" />
                ) : (
                  <Square className="h-3.5 w-3.5 shrink-0 text-muted-foreground" />
                )}
                <span>{t(l.label)}</span>
              </button>
            ))}
            <button
              type="button"
              onClick={() => setStationsOn((s) => !s)}
              className="inline-flex items-center gap-1 rounded-md px-2 py-1 text-xs text-muted-foreground transition-colors hover:bg-accent hover:text-foreground"
            >
              {stationsOn ? (
                <CheckSquare className="h-3.5 w-3.5 shrink-0 text-primary" />
              ) : (
                <Square className="h-3.5 w-3.5 shrink-0 text-muted-foreground" />
              )}
              <span>{t("Monitoring Stations")}</span>
            </button>
            <button
              type="button"
              onClick={() => setHeatOn((h) => !h)}
              className="inline-flex items-center gap-1 rounded-md px-2 py-1 text-xs text-muted-foreground transition-colors hover:bg-accent hover:text-foreground"
            >
              {heatOn ? (
                <CheckSquare className="h-3.5 w-3.5 shrink-0 text-primary" />
              ) : (
                <Square className="h-3.5 w-3.5 shrink-0 text-muted-foreground" />
              )}
              <span>{t("Heatmap")}</span>
            </button>
          </div>
          <LayersMap
            features={map.features}
            india={map.india ?? undefined}
            prediction={prediction ?? undefined}
            stations={stations}
            activeLayer={layer}
            stationsOn={stationsOn}
            heatOn={heatOn}
            onAnalyze={analyzeLocation}
            className="mt-2 h-[300px]"
          />
          <p className="mt-1.5 text-center text-[10px] text-muted-foreground">
            {t("Click the map to analyze any location.")}
          </p>
        </Section>
      )}

      {graph && graph.series.length > 0 && (
        <Section title={t("Trend")} icon={<LineChart className="h-3 w-3" />}>
          <MiniChart
            series={graph.series}
            comparison={graph.comparison}
            forecast={graph.forecast}
            scenarioForecast={graph.scenario_forecast}
            unit={graph.unit}
            metricLabel={metricLabel}
          />
        </Section>
      )}

      {sections.prediction && (
        <Section title={t("Prediction")} icon={<TrendingUp className="h-3 w-3" />}>
          <div className="mb-2 flex flex-wrap items-center gap-1.5">
            <Badge variant="secondary" className="text-[10px]">
              <DirectionIcon direction={sections.prediction.direction} />
              <span className="ml-1">{t(sections.prediction.direction)}</span>
            </Badge>
            {sections.prediction.pct_change != null && (
              <Badge variant="outline" className="text-[10px]">
                {sections.prediction.pct_change >= 0 ? "+" : ""}
                {sections.prediction.pct_change.toFixed(1)}%
              </Badge>
            )}
            {sections.prediction.method && (
              <Badge variant="outline" className="text-[10px]">
                {t("Model")}: {sections.prediction.method}
              </Badge>
            )}
            {sections.prediction.r2 != null && (
              <Badge variant="outline" className="text-[10px]">
                R²: {sections.prediction.r2.toFixed(3)}
              </Badge>
            )}
            {sections.prediction.risk && (
              <Badge variant="warning" className="text-[10px]">
                {sections.prediction.risk}
              </Badge>
            )}
          </div>
          <div className="overflow-hidden rounded-lg border">
            <table className="w-full text-left text-xs">
              <thead className="bg-muted/40 text-[10px] uppercase tracking-wide text-muted-foreground">
                <tr>
                  <th className="px-3 py-1.5 font-medium">{t("year")}</th>
                  <th className="px-3 py-1.5 font-medium">{metricLabel}</th>
                  <th className="px-3 py-1.5 font-medium">{t("confidence_band")}</th>
                </tr>
              </thead>
              <tbody>
                {sections.prediction.points.map((p) => (
                  <tr key={p.year} className="border-t">
                    <td className="px-3 py-1.5">{p.year}</td>
                    <td className="px-3 py-1.5 font-semibold">
                      {fmt(p.value)} {sections.prediction!.unit}
                    </td>
                    <td className="px-3 py-1.5 text-muted-foreground">
                      {fmt(p.lower)} – {fmt(p.upper)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Section>
      )}

      {sections.explanation && (
        <Section title={t("Explanation")} icon={<Lightbulb className="h-3 w-3" />}>
          <p className="text-sm leading-relaxed text-muted-foreground">
            {sections.explanation}
          </p>
        </Section>
      )}

      {sections.recommendation && sections.recommendation.length > 0 && (
        <Section title={t("Recommendations")} icon={<ListChecks className="h-3 w-3" />}>
          <ul className="space-y-1.5">
            {sections.recommendation.map((rec, i) => (
              <li key={i} className="flex gap-2 text-sm">
                <span className="mt-0.5 shrink-0 text-primary">•</span>
                <span>{rec}</span>
              </li>
            ))}
          </ul>
        </Section>
      )}
    </div>
  );
}