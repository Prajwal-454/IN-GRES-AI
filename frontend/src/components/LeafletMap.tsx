import L from "leaflet";
import "leaflet/dist/leaflet.css";
import { useEffect, useRef } from "react";

import { useLanguage } from "@/contexts/LanguageContext";
import { cn } from "@/lib/utils";
import type { IndiaFeature, IndiaMapData, MapFeature } from "@/services/gis";

const CATEGORY_COLORS: Record<string, string> = {
  safe: "#16a34a",
  "semi-critical": "#eab308",
  critical: "#f97316",
  "over-exploited": "#dc2626",
};

const NO_DATA_COLOR = "#e5e7eb";

function rampColor(t: number): string {
  const stops = [
    [22, 163, 74],
    [234, 179, 8],
    [220, 38, 38],
  ];
  const x = Math.min(Math.max(t, 0), 1) * (stops.length - 1);
  const i = Math.min(Math.floor(x), stops.length - 2);
  const f = x - i;
  const a = stops[i];
  const b = stops[i + 1];
  const r = Math.round(a[0] + (b[0] - a[0]) * f);
  const g = Math.round(a[1] + (b[1] - a[1]) * f);
  const bl = Math.round(a[2] + (b[2] - a[2]) * f);
  return `rgb(${r},${g},${bl})`;
}

function deltaColor(delta: number, maxAbs: number): string {
  const t = maxAbs > 0 ? delta / maxAbs : 0;
  const x = Math.min(Math.max(t, -1), 1);
  if (x >= 0) {
    return rampColor(0.5 + x * 0.5);
  }
  const stops = [
    [22, 163, 74],
    [234, 179, 8],
  ];
  const f = -x;
  const a = stops[0];
  const b = stops[1];
  const r = Math.round(a[0] + (b[0] - a[0]) * f);
  const g = Math.round(a[1] + (b[1] - a[1]) * f);
  const bl = Math.round(a[2] + (b[2] - a[2]) * f);
  return `rgb(${r},${g},${bl})`;
}

function colorFor(
  feature: MapFeature,
  metric: string,
  min: number,
  max: number,
  compare = false
): string {
  const v = feature.properties.metric_value;
  if (compare) {
    const delta = (feature.properties as MapFeature["properties"] & { delta?: number | null }).delta;
    if (delta === null || delta === undefined) return NO_DATA_COLOR;
    const abs = Math.abs(delta);
    return deltaColor(delta, abs > 0 ? abs : 1);
  }
  if (v === null || v === undefined) return NO_DATA_COLOR;
  if (metric === "stage" && feature.properties.category) {
    return CATEGORY_COLORS[feature.properties.category] ?? "#0ea5e9";
  }
  return rampColor((v - min) / (max - min || 1));
}

function stateColorFor(
  feature: IndiaFeature,
  metric: string,
  min: number,
  max: number,
  compare = false
): string {
  const p = feature.properties;
  if (compare) {
    const delta = (p as IndiaFeature["properties"] & { delta?: number | null }).delta;
    if (delta === null || delta === undefined) return NO_DATA_COLOR;
    const abs = Math.abs(delta);
    return deltaColor(delta, abs > 0 ? abs : 1);
  }
  if (!p.has_data || p.metric_value === null || p.metric_value === undefined) {
    return NO_DATA_COLOR;
  }
  if (metric === "stage" && p.category) {
    return CATEGORY_COLORS[p.category] ?? "#0ea5e9";
  }
  return rampColor((p.metric_value - min) / (max - min || 1));
}

type Translate = (key: string, vars?: Record<string, string | number | null | undefined>) => string;

function formatValue(feature: MapFeature, t: Translate): string {
  const v = feature.properties.metric_value;
  if (v === null || v === undefined) return t("No data");
  if (feature.properties.metric === "stage") return `${v.toFixed(1)}%`;
  return `${v.toFixed(1)} hm³`;
}

