import { useId, useMemo } from "react";

import { scaleColor, TEMP_STOPS } from "@/lib/weatherLayer";
import type { PointWeather } from "@/services/map";

type Hourly = PointWeather["hourly"][number];
type Daily = PointWeather["daily"][number];

const W = 560;
const PAD = { top: 14, right: 12, bottom: 26, left: 40 };
const AREA_H = 74;
const STRIP_H = 30;

function num(v: number | null | undefined): v is number {
  return typeof v === "number" && Number.isFinite(v);
}

export function HourlyForecastChart({ hours }: { hours: Hourly[] }) {
  const gid = useId();
  const view = useMemo(() => {
    const pts = hours.filter((h) => num(h.temperature_2m));
    if (pts.length < 2) return null;
    const temps = pts.map((p) => p.temperature_2m!);
    let min = Math.min(...temps);
    let max = Math.max(...temps);
    const pad = (max - min) * 0.15 || 1.5;
    min -= pad;
    max += pad;
    const sx = (i: number) =>
      PAD.left + (i / (pts.length - 1)) * (W - PAD.left - PAD.right);
    const sy = (v: number) => PAD.top + (1 - (v - min) / (max - min || 1)) * AREA_H;
    const stripTop = PAD.top + AREA_H + 10;
    const stripBot = stripTop + STRIP_H;
    const linePath = pts
      .map((p, i) => `${i === 0 ? "M" : "L"}${sx(i).toFixed(1)},${sy(p.temperature_2m!).toFixed(1)}`)
      .join(" ");
    const areaPath = `${linePath} L${sx(pts.length - 1).toFixed(1)},${stripTop - 10} L${sx(0).toFixed(1)},${stripTop - 10} Z`;
    return { pts, min, max, sx, sy, stripTop, stripBot, linePath, areaPath };
  }, [hours]);

  if (!view) return null;
  const ticks = [view.max, (view.min + view.max) / 2, view.min];
  const labelIdx = [0, 6, 12, 18].filter((i) => i < view.pts.length);
  const H = view.stripBot + PAD.bottom;
  const barW = Math.max(2, ((W - PAD.left - PAD.right) / view.pts.length) * 0.55);

  return (
    <svg
      viewBox={`0 0 ${W} ${H}`}
      className="w-full"
      role="img"
      aria-label="Hourly temperature and rain chance"
    >
      <defs>
        <linearGradient id={`${gid}-temp-area`} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor="#38bdf8" stopOpacity="0.35" />
          <stop offset="100%" stopColor="#38bdf8" stopOpacity="0.02" />
        </linearGradient>
      </defs>

      {ticks.map((t, i) => (
        <g key={i}>
          <line
            x1={PAD.left}
            x2={W - PAD.right}
            y1={view.sy(t)}
            y2={view.sy(t)}
            stroke="rgba(148,163,184,0.15)"
            strokeWidth={1}
          />
          <text x={PAD.left - 6} y={view.sy(t) + 3} textAnchor="end" fontSize={9} fill="#94a3b8">
            {Math.round(t)}°
          </text>
        </g>
      ))}

      {view.pts.map((p, i) => {
        const prob = p.precipitation_probability ?? 0;
        const h = (prob / 100) * STRIP_H;
        return (
          <rect
            key={i}
            x={view.sx(i) - barW / 2}
            y={view.stripBot - h}
            width={barW}
            height={h}
            rx={1.5}
            fill="#60a5fa"
            opacity={prob > 0 ? 0.25 + (prob / 100) * 0.6 : 0.05}
          />
        );
      })}
      <line
        x1={PAD.left}
        x2={W - PAD.right}
        y1={view.stripTop}
        y2={view.stripTop}
        stroke="rgba(148,163,184,0.25)"
        strokeWidth={1}
      />

      <path d={view.areaPath} fill={`url(#${gid}-temp-area)`} />
      <path
        d={view.linePath}
        fill="none"
        stroke="#38bdf8"
        strokeWidth={2.25}
        strokeLinejoin="round"
        strokeLinecap="round"
      />

      {labelIdx.map((i) => (
        <text
          key={i}
          x={view.sx(i)}
          y={view.stripBot + 16}
          textAnchor="middle"
          fontSize={9.5}
          fill="#94a3b8"
        >
          {new Date(view.pts[i].time).toLocaleString("en-IN", { hour: "numeric" })}
        </text>
      ))}
    </svg>
  );
}

