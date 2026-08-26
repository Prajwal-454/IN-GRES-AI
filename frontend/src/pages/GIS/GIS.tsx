import { CheckSquare, Info, Loader2, Map as MapIcon, Square } from "lucide-react";
import { useEffect, useState } from "react";

import GoogleMapView from "@/components/GoogleMapView";
import LayersMap, { RAMP_CSS, type ActiveLayer } from "@/components/LayersMap";
import LeafletMap from "@/components/LeafletMap";
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
  analyzeLocation,
  getBasinMap,
  getCompare,
  getIndiaCompare,
  getIndiaMap,
  getMap,
  getPrediction,
  getStations,
  type BasinMapData,
  type CompareData,
  type IndiaCompareData,
  type IndiaMapData,
  type MapData,
  type MapFeature,
  type Station,
} from "@/services/gis";
import { fetchDistricts, fetchVillages } from "@/services/groundwater";
import type { GroundwaterDistrict, GroundwaterVillage } from "@/types";

const METRIC_LABELS: Record<string, string> = {
  stage: "Stage of extraction",
  recharge: "Recharge",
  extraction: "Extraction",
  resource: "Extractable resource",
};

const LAYER_DEFS: { key: ActiveLayer; label: string }[] = [
  { key: "waterlevel", label: "Groundwater Level" },
  { key: "recharge", label: "Recharge" },
  { key: "extraction", label: "Extraction" },
  { key: "critical", label: "Critical Areas" },
  { key: "prediction", label: "Prediction" },
];

const GOOGLE_MAPS_KEY = import.meta.env.VITE_GOOGLE_MAPS_API_KEY as string | undefined;

export interface MapLocate {
  state?: string;
  district?: string;
  village?: string;
}

