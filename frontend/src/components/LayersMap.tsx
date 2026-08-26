import L from "leaflet";
import "leaflet/dist/leaflet.css";
import { useEffect, useRef } from "react";

import { useLanguage } from "@/contexts/LanguageContext";
import { cn } from "@/lib/utils";
import type { IndiaMapData, LocationAnalysis, MapData, MapFeature, Station } from "@/services/gis";

export type ActiveLayer =
  | "waterlevel"
  | "recharge"
  | "extraction"
  | "critical"
  | "prediction";

const METRIC_LABELS: Record<string, string> = {
  waterlevel: "Groundwater Level",
  recharge: "Recharge",
  extraction: "Extraction",
};

const CATEGORY_COLORS: Record<string, string> = {
  safe: "#1a9850",
  "semi-critical": "#fdae61",
  critical: "#f46d43",
  "over-exploited": "#d73027",
};

const NO_DATA_COLOR = "#e5e7eb";

// Perceptually smooth 5-stop sequential ramp (RdYlBu-style, colourblind-safe
// ordering): calm at low values, alarm only at the high end.
const RAMP_STOPS: [number, number, number][] = [
  [43, 131, 186],
  [171, 217, 233],
  [255, 255, 191],
  [253, 174, 97],
  [215, 25, 28],
];

export const RAMP_CSS =
  "linear-gradient(to right, rgb(43,131,186), rgb(171,217,233), rgb(255,255,191), rgb(253,174,97), rgb(215,25,28))";

function rampColor(t: number): string {
  const x = Math.min(Math.max(t, 0), 1) * (RAMP_STOPS.length - 1);
  const i = Math.min(Math.floor(x), RAMP_STOPS.length - 2);
  const f = x - i;
  const a = RAMP_STOPS[i];
  const b = RAMP_STOPS[i + 1];
  return `rgb(${Math.round(a[0] + (b[0] - a[0]) * f)},${Math.round(
    a[1] + (b[1] - a[1]) * f
  )},${Math.round(a[2] + (b[2] - a[2]) * f)})`;
}

function waterDepthFromStage(stage: number | null | undefined): number | null {
  if (stage === null || stage === undefined) return null;
  return 1.2 + (Math.max(0, stage) / 100) * 10;
}

function escapeHtml(text: string): string {
  return text.replace(/[&<>"']/g, (c) => {
    switch (c) {
      case "&":
        return "&amp;";
      case "<":
        return "&lt;";
      case ">":
        return "&gt;";
      case '"':
        return "&quot;";
      default:
        return "&#39;";
    }
  });
}

type Translate = (key: string, vars?: Record<string, string | number | null | undefined>) => string;

interface LayersMapProps {
  features: MapFeature[];
  india?: IndiaMapData;
  prediction?: MapData;
  stations: Station[];
  activeLayer: ActiveLayer;
  stationsOn: boolean;
  heatOn?: boolean;
  onAnalyze: (lat: number, lng: number) => Promise<LocationAnalysis | null>;
  className?: string;
}

function heatValue(
  props: Record<string, unknown>,
  activeLayer: ActiveLayer,
  min: number,
  max: number
): number | null {
  const stage = props.stage_of_extraction as number | null | undefined;
  const value = props.metric_value as number | null | undefined;
  const category = props.category as string | null | undefined;
  if (activeLayer === "waterlevel") {
    const depth = waterDepthFromStage(stage);
    if (depth === null) return null;
    return (depth - 1.2) / 10;
  }
  if (activeLayer === "critical") {
    const rank = ["safe", "semi-critical", "critical", "over-exploited"].indexOf(
      String(category ?? "").toLowerCase()
    );
    return rank >= 0 ? rank / 3 : 0;
  }
  if (value === null || value === undefined) return null;
  return (value - min) / (max - min || 1);
}

function pointFor(
  props: Record<string, unknown>,
  geometry: { type: string; coordinates: unknown }
): [number, number] {
  const lat = props.latitude as number | null | undefined;
  const lon = props.longitude as number | null | undefined;
  if (typeof lat === "number" && typeof lon === "number") return [lat, lon];
  const coords = geometry.coordinates as any;
  const ring: number[][] | undefined =
    geometry.type === "MultiPolygon" ? coords?.[0]?.[0] : coords?.[0];
  if (!ring || !ring.length) return [22, 80];
  const lats = ring.map((p: number[]) => p[1]);
  const lons = ring.map((p: number[]) => p[0]);
  return [
    (Math.min(...lats) + Math.max(...lats)) / 2,
    (Math.min(...lons) + Math.max(...lons)) / 2,
  ];
}

