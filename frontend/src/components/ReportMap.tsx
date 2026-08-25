import { useMemo } from "react";

import { useLanguage } from "@/contexts/LanguageContext";
import { cn } from "@/lib/utils";

const CATEGORY_COLORS: Record<string, string> = {
  safe: "#16a34a",
  "semi-critical": "#eab308",
  critical: "#f97316",
  "over-exploited": "#dc2626",
};
const NO_DATA_COLOR = "#e5e7eb";

interface ReportMapProps {
  features: { properties: Record<string, unknown>; geometry: unknown }[];
  title?: string;
  className?: string;
}

interface Shape {
  d: string;
  fill: string;
  label: string;
}

export default function ReportMap({ features, title, className }: ReportMapProps) {
  const { t } = useLanguage();

  const shapes = useMemo<Shape[]>(() => {
    interface Ring extends Array<[number, number]> {}
    const collected: { ring: Ring; fill: string; label: string }[] = [];
    for (const f of features) {
      const props = f.properties ?? {};
      const category = props.category as string | undefined;
      const fill = category ? (CATEGORY_COLORS[category] ?? NO_DATA_COLOR) : NO_DATA_COLOR;
      const label = String(
        props.name ?? props.assessment_unit ?? props.district ?? props.state ?? ""
      );
      const g = f.geometry as { type?: string; coordinates?: unknown } | null;
      if (!g || !g.coordinates) continue;
      const polys: unknown[] = g.type === "Polygon" ? [g.coordinates] : (g.coordinates as unknown[]);
      for (const poly of polys) {
        const ring0 = (poly as { [key: number]: unknown })[0] as number[][] | undefined;
        if (!ring0) continue;
        const ring = ring0.map((p) => [p[0], p[1]] as [number, number]) as unknown as Ring;
        collected.push({ ring, fill, label });
      }
    }
    if (!collected.length) return [];

    const lngs = collected.flatMap((s) => s.ring.map((p) => p[0]));
    const lats = collected.flatMap((s) => s.ring.map((p) => p[1]));
    const minLng = Math.min(...lngs);
    const maxLng = Math.max(...lngs);
    const minLat = Math.min(...lats);
    const maxLat = Math.max(...lats);
    const k = Math.cos(((minLat + maxLat) / 2) * (Math.PI / 180));
    const spanX = (maxLng - minLng) * k || 1;
    const spanY = maxLat - minLat || 1;
    const W = 640;
    const H = 400;
    const pad = 10;
    const scale = Math.min((W - pad * 2) / spanX, (H - pad * 2) / spanY);
    const cx = (minLng + maxLng) / 2;
    const cy = (minLat + maxLat) / 2;
    const px = (lng: number) => W / 2 + (lng - cx) * k * scale;
    const py = (lat: number) => H / 2 + (cy - lat) * scale;

    return collected.map((s) => ({
      d:
        s.ring
          .map((p, i) => `${i ? "L" : "M"}${px(p[0]).toFixed(2)},${py(p[1]).toFixed(2)}`)
          .join(" ") + " Z",
      fill: s.fill,
      label: s.label,
    }));
  }, [features]);

  if (!shapes.length) {
    return (
      <div
        className={cn(
          "flex items-center justify-center rounded-lg border p-8 text-sm text-muted-foreground",
          className
        )}
      >
        {t("No data")}
      </div>
    );
  }

  return (
    <div className={cn("space-y-2", className)}>
      <svg
        viewBox="0 0 640 400"
        className="w-full rounded-lg border"
        role="img"
        aria-label={title ?? t("Map")}
      >
        {shapes.map((s, i) => (
          <path key={i} d={s.d} fill={s.fill} stroke="#ffffff" strokeWidth={0.5}>
            <title>{s.label}</title>
          </path>
        ))}
      </svg>
      {title && <p className="text-xs text-muted-foreground">{title}</p>}
    </div>
  );
}