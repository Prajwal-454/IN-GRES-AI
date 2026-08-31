import {
  Activity,
  Cloud,
  CloudSun,
  Crosshair,
  Droplets,
  Info,
  Layers,
  Loader2,
  Map as MapIcon,
  MapPin,
  Minus,
  Navigation,
  Pause,
  Play,
  Plus,
  Radar,
  Search,
  Settings2,
  SkipBack,
  SkipForward,
  Thermometer,
  Wind,
  X,
} from "lucide-react";
import L from "leaflet";
import "leaflet/dist/leaflet.css";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { useLanguage } from "@/contexts/LanguageContext";
import { cn } from "@/lib/utils";
import { getApiError } from "@/services/api";
import { getMap, type MapData } from "@/services/gis";
import {
  fetchPointWeather,
  fetchWeatherMapSeries,
  searchLocations,
  type MapSearchResult,
  type WeatherMapSeries,
} from "@/services/map";
import WeatherAnimation, { sampleWeatherAt, type AnimSettings } from "@/components/WeatherAnimation";
import CityLabels from "@/components/CityLabels";
import WeatherCharts from "@/components/WeatherCharts";
import {
  formatCoords,
  scaleColor,
  STOPS,
  UNITS,
  weatherLabel,
  type Metric,
  type MetricValue,
} from "@/lib/weatherLayer";

type GwMetric = "waterlevel" | "recharge" | "extraction" | "critical";

type WeatherMode = "current" | "radar" | "forecast" | "historical";

interface LayerDef {
  key: MetricValue;
  label: string;
  icon: typeof Droplets;
}

const LAYERS: LayerDef[] = [
  { key: "none", label: "None", icon: MapIcon },
  { key: "temperature", label: "Temperature", icon: Thermometer },
  { key: "rain", label: "Rain", icon: Droplets },
  { key: "wind", label: "Wind", icon: Wind },
  { key: "humidity", label: "Humidity", icon: Droplets },
  { key: "clouds", label: "Clouds", icon: Cloud },
  { key: "aqi", label: "Air quality", icon: Activity },
];

const GW_LAYERS: { key: GwMetric; label: string }[] = [
  { key: "waterlevel", label: "Groundwater Level" },
  { key: "recharge", label: "Recharge" },
  { key: "extraction", label: "Extraction" },
  { key: "critical", label: "Critical Areas" },
];

const MODES: { key: WeatherMode; label: string; icon: typeof Radar }[] = [
  { key: "current", label: "Current", icon: CloudSun },
  { key: "radar", label: "Radar", icon: Radar },
  { key: "forecast", label: "Forecast", icon: SkipForward },
  { key: "historical", label: "Historical", icon: Info },
];

const CATEGORY_COLORS: Record<string, string> = {
  safe: "#16a34a",
  "semi-critical": "#eab308",
  critical: "#f97316",
  "over-exploited": "#dc2626",
};

const NO_DATA_COLOR = "#e5e7eb";

const BASE_MAPS: {
  key: string;
  label: string;
  url: string;
  subdomains?: string;
  className?: string;
}[] = [
  {
    key: "relief",
    label: "Relief",
    url: "https://server.arcgisonline.com/ArcGIS/rest/services/Elevation/World_Hillshade/MapServer/tile/{z}/{y}/{x}",
    className: "ingres-relief",
  },
  {
    key: "light",
    label: "Light",
    url: "https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png",
    className: "ingres-light",
  },
  {
    key: "dark",
    label: "Dark",
    url: "https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png",
    className: "ingres-dark",
  },
  {
    key: "street",
    label: "Street",
    url: "https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png",
  },
  {
    key: "terrain",
    label: "Terrain",
    url: "https://{s}.tile.opentopomap.org/{z}/{x}/{y}.png",
  },
  {
    key: "satellite",
    label: "Satellite",
    url: "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
  },
  {
    key: "hybrid",
    label: "Hybrid",
    url: "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
  },
];

function waterDepthFromStage(stage: number | null | undefined): number | null {
  if (stage === null || stage === undefined) return null;
  return 1.2 + (Math.max(0, stage) / 100) * 10;
}

function gwColor(props: { stage_of_extraction: number | null; metric_value: number | null; category: string | null }, layer: GwMetric, min: number, max: number): string {
  if (layer === "critical") {
    if (props.category) return CATEGORY_COLORS[props.category] ?? NO_DATA_COLOR;
    return NO_DATA_COLOR;
  }
  const depth = waterDepthFromStage(props.stage_of_extraction);
  const v = layer === "waterlevel" ? depth : props.metric_value;
  if (v === null || v === undefined) return NO_DATA_COLOR;
  const t = layer === "waterlevel"
    ? Math.min(Math.max((depth! - 1.2) / 10, 0), 1)
    : Math.min(Math.max((v - min) / (max - min || 1), 0), 1);
  const stops: [number, number, number][] = [
    [22, 163, 74],
    [234, 179, 8],
    [220, 38, 38],
  ];
  const x = t * (stops.length - 1);
  const i = Math.min(Math.floor(x), stops.length - 2);
  const f = x - i;
  const a = stops[i];
  const b = stops[i + 1];
  return `rgb(${Math.round(a[0] + (b[0] - a[0]) * f)},${Math.round(a[1] + (b[1] - a[1]) * f)},${Math.round(a[2] + (b[2] - a[2]) * f)})`;
}

interface LegendProps {
  metric: Metric;
  min: number | null;
  max: number | null;
}

function Legend({ metric, min, max }: LegendProps) {
  if (min === null || max === null) return null;
  const eps = (max - min) * 0.001 + 0.001;
  let stops = STOPS[metric].filter(([v]) => v >= min - eps && v <= max + eps);
  if (stops.length < 2) {
    stops = [
      [min, scaleColor(STOPS[metric], min)],
      [max, scaleColor(STOPS[metric], max)],
    ];
  }
  const gradient = `linear-gradient(to right, ${stops
    .map(([, rgb]) => `rgb(${rgb[0]},${rgb[1]},${rgb[2]})`)
    .join(", ")})`;
  const ticks = [0, 0.25, 0.5, 0.75, 1].map((f) => min + f * (max - min));
  return (
    <div className="pointer-events-none flex flex-col items-center rounded-xl border border-white/10 bg-slate-900/80 px-3 py-2 shadow-lg backdrop-blur-md">
      <div className="h-2 w-56 rounded-full" style={{ background: gradient }} />
      <div className="mt-1 flex w-56 justify-between text-[9px] font-medium tabular-nums text-slate-300">
        {ticks.map((t, i) => (
          <span key={i}>
            {t.toFixed(max - min >= 20 ? 0 : 1)}
            {i === ticks.length - 1 ? ` ${UNITS[metric]}` : ""}
          </span>
        ))}
      </div>
    </div>
  );
}

function formatTime(iso: string | null | undefined): string {
  if (!iso) return "—";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleString("en-IN", {
    weekday: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  });
}

function formatHour(iso: string | null | undefined): string {
  if (!iso) return "—";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleString("en-IN", { hour: "numeric", minute: "2-digit" });
}

function escapeHtml(text: string): string {
  return text.replace(/[&<>"']/g, (c) => {
    switch (c) {
      case "&": return "&amp;";
      case "<": return "&lt;";
      case ">": return "&gt;";
      case '"': return "&quot;";
      default: return "&#39;";
    }
  });
}

function seriesValue(
  p: WeatherMapSeries["grid"][number],
  metric: Metric,
  idx: number
): number | null {
  const arr =
    metric === "temperature" ? p.hourly.temperature_2m :
    metric === "rain" ? p.hourly.precipitation :
    metric === "humidity" ? p.hourly.relative_humidity_2m :
    metric === "clouds" ? p.hourly.cloud_cover :
    p.hourly.wind_speed_10m;
  return arr[idx] ?? null;
}

function legendRange(series: WeatherMapSeries | null, metric: MetricValue, idx: number): { min: number | null; max: number | null } {
  if (!series || metric === "none") return { min: null, max: null };
  const vs = series.grid
    .map((p) => seriesValue(p, metric, idx))
    .filter((v): v is number => v !== null);
  return {
    min: vs.length ? Math.min(...vs) : null,
    max: vs.length ? Math.max(...vs) : null,
  };
}

function modeAvailable(mode: WeatherMode, series: WeatherMapSeries | null): boolean {
  if (mode === "current") return !!series;
  if (mode === "forecast") return !!series && series.times.length > 1;
  // Radar / historical are not available from the Open-Meteo feed.
  return false;
}