export function DailyForecastChart({ days }: { days: Daily[] }) {
  const view = useMemo(() => {
    const rows = days.filter((d) => num(d.temperature_2m_max) && num(d.temperature_2m_min));
    if (!rows.length) return null;
    const loAll = rows.map((d) => d.temperature_2m_min!);
    const hiAll = rows.map((d) => d.temperature_2m_max!);
    let min = Math.min(...loAll);
    let max = Math.max(...hiAll);
    const pad = (max - min) * 0.2 || 1.5;
    min -= pad;
    max += pad;
    const innerH = 78;
    const top = PAD.top + 12;
    const sy = (v: number) => top + (1 - (v - min) / (max - min || 1)) * innerH;
    const colW = (W - PAD.left - PAD.right) / rows.length;
    const barW = Math.min(34, colW * 0.5);
    return { rows, min, max, sy, colW, barW, top, innerH };
  }, [days]);

  if (!view) return null;
  const baseY = view.top + view.innerH;
  const H = baseY + 36;

  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="w-full" role="img" aria-label="7-day temperature outlook">
      {view.rows.map((d, i) => {
        const cx = PAD.left + view.colW * (i + 0.5);
        const hi = d.temperature_2m_max!;
        const lo = d.temperature_2m_min!;
        const mid = (hi + lo) / 2;
        const [r, g, b] = scaleColor(TEMP_STOPS, mid);
        const yHi = view.sy(hi);
        const yLo = view.sy(lo);
        const dt = new Date(`${d.date}T12:00:00`);
        return (
          <g key={d.date}>
            <rect
              x={cx - view.barW / 2}
              y={yHi}
              width={view.barW}
              height={Math.max(4, yLo - yHi)}
              rx={4}
              fill={`rgb(${r},${g},${b})`}
              opacity={0.85}
              stroke="rgba(255,255,255,0.18)"
              strokeWidth={0.75}
            />
            <text x={cx} y={yHi - 5} textAnchor="middle" fontSize={9.5} fill="#e2e8f0">
              {Math.round(hi)}°
            </text>
            <text x={cx} y={baseY + 11} textAnchor="middle" fontSize={9.5} fill="#94a3b8">
              {Math.round(lo)}°
            </text>
            <text x={cx} y={baseY + 24} textAnchor="middle" fontSize={9.5} fill="#cbd5e1">
              {Number.isNaN(dt.getTime())
                ? d.date
                : dt.toLocaleDateString("en-IN", { weekday: "short" })}
            </text>
            {num(d.precipitation_sum) && d.precipitation_sum > 0 && (
              <text x={cx} y={baseY + 33} textAnchor="middle" fontSize={8.5} fill="#60a5fa">
                {d.precipitation_sum.toFixed(1)} mm
              </text>
            )}
          </g>
        );
      })}
    </svg>
  );
}

export default function WeatherCharts({ data }: { data: PointWeather }) {
  const startMs = (() => {
    const t = data.current?.time ? new Date(data.current.time).getTime() : NaN;
    return Number.isFinite(t) ? t - 30 * 60e3 : Date.now() - 90 * 60e3;
  })();
  const upcoming = data.hourly
    .filter((h) => new Date(h.time).getTime() >= startMs)
    .slice(0, 24);

  if (!upcoming.length && !data.daily.length) return null;

  return (
    <div className="space-y-3">
      {upcoming.length >= 2 && (
        <div>
          <div className="mb-1 flex items-center justify-between">
            <span className="text-[10px] font-bold uppercase tracking-wider text-slate-400">
              Next 24 hours
            </span>
            <span className="inline-flex items-center gap-1 text-[9px] text-slate-400">
              <span className="inline-block h-2 w-1 rounded-sm bg-blue-400/80" />
              rain chance
            </span>
          </div>
          <HourlyForecastChart hours={upcoming} />
        </div>
      )}
      {data.daily.length > 0 && (
        <div>
          <div className="mb-1 flex items-center justify-between">
            <span className="text-[10px] font-bold uppercase tracking-wider text-slate-400">
              7-day outlook
            </span>
            <span className="text-[9px] text-slate-500">bar = min–max °C</span>
          </div>
          <DailyForecastChart days={data.daily.slice(0, 7)} />
        </div>
      )}
    </div>
  );
}