function formatStateValue(feature: IndiaFeature, t: Translate): string {
  const v = feature.properties.metric_value;
  if (!feature.properties.has_data || v === null || v === undefined) return t("No data");
  if (feature.properties.metric === "stage") return `${v.toFixed(1)}%`;
  return `${v.toFixed(1)} hm³`;
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

function centroid(ring: number[][]): [number, number] {
  const lngs = ring.map((p) => p[0]);
  const lats = ring.map((p) => p[1]);
  return [
    (Math.min(...lngs) + Math.max(...lngs)) / 2,
    (Math.min(...lats) + Math.max(...lats)) / 2,
  ];
}

function formatDelta(delta: number | null | undefined, t: Translate): string {
  if (delta === null || delta === undefined) return t("No data");
  const sign = delta > 0 ? "+" : "";
  return `${sign}${delta.toFixed(1)}`;
}

function popupHtml(feature: MapFeature, t: Translate, compare = false): string {
  const p = feature.properties;
  const rows: string[] = [
    `<div style="font-weight:600;font-size:13px;">${escapeHtml(p.district)}</div>`,
    `<div style="color:#6b7280;font-size:12px;">${escapeHtml(p.state)} · ${p.year}</div>`,
    `<div style="font-size:12px;margin-top:4px;"><b>${escapeHtml(formatValue(feature, t))}</b></div>`,
  ];
  if (compare) {
    const c = p as MapFeature["properties"] & {
      metric_value_a?: number | null;
      metric_value_b?: number | null;
      delta?: number | null;
      category_a?: string | null;
      category_b?: string | null;
      category_changed?: boolean;
    };
    if (c.metric_value_a !== null && c.metric_value_a !== undefined) {
      rows.push(
        `<div style="color:#6b7280;font-size:12px;">${c.metric_value_a} → ${c.metric_value_b} (${escapeHtml(
          formatDelta(c.delta, t)
        )})</div>`
      );
    }
    if (c.category_changed) {
      rows.push(
        `<div style="color:#b45309;font-size:12px;">${escapeHtml(
          t("Category: {a} → {b}", { a: c.category_a ?? "n/a", b: c.category_b ?? "n/a" })
        )}</div>`
      );
    }
  }
  if (p.stage_of_extraction !== null && !compare) {
    rows.push(
      `<div style="color:#6b7280;font-size:12px;">${escapeHtml(
        t("Stage: {stage}% · {category}", {
          stage: p.stage_of_extraction.toFixed(1),
          category: p.category ?? "n/a",
        })
      )}</div>`
    );
  }
  if (p.is_demo) {
    rows.push(
      `<div style="color:#b45309;font-size:11px;margin-top:2px;">${escapeHtml(
        t("Synthetic demo data")
      )}</div>`
    );
  }
  return rows.join("");
}

function statePopupHtml(feature: IndiaFeature, t: Translate, compare = false): string {
  const p = feature.properties;
  const rows: string[] = [
    `<div style="font-weight:600;font-size:13px;">${escapeHtml(p.name)}</div>`,
    `<div style="color:#6b7280;font-size:12px;">${escapeHtml(t("State / UT"))} · ${p.year}</div>`,
  ];
  if (!p.has_data) {
    rows.push(
      `<div style="color:#6b7280;font-size:12px;margin-top:4px;">${escapeHtml(
        t("No assessment data in demo dataset")
      )}</div>`
    );
    return rows.join("");
  }
  rows.push(
    `<div style="font-size:12px;margin-top:4px;"><b>${escapeHtml(formatStateValue(feature, t))}</b> · ${
      p.unit_count
    } ${p.unit_count === 1 ? t("unit") : t("unit.plural")}</div>`
  );
  if (compare) {
    const c = p as IndiaFeature["properties"] & {
      metric_value_a?: number | null;
      metric_value_b?: number | null;
      delta?: number | null;
      category_a?: string | null;
      category_b?: string | null;
      category_changed?: boolean;
    };
    if (c.metric_value_a !== null && c.metric_value_a !== undefined) {
      rows.push(
        `<div style="color:#6b7280;font-size:12px;">${c.metric_value_a} → ${c.metric_value_b} (${escapeHtml(
          formatDelta(c.delta, t)
        )})</div>`
      );
    }
    if (c.category_changed) {
      rows.push(
        `<div style="color:#b45309;font-size:12px;">${escapeHtml(
          t("Category: {a} → {b}", { a: c.category_a ?? "n/a", b: c.category_b ?? "n/a" })
        )}</div>`
      );
    }
  }
  if (p.stage_of_extraction !== null && !compare) {
    rows.push(
      `<div style="color:#6b7280;font-size:12px;">${escapeHtml(
        t("Avg stage: {stage}% · {category}", {
          stage: p.stage_of_extraction.toFixed(1),
          category: p.category ?? "n/a",
        })
      )}</div>`
    );
  }
  if (p.is_demo) {
    rows.push(
      `<div style="color:#b45309;font-size:11px;margin-top:2px;">${escapeHtml(
        t("Synthetic demo data")
      )}</div>`
    );
  }
  return rows.join("");
}

function polygonsOf(feature: IndiaFeature): number[][][][] {
  if (feature.geometry.type === "Polygon") {
    return [feature.geometry.coordinates as number[][][]];
  }
  return feature.geometry.coordinates as number[][][][];
}

function extendBoundsWithGeometry(bounds: L.LatLngBounds, feature: IndiaFeature): void {
  for (const polygon of polygonsOf(feature)) {
    for (const ring of polygon) {
      for (const [lng, lat] of ring) bounds.extend([lat, lng]);
    }
  }
}

function unitIcon(color: string): L.DivIcon {
  return L.divIcon({
    className: "",
    html:
      `<div style="width:15px;height:15px;border-radius:50%;background:${color};` +
      `border:2px solid rgba(255,255,255,0.95);box-shadow:0 0 0 1px rgba(15,23,42,0.35),0 1px 4px rgba(0,0,0,0.35);"></div>`,
    iconSize: [15, 15],
    iconAnchor: [7.5, 7.5],
  });
}

interface LeafletMapProps {
  features: MapFeature[];
  metric: string;
  india?: IndiaMapData;
  compare?: boolean;
  className?: string;
}

export default function LeafletMap({ features, metric, india, compare, className }: LeafletMapProps) {
  const { t } = useLanguage();
  const containerRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<L.Map | null>(null);
  const layerRef = useRef<L.LayerGroup | null>(null);

  useEffect(() => {
    if (!containerRef.current || mapRef.current) return;

    const map = L.map(containerRef.current, {
      center: [22, 80],
      zoom: 4,
      scrollWheelZoom: true,
      minZoom: 3,
    });
    mapRef.current = map;

    L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
      maxZoom: 19,
      attribution:
        '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
    }).addTo(map);

    const layer = L.layerGroup().addTo(map);
    layerRef.current = layer;

    return () => {
      map.remove();
      mapRef.current = null;
      layerRef.current = null;
    };
  }, []);

  useEffect(() => {
    const map = mapRef.current;
    const layer = layerRef.current;
    if (!map || !layer) return;

    layer.clearLayers();

    const values = features
      .map((f) => f.properties.metric_value)
      .filter((v): v is number => v !== null && v !== undefined);
    const min = values.length ? Math.min(...values) : 0;
    const max = values.length ? Math.max(...values) : 1;

    const bounds = L.latLngBounds([]);

    if (india) {
      for (const feature of india.features) {
        const color = stateColorFor(feature, metric, min, max, compare);
        for (const polygon of polygonsOf(feature)) {
          const shape = L.polygon(
            polygon.map((ring) => ring.map(([lng, lat]) => [lat, lng] as [number, number])),
            {
              color: "#ffffff",
              weight: 1,
              fillColor: color,
              fillOpacity: feature.properties.has_data ? 0.7 : 0.35,
            }
          ).addTo(layer);
          shape.bindPopup(statePopupHtml(feature, t, compare));
        }
        extendBoundsWithGeometry(bounds, feature);
      }
    }

    for (const feature of features) {
      const color = colorFor(feature, metric, min, max, compare);

      const lat = feature.properties.latitude;
      const lng = feature.properties.longitude;
      const [clng, clat] =
        lat !== null && lat !== undefined && lng !== null && lng !== undefined
          ? [lng, lat]
          : centroid(feature.geometry.coordinates[0]);
      const marker = L.marker([clat, clng], { icon: unitIcon(color) }).addTo(layer);
      marker.bindPopup(popupHtml(feature, t, compare));

      for (const [lng, lat] of feature.geometry.coordinates[0]) {
        bounds.extend([lat, lng]);
      }
    }

    if (bounds.isValid()) {
      map.fitBounds(bounds, { padding: [25, 25] });
    }
  }, [features, metric, india, compare, t]);

  return (
    <div
      ref={containerRef}
      className={cn("z-0 h-[460px] w-full rounded-lg border", className)}
      aria-label="Leaflet map of India and assessment units"
    />
  );
}