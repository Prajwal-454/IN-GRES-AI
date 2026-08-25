import { useMemo } from "react";

import type { ForecastPoint, SeriesPoint } from "@/services/chat";

interface MiniChartProps {
  series: SeriesPoint[];
  comparison?: SeriesPoint[] | null;
  forecast?: ForecastPoint[] | null;
  scenarioForecast?: ForecastPoint[] | null;
  unit: string;
  metricLabel: string;
  height?: number;
}

const W = 560;
const H = 200;
const PAD = { top: 14, right: 16, bottom: 28, left: 52 };

const SERIES_COLOR = "#0ea5e9";
const COMPARISON_COLOR = "#f59e0b";
const FORECAST_COLOR = "#16a34a";
const SCENARIO_COLOR = "#8b5cf6";

function pathOf(points: { x: number; y: number }[]): string {
  return points
    .map((p, i) => `${i === 0 ? "M" : "L"}${p.x.toFixed(1)},${p.y.toFixed(1)}`)
    .join(" ");
}

function fmtTick(v: number): string {
  if (Math.abs(v) >= 1000) return v.toFixed(0);
  return Number.isInteger(v) ? String(v) : v.toFixed(1);
}

export default function MiniChart({
  series,
  comparison,
  forecast,
  scenarioForecast,
  unit,
  metricLabel,
  height = 230,
}: MiniChartProps) {
  const view = useMemo(() => {
    const values: number[] = [];
    const years = new Set<number>();
    const collect = (pts: { year: number; value: number }[]) => {
      for (const p of pts) {
        values.push(p.value);
        years.add(p.year);
      }
    };
    collect(series);
    collect(comparison ?? []);
    for (const f of forecast ?? []) {
      values.push(f.value, f.lower, f.upper);
      years.add(f.year);
    }
    for (const f of scenarioForecast ?? []) {
      values.push(f.value, f.lower, f.upper);
      years.add(f.year);
    }
    if (!values.length) return null;

    let min = Math.min(...values);
    let max = Math.max(...values);
    const pad = (max - min) * 0.12 || (max || 1) * 0.1;
    min -= pad;
    max += pad;

    const sorted = [...years].sort((a, b) => a - b);
    const yMin = sorted[0];
    const yMax = sorted[sorted.length - 1] || yMin + 1;

    const sx = (year: number) =>
      PAD.left +
      ((year - yMin) / (yMax - yMin || 1)) * (W - PAD.left - PAD.right);
    const sy = (v: number) =>
      PAD.top + (1 - (v - min) / (max - min || 1)) * (H - PAD.top - PAD.bottom);

    return { min, max, yMin, yMax, sx, sy, years: sorted };
  }, [series, comparison, forecast, scenarioForecast]);

  if (!view) return null;

  const { min, max, sx, sy, years } = view;
  const yTicks = [min, (min + max) / 2, max];
  const xLabels =
    years.length <= 3
      ? years
      : [years[0], years[Math.floor(years.length / 2)], years[years.length - 1]];

  const mainPath = pathOf(series.map((p) => ({ x: sx(p.year), y: sy(p.value) })));
  const compPath = comparison?.length
    ? pathOf(comparison.map((p) => ({ x: sx(p.year), y: sy(p.value) })))
    : null;

  const forecastPath = forecast?.length
    ? pathOf(forecast.map((p) => ({ x: sx(p.year), y: sy(p.value) })))
    : null;
  const scenarioPath = scenarioForecast?.length
    ? pathOf(scenarioForecast.map((p) => ({ x: sx(p.year), y: sy(p.value) })))
    : null;

  let bandPath: string | null = null;
  if (forecast?.length) {
    const up = forecast.map((p) => `${sx(p.year)},${sy(p.upper)}`);
    const lo = [...forecast].reverse().map((p) => `${sx(p.year)},${sy(p.lower)}`);
    bandPath = `M${up.join(" L")} L${lo.join(" L")} Z`;
  }
  let scenarioBandPath: string | null = null;
  if (scenarioForecast?.length) {
    const up = scenarioForecast.map((p) => `${sx(p.year)},${sy(p.upper)}`);
    const lo = [...scenarioForecast].reverse().map((p) => `${sx(p.year)},${sy(p.lower)}`);
    scenarioBandPath = `M${up.join(" L")} L${lo.join(" L")} Z`;
  }

  return (
    <div className="w-full" style={{ height }}>
      <svg
        viewBox={`0 0 ${W} ${H}`}
        className="h-full w-full"
        role="img"
        aria-label={`${metricLabel} trend chart`}
      >
        {yTicks.map((t, i) => (
          <g key={i}>
            <line
              x1={PAD.left}
              y1={sy(t)}
              x2={W - PAD.right}
              y2={sy(t)}
              className="stroke-border"
              strokeWidth={1}
            />
            <text
              x={PAD.left - 6}
              y={sy(t) + 3}
              textAnchor="end"
              className="fill-muted-foreground text-[10px]"
            >
              {fmtTick(t)}
            </text>
          </g>
        ))}

        {xLabels.map((yr, i) => (
          <text
            key={i}
            x={sx(yr)}
            y={H - 6}
            textAnchor="middle"
            className="fill-muted-foreground text-[10px]"
          >
            {yr}
          </text>
        ))}

        {scenarioBandPath && (
          <path d={scenarioBandPath} fill={SCENARIO_COLOR} fillOpacity={0.08} />
        )}
        {bandPath && <path d={bandPath} fill={FORECAST_COLOR} fillOpacity={0.08} />}

        {compPath && (
          <path
            d={compPath}
            fill="none"
            stroke={COMPARISON_COLOR}
            strokeWidth={1.75}
            strokeLinejoin="round"
          />
        )}
        {mainPath && (
          <path
            d={mainPath}
            fill="none"
            stroke={SERIES_COLOR}
            strokeWidth={2.25}
            strokeLinejoin="round"
          />
        )}
        {scenarioPath && (
          <path
            d={scenarioPath}
            fill="none"
            stroke={SCENARIO_COLOR}
            strokeWidth={2}
            strokeDasharray="6 4"
            strokeLinejoin="round"
          />
        )}
        {forecastPath && (
          <path
            d={forecastPath}
            fill="none"
            stroke={FORECAST_COLOR}
            strokeWidth={2}
            strokeDasharray="6 4"
            strokeLinejoin="round"
          />
        )}

        {series.map((p, i) => (
          <circle key={i} cx={sx(p.year)} cy={sy(p.value)} r={2.5} fill={SERIES_COLOR} />
        ))}
      </svg>

      <div className="mt-1 flex flex-wrap items-center gap-x-4 gap-y-1 text-[11px] text-muted-foreground">
        <span className="inline-flex items-center gap-1.5">
          <span className="h-0.5 w-4 rounded bg-[#0ea5e9]" />
          {metricLabel} ({unit})
        </span>
        {compPath && (
          <span className="inline-flex items-center gap-1.5">
            <span className="h-0.5 w-4 rounded bg-[#f59e0b]" />
            {(comparison && comparison[0] && metricLabel === "Stage of extraction"
              ? "Extraction"
              : "Recharge")}{" "}
            (hm³)
          </span>
        )}
        {forecastPath && (
          <span className="inline-flex items-center gap-1.5">
            <span className="h-0.5 w-4 border-t-2 border-dashed border-[#16a34a]" />
            Forecast
          </span>
        )}
        {scenarioPath && (
          <span className="inline-flex items-center gap-1.5">
            <span className="h-0.5 w-4 border-t-2 border-dashed border-[#8b5cf6]" />
            Scenario
          </span>
        )}
      </div>
    </div>
  );
}