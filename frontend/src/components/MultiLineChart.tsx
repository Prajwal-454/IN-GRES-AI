import { cn } from "@/lib/utils";

export interface MultiLineSeries {
  label: string;
  color: string;
  points: { label: string; value: number }[];
}

interface MultiLineChartProps {
  series: MultiLineSeries[];
  height?: number;
  formatValue?: (value: number) => string;
  className?: string;
  legendClassName?: string;
}

export const SERIES_COLORS = [
  "#0f766e",
  "#b91c1c",
  "#1d4ed8",
  "#a16207",
  "#7e22ce",
  "#0e7490",
];

export default function MultiLineChart({
  series,
  height = 220,
  formatValue = (v) => String(v),
  className,
}: MultiLineChartProps) {
  const usable = series.filter((s) => s.points.length > 0);
  if (usable.length === 0) return null;

  const width = 600;
  const padX = 8;
  const padY = 20;

  // Shared x axis from the union of all labels (assumed comparable, e.g. years).
  const labels: string[] = [];
  for (const s of usable) {
    for (const p of s.points) {
      if (!labels.includes(p.label)) labels.push(p.label);
    }
  }
  labels.sort((a, b) => Number(a) - Number(b));
  const labelIndex = new Map(labels.map((l, i) => [l, i]));

  const values = usable.flatMap((s) => s.points.map((p) => p.value));
  const min = Math.min(...values);
  const max = Math.max(...values);
  const range = max - min || Math.abs(max) || 1;
  const lo = min - range * 0.08;
  const hi = max + range * 0.08;
  const span = hi - lo || 1;

  const xFor = (i: number) =>
    padX + (i * (width - padX * 2)) / Math.max(labels.length - 1, 1);
  const yFor = (v: number) => padY + (1 - (v - lo) / span) * (height - padY * 2);

  return (
    <div className={cn("w-full", className)}>
      <svg
        viewBox={`0 0 ${width} ${height}`}
        className="w-full"
        role="img"
        aria-label="Multi-series line chart"
      >
        <line
          x1={padX}
          y1={height - padY}
          x2={width - padX}
          y2={height - padY}
          stroke="currentColor"
          strokeOpacity={0.2}
        />
        {usable.map((s) => {
          const pts = s.points
            .slice()
            .sort((a, b) => (labelIndex.get(a.label) ?? 0) - (labelIndex.get(b.label) ?? 0))
            .map((p) => ({ ...p, i: labelIndex.get(p.label) ?? 0 }));
          const path = pts
            .map(
              (p, idx) =>
                `${idx === 0 ? "M" : "L"}${xFor(p.i).toFixed(1)},${yFor(p.value).toFixed(1)}`
            )
            .join(" ");
          return (
            <g key={s.label}>
              <path
                d={path}
                fill="none"
                stroke={s.color}
                strokeWidth={2.5}
                strokeLinecap="round"
              />
              {pts.map((p) => (
                <circle key={`${s.label}-${p.label}`} cx={xFor(p.i)} cy={yFor(p.value)} r={3} fill={s.color}>
                  <title>
                    {`${s.label} · ${p.label}: ${formatValue(p.value)}`}
                  </title>
                </circle>
              ))}
            </g>
          );
        })}
      </svg>
      <div className="mt-1 flex justify-between text-xs text-muted-foreground">
        {labels.map((l) => (
          <span key={l}>{l}</span>
        ))}
      </div>
      <div className={cn("mt-2 flex flex-wrap gap-x-4 gap-y-1 text-xs")}>
        {usable.map((s) => (
          <span key={s.label} className="inline-flex items-center gap-1.5">
            <span
              aria-hidden
              className="inline-block h-2 w-4 rounded-sm"
              style={{ backgroundColor: s.color }}
            />
            {s.label}
          </span>
        ))}
      </div>
    </div>
  );
}