function colorFor(
  props: Record<string, unknown>,
  activeLayer: ActiveLayer,
  min: number,
  max: number
): string {
  const stage = props.stage_of_extraction as number | null | undefined;
  const value = props.metric_value as number | null | undefined;
  const category = props.category as string | null | undefined;

  if (activeLayer === "critical" || activeLayer === "prediction") {
    if (category) return CATEGORY_COLORS[category] ?? "#0ea5e9";
    return NO_DATA_COLOR;
  }
  if (activeLayer === "waterlevel") {
    const depth = waterDepthFromStage(stage);
    if (depth === null) return NO_DATA_COLOR;
    return rampColor((depth - 1.2) / 10);
  }
  if (value === null || value === undefined) return NO_DATA_COLOR;
  return rampColor((value - min) / (max - min || 1));
}

function analysisHtml(a: LocationAnalysis, t: Translate): string {
  const rows: string[] = [
    `<div style="font-weight:600;font-size:13px;">📍 ${escapeHtml(a.location ?? "—")}</div>`,
  ];
  const wl = a.water_level;
  if (wl.value !== null && wl.value !== undefined) {
    rows.push(
      `<div style="font-size:12px;margin-top:4px;"><b>${escapeHtml(
        t("Groundwater Level")
      )}</b>: ${wl.value} ${escapeHtml(wl.unit)}</div>`
    );
  }
  if (wl.trend_per_year !== null && wl.trend_per_year !== undefined && wl.trend_per_year !== 0) {
    const arrow = wl.trend_per_year > 0 ? "↓" : "↑";
    rows.push(
      `<div style="color:#6b7280;font-size:12px;">${escapeHtml(t("Trend"))}: ${arrow} ${Math.abs(
        wl.trend_per_year
      ).toFixed(2)} ${escapeHtml(t("m/year"))}</div>`
    );
  } else if (wl.value !== null && wl.value !== undefined) {
    rows.push(
      `<div style="color:#6b7280;font-size:12px;">${escapeHtml(t("Trend"))}: ${escapeHtml(
        t("Stable")
      )}</div>`
    );
  }
  if (a.risk) {
    rows.push(
      `<div style="color:#b45309;font-size:12px;">${escapeHtml(t("Risk"))}: ${escapeHtml(
        a.risk
      )}</div>`
    );
  }
  if (a.prediction && a.prediction.value !== null && a.prediction.value !== undefined) {
    rows.push(
      `<div style="font-size:12px;margin-top:4px;">${escapeHtml(
        t("AI Prediction")
      )} ${a.prediction.target_year} → <b>${a.prediction.value} ${escapeHtml(
        a.prediction.unit
      )}</b></div>`
    );
  }
  if (a.recommendation && a.recommendation.length) {
    rows.push(
      `<div style="font-size:12px;margin-top:4px;"><b>${escapeHtml(
        t("Recommendation")
      )}:</b> ${escapeHtml(a.recommendation[0])}</div>`
    );
  }
  rows.push(
    `<div style="color:#b45309;font-size:11px;margin-top:4px;">${escapeHtml(
      t("IN-GRES Assessment Dataset")
    )}</div>`
  );
  return rows.join("");
}

