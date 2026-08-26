import { useEffect, useRef, useState } from "react";

import { useLanguage } from "@/contexts/LanguageContext";
import { cn } from "@/lib/utils";
import type { MapLocate } from "@/pages/GIS/GIS";
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

let loadPromise: Promise<any> | null = null;

function loadGoogleMaps(apiKey: string): Promise<any> {
  if (loadPromise) return loadPromise;
  loadPromise = new Promise((resolve, reject) => {
    if ((window as any).google?.maps) {
      resolve((window as any).google);
      return;
    }
    const callback = "__gmapsInit_" + Math.random().toString(36).slice(2);
    (window as any)[callback] = () => {
      delete (window as any)[callback];
      resolve((window as any).google);
    };
    const script = document.createElement("script");
    script.src = `https://maps.googleapis.com/maps/api/js?key=${encodeURIComponent(
      apiKey
    )}&callback=${callback}&v=weekly`;
    script.async = true;
    script.defer = true;
    script.onerror = () => reject(new Error("Failed to load the Google Maps script."));
    document.head.appendChild(script);
  });
  return loadPromise;
}

function featureCollection(features: any[]) {
  return { type: "FeatureCollection", features };
}

type Translate = (key: string, vars?: Record<string, string | number | null | undefined>) => string;

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

function stateColor(
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

function formatValue(feature: MapFeature, t: Translate): string {
  const v = feature.properties.metric_value;
  if (v === null || v === undefined) return t("No data");
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

function formatDelta(delta: number | null | undefined, t: Translate): string {
  if (delta === null || delta === undefined) return t("No data");
  const sign = delta > 0 ? "+" : "";
  return `${sign}${delta.toFixed(1)}`;
}

function infoContent(feature: MapFeature, t: Translate, compare = false): string {
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
        t("IN-GRES Assessment Dataset")
      )}</div>`
    );
  }
  return rows.join("");
}

function stateInfoContent(feature: IndiaFeature, t: Translate, compare = false): string {
  const p = feature.properties;
  const rows: string[] = [
    `<div style="font-weight:600;font-size:13px;">${escapeHtml(p.name)}</div>`,
    `<div style="color:#6b7280;font-size:12px;">${escapeHtml(t("State / UT"))} · ${p.year}</div>`,
  ];
  if (!p.has_data) {
    rows.push(
      `<div style="color:#6b7280;font-size:12px;margin-top:4px;">${escapeHtml(
        t("No assessment data for this location")
      )}</div>`
    );
    return rows.join("");
  }
  rows.push(
    `<div style="font-size:12px;margin-top:4px;"><b>${escapeHtml(
      p.metric_value === null || p.metric_value === undefined
        ? t("No data")
        : `${p.metric_value.toFixed(1)}${p.metric === "stage" ? "%" : " hm³"}`
    )}</b> · ${p.unit_count} ${p.unit_count === 1 ? t("unit") : t("unit.plural")}</div>`
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
        t("IN-GRES Assessment Dataset")
      )}</div>`
    );
  }
  return rows.join("");
}

interface GoogleMapViewProps {
  features: MapFeature[];
  metric: string;
  apiKey: string;
  india?: IndiaMapData;
  compare?: boolean;
  focus?: { lat: number; lng: number; zoom: number } | null;
  locate?: MapLocate | null;
  className?: string;
}

function focusFromFeatures(
  features: MapFeature[]
): { lat: number; lng: number; zoom: number } | null {
  let minLat = Infinity;
  let maxLat = -Infinity;
  let minLng = Infinity;
  let maxLng = -Infinity;
  let count = 0;
  for (const f of features) {
    for (const ring of f.geometry.coordinates) {
      for (const [lng, lat] of ring) {
        if (lat < minLat) minLat = lat;
        if (lat > maxLat) maxLat = lat;
        if (lng < minLng) minLng = lng;
        if (lng > maxLng) maxLng = lng;
        count++;
      }
    }
  }
  if (!count) return null;
  const span = Math.max(maxLat - minLat, maxLng - minLng);
  const zoom = Math.max(6, Math.min(15, Math.round(12 - Math.log2(Math.max(span, 1e-6)))));
  return {
    lat: (minLat + maxLat) / 2,
    lng: (minLng + maxLng) / 2,
    zoom,
  };
}

