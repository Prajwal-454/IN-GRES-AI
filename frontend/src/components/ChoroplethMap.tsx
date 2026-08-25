import { useMemo, useState } from "react";

import type { MapFeature } from "@/services/gis";
import { cn } from "@/lib/utils";

const CATEGORY_COLORS: Record<string, string> = {
  safe: "#16a34a",
  "semi-critical": "#eab308",
  critical: "#f97316",
  "over-exploited": "#dc2626",
};

interface ChoroplethMapProps {
  features: MapFeature[];
  metric: string;
  className?: string;
}

interface Projected {
  feature: MapFeature;
  path: string;
}

function project(features: MapFeature[], vw: number, vh: number, pad: number): Projected[] {
  const xs: number[] = [];
  const ys: number[] = [];
  for (const f of features) {
    for (const [lon, lat] of f.geometry.coordinates[0]) {
      xs.push(lon);
      ys.push(lat);
    }
  }
  const minX = Math.min(...xs);
  const maxX = Math.max(...xs);
  const minY = Math.min(...ys);
  const maxY = Math.max(...ys);
  const spanX = maxX - minX || 1;
  const spanY = maxY - minY || 1;
  const scale = Math.min((vw - pad * 2) / spanX, (vh - pad * 2) / spanY);
  const offsetX = (vw - spanX * scale) / 2;
  const offsetY = (vh - spanY * scale) / 2;

  return features.map((feature) => {
    const rings = feature.geometry.coordinates.map((ring) =>
      ring
        .map(([lon, lat]) => {
          const x = offsetX + (lon - minX) * scale;
          const y = offsetY + (maxY - lat) * scale;
          return `${x.toFixed(1)},${y.toFixed(1)}`;
        })
        .join(" ")
    );
    return { feature, path: rings.map((r) => `M${r} Z`).join(" ") };
  });
}

function colorFor(feature: MapFeature, metric: string, min: number, max: number): string {
  const v = feature.properties.metric_value;
  if (v === null || v === undefined) return "#e5e7eb";
  if (metric === "stage" && feature.properties.category) {
    return CATEGORY_COLORS[feature.properties.category] ?? "#0ea5e9";
  }
  const t = Math.min(Math.max((v - min) / (max - min || 1), 0), 1);
  const r = Math.round(22 + t * (220 - 22));
  const g = Math.round(163 - t * 130);
  const b = Math.round(101 - t * 70);
  return `rgb(${r},${g},${b})`;
}

function formatValue(feature: MapFeature): string {
  const v = feature.properties.metric_value;
  if (v === null || v === undefined) return "No data";
  if (feature.properties.metric === "stage") return `${v.toFixed(1)}%`;
  return `${v.toFixed(1)} hm³`;
}

export default function ChoroplethMap({ features, metric, className }: ChoroplethMapProps) {
  const [selected, setSelected] = useState<MapFeature | null>(null);
  const vw = 420;
  const vh = 300;

  const projected = useMemo(() => project(features, vw, vh, 10), [features]);
  const values = features
    .map((f) => f.properties.metric_value)
    .filter((v): v is number => v !== null && v !== undefined);
  const min = values.length ? Math.min(...values) : 0;
  const max = values.length ? Math.max(...values) : 1;

  return (
    <div className={cn("relative", className)}>
      <svg viewBox={`0 0 ${vw} ${vh}`} className="w-full rounded-lg border bg-muted/40">
        {projected.map(({ feature, path }) => (
          <path
            key={feature.properties.id}
            d={path}
            fill={colorFor(feature, metric, min, max)}
            stroke="#ffffff"
            strokeWidth={1.2}
            className="cursor-pointer transition-opacity hover:opacity-70"
            onClick={() => setSelected(feature)}
            onMouseEnter={() => setSelected(feature)}
            onMouseLeave={() => setSelected(null)}
          >
            <title>
              {feature.properties.district} — {formatValue(feature)}
            </title>
          </path>
        ))}
      </svg>

      {selected && (
        <div className="pointer-events-none absolute left-3 top-3 rounded-md border bg-background/95 px-3 py-2 text-xs shadow-sm">
          <div className="font-semibold">{selected.properties.district}</div>
          <div className="text-muted-foreground">{selected.properties.state}</div>
          <div className="mt-0.5 font-medium">{formatValue(selected)}</div>
          {selected.properties.stage_of_extraction !== null && (
            <div className="text-muted-foreground">
              Stage: {selected.properties.stage_of_extraction.toFixed(1)}% ·{" "}
              {selected.properties.category ?? "n/a"}
            </div>
          )}
        </div>
      )}
    </div>
  );
}