export default function LayersMap({
  features,
  india,
  prediction,
  stations,
  activeLayer,
  stationsOn,
  heatOn = false,
  onAnalyze,
  className,
}: LayersMapProps) {
  const { t } = useLanguage();
  const containerRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<L.Map | null>(null);
  const layerRef = useRef<L.LayerGroup | null>(null);
  const stationLayerRef = useRef<L.LayerGroup | null>(null);
  const heatLayerRef = useRef<L.LayerGroup | null>(null);
  const fitKeyRef = useRef<string>("");
  const propsRef = useRef<LayersMapProps & { t: Translate }>({
    features,
    india,
    prediction,
    stations,
    activeLayer,
    stationsOn,
    onAnalyze,
    className,
    t,
  });
  propsRef.current = {
    features,
    india,
    prediction,
    stations,
    activeLayer,
    stationsOn,
    heatOn,
    onAnalyze,
    className,
    t,
  };

  useEffect(() => {
    const el = containerRef.current;
    if (!el || mapRef.current) return;

    const map = L.map(el, {
      center: [22, 80],
      zoom: 4,
      scrollWheelZoom: true,
      minZoom: 3,
      zoomControl: false,
    });
    mapRef.current = map;
    L.control.zoom({ position: "bottomright" }).addTo(map);

    // Light muted basemap (CARTO Positron): calm geography, choropleth owns the
    // colour. Place-name tiles sit in a pane ABOVE the polygons so labels stay
    // readable.
    map.createPane("gwBase");
    map.getPane("gwBase")!.style.zIndex = "200";
    map.createPane("gwPoly");
    const polyPane = map.getPane("gwPoly")!;
    polyPane.style.zIndex = "380";
    polyPane.style.pointerEvents = "auto";
    map.createPane("gwLabels");
    const labelPane = map.getPane("gwLabels")!;
    labelPane.style.zIndex = "420";
    labelPane.style.pointerEvents = "none";

    L.tileLayer(
      "https://{s}.basemaps.cartocdn.com/light_nolabels/{z}/{x}/{y}{r}.png",
      { maxZoom: 19, subdomains: "abcd", pane: "gwBase", attribution: "&copy; OpenStreetMap &copy; CARTO" }
    ).addTo(map);
    L.tileLayer("https://{s}.basemaps.cartocdn.com/light_only_labels/{z}/{x}/{y}{r}.png", {
      maxZoom: 19,
      subdomains: "abcd",
      pane: "gwLabels",
      opacity: 0.9,
    }).addTo(map);

    const layer = L.layerGroup().addTo(map);
    layerRef.current = layer;
    const stationLayer = L.layerGroup().addTo(map);
    stationLayerRef.current = stationLayer;
    const heatLayer = L.layerGroup([], { pane: "gwPoly" }).addTo(map);
    heatLayerRef.current = heatLayer;

    map.on("click", async (e: L.LeafletMouseEvent) => {
      const { t: tt, onAnalyze: analyze } = propsRef.current;
      if (!analyze) return;
      const popup = L.popup()
        .setLatLng(e.latlng)
        .setContent(escapeHtml(tt("Analyzing location…")))
        .openOn(map);
      try {
        const a = await analyze(e.latlng.lat, e.latlng.lng);
        if (!a || a.error || !a.location) {
          popup.setContent(escapeHtml(tt("No groundwater data near this location.")));
        } else {
          popup.setContent(analysisHtml(a, tt));
        }
      } catch {
        popup.setContent(escapeHtml(tt("Could not analyze this location.")));
      }
    });

    return () => {
      map.remove();
      mapRef.current = null;
      layerRef.current = null;
      stationLayerRef.current = null;
      heatLayerRef.current = null;
    };
  }, []);

  useEffect(() => {
    const map = mapRef.current;
    const layer = layerRef.current;
    if (!map || !layer) return;

    layer.clearLayers();
    stationLayerRef.current?.clearLayers();
    heatLayerRef.current?.clearLayers();

    const { features: fs, india: ind, prediction: pred, activeLayer: active, stations: sts, stationsOn: sOn, heatOn: hOn } =
      propsRef.current;

    const valueFeatures: (MapFeature | IndiaMapData["features"][number])[] = [
      ...(ind?.features ?? []),
      ...fs,
    ];
    const predFeatures = active === "prediction" ? (pred?.features ?? []) : [];

    const values: number[] = [];
    for (const f of valueFeatures) {
      const p = f.properties;
      if (active === "waterlevel") {
        const d = waterDepthFromStage(p.stage_of_extraction);
        if (d !== null) values.push(d);
      } else if (active !== "critical" && p.metric_value !== null && p.metric_value !== undefined) {
        values.push(p.metric_value);
      }
    }
    const min = values.length ? Math.min(...values) : 0;
    const max = values.length ? Math.max(...values) : 1;

    const bounds = L.latLngBounds([]);
    const scopeSig = `${ind ? "india" : "units"}|${active}|${valueFeatures.length}|${
      (valueFeatures[0] as { properties?: { name?: string } })?.properties?.name ?? ""
    }|${
      (valueFeatures[valueFeatures.length - 1] as { properties?: { name?: string } } | undefined)
        ?.properties?.name ?? ""
    }`;

    if (valueFeatures.length) {
      const geo = L.geoJSON(valueFeatures as unknown as GeoJSON.FeatureCollection, {
        pane: "gwPoly",
        style: (feature) => {
          const props = (feature?.properties ?? {}) as Record<string, unknown>;
          const fill =
            active === "prediction" ? NO_DATA_COLOR : colorFor(props, active, min, max);
          return {
            fillColor: fill,
            color: "#ffffff",
            weight: 1,
            smoothFactor: 1,
            lineJoin: "round",
            fillOpacity: hOn ? 0.25 : 0.78,
          };
        },
        onEachFeature: (feature, lyr) => {
          const props = (feature?.properties ?? {}) as Record<string, unknown>;
          const name = String(props.name ?? props.state ?? "—");
          const stage = props.stage_of_extraction as number | null | undefined;
          const value = props.metric_value as number | null | undefined;
          const category = props.category as string | null | undefined;
          const lines = [`<b>${escapeHtml(name)}</b>`];
          if (stage !== null && stage !== undefined) {
            lines.push(`${escapeHtml(t("Stage of extraction"))}: ${Number(stage).toFixed(1)}%`);
          }
          if (value !== null && value !== undefined) {
            lines.push(
              `${escapeHtml(t(METRIC_LABELS[active] ?? "Value"))}: ${Number(value).toFixed(1)}`
            );
          }
          if (category) lines.push(escapeHtml(category));
          lyr.bindTooltip(lines.join("<br/>"), {
            sticky: true,
            className: "gw-tooltip",
            opacity: 0.95,
          });
          lyr.on("mouseover", () => {
            (lyr as L.Path).setStyle({ weight: 2, color: "#334155", fillOpacity: 0.88 });
            (lyr as L.Path).bringToFront();
          });
          lyr.on("mouseout", () => {
            (lyr as L.Path).setStyle({ weight: 1, color: "#ffffff", fillOpacity: hOn ? 0.25 : 0.78 });
          });
        },
      }).addTo(layer);
      geo.eachLayer((l) => {
        const ll = l as L.Polygon;
        if (ll.getBounds) bounds.extend(ll.getBounds());
      });
    }

    if (predFeatures.length) {
      const geo = L.geoJSON(predFeatures as unknown as GeoJSON.FeatureCollection, {
        pane: "gwPoly",
        style: (feature) => ({
          fillColor: colorFor(
            (feature?.properties ?? {}) as Record<string, unknown>,
            "prediction",
            min,
            max
          ),
          color: "#94a3b8",
          weight: 1,
          dashArray: "3 4",
          fillOpacity: 0.6,
        }),
      }).addTo(layer);
      geo.eachLayer((l) => {
        const ll = l as L.Polygon;
        if (ll.getBounds) bounds.extend(ll.getBounds());
      });
    }

    if (hOn) {
      const heatLayer = heatLayerRef.current;
      if (heatLayer) {
        const heatFeatures =
          active === "prediction" && predFeatures.length ? predFeatures : valueFeatures;
        for (const f of heatFeatures as unknown as {
          properties: Record<string, unknown>;
          geometry: { type: string; coordinates: unknown };
        }[]) {
          const tv = heatValue(f.properties, active, min, max);
          if (tv === null) continue;
          const [lat, lon] = pointFor(f.properties, f.geometry);
          L.circleMarker([lat, lon], {
            radius: 6 + 16 * tv,
            stroke: false,
            fillColor: rampColor(Math.min(Math.max(tv, 0), 1)),
            fillOpacity: 0.28,
          }).addTo(heatLayer);
        }
      }
    }

    if (sOn && sts.length) {
      for (const s of sts) {
        const icon = L.divIcon({
          className: "",
          html: `<div style="width:11px;height:11px;border-radius:50%;background:#0284c7;border:2px solid #ffffff;box-shadow:0 0 0 1px rgba(15,23,42,0.35),0 1px 3px rgba(0,0,0,0.3);"></div>`,
          iconSize: [11, 11],
          iconAnchor: [5.5, 5.5],
        });
        const marker = L.marker([s.latitude, s.longitude], { icon }).addTo(
          stationLayerRef.current!
        );
        marker.bindPopup(
          `<div style="font-weight:600;font-size:12px;">${escapeHtml(s.district)}</div><div style="color:#6b7280;font-size:12px;">${escapeHtml(
            t("Monitoring station")
          )} · ${escapeHtml(s.state)}</div>`
        );
      }
    }

    // Refit the camera only when the *scope* changes — not on every year tick
    // of a time-lapse, which made the map constantly jump around.
    if (bounds.isValid() && fitKeyRef.current !== scopeSig) {
      fitKeyRef.current = scopeSig;
      map.fitBounds(bounds, { padding: [25, 25], animate: true });
    }
  }, [features, india, prediction, stations, activeLayer, stationsOn, heatOn, t]);

  return (
    <div
      ref={containerRef}
      className={cn("z-0 h-[520px] w-full rounded-lg border", className)}
      aria-label="Layered groundwater map of India"
    />
  );
}