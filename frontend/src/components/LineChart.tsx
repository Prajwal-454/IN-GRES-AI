import { cn } from "@/lib/utils";

export interface LinePoint {
  label: string;
  value: number;
}

interface LineChartProps {
  data: LinePoint[];
  color?: string;
  height?: number;
  formatValue?: (value: number) => string;
  className?: string;
}

export default function LineChart({
  data,
  color = "#0f766e",
  height = 220,
  formatValue = (v) => String(v),
  className,
}: LineChartProps) {
  if (data.length === 0) return null;

  const width = 600;
  const padX = 8;
  const padY = 20;
  const values = data.map((d) => d.value);
  const min = Math.min(...values, 0);
  const max = Math.max(...values, 1);
  const range = max - min || 1;

  const points = data.map((d, i) => {
    const x = padX + (i * (width - padX * 2)) / Math.max(data.length - 1, 1);
    const y = padY + (1 - (d.value - min) / range) * (height - padY * 2);
    return { x, y, ...d };
  });

  const path = points
    .map((p, i) => `${i === 0 ? "M" : "L"}${p.x.toFixed(1)},${p.y.toFixed(1)}`)
    .join(" ");
  const areaPath = `${path} L${points[points.length - 1].x.toFixed(1)},${(
    height - padY
  ).toFixed(1)} L${points[0].x.toFixed(1)},${(height - padY).toFixed(1)} Z`;

  return (
    <div className={cn("w-full", className)}>
      <svg
        viewBox={`0 0 ${width} ${height}`}
        className="w-full"
        role="img"
        aria-label="Line chart"
      >
        <path d={areaPath} fill={color} opacity={0.12} />
        <path d={path} fill="none" stroke={color} strokeWidth={2.5} strokeLinecap="round" />
        {points.map((p) => (
          <g key={p.label}>
            <circle cx={p.x} cy={p.y} r={3.5} fill={color} />
            <title>
              {p.label}: {formatValue(p.value)}
            </title>
          </g>
        ))}
      </svg>
      <div className="mt-1 flex justify-between text-xs text-muted-foreground">
        {points.map((p) => (
          <span key={p.label}>{p.label}</span>
        ))}
      </div>
    </div>
  );
}