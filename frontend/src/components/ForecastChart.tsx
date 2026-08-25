import { useRef, useState } from "react";

import { cn } from "@/lib/utils";
import type { ForecastPoint } from "@/services/predictions";

interface ForecastChartProps {
  points: ForecastPoint[];
  forecastFrom?: number;
  metric?: "stage" | "recharge" | "extraction";
  height?: number;
  formatValue?: (value: number) => string;
  className?: string;
}

const WIDTH = 720;
const PAD_L = 58;
const PAD_R = 20;
const PAD_T = 22;
const PAD_B = 34;

const STAGE_ZONES = [
  { max: 70, color: "#16a34a", label: "Safe <70%" },
  { max: 90, color: "#f59e0b", label: "Semi-critical 70–90%" },
  { max: 100, color: "#f97316", label: "Critical 90–100%" },
  { max: Infinity, color: "#dc2626", label: "Over-exploited >100%" },
];

function formatTick(v: number): string {
  if (Math.abs(v) >= 1e9) return `${(v / 1e9).toFixed(1)}B`;
  if (Math.abs(v) >= 1e6) return `${(v / 1e6).toFixed(1)}M`;
  if (Math.abs(v) >= 1e3) return `${(v / 1e3).toFixed(0)}K`;
  return v.toFixed(0);
}