export default function IngresMap() {
  const { t } = useLanguage();
  const containerRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<L.Map | null>(null);
  const tileRef = useRef<L.TileLayer | null>(null);
  const labelsRef = useRef<L.TileLayer | null>(null);
  const gwLayerRef = useRef<L.LayerGroup | null>(null);
  const pinMarkerRef = useRef<L.Marker | null>(null);
  const tooltipRef = useRef<HTMLDivElement | null>(null);
  const hoverRafRef = useRef(0);
  const seriesRef = useRef<WeatherMapSeries | null>(null);
  const frameRef = useRef(0);
  const windUnitRef = useRef<"kmh" | "ms">("kmh");
  const [baseMap, setBaseMap] = useState("light");
  // Clean-map default: no colour field, no translucent overlays. All weather
  // layers are opt-in via the Layers panel.
  const [metric, setMetric] = useState<MetricValue>("none");
  const [gwLayer, setGwLayer] = useState<GwMetric | null>(null);
  const [opacity, setOpacity] = useState(0.6);
  const [series, setSeries] = useState<WeatherMapSeries | null>(null);
  const [gwData, setGwData] = useState<MapData | null>(null);
  const [gwYear, setGwYear] = useState<number | null>(null);
  const [gwPlaying, setGwPlaying] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<MapSearchResult[]>([]);
  const [searching, setSearching] = useState(false);
  const [layerOpen, setLayerOpen] = useState(false);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [infoOpen, setInfoOpen] = useState(false);
  const [pin, setPin] = useState<[number, number] | null>(null);
  const [pinLabel, setPinLabel] = useState<string | null>(null);
  const [mode, setMode] = useState<WeatherMode>("current");
  const [frame, setFrame] = useState(0);
  const [playing, setPlaying] = useState(false);
  const [settings, setSettings] = useState<AnimSettings>({
    enabled: false,
    speed: 1,
    opacity: 0.6,
    density: "medium",
    trail: "medium",
    smoothing: "medium",
    windUnit: "kmh",
  });

  const maxFrame = series ? Math.max(0, series.times.length - 1) : 0;
  const nowIndex = useMemo(() => {
    if (!series || !series.time) return 0;
    const target = new Date(series.time).getTime();
    let best = 0;
    let bestD = Infinity;
    series.times.forEach((ts, i) => {
      const d = Math.abs(new Date(ts).getTime() - target);
      if (d < bestD) {
        bestD = d;
        best = i;
      }
    });
    return best;
  }, [series]);

  const effectiveFrame = useMemo(() => {
    if (!series) return 0;
    if (mode === "current" || mode === "radar" || mode === "historical") return nowIndex;
    return Math.min(frame, maxFrame);
  }, [mode, nowIndex, frame, maxFrame, series]);

  const layers = useMemo(
    () => ({
      clouds: metric === "clouds" || settings.enabled,
      rain: metric === "rain" || settings.enabled,
      wind: metric === "wind" || settings.enabled,
      temperature: metric === "temperature" || settings.enabled,
      humidity: metric === "humidity" || settings.enabled,
      aqi: metric === "aqi" || settings.enabled,
    }),
    [metric, settings.enabled]
  );

  useEffect(() => {
    seriesRef.current = series;
  }, [series]);
  useEffect(() => {
    frameRef.current = effectiveFrame;
  }, [effectiveFrame]);
  useEffect(() => {
    windUnitRef.current = settings.windUnit;
  }, [settings.windUnit]);

  useEffect(() => {
    let active = true;
    setLoading(true);
    setError(null);
    fetchWeatherMapSeries({ maxPoints: 44, hours: 24 })
      .then((d) => {
        if (!active) return;
        setSeries(d);
        setFrame(d.times.length > 1 ? Math.max(0, Math.round(d.times.length / 3)) : 0);
      })
      .catch((err) => active && setError(getApiError(err)))
      .finally(() => active && setLoading(false));
    return () => {
      active = false;
    };
  }, []);

  // Smooth forecast playback: requestAnimationFrame advances a *fractional*
  // frame index so WeatherAnimation interpolates continuously between hourly
  // model frames instead of hard-swapping them (MSN-style temporal morphing).
  useEffect(() => {
    if (!playing || mode !== "forecast" || !series || series.times.length < 2) return;
    let raf = 0;
    let last = performance.now();
    const hoursPerSecond = 1.25 * settings.speed;
    const tick = (now: number) => {
      const dt = Math.min((now - last) / 1000, 0.25);
      last = now;
      setFrame((prev) => {
        const next = prev + dt * hoursPerSecond;
        if (next >= series.times.length - 1) return 0;
        return next;
      });
      raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [playing, mode, series, settings.speed]);

  useEffect(() => {
    let active = true;
    if (!gwLayer) {
      setGwData(null);
      setGwYear(null);
      setGwPlaying(false);
      return;
    }
    setLoading(true);
    setError(null);
    getMap({ year: gwYear ?? undefined, metric: gwLayer })
      .then((d) => {
        if (!active) return;
        setGwData(d);
        if (gwYear === null && d.meta.year) setGwYear(d.meta.year);
      })
      .catch((err) => active && setError(getApiError(err)))
      .finally(() => active && setLoading(false));
    return () => {
      active = false;
    };
  }, [gwLayer, gwYear]);

  useEffect(() => {
    if (!gwPlaying || !gwData) return;
    const years = gwData.meta.years ?? [];
    if (years.length < 2) return;
    const id = setInterval(() => {
      setGwYear((prev) => {
        const cur = prev ?? years[years.length - 1];
        const idx = years.indexOf(cur);
        return years[(idx + 1) % years.length];
      });
    }, 900);
    return () => clearInterval(id);
  }, [gwPlaying, gwData]);

  useEffect(() => {
    const el = containerRef.current;
    if (!el || mapRef.current) return;
    const map = L.map(el, {
      center: [22, 80],
      zoom: 4.2,
      minZoom: 3,
      maxZoom: 12,
      zoomControl: false,
    });
    mapRef.current = map;
    // Pane above the weather canvas (z-420) so geographic labels stay readable.
    map.createPane("mapLabels");
    const labelPane = map.getPane("mapLabels");
    if (labelPane) {
      labelPane.style.zIndex = "430";
      labelPane.style.pointerEvents = "none";
    }
    map.createPane("cityLabels");
    const cityPane = map.getPane("cityLabels");
    if (cityPane) {
      cityPane.style.zIndex = "440";
      cityPane.style.pointerEvents = "none";
    }
    const base = BASE_MAPS.find((b) => b.key === baseMap) ?? BASE_MAPS[0];
    const tile = L.tileLayer(base.url, {
      subdomains: base.subdomains ?? "abc",
      maxZoom: 19,
      className: base.className,
      attribution:
        '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
    }).addTo(map);
    tileRef.current = tile;
    // Light/street basemaps carry their own labels; flat imagery needs ours.
    const initNeedsLabels = !["light", "street", "terrain"].includes(baseMap);
    if (initNeedsLabels) {
      labelsRef.current = L.tileLayer(
        "https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png",
        { subdomains: "abc", pane: "mapLabels", opacity: 0.9, maxZoom: 19, className: "ingres-dark-labels" }
      ).addTo(map);
    }

    map.on("click", (e: L.LeafletMouseEvent) => {
      setPinLabel(null);
      setPin([e.latlng.lat, e.latlng.lng]);
    });

    // Hover tooltip: sample the interpolated weather field at the cursor.
    // Runs outside React state (rAF-throttled, direct DOM writes) so panning
    // and zooming stay at 60fps even with the full field under the pointer.
    const buildTooltip = (lat: number, lon: number): string | null => {
      const s = seriesRef.current;
      if (!s || !s.grid.length || !s.times.length) return null;
      const b = s.bounds;
      if (lat < b.min_lat || lat > b.max_lat || lon < b.min_lon || lon > b.max_lon) return null;
      const w = sampleWeatherAt(s, lat, lon, frameRef.current);
      if (w.temperature_2m === null && w.precipitation === null) return null;
      const unit = windUnitRef.current === "ms" ? "m/s" : "km/h";
      const windV =
        w.wind_speed_10m !== null
          ? (windUnitRef.current === "ms" ? w.wind_speed_10m / 3.6 : w.wind_speed_10m).toFixed(1)
          : "—";
      const cond = weatherLabel(s.grid.length ? w.weather_code : null);
      const row = (label: string, value: string) =>
        `<div style="display:flex;justify-content:space-between;gap:12px;">
           <span style="color:#94a3b8;">${label}</span>
           <span style="font-weight:600;color:#e2e8f0;">${value}</span>
         </div>`;
      const rows =
        row("Feels like", w.apparent_temperature !== null ? `${Math.round(w.apparent_temperature)}°C` : "—") +
        row("Rain", w.precipitation !== null ? `${w.precipitation.toFixed(1)} mm` : "—") +
        row("Humidity", w.relative_humidity_2m !== null ? `${Math.round(w.relative_humidity_2m)}%` : "—") +
        row("Wind", `${windV} ${unit}`) +
        row("Cloud", w.cloud_cover !== null ? `${Math.round(w.cloud_cover)}%` : "—") +
        (w.us_aqi !== null ? row("AQI", String(Math.round(w.us_aqi))) : "");
      const hour = s.times[Math.min(Math.round(frameRef.current), s.times.length - 1)];
      return (
        `<div style="min-width:190px;">
           <div style="font-size:10.5px;color:#94a3b8;margin-bottom:2px;">${escapeHtml(formatCoords(lat, lon))}</div>
           <div style="display:flex;align-items:baseline;gap:8px;">
             <span style="font-size:22px;font-weight:700;color:#f8fafc;line-height:1.1;">
               ${w.temperature_2m !== null ? Math.round(w.temperature_2m) : "—"}°C
             </span>
             ${cond ? `<span style="font-size:11px;color:#cbd5e1;">${escapeHtml(cond)}</span>` : ""}
           </div>
           <div style="margin-top:6px;display:flex;flex-direction:column;gap:1px;font-size:11px;">
             ${rows}
           </div>
           <div style="margin-top:5px;padding-top:4px;border-top:1px solid rgba(148,163,184,0.2);font-size:9.5px;color:#64748b;">
             ${escapeHtml(formatHour(hour))} · Open-Meteo model
           </div>
         </div>`
      );
    };
    map.on("mousemove", (e: L.LeafletMouseEvent) => {
      if (hoverRafRef.current) return;
      hoverRafRef.current = requestAnimationFrame(() => {
        hoverRafRef.current = 0;
        const tip = tooltipRef.current;
        if (!tip) return;
        const html = buildTooltip(e.latlng.lat, e.latlng.lng);
        if (!html) {
          tip.style.display = "none";
          return;
        }
        const size = map.getSize();
        const px = Math.min(e.containerPoint.x + 16, size.x - 210);
        const py = Math.max(e.containerPoint.y - 12, 90);
        tip.innerHTML = html;
        tip.style.left = `${px}px`;
        tip.style.top = `${py}px`;
        tip.style.display = "block";
      });
    });
    map.on("mouseout", () => {
      if (tooltipRef.current) tooltipRef.current.style.display = "none";
    });

    return () => {
      if (hoverRafRef.current) cancelAnimationFrame(hoverRafRef.current);
      map.remove();
      mapRef.current = null;
      tileRef.current = null;
      gwLayerRef.current = null;
      pinMarkerRef.current = null;
    };
  }, [t]);

  // Animated pulse marker for the selected location.
  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;
    if (!pin) {
      pinMarkerRef.current?.remove();
      pinMarkerRef.current = null;
      return;
    }
    const icon = L.divIcon({
      className: "",
      html: '<div class="ingres-pin-marker"></div>',
      iconSize: [18, 30],
      iconAnchor: [9, 28],
    });
    if (pinMarkerRef.current) {
      pinMarkerRef.current.setLatLng(pin);
    } else {
      pinMarkerRef.current = L.marker(pin, {
        icon,
        interactive: false,
        zIndexOffset: 1000,
      }).addTo(map);
    }
  }, [pin]);

  // Selected-location info bar tracks the marker's screen position.
  const [barPos, setBarPos] = useState<{ x: number; y: number } | null>(null);
  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;
    if (!pin) {
      setBarPos(null);
      return;
    }
    const update = () => {
      const pt = map.latLngToContainerPoint(L.latLng(pin[0], pin[1]));
      setBarPos({ x: pt.x, y: pt.y });
    };
    update();
    map.on("move zoom", update);
    return () => {
      map.off("move zoom", update);
    };
  }, [pin]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map || !tileRef.current) return;
    const base = BASE_MAPS.find((b) => b.key === baseMap) ?? BASE_MAPS[0];
    tileRef.current.remove();
    const tile = L.tileLayer(base.url, {
      subdomains: base.subdomains ?? "abc",
      maxZoom: 19,
      className: base.className,
      attribution:
        '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
    }).addTo(map);
    tileRef.current = tile;
    // Light basemaps carry their own dark labels; dark/imagery ones need ours.
    const needsOverlay = !["light", "street", "terrain"].includes(baseMap);
    if (needsOverlay && !labelsRef.current) {
      labelsRef.current = L.tileLayer(
        "https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png",
        { subdomains: "abc", pane: "mapLabels", opacity: 0.9, maxZoom: 19, className: "ingres-dark-labels" }
      ).addTo(map);
    } else if (!needsOverlay && labelsRef.current) {
      labelsRef.current.remove();
      labelsRef.current = null;
    }
  }, [baseMap]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;
    gwLayerRef.current?.remove();
    gwLayerRef.current = null;
    if (!gwLayer || !gwData) return;
    const features = gwData.features as unknown as GeoJSON.FeatureCollection;
    const values = gwData.features
      .map((f) => f.properties.metric_value)
      .filter((v): v is number => v !== null);
    const min = values.length ? Math.min(...values) : 0;
    const max = values.length ? Math.max(...values) : 1;
    const layer = L.layerGroup().addTo(map);
    gwLayerRef.current = layer;
    const geo = L.geoJSON(features, {
      style: (feature) => ({
        fillColor: gwColor(
          (feature?.properties ?? {}) as { stage_of_extraction: number | null; metric_value: number | null; category: string | null },
          gwLayer,
          min,
          max
        ),
        color: "#ffffff",
        weight: 1,
        fillOpacity: gwLayer === "critical" ? 0.6 : 0.65,
      }),
    });
    geo.addTo(layer);
    geo.eachLayer((l) => {
      const ll = l as L.Polygon;
      const bounds = ll.getBounds();
      if (bounds) {
        L.marker(bounds.getCenter(), {
          icon: L.divIcon({
            className: "",
            html: `<div style="font-size:9px;font-weight:600;color:#334155;background:rgba(255,255,255,0.85);padding:0 3px;border-radius:3px;white-space:nowrap;">${escapeHtml(
              (ll.feature?.properties as { name?: string } | undefined)?.name ?? ""
            )}</div>`,
            iconSize: [0, 0],
          }),
        }).addTo(layer);
      }
    });
    return () => {
      layer.remove();
    };
  }, [gwLayer, gwData, gwYear]);

  const doSearch = useCallback(async (q: string) => {
    const term = q.trim();
    if (term.length < 2) {
      setResults([]);
      return;
    }
    setSearching(true);
    try {
      setResults(await searchLocations(term, 8));
    } catch {
      setResults([]);
    } finally {
      setSearching(false);
    }
  }, []);

  useEffect(() => {
    const id = setTimeout(() => doSearch(query), 350);
    return () => clearTimeout(id);
  }, [query, doSearch]);

  const goToLocation = (r: MapSearchResult) => {
    const map = mapRef.current;
    setQuery("");
    setResults([]);
    if (!map) return;
    const lat = r.latitude;
    const lon = r.longitude;
    if (lat === null || lon === null) {
      map.flyTo([22, 80], 4.2);
      return;
    }
    map.flyTo([lat, lon], r.type === "state" ? 6 : 9);
    setPinLabel(r.name);
    setPin([lat, lon]);
  };

  const locateMe = () => {
    const map = mapRef.current;
    if (!map) return;
    if (!navigator.geolocation) return;
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        const lat = pos.coords.latitude;
        const lon = pos.coords.longitude;
        map.flyTo([lat, lon], 10);
        setPinLabel(t("Your location"));
        setPin([lat, lon]);
      },
      () => undefined,
      { enableHighAccuracy: true, timeout: 8000 }
    );
  };

  const legend = legendRange(series, metric, effectiveFrame);

  const selectMode = (m: WeatherMode) => {
    setMode(m);
    setPlaying(false);
  };

  const stepFrame = (delta: number) => {
    setPlaying(false);
    setFrame((prev) => Math.max(0, Math.min(maxFrame, prev + delta)));
  };

  const pinWeather = useMemo(() => {
    if (!series || !pin || !series.grid.length || !series.times.length) return null;
    const b = series.bounds;
    if (pin[0] < b.min_lat || pin[0] > b.max_lat || pin[1] < b.min_lon || pin[1] > b.max_lon) return null;
    return sampleWeatherAt(series, pin[0], pin[1], effectiveFrame);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [series, pin, Math.round(effectiveFrame)]);

  const barTime = series && series.times.length
    ? new Date(series.times[Math.min(Math.round(effectiveFrame), maxFrame)])
    : null;
  const barTimeText =
    barTime && !Number.isNaN(barTime.getTime())
      ? `${barTime.toLocaleString("en-IN", { weekday: "short" })} ${barTime.getDate()}, ` +
        barTime.toLocaleString("en-IN", { hour: "numeric", hour12: true })
      : "—";

  const togglePlayFromBar = () => {
    if (mode !== "forecast") {
      setMode("forecast");
      setPlaying(true);
      return;
    }
    setPlaying((p) => !p);
  };

  // Village-friendly timeline wording: "Now", "+3 hrs", "Tomorrow · 9:30 AM".
  const timelineLabel = (iso: string | undefined): string => {
    if (!iso) return "—";
    const d = new Date(iso);
    if (Number.isNaN(d.getTime())) return iso;
    const now = series?.time ? new Date(series.time) : null;
    const timeText = d.toLocaleString("en-IN", { hour: "numeric", minute: "2-digit", hour12: true });
    if (!now || Number.isNaN(now.getTime())) return timeText;
    const diffH = (d.getTime() - now.getTime()) / 3_600_000;
    if (Math.abs(diffH) < 0.75) return t("Now");
    const dayA = new Date(d.getFullYear(), d.getMonth(), d.getDate()).getTime();
    const dayB = new Date(now.getFullYear(), now.getMonth(), now.getDate()).getTime();
    const dayDiff = Math.round((dayA - dayB) / 86_400_000);
    if (dayDiff === 0) return `+${Math.max(1, Math.round(diffH))} hrs`;
    if (dayDiff === 1) return `${t("Tomorrow")} · ${timeText}`;
    return `${d.toLocaleString("en-IN", { weekday: "short" })} · ${timeText}`;
  };

  // Tick positions (as % of the slider) for the forecast-time scale.
  const tickSpecs: { label: string; pct: number }[] = useMemo(() => {
    if (mode !== "forecast" || !series || !series.times.length || maxFrame === 0) return [];
    const mk = (hoursAhead: number, label: string) => {
      const idx = Math.min(nowIndex + hoursAhead, maxFrame);
      return { label, idx };
    };
    const specs = [
      { label: t("Now"), idx: nowIndex },
      mk(3, "+3h"),
      mk(6, "+6h"),
      mk(12, "+12h"),
      mk(Math.max(13, maxFrame - nowIndex), "+24h"),
    ];
    const seen = new Set<number>();
    return specs
      .filter((s) => {
        if (seen.has(s.idx)) return false;
        seen.add(s.idx);
        return true;
      })
      .map((s) => ({ label: s.label, pct: (s.idx / maxFrame) * 100 }));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [mode, series, maxFrame, nowIndex]);

  return (
    <div className="relative h-[calc(100vh-7rem)] min-h-[520px] w-full overflow-hidden bg-slate-950">
      <div
        ref={containerRef}
        className="z-0 h-full w-full"
        aria-label={t("Interactive hydro-meteorological map of India")}
      />
      <WeatherAnimation
        map={mapRef.current}
        series={series}
        metric={metric}
        frame={effectiveFrame}
        mode={mode}
        layers={layers}
        settings={settings}
      />
      <CityLabels map={mapRef.current} series={series} frame={effectiveFrame} />

      {/* MSN-style info bar anchored to the selected marker. */}
      {pin && series && (
        <MarkerInfoBar
          map={mapRef.current}
          series={series}
          pin={pin}
          frame={Math.round(effectiveFrame)}
          playing={playing}
          canPlay={modeAvailable("forecast", series) && mode === "forecast"}
          onTogglePlay={() => {
            if (mode !== "forecast") {
              setMode("forecast");
              setPlaying(true);
            } else {
              setPlaying((p) => !p);
            }
          }}
          onClose={() => setPin(null)}
        />
      )}

      {/* Hover tooltip (content written directly by the mousemove handler). */}
      <div
        ref={tooltipRef}
        style={{ display: "none" }}
        className="pointer-events-none absolute z-[450] rounded-xl border border-white/10 bg-slate-900/85 px-3 py-2 shadow-2xl backdrop-blur-md"
      />

      {/* Selected-location info bar (MSN-style): temp · time · play · close. */}
      {barPos && pin && (
        <div
          className="absolute z-[520] flex -translate-x-[10%] -translate-y-full items-center gap-3 rounded-xl border border-white/10 bg-slate-800/90 px-3.5 py-2 shadow-2xl backdrop-blur-md"
          style={{ left: barPos.x + 10, top: barPos.y - 44 }}
        >
          <span className="text-xl font-bold leading-none text-white tabular-nums">
            {pinWeather?.temperature_2m != null ? `${Math.round(pinWeather.temperature_2m)}°` : "—"}
          </span>
          <span className="text-xs font-medium text-slate-300 tabular-nums">{barTimeText}</span>
          <button
            type="button"
            onClick={togglePlayFromBar}
            disabled={!modeAvailable("forecast", series)}
            className="flex h-7 w-7 items-center justify-center rounded-full bg-amber-400 text-slate-900 shadow transition-colors hover:bg-amber-300 disabled:opacity-40"
            aria-label={playing && mode === "forecast" ? t("Pause") : t("Play")}
          >
            {playing && mode === "forecast" ? (
              <Pause className="h-3.5 w-3.5" />
            ) : (
              <Play className="h-3.5 w-3.5 translate-x-[1px]" />
            )}
          </button>
          <button
            type="button"
            onClick={() => setPin(null)}
            className="text-slate-400 transition-colors hover:text-white"
            aria-label={t("Close")}
          >
            <X className="h-4 w-4" />
          </button>
        </div>
      )}

      {/* Top bar */}
      <div className="absolute left-3 right-3 top-3 z-[500] flex flex-wrap items-center gap-2">
        <div className="flex items-center gap-2 rounded-lg border border-white/10 bg-slate-900/80 px-3 py-2 shadow-lg backdrop-blur-md">
          <CloudSun className="h-5 w-5 text-sky-400" />
          <span className="text-sm font-bold text-slate-100">IN-GRES Map</span>
          {loading ? (
            <Loader2 className="ml-1 h-3.5 w-3.5 animate-spin text-slate-500" />
          ) : series?.time ? (
            <Badge variant="outline" className="ml-1 border-white/15 bg-white/5 text-[10px] text-slate-300">
              {formatTime(series.time)}
            </Badge>
          ) : null}
          {series?.official === false && (
            <Badge variant="outline" className="ml-0.5 border-amber-400/30 bg-amber-400/10 text-[9px] font-semibold uppercase tracking-wide text-amber-300">
              model
            </Badge>
          )}
        </div>

        <div className="relative flex-1 max-w-md">
          <div className="flex items-center gap-2 rounded-lg border border-white/10 bg-slate-900/80 px-3 py-2 shadow-lg backdrop-blur-md">
            <Search className="h-4 w-4 shrink-0 text-slate-500" />
            <input
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder={t("Search village, district, state, lat/lon…")}
              className="w-full bg-transparent text-sm text-slate-200 outline-none placeholder:text-slate-500"
            />
            {searching && <Loader2 className="h-3.5 w-3.5 animate-spin text-slate-500" />}
          </div>
          {results.length > 0 && (
            <div className="absolute left-0 right-0 top-full z-[600] mt-1 max-h-80 overflow-y-auto rounded-lg border border-white/10 bg-slate-900/95 shadow-xl backdrop-blur-md">
              {results.map((r, i) => (
                <button
                  key={`${r.type}-${r.name}-${i}`}
                  type="button"
                  onClick={() => goToLocation(r)}
                  className="flex w-full items-center gap-2 px-3 py-2 text-left text-sm hover:bg-white/5"
                >
                  <MapPin className="h-3.5 w-3.5 shrink-0 text-sky-400" />
                  <span className="min-w-0 flex-1">
                    <span className="block truncate font-medium text-slate-200">{r.name}</span>
                    <span className="block truncate text-xs text-slate-500">
                      {r.type} · {[r.state, r.district].filter(Boolean).join(" · ")}
                    </span>
                  </span>
                  {r.latitude !== null && r.longitude !== null && (
                    <span className="shrink-0 text-xs tabular-nums text-slate-600">
                      {r.latitude.toFixed(2)}, {r.longitude.toFixed(2)}
                    </span>
                  )}
                </button>
              ))}
            </div>
          )}
        </div>

        <Button
          variant="outline"
          size="sm"
          className="border-white/10 bg-slate-900/80 text-slate-200 shadow-lg backdrop-blur-md hover:bg-slate-800/80 hover:text-white"
          onClick={locateMe}
        >
          <Crosshair className="h-3.5 w-3.5" />
          <span className="hidden sm:inline">{t("My location")}</span>
        </Button>

        <div className="relative">
          <Button
            variant="outline"
            size="sm"
            className="border-white/10 bg-slate-900/80 text-slate-200 shadow-lg backdrop-blur-md hover:bg-slate-800/80 hover:text-white"
            onClick={() => setLayerOpen((o) => !o)}
          >
            <Layers className="h-3.5 w-3.5" />
            {t("Layers")}
          </Button>
          {layerOpen && (
            <div className="absolute right-0 top-full z-[600] mt-1 max-h-[70vh] w-64 overflow-y-auto rounded-lg border border-white/10 bg-slate-900/95 p-3 shadow-xl backdrop-blur-md">
              <div className="mb-1 text-xs font-bold uppercase tracking-wide text-slate-500">
                {t("Weather mode")}
              </div>
              <div className="mb-3 grid grid-cols-2 gap-1">
                {MODES.map((m) => (
                  <button
                    key={m.key}
                    type="button"
                    onClick={() => selectMode(m.key)}
                    className={cn(
                      "flex items-center gap-1 rounded-md px-2 py-1.5 text-[11px] font-medium",
                      mode === m.key
                        ? "bg-sky-500 text-white"
                        : "bg-white/5 text-slate-300 hover:bg-white/10"
                    )}
                  >
                    <m.icon className="h-3 w-3" />
                    {m.label}
                  </button>
                ))}
              </div>
              <div className="mb-1 text-xs font-bold uppercase tracking-wide text-slate-500">
                {t("Base map")}
              </div>
              <div className="mb-3 grid grid-cols-3 gap-1">
                {BASE_MAPS.map((b) => (
                  <button
                    key={b.key}
                    type="button"
                    onClick={() => setBaseMap(b.key)}
                    className={cn(
                      "rounded-md px-1.5 py-1 text-[11px] font-medium",
                      baseMap === b.key
                        ? "bg-sky-500 text-white"
                        : "bg-white/5 text-slate-300 hover:bg-white/10"
                    )}
                  >
                    {b.label}
                  </button>
                ))}
              </div>
              <div className="mb-1 text-xs font-bold uppercase tracking-wide text-slate-500">
                {t("Weather layer")}
              </div>
              <div className="space-y-0.5">
                {LAYERS.map((l) => (
                  <button
                    key={l.key}
                    type="button"
                    onClick={() => setMetric(l.key)}
                    className={cn(
                      "flex w-full items-center gap-2 rounded-md px-2 py-1.5 text-left text-sm",
                      metric === l.key ? "bg-sky-500/20 text-sky-300" : "text-slate-300 hover:bg-white/5"
                    )}
                  >
                    <l.icon className="h-3.5 w-3.5" />
                    {t(l.label)}
                  </button>
                ))}
              </div>
              {metric !== "none" && (
                <div className="mt-3">
                  <div className="mb-1 flex justify-between text-[11px] text-slate-500">
                    <span>{t("Opacity")}</span>
                    <span>{Math.round(opacity * 100)}%</span>
                  </div>
                  <input
                    type="range"
                    min={0.1}
                    max={1}
                    step={0.05}
                    value={opacity}
                    onChange={(e) => setOpacity(Number(e.target.value))}
                    className="w-full accent-sky-400"
                    aria-label={t("Layer opacity")}
                  />
                </div>
              )}
              <div className="mb-1 mt-3 text-xs font-bold uppercase tracking-wide text-slate-500">
                {t("Groundwater layer")}
              </div>
              <div className="space-y-0.5">
                <button
                  type="button"
                  onClick={() => setGwLayer(null)}
                  className={cn(
                    "flex w-full items-center gap-2 rounded-md px-2 py-1.5 text-left text-sm",
                    gwLayer === null ? "bg-sky-500/20 text-sky-300" : "text-slate-300 hover:bg-white/5"
                  )}
                >
                  <MapIcon className="h-3.5 w-3.5" />
                  {t("None")}
                </button>
                {GW_LAYERS.map((l) => (
                  <button
                    key={l.key}
                    type="button"
                    onClick={() => setGwLayer(l.key)}
                    className={cn(
                      "flex w-full items-center gap-2 rounded-md px-2 py-1.5 text-left text-sm",
                      gwLayer === l.key ? "bg-sky-500/20 text-sky-300" : "text-slate-300 hover:bg-white/5"
                    )}
                  >
                    <Droplets className="h-3.5 w-3.5" />
                    {t(l.label)}
                  </button>
                ))}
              </div>
              {gwLayer && (
                <div className="mt-3 flex items-center gap-2">
                  <Button
                    size="sm"
                    variant="outline"
                    className="h-7 border-white/10 bg-white/5 text-[11px] text-slate-200 hover:bg-white/10 hover:text-white"
                    onClick={() => setGwPlaying((p) => !p)}
                    aria-pressed={gwPlaying}
                  >
                    {gwPlaying ? t("Pause") : t("Play")}
                  </Button>
                  <span className="text-xs font-semibold tabular-nums text-slate-300">
                    {gwYear ?? "—"}
                  </span>
                </div>
              )}
            </div>
          )}
        </div>

        <Button
          variant="outline"
          size="sm"
          className="border-white/10 bg-slate-900/80 text-slate-200 shadow-lg backdrop-blur-md hover:bg-slate-800/80 hover:text-white"
          onClick={() => setInfoOpen(true)}
        >
          <Info className="h-3.5 w-3.5" />
          <span className="hidden sm:inline">{t("Layer info")}</span>
        </Button>

        <div className="relative">
          <Button
            variant="outline"
            size="sm"
            className="border-white/10 bg-slate-900/80 text-slate-200 shadow-lg backdrop-blur-md hover:bg-slate-800/80 hover:text-white"
            onClick={() => setSettingsOpen((o) => !o)}
          >
            <Settings2 className="h-3.5 w-3.5" />
            <span className="hidden sm:inline">{t("Animation")}</span>
          </Button>
          {settingsOpen && (
            <div className="absolute right-0 top-full z-[600] mt-1 w-72 rounded-lg border border-white/10 bg-slate-900/95 p-3 shadow-xl backdrop-blur-md">
              <div className="mb-2 flex items-center justify-between">
                <span className="text-xs font-bold uppercase tracking-wide text-slate-500">
                  {t("Animation settings")}
                </span>
                <button
                  type="button"
                  onClick={() => setSettingsOpen(false)}
                  className="text-slate-500 hover:text-slate-300"
                >
                  <X className="h-3.5 w-3.5" />
                </button>
              </div>

              <label className="mb-3 flex items-center justify-between text-xs text-slate-300">
                {t("Animation")}
                <button
                  type="button"
                  role="switch"
                  aria-checked={settings.enabled}
                  onClick={() => setSettings((s) => ({ ...s, enabled: !s.enabled }))}
                  className={cn(
                    "relative h-5 w-9 rounded-full transition-colors",
                    settings.enabled ? "bg-sky-500" : "bg-slate-700"
                  )}
                >
                  <span
                    className={cn(
                      "absolute top-0.5 h-4 w-4 rounded-full bg-white shadow transition-transform",
                      settings.enabled ? "translate-x-4" : "translate-x-0.5"
                    )}
                  />
                </button>
              </label>

              <div className="mb-3">
                <div className="mb-1 flex justify-between text-[11px] text-slate-500">
                  <span>{t("Speed")}</span>
                  <span>{settings.speed}×</span>
                </div>
                <div className="grid grid-cols-4 gap-1">
                  {[0.5, 1, 2, 4].map((s) => (
                    <button
                      key={s}
                      type="button"
                      onClick={() => setSettings((st) => ({ ...st, speed: s }))}
                      className={cn(
                        "rounded-md py-1 text-[11px] font-medium",
                        settings.speed === s
                          ? "bg-sky-500 text-white"
                          : "bg-white/5 text-slate-300 hover:bg-white/10"
                      )}
                    >
                      {s}×
                    </button>
                  ))}
                </div>
              </div>

              <div className="mb-3">
                <div className="mb-1 flex justify-between text-[11px] text-slate-500">
                  <span>{t("Opacity")}</span>
                  <span>{Math.round(settings.opacity * 100)}%</span>
                </div>
                <input
                  type="range"
                  min={0}
                  max={1}
                  step={0.05}
                  value={settings.opacity}
                  onChange={(e) => setSettings((s) => ({ ...s, opacity: Number(e.target.value) }))}
                  className="w-full accent-sky-400"
                />
              </div>

              <div className="mb-3">
                <div className="mb-1 text-[11px] text-slate-500">{t("Particle density")}</div>
                <div className="grid grid-cols-3 gap-1">
                  {(["low", "medium", "high"] as const).map((d) => (
                    <button
                      key={d}
                      type="button"
                      onClick={() => setSettings((s) => ({ ...s, density: d }))}
                      className={cn(
                        "rounded-md py-1 text-[11px] font-medium capitalize",
                        settings.density === d
                          ? "bg-sky-500 text-white"
                          : "bg-white/5 text-slate-300 hover:bg-white/10"
                      )}
                    >
                      {d}
                    </button>
                  ))}
                </div>
              </div>

              <div className="mb-3">
                <div className="mb-1 text-[11px] text-slate-500">{t("Trail length")}</div>
                <div className="grid grid-cols-3 gap-1">
                  {(["short", "medium", "long"] as const).map((d) => (
                    <button
                      key={d}
                      type="button"
                      onClick={() => setSettings((s) => ({ ...s, trail: d }))}
                      className={cn(
                        "rounded-md py-1 text-[11px] font-medium capitalize",
                        settings.trail === d
                          ? "bg-sky-500 text-white"
                          : "bg-white/5 text-slate-300 hover:bg-white/10"
                      )}
                    >
                      {d}
                    </button>
                  ))}
                </div>
              </div>

              <div className="mb-3">
                <div className="mb-1 text-[11px] text-slate-500">{t("Smoothing")}</div>
                <div className="grid grid-cols-4 gap-1">
                  {(["off", "low", "medium", "high"] as const).map((d) => (
                    <button
                      key={d}
                      type="button"
                      onClick={() => setSettings((s) => ({ ...s, smoothing: d }))}
                      className={cn(
                        "rounded-md py-1 text-[11px] font-medium capitalize",
                        settings.smoothing === d
                          ? "bg-sky-500 text-white"
                          : "bg-white/5 text-slate-300 hover:bg-white/10"
                      )}
                    >
                      {d}
                    </button>
                  ))}
                </div>
              </div>

              <div className="mb-1 text-[11px] text-slate-500">{t("Wind unit")}</div>
              <div className="grid grid-cols-2 gap-1">
                {(["kmh", "ms"] as const).map((u) => (
                  <button
                    key={u}
                    type="button"
                    onClick={() => setSettings((s) => ({ ...s, windUnit: u }))}
                    className={cn(
                      "rounded-md py-1 text-[11px] font-medium",
                      settings.windUnit === u
                        ? "bg-sky-500 text-white"
                        : "bg-white/5 text-slate-300 hover:bg-white/10"
                    )}
                  >
                    {u === "kmh" ? "km/h" : "m/s"}
                  </button>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>

      {error && (
        <div className="absolute left-1/2 top-16 z-[500] -translate-x-1/2 rounded-full bg-red-600/90 px-3 py-1.5 text-xs font-medium text-white shadow">
          {error}
        </div>
      )}

      {series && series.available === false && (
        <div className="absolute left-1/2 top-16 z-[500] -translate-x-1/2 rounded-lg border border-amber-400/30 bg-slate-900/90 px-3 py-1.5 text-xs font-medium text-amber-300 shadow backdrop-blur-md">
          {series.detail
            ? t("Live weather animation temporarily unavailable (data provider throttled). Groundwater layers remain active.")
            : t("Live weather animation temporarily unavailable. Groundwater layers remain active.")}
        </div>
      )}

      {mode !== "current" && !modeAvailable(mode, series) && (
        <div className="absolute left-1/2 top-16 z-[500] -translate-x-1/2 rounded-lg border border-amber-400/30 bg-slate-900/90 px-3 py-1.5 text-xs font-medium text-amber-300 shadow backdrop-blur-md">
          {mode === "radar"
            ? t("Radar animation unavailable — showing latest precipitation observation.")
            : t("Historical animation unavailable — showing latest observation.")}
        </div>
      )}

      {/* Unified bottom dock: legend stacked above the timeline (MSN-style). */}
      {series && series.times.length > 0 && (
        <div className="absolute bottom-4 left-1/2 z-[500] flex -translate-x-1/2 flex-col items-center gap-1.5">
          {metric !== "none" && !loading && (
            <Legend metric={metric} min={legend.min} max={legend.max} />
          )}
          <div className="flex items-center gap-2 rounded-xl border border-white/10 bg-slate-900/80 px-3 py-2 shadow-xl backdrop-blur-md">
            <button
              type="button"
              onClick={() => setPlaying((p) => !p)}
              disabled={mode === "current" || mode === "radar" || mode === "historical"}
              className="flex h-7 w-7 items-center justify-center rounded-full bg-sky-500 text-white shadow transition-colors hover:bg-sky-400 disabled:opacity-40"
              aria-label={playing ? t("Pause") : t("Play")}
            >
              {playing ? <Pause className="h-3.5 w-3.5" /> : <Play className="h-3.5 w-3.5 translate-x-[1px]" />}
            </button>
            <button
              type="button"
              onClick={() => stepFrame(-1)}
              disabled={mode === "current" || mode === "radar" || mode === "historical"}
              className="flex h-6 w-6 items-center justify-center rounded text-slate-400 hover:bg-white/10 hover:text-slate-200 disabled:opacity-40"
              aria-label={t("Previous")}
            >
              <SkipBack className="h-3.5 w-3.5" />
            </button>
            <span
              className={cn(
                "rounded-full px-2 py-0.5 text-[9px] font-bold uppercase tracking-wider",
                Math.round(effectiveFrame) <= nowIndex
                  ? "bg-sky-500/20 text-sky-300"
                  : "bg-violet-500/20 text-violet-300"
              )}
            >
              {Math.round(effectiveFrame) <= nowIndex ? t("Observed") : t("Forecast")}
            </span>
            <div className="relative flex items-center pb-5">
              <input
                type="range"
                min={0}
                max={maxFrame}
                step={1}
                value={Math.round(effectiveFrame)}
                disabled={mode === "current" || mode === "radar" || mode === "historical"}
                onChange={(e) => {
                  setPlaying(false);
                  setFrame(Number(e.target.value));
                }}
                className="w-40 accent-sky-400 sm:w-64"
                aria-label={t("Timeline")}
              />
              <span
                className="pointer-events-none absolute bottom-4 mt-0.5 h-1.5 w-px bg-sky-300/80"
                style={{ left: `${maxFrame > 0 ? (nowIndex / maxFrame) * 100 : 0}%` }}
                title={t("Now")}
              />
              {/* Forecast-time scale: Now → +3h → +6h → +12h → Max. */}
              {tickSpecs.length > 0 &&
                tickSpecs.map((s) => (
                  <span
                    key={s.label}
                    className="pointer-events-none absolute bottom-0 -translate-x-1/2 whitespace-nowrap text-[9px] font-semibold tabular-nums text-slate-400 first:translate-x-0 last:-translate-x-full"
                    style={{ left: `${Math.min(96, Math.max(2, s.pct))}%` }}
                  >
                    {s.label}
                  </span>
                ))}
            </div>
            <button
              type="button"
              onClick={() => stepFrame(1)}
              disabled={mode === "current" || mode === "radar" || mode === "historical"}
              className="flex h-6 w-6 items-center justify-center rounded text-slate-400 hover:bg-white/10 hover:text-slate-200 disabled:opacity-40"
              aria-label={t("Next")}
            >
              <SkipForward className="h-3.5 w-3.5" />
            </button>
            <span className="min-w-[5.5rem] text-right text-xs font-semibold tabular-nums text-slate-200 sm:min-w-[7rem]">
              {timelineLabel(series.times[Math.min(Math.round(effectiveFrame), maxFrame)])}
            </span>
          </div>
        </div>
      )}

      {gwLayer && gwData && gwData.meta.years.length > 0 && (
        <div className="absolute bottom-24 left-1/2 z-[500] flex -translate-x-1/2 items-center gap-3 rounded-xl border border-white/10 bg-slate-900/80 px-4 py-2 shadow-xl backdrop-blur-md">
          <button
            type="button"
            onClick={() => setGwPlaying((p) => !p)}
            className="flex h-7 w-7 items-center justify-center rounded-full bg-sky-500 text-white shadow transition-colors hover:bg-sky-400"
            aria-label={gwPlaying ? t("Pause") : t("Play")}
          >
            {gwPlaying ? <Pause className="h-3.5 w-3.5" /> : <Play className="h-3.5 w-3.5 translate-x-[1px]" />}
          </button>
          <input
            type="range"
            min={gwData.meta.years[0]}
            max={gwData.meta.years[gwData.meta.years.length - 1]}
            step={1}
            value={gwYear ?? gwData.meta.years[gwData.meta.years.length - 1]}
            onChange={(e) => {
              setGwPlaying(false);
              setGwYear(Number(e.target.value));
            }}
            className="w-40 accent-sky-400 sm:w-56"
            aria-label={t("Year")}
          />
          <span className="w-12 text-sm font-semibold tabular-nums text-slate-200">
            {gwYear ?? gwData.meta.years[gwData.meta.years.length - 1]}
          </span>
        </div>
      )}

      {/* Zoom controls */}
      <div className="absolute bottom-16 left-3 z-[550] flex flex-col overflow-hidden rounded-lg border border-white/10 bg-slate-900/80 shadow-lg backdrop-blur-md">
        <button
          type="button"
          onClick={() => mapRef.current?.zoomIn()}
          className="flex h-9 w-9 items-center justify-center text-slate-300 transition-colors hover:bg-white/10 hover:text-white"
          aria-label={t("Zoom in")}
        >
          <Plus className="h-4 w-4" />
        </button>
        <div className="h-px bg-white/10" />
        <button
          type="button"
          onClick={() => mapRef.current?.zoomOut()}
          className="flex h-9 w-9 items-center justify-center text-slate-300 transition-colors hover:bg-white/10 hover:text-white"
          aria-label={t("Zoom out")}
        >
          <Minus className="h-4 w-4" />
        </button>
      </div>

      {pin && (
        <div className="absolute bottom-16 right-3 z-[500] max-h-[calc(100%-6rem)] w-72 overflow-y-auto rounded-xl border border-white/10 bg-slate-900/90 p-3 shadow-2xl backdrop-blur-md">
          <div className="mb-1 flex items-center justify-between">
            <span className="truncate text-sm font-bold text-slate-100">
              {pinLabel ?? t("Location")}
            </span>
            <button
              type="button"
              onClick={() => setPin(null)}
              className="ml-2 shrink-0 text-slate-500 hover:text-slate-300"
              aria-label={t("Close")}
            >
              <X className="h-3.5 w-3.5" />
            </button>
          </div>
          <span className="text-xs tabular-nums text-slate-500">
            {formatCoords(pin[0], pin[1])}
          </span>
          <WeatherCard lat={pin[0]} lon={pin[1]} settings={settings} />
        </div>
      )}

      {infoOpen && series && (
        <div className="absolute bottom-1/2 left-1/2 z-[700] w-96 max-w-[calc(100vw-2rem)] -translate-x-1/2 translate-y-1/2 rounded-xl border border-white/10 bg-slate-900/95 p-4 shadow-2xl backdrop-blur-md">
          <div className="mb-2 flex items-center justify-between">
            <span className="text-sm font-bold text-slate-100">{t("Layer information")}</span>
            <button
              type="button"
              onClick={() => setInfoOpen(false)}
              className="text-slate-500 hover:text-slate-300"
              aria-label={t("Close")}
            >
              <X className="h-3.5 w-3.5" />
            </button>
          </div>
          <p className="mb-3 rounded-lg bg-sky-500/10 px-3 py-2 text-xs leading-relaxed text-sky-200">
            {metric !== "none"
              ? t(
                  "The map colours every area by {layer}. Tap any spot on the map to see its exact numbers.",
                  { layer: (LAYERS.find((l) => l.key === metric)?.label ?? "").toLowerCase() }
                )
              : t(
                  "Open the Layers menu and pick Temperature or Rainfall to colour the map. Tap any spot for detailed weather."
                )}
          </p>
          <dl className="space-y-1.5 text-xs">
            {[
              [t("Source"), series.source],
              [t("Dataset"), "Open-Meteo hourly forecast (GFS/ICON/IFS) + CAMS air quality"],
              [t("Timestamp"), formatTime(series.time)],
              [t("Update time"), formatTime(series.time)],
              [t("Spatial resolution"), `${series.grid.length} grid points over national scope`],
              [t("Temporal resolution"), "1 hour"],
              [t("Units"), "°C, mm, %, km/h, AQI"],
              [t("Data quality"), series.official ? "Official IMD source" : "Model forecast (non-official)"],
              [t("Processing"), "Bilinear spatial interpolation + linear temporal interpolation, canvas rendering"],
            ].map(([k, v]) => (
              <div key={k} className="flex justify-between gap-4">
                <dt className="shrink-0 text-slate-500">{k}</dt>
                <dd className="text-right text-slate-300">{v}</dd>
              </div>
            ))}
          </dl>
          <p className="mt-3 text-[10px] text-amber-400/90">
            {t("Radar and historical animations require radar/satellite feeds that are not available in the current deployment. Animations are driven only by actual forecast data; no synthetic precipitation is generated.")}
          </p>
        </div>
      )}
    </div>
  );
}

function MarkerInfoBar({
  map,
  series,
  pin,
  frame,
  playing,
  canPlay,
  onTogglePlay,
  onClose,
}: {
  map: L.Map | null;
  series: WeatherMapSeries;
  pin: [number, number];
  frame: number;
  playing: boolean;
  canPlay: boolean;
  onTogglePlay: () => void;
  onClose: () => void;
}) {
  const ref = useRef<HTMLDivElement | null>(null);

  // Keep the bar glued to the geographic coordinate through pan/zoom.
  useEffect(() => {
    if (!map) return;
    const update = () => {
      const el = ref.current;
      if (!el) return;
      const pt = map.latLngToContainerPoint(L.latLng(pin[0], pin[1]));
      el.style.left = `${pt.x}px`;
      el.style.top = `${Math.max(pt.y - 46, 64)}px`;
    };
    update();
    map.on("move zoom resize viewreset", update);
    return () => {
      map.off("move zoom resize viewreset", update);
    };
  }, [map, pin[0], pin[1]]);

  const w = sampleWeatherAt(series, pin[0], pin[1], frame);
  const when = series.times[Math.min(frame, series.times.length - 1)];
  const d = new Date(when);
  const dateLabel = Number.isNaN(d.getTime())
    ? when
    : `${d.toLocaleString("en-IN", { weekday: "short" })} ${d.getDate()}, ${d.toLocaleString("en-IN", { hour: "numeric" })}`;

  return (
    <div
      ref={ref}
      className="absolute z-[520] flex -translate-x-1/2 -translate-y-full items-center gap-3 rounded-xl border border-white/10 bg-slate-800/85 px-4 py-2 shadow-2xl backdrop-blur-md"
      style={{ pointerEvents: "auto" }}
    >
      <span className="text-xl font-bold tabular-nums text-white">
        {w.temperature_2m !== null ? `${Math.round(w.temperature_2m)}°` : "—"}
      </span>
      <span className="whitespace-nowrap text-xs font-semibold text-slate-200">{dateLabel}</span>
      <button
        type="button"
        onClick={onTogglePlay}
        disabled={!canPlay && !playing}
        title={playing ? "Pause forecast animation" : "Play forecast animation"}
        className={cn(
          "flex h-7 w-7 items-center justify-center rounded-full shadow transition-colors",
          playing ? "bg-slate-500 hover:bg-slate-400" : "bg-amber-400 text-slate-900 hover:bg-amber-300",
          !canPlay && !playing && "cursor-not-allowed opacity-40"
        )}
        aria-label={playing ? "Pause" : "Play"}
      >
        {playing ? (
          <Pause className="h-3.5 w-3.5" />
        ) : (
          <Play className="h-3.5 w-3.5 translate-x-[1px]" />
        )}
      </button>
      <button
        type="button"
        onClick={onClose}
        className="flex h-6 w-6 items-center justify-center rounded text-slate-400 hover:bg-white/10 hover:text-white"
        aria-label="Close"
      >
        <X className="h-3.5 w-3.5" />
      </button>
    </div>
  );
}

function WeatherCard({
  lat,
  lon,
  settings,
}: {
  lat: number;
  lon: number;
  settings: AnimSettings;
}) {
  const { t } = useLanguage();
  const [data, setData] = useState<Awaited<ReturnType<typeof fetchPointWeather>> | null>(null);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState<string | null>(null);
  const [ai, setAi] = useState<string | null>(null);
  const [aiLoading, setAiLoading] = useState(false);
  const [tab, setTab] = useState<"now" | "week" | "charts">("now");

  useEffect(() => {
    let active = true;
    setLoading(true);
    setErr(null);
    setTab("now");
    fetchPointWeather(lat, lon, 7)
      .then((d) => active && setData(d))
      .catch((e) => active && setErr(getApiError(e)))
      .finally(() => active && setLoading(false));
    return () => {
      active = false;
    };
  }, [lat, lon]);

  const runAI = async () => {
    setAiLoading(true);
    setAi(null);
    try {
      const c = data?.current;
      const temp = c?.temperature_2m;
      const rain = c?.precipitation;
      const hum = c?.relative_humidity_2m;
      const wind = c?.wind_speed_10m;
      const parts = [
        `Weather at (${lat.toFixed(3)}, ${lon.toFixed(3)}) — model forecast (non-official):`,
      ];
      if (temp != null) parts.push(`temperature ${Math.round(temp)}°C`);
      if (rain != null) parts.push(`precipitation ${rain.toFixed(2)} mm`);
      if (hum != null) parts.push(`humidity ${hum}%`);
      if (wind != null) parts.push(`wind ${wind.toFixed(1)} km/h`);
      if (parts.length === 1) parts.push("no current observation available");
      setAi(
        parts.join(" ") +
          " Groundwater recharge may increase if soil, land-use, aquifer and runoff conditions permit. This is a conceptual relationship, not a direct causal claim."
      );
    } catch {
      setAi(t("AI analysis failed. Please try again."));
    } finally {
      setAiLoading(false);
    }
  };

  const tabs: { key: "now" | "week" | "charts"; label: string }[] = [
    { key: "now", label: t("Current") },
    { key: "week", label: t("7-day forecast") },
    { key: "charts", label: t("Graphs") },
  ];

  const c = data?.current;
  const today = data?.daily?.[0] ?? null;

  return (
    <div className="mt-2">
      {/* Hero: big icon + temperature, understandable in one glance. */}
      {c && (
        <div className="mb-2 rounded-lg bg-gradient-to-br from-sky-500/15 to-transparent p-3">
          <div className="flex items-center gap-3">
            <span aria-hidden className="text-4xl leading-none">
              {weatherEmoji(c.weather_code, c.is_day)}
            </span>
            <div>
              <div className="flex items-start gap-1 text-4xl font-bold leading-none text-white tabular-nums">
                {c.temperature_2m != null ? Math.round(c.temperature_2m) : "—"}
                <span className="mt-0.5 text-lg font-semibold">°C</span>
              </div>
              <div className="mt-1 text-xs font-medium capitalize text-slate-300">
                {c.weather_label ?? t("Weather")}
              </div>
            </div>
          </div>
          {(today?.temperature_2m_max != null || today?.temperature_2m_min != null) && (
            <div className="mt-2 flex items-center gap-4 text-xs font-medium text-slate-300 tabular-nums">
              <span>
                {t("High")} {today?.temperature_2m_max != null ? `${Math.round(today.temperature_2m_max)}°` : "—"}
              </span>
              <span>
                {t("Low")} {today?.temperature_2m_min != null ? `${Math.round(today.temperature_2m_min)}°` : "—"}
              </span>
              {today?.precipitation_probability_max != null && (
                <span>
                  🌧️ {t("{pct}% rain", { pct: today.precipitation_probability_max })}
                </span>
              )}
            </div>
          )}
        </div>
      )}
      {/* Simple weather warnings computed from the actual forecast. */}
      {data && <WeatherAlerts data={data} />}
      <div className="mb-2 grid grid-cols-3 gap-1 rounded-lg bg-white/5 p-0.5">
        {tabs.map((tb) => (
          <button
            key={tb.key}
            type="button"
            onClick={() => setTab(tb.key)}
            className={cn(
              "rounded-md py-1 text-[11px] font-semibold transition-colors",
              tab === tb.key ? "bg-sky-500 text-white" : "text-slate-400 hover:text-slate-200"
            )}
          >
            {tb.label}
          </button>
        ))}
      </div>

      {loading ? (
        <div className="flex items-center gap-2 py-3 text-xs text-slate-500">
          <Loader2 className="h-3.5 w-3.5 animate-spin" />
          {t("Loading weather…")}
        </div>
      ) : err || !data || !data.current ? (
        <div className="py-3 text-xs text-slate-500">{t("Weather data unavailable for this location.")}</div>
      ) : tab === "now" ? (
        <CurrentPanel data={data} settings={settings} ai={ai} aiLoading={aiLoading} onAI={runAI} />
      ) : tab === "week" ? (
        <WeekPanel data={data} />
      ) : (
        <WeatherCharts data={data} />
      )}
    </div>
  );
}

function CurrentPanel({
  data,
  settings,
  ai,
  aiLoading,
  onAI,
}: {
  data: Awaited<ReturnType<typeof fetchPointWeather>>;
  settings: AnimSettings;
  ai: string | null;
  aiLoading: boolean;
  onAI: () => void;
}) {
  const { t } = useLanguage();
  const c = data.current;
  if (!c) return null;
  const windUnit = settings.windUnit === "ms" ? "m/s" : "km/h";
  const windVal = c.wind_speed_10m != null
    ? settings.windUnit === "ms"
      ? (c.wind_speed_10m / 3.6).toFixed(1)
      : c.wind_speed_10m.toFixed(1)
    : null;
  const rows: { icon: typeof Droplets; label: string; value: string }[] = [
    { icon: Navigation, label: t("Feels like"), value: c.apparent_temperature != null ? `${Math.round(c.apparent_temperature)}°C` : "—" },
    { icon: Droplets, label: t("Humidity"), value: c.relative_humidity_2m != null ? `${c.relative_humidity_2m}%` : "—" },
    { icon: Droplets, label: t("Rainfall"), value: c.precipitation != null ? `${c.precipitation.toFixed(1)} mm` : "—" },
    { icon: Wind, label: t("Wind"), value: windVal != null ? `${windVal} ${windUnit}` : "—" },
  ];
  return (
    <div className="space-y-2">
      <div className="grid grid-cols-2 gap-1.5">
        {rows.map((r) => (
          <div key={r.label} className="rounded-md bg-white/5 px-2 py-1.5">
            <div className="flex items-center gap-1 text-[10px] text-slate-500">
              <r.icon className="h-3 w-3" />
              {r.label}
            </div>
            <div className="truncate text-xs font-semibold text-slate-200">{r.value}</div>
          </div>
        ))}
      </div>
      <RainOutlook data={data} />
      <Button
        size="sm"
        variant="outline"
        className="h-7 border-white/10 bg-white/5 text-[11px] text-slate-200 hover:bg-white/10 hover:text-white"
        onClick={onAI}
        disabled={aiLoading}
      >
        {aiLoading ? <Loader2 className="h-3 w-3 animate-spin" /> : null}
        {t("AI analysis")}
      </Button>
      {ai && (
        <div className="rounded-md bg-sky-500/10 px-2 py-1.5 text-[11px] leading-relaxed text-slate-300">
          {ai}
        </div>
      )}
      <div className="text-[10px] text-slate-600">
        {data.source} · {formatTime(c.time)}
      </div>
    </div>
  );
}
// ---------------------------------------------------------------------------
// Village-friendly weather panels (weather-map transformation)
// ---------------------------------------------------------------------------

type PointData = Awaited<ReturnType<typeof fetchPointWeather>>;

/** Familiar emoji for a WMO weather code (night-aware for clear skies). */
export function weatherEmoji(
  code: number | null | undefined,
  isDay?: number | null
): string {
  if (code == null) return "\u{1F321}";
  if (code === 0 || code === 1) return isDay === 0 ? "\u{1F319}" : "\u{2600}\u{FE0F}";
  if (code === 2) return isDay === 0 ? "\u{2601}" : "\u{1F324}\u{FE0F}";
  if (code === 3) return "\u2601\uFE0F";
  if (code === 45 || code === 48) return "\u{1F32B}\u{FE0F}";
  if (code >= 51 && code <= 57) return "\u{1F326}\u{FE0F}";
  if ((code >= 61 && code <= 67) || (code >= 80 && code <= 82)) return "\u{1F327}\u{FE0F}";
  if ((code >= 71 && code <= 77) || code === 85 || code === 86) return "\u{1F328}\u{FE0F}";
  if (code >= 95) return "\u26C8\uFE0F";
  return "\u{1F324}\u{FE0F}";
}

/** Translation key describing an expected rainfall total in plain words. */
function rainfallWordKey(mm: number): string {
  if (mm < 0.2) return "rain_no";
  if (mm < 7.5) return "rain_light";
  if (mm < 35) return "rain_moderate";
  if (mm < 65) return "rain_heavy";
  return "rain_very_heavy";
}

function nextHourIndex(data: PointData): number {
  const cur = data.current?.time;
  if (!cur) return 0;
  const idx = data.hourly.findIndex((h) => h.time >= cur);
  return idx < 0 ? 0 : idx;
}

/** Highest chance-of-rain (%) within the next N hours. */
function maxRainChance(data: PointData, start: number, count: number): number {
  let maxP = 0;
  for (let i = start; i < Math.min(start + count, data.hourly.length); i++) {
    maxP = Math.max(maxP, data.hourly[i]?.precipitation_probability ?? 0);
  }
  return maxP;
}

/** Highly visible, plainly-worded warnings derived from the real forecast. */
export function WeatherAlerts({ data }: { data: PointData }) {
  const { t } = useLanguage();
  const alerts: { tone: "warn" | "info"; text: string }[] = [];
  const idx = nextHourIndex(data);

  const chance3h = maxRainChance(data, idx, 3);
  if (chance3h >= 50) {
    alerts.push({ tone: "info", text: t("Rain is likely within the next 3 hours ({pct}% chance).", { pct: Math.round(chance3h) }) });
  }
  const todayRainMm = data.daily?.[0]?.precipitation_sum ?? null;
  if (todayRainMm != null && todayRainMm >= 35) {
    alerts.push({ tone: "warn", text: t("Heavy rainfall may occur today (about {mm} mm). Take care around streams and low areas.", { mm: Math.round(todayRainMm) }) });
  }
  const tomorrowMax = data.daily?.[1]?.temperature_2m_max ?? null;
  if (tomorrowMax != null && tomorrowMax >= 40) {
    alerts.push({ tone: "warn", text: t("Very hot tomorrow — about {deg}°C. Stay hydrated.", { deg: Math.round(tomorrowMax) }) });
  }
  const todayMax = data.daily?.[0]?.temperature_2m_max ?? null;
  if (todayMax != null && todayMax >= 41) {
    alerts.push({ tone: "warn", text: t("Very hot today — about {deg}°C.", { deg: Math.round(todayMax) }) });
  }
  let windMax = 0;
  for (let i = idx; i < Math.min(idx + 12, data.hourly.length); i++) {
    windMax = Math.max(windMax, data.hourly[i]?.wind_speed_10m ?? 0);
  }
  if (windMax >= 35) {
    alerts.push({ tone: "warn", text: t("Strong winds expected today.") });
  }

  if (!alerts.length) return null;
  return (
    <div className="mb-2 space-y-1.5">
      {alerts.slice(0, 2).map((a, i) => (
        <div
          key={i}
          className={
            a.tone === "warn"
              ? "flex items-start gap-2 rounded-lg border border-amber-400/40 bg-amber-400/15 px-2.5 py-1.5 text-[11px] font-semibold leading-snug text-amber-200"
              : "flex items-start gap-2 rounded-lg border border-sky-400/30 bg-sky-400/10 px-2.5 py-1.5 text-[11px] font-semibold leading-snug text-sky-200"
          }
        >
          <span aria-hidden>{a.tone === "warn" ? "\u26A0\uFE0F" : "\u{1F327}\u{FE0F}"}</span>
          <span>{a.text}</span>
        </div>
      ))}
    </div>
  );
}

/** Simple hourly rain-chance bars for the next 24 hours + plain totals. */
export function RainOutlook({ data }: { data: PointData }) {
  const { t } = useLanguage();
  const idx = nextHourIndex(data);
  const hours = data.hourly.slice(idx, idx + 24);
  const chances = hours.map((h) => h.precipitation_probability ?? 0);
  const todayRainMm = data.daily?.[0]?.precipitation_sum ?? null;
  const chance24 = Math.max(...chances, 0);

  return (
    <div className="rounded-md bg-white/5 px-2 py-2">
      <div className="mb-1.5 flex items-center justify-between text-[10px] font-semibold uppercase tracking-wide text-slate-500">
        <span>{t("When will it rain?")}</span>
        <span>{t("Next 24 hours")}</span>
      </div>
      <div
        className="flex h-12 items-end gap-[2px]"
        role="img"
        aria-label={t("Chance of rain over the next 24 hours")}
      >
        {chances.map((p, i) => (
          <div
            key={i}
            title={`${formatHour(hours[i]?.time)} · ${t("{pct}% rain", { pct: p })}`}
            className={
              p >= 50
                ? "min-w-[3px] flex-1 rounded-t bg-sky-500"
                : p > 0
                  ? "min-w-[3px] flex-1 rounded-t bg-sky-500/40"
                  : "min-w-[3px] flex-1 rounded-t bg-white/10"
            }
            style={{ height: `${Math.max(3, (p / 100) * 44)}px` }}
          />
        ))}
      </div>
      <p className="mt-1.5 text-[11px] leading-snug text-slate-300">
        {todayRainMm != null && todayRainMm > 0.2
          ? t(
              "{word} expected today (about {mm} mm). Highest chance: {pct}%.",
              {
                word: t(rainfallWordKey(todayRainMm)),
                mm: todayRainMm.toFixed(1),
                pct: Math.round(chance24),
              }
            )
          : t("No rain expected in the next 24 hours.")}
      </p>
    </div>
  );
}

/** Friendly 7-day list: day, icon, high/low and chance of rain. */
export function WeekPanel({ data }: { data: PointData }) {
  const { t } = useLanguage();
  const days = (data.daily ?? []).slice(0, 7);
  if (!days.length) {
    return <div className="py-3 text-xs text-slate-500">{t("Weather data unavailable for this location.")}</div>;
  }
  return (
    <div className="space-y-1">
      {days.map((d, i) => {
        const dt = new Date(d.date);
        const dayLabel =
          i === 0
            ? t("Today")
            : Number.isNaN(dt.getTime())
              ? d.date
              : dt.toLocaleString("en-IN", { weekday: "short" });
        return (
          <div
            key={d.date}
            className="flex items-center gap-2 rounded-md bg-white/5 px-2 py-1.5"
          >
            <span className="w-14 shrink-0 text-xs font-semibold text-slate-300">{dayLabel}</span>
            <span aria-hidden className="w-7 shrink-0 text-center text-lg leading-none">
              {weatherEmoji(d.weather_code, 1)}
            </span>
            <span className="min-w-0 flex-1 truncate text-[11px] text-slate-500">
              {d.weather_label ?? ""}
            </span>
            <span className="shrink-0 text-xs font-bold tabular-nums text-white">
              {d.temperature_2m_max != null ? `${Math.round(d.temperature_2m_max)}°` : "—"}
            </span>
            <span className="shrink-0 text-xs font-medium tabular-nums text-slate-500">
              {d.temperature_2m_min != null ? `${Math.round(d.temperature_2m_min)}°` : "—"}
            </span>
            <span className="inline-flex w-12 shrink-0 items-center justify-end gap-0.5 text-[11px] font-semibold tabular-nums text-sky-300">
              🌧️ {d.precipitation_probability_max != null ? `${d.precipitation_probability_max}%` : "—"}
            </span>
          </div>
        );
      })}
    </div>
  );
}
