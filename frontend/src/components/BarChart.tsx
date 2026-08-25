import { cn } from "@/lib/utils";

export interface BarDatum {
  label: string;
  value: number;
  color?: string;
}

interface BarChartProps {
  data: BarDatum[];
  formatValue?: (value: number) => string;
  className?: string;
}

export default function BarChart({ data, formatValue, className }: BarChartProps) {
  const max = Math.max(...data.map((d) => d.value), 1);

  return (
    <div className={cn("space-y-3", className)}>
      {data.map((d) => (
        <div key={d.label} className="flex items-center gap-3">
          <div className="w-36 shrink-0 truncate text-right text-sm text-muted-foreground">
            {d.label}
          </div>
          <div className="h-6 flex-1 overflow-hidden rounded-md bg-muted">
            <div
              className="flex h-full items-center rounded-md px-2 text-xs font-medium text-primary-foreground transition-all"
              style={{
                width: `${Math.max((d.value / max) * 100, 3)}%`,
                backgroundColor: d.color,
              }}
            >
              {formatValue ? formatValue(d.value) : d.value}
            </div>
          </div>
        </div>
      ))}
    </div>
  );
}