export default function GoogleMapView({
  features,
  metric,
  apiKey,
  india,
  compare,
  focus,
  locate,
  className,
}: GoogleMapViewProps) {
  const { t } = useLanguage();
  const mapRef = useRef<HTMLDivElement>(null);
  const [status, setStatus] = useState<"loading" | "ready" | "error">("loading");
  const [message, setMessage] = useState("Loading Google Maps…");

  useEffect(() => {
    setStatus("loading");
    setMessage(t("Loading Google Maps…"));
    if (!apiKey) {
      setStatus("error");
      setMessage(t("Set VITE_GOOGLE_MAPS_API_KEY to use Google Maps."));
      return;
    }

    let cancelled = false;
    let map: any = null;
    let infoWindow: any = null;

    loadGoogleMaps(apiKey)
      .then((google) => {
        if (cancelled || !mapRef.current) return;

        const values = features
          .map((f) => f.properties.metric_value)
          .filter((v): v is number => v !== null && v !== undefined);
        if (india) {
          for (const f of india.features) {
            if (f.properties.metric_value !== null && f.properties.metric_value !== undefined) {
              values.push(f.properties.metric_value);
            }
          }
        }
        const min = values.length ? Math.min(...values) : 0;
        const max = values.length ? Math.max(...values) : 1;

        map = new google.maps.Map(mapRef.current, {
          center: { lat: 22, lng: 80 },
          zoom: 4,
          mapTypeId: google.maps.MapTypeId.TERRAIN,
          fullscreenControl: true,
          streetViewControl: false,
        });
        infoWindow = new google.maps.InfoWindow();

        if (india) {
          map.data.addGeoJson(featureCollection(india.features));
        }
        map.data.addGeoJson(featureCollection(features));

        map.data.setStyle((feature: any) => {
          const isState =
            feature.getProperty("has_data") !== null && feature.getProperty("has_data") !== undefined;
          const value = feature.getProperty("metric_value");
          if (isState) {
            const prop = {
              name: String(feature.getProperty("name")),
              has_data: Boolean(feature.getProperty("has_data")),
              unit_count: Number(feature.getProperty("unit_count")),
              metric_value: value,
              stage_of_extraction: feature.getProperty("stage_of_extraction"),
              category: feature.getProperty("category"),
              is_demo: Boolean(feature.getProperty("is_demo")),
              year: Number(feature.getProperty("year")),
              metric: String(feature.getProperty("metric")),
              delta: feature.getProperty("delta") as number | null | undefined,
            };
            const color = stateColor(
              { properties: prop } as unknown as IndiaFeature,
              metric,
              min,
              max,
              compare
            );
            return {
              fillColor: color,
              fillOpacity: prop.has_data ? 0.7 : 0.35,
              strokeColor: "#ffffff",
              strokeWeight: 1,
            };
          }
          const prop = {
            ...features[0]?.properties,
            metric_value: value,
            delta: feature.getProperty("delta") as number | null | undefined,
          } as MapFeature["properties"];
          return {
            fillColor: colorFor(
              { properties: prop } as unknown as MapFeature,
              metric,
              min,
              max,
              compare
            ),
            fillOpacity: 0.85,
            strokeColor: "#ffffff",
            strokeWeight: 1.2,
          };
        });

        map.data.addListener("click", (event: any) => {
          const f = event.feature as unknown as { getProperty: (k: string) => unknown };
          const isState =
            f.getProperty("has_data") !== null && f.getProperty("has_data") !== undefined;
          if (isState) {
            const prop = {
              name: String(f.getProperty("name")),
              has_data: Boolean(f.getProperty("has_data")),
              unit_count: Number(f.getProperty("unit_count")),
              metric_value: f.getProperty("metric_value") as number | null,
              stage_of_extraction: f.getProperty("stage_of_extraction") as number | null,
              category: f.getProperty("category") as string | null,
              is_demo: Boolean(f.getProperty("is_demo")),
              year: Number(f.getProperty("year")),
              metric: String(f.getProperty("metric")),
              delta: f.getProperty("delta") as number | null | undefined,
              metric_value_a: f.getProperty("metric_value_a") as number | null | undefined,
              metric_value_b: f.getProperty("metric_value_b") as number | null | undefined,
              category_a: f.getProperty("category_a") as string | null | undefined,
              category_b: f.getProperty("category_b") as string | null | undefined,
              category_changed: Boolean(f.getProperty("category_changed")),
            };
            infoWindow.setContent(
              stateInfoContent({ properties: prop } as unknown as IndiaFeature, t, compare)
            );
          } else {
            const prop = {
              id: Number(f.getProperty("id")),
              name: String(f.getProperty("name")),
              state: String(f.getProperty("state")),
              district: String(f.getProperty("district")),
              year: Number(f.getProperty("year")),
              metric: String(f.getProperty("metric")),
              metric_value: f.getProperty("metric_value") as number | null,
              stage_of_extraction: f.getProperty("stage_of_extraction") as number | null,
              category: f.getProperty("category") as string | null,
              is_demo: Boolean(f.getProperty("is_demo")),
              latitude: f.getProperty("latitude") as number | null,
              longitude: f.getProperty("longitude") as number | null,
              delta: f.getProperty("delta") as number | null | undefined,
              metric_value_a: f.getProperty("metric_value_a") as number | null | undefined,
              metric_value_b: f.getProperty("metric_value_b") as number | null | undefined,
              category_a: f.getProperty("category_a") as string | null | undefined,
              category_b: f.getProperty("category_b") as string | null | undefined,
              category_changed: Boolean(f.getProperty("category_changed")),
            };
            infoWindow.setContent(
              infoContent({ properties: prop } as unknown as MapFeature, t, compare)
            );
          }
          infoWindow.open(map);
        });

        map.data.addListener("mouseover", (event: any) => {
          map.data.revertStyle();
          map.data.overrideStyle(event.feature, { strokeWeight: 3, fillOpacity: 0.9 });
        });
        map.data.addListener("mouseout", () => map.data.revertStyle());

        const bounds = new google.maps.LatLngBounds();
        for (const f of india ? india.features : []) {
          const geom = f.geometry as { type: string; coordinates: any };
          const polys = geom.type === "Polygon" ? [geom.coordinates] : geom.coordinates;
          for (const poly of polys) {
            for (const ring of poly) {
              for (const [lng, lat] of ring) bounds.extend({ lat, lng });
            }
          }
        }
        for (const f of features) {
          for (const ring of f.geometry.coordinates) {
            for (const [lng, lat] of ring) bounds.extend({ lat, lng });
          }
        }
        const target = locate ? focusFromFeatures(features) : focus;
        if (target) {
          map.setCenter({ lat: target.lat, lng: target.lng });
          map.setZoom(target.zoom);
        } else if (!bounds.isEmpty()) {
          map.fitBounds(bounds);
        }

        setStatus("ready");
      })
      .catch((err) => {
        if (cancelled) return;
        setStatus("error");
        setMessage(err instanceof Error ? err.message : t("Failed to load Google Maps."));
      });

    return () => {
      cancelled = true;
      const gmaps = (window as any).google;
      if (map && gmaps?.maps) gmaps.maps.event.clearInstanceListeners(map);
    };
  }, [features, metric, apiKey, india, compare, locate, t]);

  if (status === "error") {
    return (
      <div
        className={cn(
          "flex h-64 items-center justify-center rounded-lg border border-destructive/30 bg-destructive/10 px-6 text-center text-sm text-destructive",
          className
        )}
      >
        {message}
      </div>
    );
  }

  return (
    <div
      ref={mapRef}
      className={cn("h-[460px] w-full rounded-lg border", className)}
      aria-label="Google Maps view of India and assessment units"
    >
      {status === "loading" && (
        <div className="flex h-full items-center justify-center text-sm text-muted-foreground">
          {t("Loading Google Maps…")}
        </div>
      )}
    </div>
  );
}