export default function ForecastChart({
  points,
  forecastFrom,
  metric = "stage",
  height = 340,
  formatValue = (v) => String(v),
  className,
}: ForecastChartProps) {
  const svgRef = useRef<SVGSVGElement>(null);
  const [hover, setHover] = useState<number | null>(null);

  if (points.length === 0) return null;

  const n = points.length;
  const plotW = WIDTH - PAD_L - PAD_R;
  const plotH = height - PAD_T - PAD_B;

  const values = points.flatMap((p) =>
    p.upper != null && p.lower != null ? [p.value, p.upper, p.lower] : [p.value]
  );
  const padMin = metric === "stage" ? 0 : 0;
  let min = Math.min(...values, padMin);
  let max = Math.max(...values, 1);
  if (metric === "stage") {
    min = Math.min(min, 0);
    max = Math.max(max, 105);
  } else {
    const span = max - min || 1;
    min = Math.max(min - span * 0.08, 0);
    max = max + span * 0.08;
  }
  const range = max - min || 1;

  const xFor = (i: number) => PAD_L + (i * plotW) / Math.max(n - 1, 1);
  const yFor = (v: number) => PAD_T + (1 - (v - min) / range) * plotH;
  const clampY = (v: number) => Math.max(PAD_T, Math.min(PAD_T + plotH, v));

  const isForecast = (p: ForecastPoint) =>
    forecastFrom !== undefined ? p.year >= forecastFrom : p.upper !== null;

  const hist = points.filter((p) => !isForecast(p));
  const proj = points.filter((p) => isForecast(p));
  const histIndex = hist.length > 0 ? points.indexOf(hist[hist.length - 1]) : -1;

  const toPt = (p: ForecastPoint) => ({ x: xFor(points.indexOf(p)), y: yFor(p.value) });
  const histPts = hist.map(toPt);
  const projPts = proj.map(toPt);

  const linePath = (pts: { x: number; y: number }[]) =>
    pts.map((p, i) => `${i === 0 ? "M" : "L"}${p.x.toFixed(1)},${p.y.toFixed(1)}`).join(" ");

  const areaPath =
    histPts.length > 1
      ? `${linePath(histPts)} L${histPts[histPts.length - 1].x.toFixed(1)},${PAD_T + plotH} L${histPts[0].x.toFixed(1)},${PAD_T + plotH} Z`
      : "";

  // Fan band: progressive shading of the forecast confidence interval.
  let bandPath = "";
  if (proj.length > 0) {
    const upperPts = proj.map((p) => {
      const globalI = points.indexOf(p);
      return { x: xFor(globalI), y: yFor(p.upper ?? p.value) };
    });
    const lowerPts = [...upperPts].reverse().map((p, k) => {
      const src = proj[proj.length - 1 - k];
      return { x: p.x, y: yFor(src.lower ?? src.value) };
    });
    bandPath = `${linePath(upperPts)} ${linePath(lowerPts)} Z`;
  }

  // Zone backgrounds (stage metric).
  const zoneRects =
    metric === "stage"
      ? STAGE_ZONES.map((z, i) => {
          const lo = i === 0 ? 0 : STAGE_ZONES[i - 1].max;
          const yTop = clampY(yFor(lo));
          const yBot = clampY(yFor(z.max));
          return { ...z, yTop, yBot };
        })
      : [];

  // Y-axis ticks: ~5 gridlines.
  const tickCount = 5;
  const ticks = Array.from({ length: tickCount + 1 }, (_, i) => min + (range * i) / tickCount);

  // X labels: show every other year when crowded.
  const labelStep = n > 10 ? 2 : 1;

  function handleMouseMove(e: React.MouseEvent<SVGSVGElement>) {
    const svg = svgRef.current;
    if (!svg) return;
    const rect = svg.getBoundingClientRect();
    const px = e.clientX - rect.left;
    const x = ((px / rect.width) * WIDTH - PAD_L) / Math.max(plotW, 1) * (n - 1);
    const idx = Math.max(0, Math.min(n - 1, Math.round(x)));
    setHover(idx);
  }

  const hoverPt = hover !== null ? points[hover] : null;
  const hoverX = hover !== null ? xFor(hover) : 0;

  return (
    <div className={cn("relative w-full", className)}>
      <svg
        ref={svgRef}
        viewBox={`0 0 ${WIDTH} ${height}`}
        className="w-full select-none"
        role="img"
        aria-label="Forecast chart with historical and projected values"
        onMouseMove={handleMouseMove}
        onMouseLeave={() => setHover(null)}
      >
        <defs>
          <linearGradient id="histArea" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="#0f766e" stopOpacity="0.28" />
            <stop offset="100%" stopColor="#0f766e" stopOpacity="0.02" />
          </linearGradient>
          <linearGradient id="fanBand" x1="0" y1="0" x2="1" y2="0">
            <stop offset="0%" stopColor="#0284c7" stopOpacity="0.28" />
            <stop offset="100%" stopColor="#0284c7" stopOpacity="0.04" />
          </linearGradient>
        </defs>

        {zoneRects.map((z, zi) => (
          <g key={`zone-${zi}`}>
            <rect
              x={PAD_L}
              y={z.yTop}
              width={plotW}
              height={Math.max(z.yBot - z.yTop, 0)}
              fill={z.color}
              opacity={0.07}
            />
            {z.yBot < PAD_T + plotH && (
              <line
                x1={PAD_L}
                y1={z.yBot}
                x2={WIDTH - PAD_R}
                y2={z.yBot}
                stroke={z.color}
                strokeOpacity={0.35}
                strokeDasharray="3 3"
                strokeWidth={1}
              />
            )}
            <text
              x={WIDTH - PAD_R - 6}
              y={clampY((z.yTop + z.yBot) / 2) + 4}
              textAnchor="end"
              fontSize="9.5"
              fill={z.color}
              opacity={0.85}
            >
              {z.label}
            </text>
          </g>
        ))}

        {ticks.map((t, i) => {
          const y = clampY(yFor(t));
          return (
            <g key={`tick-${i}`}>
              <line
                x1={PAD_L}
                y1={y}
                x2={WIDTH - PAD_R}
                y2={y}
                stroke="#e2e8f0"
                strokeWidth={1}
                strokeDasharray="2 3"
              />
              <text x={PAD_L - 8} y={y + 3.5} textAnchor="end" fontSize="10" fill="#64748b">
                {formatTick(t)}
              </text>
            </g>
          );
        })}

        {areaPath && <path d={areaPath} fill="url(#histArea)" />}
        {bandPath && <path d={bandPath} fill="url(#fanBand)" />}

        {histPts.length > 1 && (
          <path
            d={linePath(histPts)}
            fill="none"
            stroke="#0f766e"
            strokeWidth={3}
            strokeLinecap="round"
            strokeLinejoin="round"
          />
        )}
        {projPts.length > 1 && (
          <path
            d={linePath(projPts)}
            fill="none"
            stroke="#0284c7"
            strokeWidth={3}
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeDasharray="7 5"
          />
        )}

        {/* Confidence whiskers on projected points */}
        {proj.map((p) => {
          const globalI = points.indexOf(p);
          const x = xFor(globalI);
          const yLo = clampY(yFor(p.lower ?? p.value));
          const yHi = clampY(yFor(p.upper ?? p.value));
          return (
            <g key={`whisker-${p.year}`} opacity={0.85}>
              <line x1={x} y1={yLo} x2={x} y2={yHi} stroke="#0284c7" strokeWidth={2} />
              <line x1={x - 3} y1={yLo} x2={x + 3} y2={yLo} stroke="#0284c7" strokeWidth={2} />
              <line x1={x - 3} y1={yHi} x2={x + 3} y2={yHi} stroke="#0284c7" strokeWidth={2} />
            </g>
          );
        })}

        {/* Forecast divider */}
        {histIndex >= 0 && histIndex < n - 1 && (
          <g>
            <line
              x1={xFor(histIndex + 0.5)}
              y1={PAD_T}
              x2={xFor(histIndex + 0.5)}
              y2={PAD_T + plotH}
              stroke="#64748b"
              strokeWidth={1.5}
              strokeDasharray="4 4"
            />
            <text
              x={xFor(histIndex + 0.5) - 8}
              y={PAD_T + 12}
              textAnchor="end"
              fontSize="10"
              fontWeight="600"
              fill="#475569"
            >
              Forecast →
            </text>
          </g>
        )}

        {/* Point markers */}
        {points.map((p, i) => {
          const f = isForecast(p);
          const x = xFor(i);
          const y = yFor(p.value);
          return (
            <g key={`dot-${p.year}`} onMouseEnter={() => setHover(i)}>
              <circle cx={x} cy={y} r={4.5} fill={f ? "#0284c7" : "#0f766e"} stroke="#fff" strokeWidth={1.5} />
              <title>
                {p.year}: {formatValue(p.value)}
              </title>
            </g>
          );
        })}

        {/* End-of-projection highlight */}
        {projPts.length > 0 && (
          <g>
            <circle cx={projPts[projPts.length - 1].x} cy={projPts[projPts.length - 1].y} r={7} fill="none" stroke="#0284c7" strokeWidth={2.5} />
          </g>
        )}

        {/* Hover crosshair */}
        {hoverPt && (
          <g pointerEvents="none">
            <line x1={hoverX} y1={PAD_T} x2={hoverX} y2={PAD_T + plotH} stroke="#334155" strokeWidth={1} strokeDasharray="3 3" opacity={0.5} />
            <circle cx={hoverX} cy={yFor(hoverPt.value)} r={5.5} fill="none" stroke="#334155" strokeWidth={2} />
          </g>
        )}

        {points.map((p, i) =>
          i % labelStep === 0 ? (
            <text
              key={`xlabel-${p.year}`}
              x={xFor(i)}
              y={height - 10}
              textAnchor="middle"
              fontSize="10"
              fill="#64748b"
            >
              {p.year}
            </text>
          ) : null
        )}
      </svg>

      {/* Floating tooltip */}
      {hoverPt && hover !== null && (
        <div
          className="pointer-events-none absolute z-10 min-w-36 rounded-lg border bg-background/95 px-3 py-2 text-xs shadow-lg backdrop-blur"
          style={{
            left: `${(hoverX / WIDTH) * 100}%`,
            top: 0,
            transform: `translateX(${hoverX > WIDTH * 0.75 ? "-110%" : "4%"})`,
          }}
        >
          <div className="font-semibold text-foreground">{hoverPt.year}</div>
          <div className="mt-0.5 flex items-center gap-1.5">
            <span className={`inline-block h-2 w-2 rounded-full ${isForecast(hoverPt) ? "bg-sky-600" : "bg-teal-700"}`} />
            <span className="text-muted-foreground">{isForecast(hoverPt) ? "Projected" : "Observed"}:</span>
            <span className="font-semibold">{formatValue(hoverPt.value)}</span>
          </div>
          {hoverPt.upper != null && hoverPt.lower != null && (
            <div className="mt-1 text-[11px] text-muted-foreground">
              Range: {formatValue(hoverPt.lower)} – {formatValue(hoverPt.upper)}
            </div>
          )}
        </div>
      )}

      <div className="mt-3 flex flex-wrap items-center gap-x-4 gap-y-2 text-xs text-muted-foreground">
        <span className="inline-flex items-center gap-1.5">
          <span className="inline-block h-0.5 w-5 rounded bg-teal-700" />
          Historical
        </span>
        <span className="inline-flex items-center gap-1.5">
          <span className="inline-block h-0.5 w-5 rounded border-t-2 border-dashed border-sky-600" />
          Projected
        </span>
        <span className="inline-flex items-center gap-1.5">
          <span className="inline-block h-2 w-5 rounded-sm bg-sky-500/30" />
          95% confidence band
        </span>
        {metric === "stage" && (
          <span className="inline-flex items-center gap-1.5">
            <span className="inline-flex h-3 w-5 overflow-hidden rounded-sm">
              <span className="flex-1 bg-green-600/70" />
              <span className="flex-1 bg-amber-500/70" />
              <span className="flex-1 bg-orange-500/70" />
              <span className="flex-1 bg-red-600/70" />
            </span>
            Stage-of-extraction zones
          </span>
        )}
      </div>
    </div>
  );
}