export default function GIS() {
  const { t } = useLanguage();
  const [view, setView] = useState<"india" | "units" | "basins">("india");
  const [data, setData] = useState<MapData | null>(null);
  const [india, setIndia] = useState<IndiaMapData | null>(null);
  const [basinData, setBasinData] = useState<BasinMapData | null>(null);
  const [compareData, setCompareData] = useState<CompareData | null>(null);
  const [indiaCompare, setIndiaCompare] = useState<IndiaCompareData | null>(null);
  const [state, setState] = useState("");
  const [district, setDistrict] = useState("");
  const [village, setVillage] = useState("");
  const [districts, setDistricts] = useState<GroundwaterDistrict[]>([]);
  const [villages, setVillages] = useState<GroundwaterVillage[]>([]);
  const [year, setYear] = useState("");
  const [yearB, setYearB] = useState("");
  const [metric, setMetric] = useState("stage");
  const [compareMode, setCompareMode] = useState(false);
  const [playing, setPlaying] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [activeLayer, setActiveLayer] = useState<ActiveLayer>("waterlevel");
  const [stationsOn, setStationsOn] = useState(false);
  const [stations, setStations] = useState<Station[]>([]);
  const [prediction, setPrediction] = useState<MapData | null>(null);

  const latestYear = data?.meta.year ?? india?.meta.year ?? 0;

  function layerLegend(layer: ActiveLayer) {
    if (layer === "critical" || layer === "prediction") {
      return (
        <>
          {layer === "prediction" && (
            <p className="text-xs text-muted-foreground">{t("Predicted category")}</p>
          )}
          {[
            ["safe", "#1a9850", "Safe (<70%)"],
            ["semi-critical", "#fdae61", "Semi-critical (70–90%)"],
            ["critical", "#f46d43", "Critical (90–100%)"],
            ["over-exploited", "#d73027", "Over-exploited (>100%)"],
          ].map(([key, color, label]) => (
            <div key={key} className="flex items-center gap-2">
              <span className="h-3 w-3 rounded-sm" style={{ backgroundColor: color }} />
              <span className="text-muted-foreground">{t(label)}</span>
            </div>
          ))}
          {layer === "prediction" && (
            <p className="text-xs text-muted-foreground">
              {t("Forecast to {year}", { year: latestYear ? latestYear + 5 : "" })} ·{" "}
              {t("Statistical projection · not official data")}
            </p>
          )}
        </>
      );
    }
    if (layer === "waterlevel") {
      return (
        <>
          <div className="h-3 w-full rounded-sm" style={{ background: RAMP_CSS }} />
          <div className="flex justify-between text-xs text-muted-foreground">
            <span>{t("Shallow")}</span>
            <span>{t("Deep")}</span>
          </div>
          <p className="text-xs text-muted-foreground">
            1.2 m → 11.2 m · derived from stage of extraction
          </p>
        </>
      );
    }
    return (
      <>
        <div className="h-3 w-full rounded-sm" style={{ background: RAMP_CSS }} />
        <p className="text-xs text-muted-foreground">{t("Low → high value (hm³)")}</p>
      </>
    );
  }

  useEffect(() => {
    let active = true;
    setLoading(true);
    setError(null);
    if (compareMode) {
      const params = {
        metric,
        year_a: year ? Number(year) : undefined,
        year_b: yearB ? Number(yearB) : undefined,
      };
      const request =
        view === "india"
          ? getIndiaCompare(params)
          : getCompare({
              ...params,
              state: state || undefined,
              district: district || undefined,
              village: village || undefined,
            });
      request
        .then((d) => {
          if (!active) return;
          if (view === "india") setIndiaCompare(d as IndiaCompareData);
          else setCompareData(d as CompareData);
        })
        .catch(() => active && setError(t("Failed to load map data.")))
        .finally(() => active && setLoading(false));
      return () => {
        active = false;
      };
    }
    const params = { year: year ? Number(year) : undefined, metric };
    let request: Promise<unknown>;
    if (view === "basins") {
      request = getBasinMap(params);
    } else if (view === "india") {
      request = getIndiaMap(params);
    } else {
      request = getMap({
        ...params,
        state: state || undefined,
        district: district || undefined,
        village: village || undefined,
      });
    }
    request
      .then((d) => {
        if (!active) return;
        if (view === "basins") setBasinData(d as BasinMapData);
        else if (view === "india") setIndia(d as IndiaMapData);
        else setData(d as MapData);
      })
      .catch(() => active && setError(t("Failed to load map data.")))
      .finally(() => active && setLoading(false));
    return () => {
      active = false;
    };
  }, [view, state, district, village, year, yearB, metric, compareMode]);

  useEffect(() => {
    if (!playing) return;
    const years = data?.meta.years ?? india?.meta.years ?? basinData?.meta.years ?? [];
    if (years.length < 2) return;
    const id = setInterval(() => {
      setYear((prev) => {
        const cur = prev ? Number(prev) : years[years.length - 1];
        const idx = years.indexOf(cur);
        return String(years[(idx + 1) % years.length]);
      });
    }, 900);
    return () => clearInterval(id);
  }, [playing, data, india, basinData]);

  const years = data?.meta.years ?? india?.meta.years ?? basinData?.meta.years ?? [];

  useEffect(() => {
    setDistrict("");
    setVillage("");
    if (!state || view !== "units") {
      setDistricts([]);
      setVillages([]);
      return;
    }
    let active = true;
    fetchDistricts(state)
      .then((d) => active && setDistricts(d))
      .catch(() => active && setDistricts([]));
    return () => {
      active = false;
    };
  }, [state, view]);

  useEffect(() => {
    setVillage("");
    if (!state || !district || view !== "units") {
      setVillages([]);
      return;
    }
    let active = true;
    fetchVillages(state, district)
      .then((v) => active && setVillages(v))
      .catch(() => active && setVillages([]));
    return () => {
      active = false;
    };
  }, [state, district, view]);

  useEffect(() => {
    let active = true;
    getStations({
      state: state || undefined,
      district: district || undefined,
      village: village || undefined,
    })
      .then((s) => active && setStations(s))
      .catch(() => active && setStations([]));
    return () => {
      active = false;
    };
  }, [state, district, village]);

  useEffect(() => {
    if (compareMode || activeLayer !== "prediction" || view === "basins") {
      setPrediction(null);
      return;
    }
    let active = true;
    getPrediction({
      state: state || undefined,
      district: district || undefined,
      village: village || undefined,
      year: year ? Number(year) : undefined,
      target_year: latestYear ? latestYear + 5 : undefined,
    })
      .then((p) => active && setPrediction(p))
      .catch(() => active && setPrediction(null));
    return () => {
      active = false;
    };
  }, [compareMode, activeLayer, state, district, village, year, latestYear]);

  const allUnits = view === "india" ? (india?.units.features ?? []) : (data?.features ?? []);
  const visibleUnits = state
    ? allUnits.filter((f) => f.properties.state.toLowerCase() === state.toLowerCase())
    : allUnits;
  const basinFeatures = (basinData?.features ?? []) as unknown as MapFeature[];
  const units = view === "basins" ? basinFeatures.length : visibleUnits.length;
  const stageValues = (view === "basins" ? basinFeatures : visibleUnits)
    .map((f) => f.properties.stage_of_extraction)
    .filter((v): v is number => v !== null && v !== undefined);
  const avgStage = stageValues.length
    ? stageValues.reduce((s, v) => s + v, 0) / stageValues.length
    : 0;
  const overExploited = (view === "basins" ? basinFeatures : visibleUnits).filter(
    (f) => f.properties.category === "over-exploited"
  ).length;

  const compareFeatures = compareMode
    ? view === "india"
      ? indiaCompare?.features ?? []
      : compareData?.features ?? []
    : [];
  const unitsCompared = compareMode
    ? view === "india"
      ? compareFeatures.reduce(
          (s, f) => s + ((f.properties as { unit_count?: number }).unit_count ?? 0),
          0
        )
      : compareFeatures.length
    : units;
  const categoryChanges = compareMode
    ? compareFeatures.filter((f) => f.properties.category_changed).length
    : 0;
  const compareDeltas = compareFeatures
    .map((f) => f.properties.delta)
    .filter((v): v is number => v !== null && v !== undefined);
  const avgDelta = compareDeltas.length
    ? compareDeltas.reduce((s, v) => s + v, 0) / compareDeltas.length
    : 0;

  return (
    <div className="mx-auto max-w-6xl space-y-6">
      <section className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="flex items-center gap-2 text-2xl font-bold">
            <MapIcon className="h-6 w-6 text-primary" />
            {t("nav_gis")}
          </h2>
          <p className="mt-1 text-muted-foreground">
            {t(
              "Full-India map of all states and union territories with the IN-GRES national dataset."
            )}
          </p>
        </div>
        <Badge variant="warning">{t("demo_data")}</Badge>
      </section>

      <Card>
        <CardHeader>
          <CardTitle className="text-sm">{t("Map filters")}</CardTitle>
        </CardHeader>
        <CardContent className="grid gap-4 sm:grid-cols-4">
          <div className="space-y-1.5">
            <label className="text-sm font-medium">{t("View")}</label>
            <div className="flex overflow-hidden rounded-md border">
              <button
                type="button"
                onClick={() => setView("india")}
                className={`flex-1 px-3 py-1.5 text-sm ${
                  view === "india"
                    ? "bg-primary text-primary-foreground"
                    : "bg-background text-muted-foreground hover:bg-accent"
                }`}
              >
                {t("All India")}
              </button>
              <button
                type="button"
                onClick={() => setView("units")}
                className={`flex-1 px-3 py-1.5 text-sm ${
                  view === "units"
                    ? "bg-primary text-primary-foreground"
                    : "bg-background text-muted-foreground hover:bg-accent"
                }`}
              >
                {t("units")}
              </button>
              <button
                type="button"
                onClick={() => setView("basins")}
                className={`flex-1 px-3 py-1.5 text-sm ${
                  view === "basins"
                    ? "bg-primary text-primary-foreground"
                    : "bg-background text-muted-foreground hover:bg-accent"
                }`}
              >
                {t("basins")}
              </button>
            </div>
          </div>
          {compareMode && (
            <div className="space-y-1.5">
              <label className="text-sm font-medium">{t("metric")}</label>
              <Select value={metric} onChange={(e) => setMetric(e.target.value)}>
                {Object.entries(METRIC_LABELS).map(([k, v]) => (
                  <option key={k} value={k}>
                    {t(v)}
                  </option>
                ))}
              </Select>
            </div>
          )}
          {view !== "basins" && (
            <div className="space-y-1.5">
              <label className="text-sm font-medium">{t("state")}</label>
              <Select value={state} onChange={(e) => setState(e.target.value)}>
                <option value="">{t("all_states")}</option>
                {(data?.meta.states ?? india?.meta.states ?? []).map((s) => (
                  <option key={s} value={s}>
                    {s}
                  </option>
                ))}
              </Select>
            </div>
          )}
          {view === "units" && state && (
            <div className="space-y-1.5">
              <label className="text-sm font-medium">{t("district")}</label>
              <Select
                value={district}
                onChange={(e) => setDistrict(e.target.value)}
                disabled={!districts.length}
              >
                <option value="">{t("all_districts")}</option>
                {districts.map((d) => (
                  <option key={d.id} value={d.name}>
                    {d.name}
                  </option>
                ))}
              </Select>
            </div>
          )}
          {view === "units" && state && district && (
            <div className="space-y-1.5">
              <label className="text-sm font-medium">{t("Village")}</label>
              <Select
                value={village}
                onChange={(e) => setVillage(e.target.value)}
                disabled={!villages.length}
              >
                <option value="">{t("All villages")}</option>
                {villages.map((v) => (
                  <option key={v.id} value={v.name}>
                    {v.name}
                  </option>
                ))}
              </Select>
            </div>
          )}
          <div className="space-y-1.5">
            <label className="text-sm font-medium">{t("year")}</label>
            <Select value={year} onChange={(e) => setYear(e.target.value)}>
              <option value="">
                {t("Latest ({year})", { year: data?.meta.year ?? india?.meta.year ?? basinData?.meta.year })}
              </option>
              {(data?.meta.years ?? india?.meta.years ?? basinData?.meta.years ?? []).map((y) => (
                <option key={y} value={y}>
                  {y}
                </option>
              ))}
            </Select>
          </div>
          <div className="mt-4 space-y-3 border-t pt-4 sm:col-span-4">
            <button
              type="button"
              onClick={() => {
                setPlaying(false);
                setCompareMode((c) => !c);
              }}
              className={`rounded-md border px-3 py-1.5 text-sm font-medium ${
                compareMode
                  ? "border-primary bg-primary text-primary-foreground"
                  : "bg-background text-muted-foreground hover:bg-accent"
              }`}
            >
              {t("Compare years")}
            </button>
            {compareMode ? (
              <div className="flex flex-wrap items-end gap-4">
                <div className="space-y-1.5">
                  <label className="text-sm font-medium">{t("From")}</label>
                  <Select value={year} onChange={(e) => setYear(e.target.value)}>
                    <option value="">{years.length ? years[0] : ""}</option>
                    {years.map((y) => (
                      <option key={y} value={y}>
                        {y}
                      </option>
                    ))}
                  </Select>
                </div>
                <div className="space-y-1.5">
                  <label className="text-sm font-medium">{t("To")}</label>
                  <Select value={yearB} onChange={(e) => setYearB(e.target.value)}>
                    <option value="">
                      {t("Latest ({year})", {
                        year: data?.meta.year ?? india?.meta.year ?? basinData?.meta.year ?? "",
                      })}
                    </option>
                    {years.map((y) => (
                      <option key={y} value={y}>
                        {y}
                      </option>
                    ))}
                  </Select>
                </div>
              </div>
            ) : years.length > 1 ? (
              <div className="flex flex-wrap items-center gap-x-3 gap-y-2">
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => setPlaying((p) => !p)}
                  aria-pressed={playing}
                >
                  {playing ? t("Pause") : t("Play time-lapse")}
                </Button>
                <input
                  type="range"
                  min={years[0]}
                  max={years[years.length - 1]}
                  step={1}
                  value={(Number(year) || (data?.meta.year ?? india?.meta.year)) ?? years[0]}
                  onChange={(e) => {
                    setPlaying(false);
                    setYear(e.target.value);
                  }}
                  className="h-2 min-w-40 max-w-full flex-1 basis-48 accent-primary"
                  aria-label={t("year")}
                />
                <span className="w-14 shrink-0 text-right text-sm tabular-nums">
                  {(Number(year) || (data?.meta.year ?? india?.meta.year)) ?? years[0]}
                </span>
              </div>
            ) : null}
          </div>
        </CardContent>
      </Card>

      {!compareMode && (
        <Card>
          <CardHeader>
            <CardTitle className="text-sm">{t("Layers")}</CardTitle>
            <CardDescription>
              {t("Click the map to analyze any location.")}
            </CardDescription>
          </CardHeader>
          <CardContent className="grid gap-6 sm:grid-cols-[1fr_1.2fr]">
            <div className="space-y-1">
              {LAYER_DEFS.map((l) => (
                <button
                  key={l.key}
                  type="button"
                  onClick={() => setActiveLayer(l.key)}
                  className="flex w-full items-center gap-2 rounded-md px-2 py-1.5 text-left text-sm hover:bg-accent"
                >
                  {activeLayer === l.key ? (
                    <CheckSquare className="h-4 w-4 shrink-0 text-primary" />
                  ) : (
                    <Square className="h-4 w-4 shrink-0 text-muted-foreground" />
                  )}
                  <span>{t(l.label)}</span>
                </button>
              ))}
              <div className="border-t pt-2">
                <button
                  type="button"
                  onClick={() => setStationsOn((s) => !s)}
                  className="flex w-full items-center gap-2 rounded-md px-2 py-1.5 text-left text-sm hover:bg-accent"
                >
                  {stationsOn ? (
                    <CheckSquare className="h-4 w-4 shrink-0 text-primary" />
                  ) : (
                    <Square className="h-4 w-4 shrink-0 text-muted-foreground" />
                  )}
                  <span>{t("Monitoring Stations")}</span>
                </button>
              </div>
            </div>
            <div className="space-y-2 text-sm">{layerLegend(activeLayer)}</div>
          </CardContent>
        </Card>
      )}

      {error && (
        <div className="rounded-md border border-destructive/30 bg-destructive/10 p-4 text-sm text-destructive">
          {error}
        </div>
      )}

      {loading ? (
        <div className="flex items-center justify-center gap-2 py-16 text-sm text-muted-foreground">
          <Loader2 className="h-4 w-4 animate-spin" />
          {t("loading")}
        </div>
      ) : compareMode ? (
        compareData || indiaCompare ? (
          <>
            <section className="grid gap-4 sm:grid-cols-3">
              <Card>
                <CardHeader>
                  <CardDescription>{t("Units compared")}</CardDescription>
                  <CardTitle className="text-3xl">{unitsCompared}</CardTitle>
                </CardHeader>
              </Card>
              <Card>
                <CardHeader>
                  <CardDescription>{t("Category changes")}</CardDescription>
                  <CardTitle className="text-3xl">{categoryChanges}</CardTitle>
                </CardHeader>
              </Card>
              <Card>
                <CardHeader>
                  <CardDescription>{t("Avg change")}</CardDescription>
                  <CardTitle className="text-3xl">
                    {avgDelta !== 0
                      ? `${avgDelta > 0 ? "+" : ""}${avgDelta.toFixed(1)}${metric === "stage" ? "%" : " hm³"}`
                      : "—"}
                  </CardTitle>
                </CardHeader>
              </Card>
            </section>

            <div className="grid gap-4 lg:grid-cols-3">
              <Card className="lg:col-span-2">
                <CardHeader>
                  <CardTitle>
                    {view === "india"
                      ? t("All India — change between {a} and {b}", {
                          a: compareData?.meta.year_a ?? indiaCompare?.meta.year_a ?? "",
                          b: compareData?.meta.year_b ?? indiaCompare?.meta.year_b ?? "",
                        })
                      : t("Change over time")}
                  </CardTitle>
                  <CardDescription>
                    {(compareData?.meta.year_a ?? indiaCompare?.meta.year_a) ?? ""} →{" "}
                    {(compareData?.meta.year_b ?? indiaCompare?.meta.year_b) ?? ""} ·{" "}
                    {view === "india" ? t("36 states & UTs") : state || t("both states")}
                  </CardDescription>
                </CardHeader>
                <CardContent>
                  {GOOGLE_MAPS_KEY ? (
                    <GoogleMapView
                      features={
                        (view === "india" ? [] : compareData?.features ?? []) as MapFeature[]
                      }
                      metric={metric}
                      apiKey={GOOGLE_MAPS_KEY}
                      india={
                        view === "india"
                          ? (indiaCompare as unknown as IndiaMapData | undefined)
                          : undefined
                      }
                      compare
                    />
                  ) : (
                    <LeafletMap
                      features={
                        (view === "india" ? [] : compareData?.features ?? []) as MapFeature[]
                      }
                      metric={metric}
                      india={
                        view === "india"
                          ? (indiaCompare as unknown as IndiaMapData | undefined)
                          : undefined
                      }
                      compare
                    />
                  )}
                </CardContent>
              </Card>

              <Card>
                <CardHeader>
                  <CardTitle className="text-sm">{t("Legend")}</CardTitle>
                </CardHeader>
                <CardContent className="space-y-2 text-sm">
                  <div className="h-3 w-full rounded-sm" style={{ background: RAMP_CSS }} />
                  <div className="flex justify-between text-xs text-muted-foreground">
                    <span>{t("Improved")}</span>
                    <span>{t("No change")}</span>
                    <span>{t("Worsened")}</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <span className="h-3 w-3 rounded-sm" style={{ backgroundColor: "#e5e7eb" }} />
                    <span className="text-muted-foreground">{t("No data available for this selection")}</span>
                  </div>
                  <div className="mt-4 flex gap-2 text-xs text-muted-foreground">
                    <Info className="h-4 w-4 shrink-0" />
                    {t("Click a state or unit to see its change between the two years.")}
                  </div>
                </CardContent>
              </Card>
            </div>

            <Button
              variant="outline"
              onClick={() => {
                setState("");
                setDistrict("");
                setVillage("");
                setYear("");
                setYearB("");
                setMetric("stage");
                setView("india");
                setCompareMode(false);
                setActiveLayer("waterlevel");
                setStationsOn(false);
              }}
            >
              {t("Reset map")}
            </Button>
          </>
        ) : null
      ) : data || india || basinData ? (
        <>
          <section className="grid gap-4 sm:grid-cols-3">
            <Card>
              <CardHeader>
                <CardDescription>{view === "basins" ? t("basins") : t("units")}</CardDescription>
                <CardTitle className="text-3xl">{units}</CardTitle>
              </CardHeader>
            </Card>
            <Card>
              <CardHeader>
                <CardDescription>{t("Avg stage of extraction")}</CardDescription>
                <CardTitle className="text-3xl">
                  {avgStage ? `${avgStage.toFixed(1)}%` : "—"}
                </CardTitle>
              </CardHeader>
            </Card>
            <Card>
              <CardHeader>
                <CardDescription>
                  {view === "basins" ? t("Over-exploited basins") : t("Over-exploited units")}
                </CardDescription>
                <CardTitle className="text-3xl text-destructive">{overExploited}</CardTitle>
              </CardHeader>
            </Card>
          </section>

          <div className="grid gap-4 lg:grid-cols-3">
            <Card className="lg:col-span-2">
              <CardHeader>
                <CardTitle>
                  {view === "india"
                    ? t("All India — groundwater overview")
                    : view === "basins"
                      ? t("River basins — groundwater overview")
                      : t(LAYER_DEFS.find((l) => l.key === activeLayer)?.label ?? "Groundwater Level")}
                </CardTitle>
                <CardDescription>
                  {(data?.meta.year ?? india?.meta.year ?? basinData?.meta.year)} ·{" "}
                  {view === "india"
                    ? t("36 states & UTs")
                    : view === "basins"
                      ? t("20 CWC river basins")
                      : state || t("both states")}{" "}
                  ·{" "}
                  {t(
                    view === "basins"
                      ? METRIC_LABELS[metric] ?? metric
                      : LAYER_DEFS.find((l) => l.key === activeLayer)?.label ?? "Groundwater Level"
                  )}
                </CardDescription>
              </CardHeader>
              <CardContent>
                <LayersMap
                  features={view === "basins" ? basinFeatures : visibleUnits}
                  india={view === "india" ? india ?? undefined : undefined}
                  prediction={prediction ?? undefined}
                  stations={stations}
                  activeLayer={activeLayer}
                  stationsOn={stationsOn}
                  onAnalyze={async (lat, lng) => analyzeLocation(lat, lng)}
                />
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle className="text-sm">{t("Legend")}</CardTitle>
              </CardHeader>
              <CardContent className="space-y-2 text-sm">
                {layerLegend(activeLayer)}
                {view === "india" && (
                  <div className="flex items-center gap-2">
                    <span
                      className="h-3 w-3 rounded-sm"
                      style={{ backgroundColor: "#e5e7eb" }}
                    />
                    <span className="text-muted-foreground">
                      {t("No data available for this selection")}
                    </span>
                  </div>
                )}
                <div className="mt-4 flex gap-2 text-xs text-muted-foreground">
                  <Info className="h-4 w-4 shrink-0" />
                  {t("Click the map to analyze any location.")}
                </div>
              </CardContent>
            </Card>
          </div>

          <Button
            variant="outline"
            onClick={() => {
              setState("");
              setDistrict("");
              setVillage("");
              setYear("");
              setYearB("");
              setMetric("stage");
              setView("india");
              setCompareMode(false);
              setPlaying(false);
              setActiveLayer("waterlevel");
              setStationsOn(false);
            }}
          >
            {t("Reset map")}
          </Button>
        </>
      ) : null}
    </div>
  );
}
