import L from "leaflet";
import { useCallback, useEffect, useRef } from "react";

import {
  STOPS,
  rainCategory,
  scaleColor,
  type Metric,
  type MetricValue,
  type SeriesBounds,
} from "@/lib/weatherLayer";
import type { WeatherMapSeries } from "@/services/map";

export interface AnimSettings {
  enabled: boolean;
  speed: number;
  opacity: number;
  density: "low" | "medium" | "high";
  trail: "short" | "medium" | "long";
  smoothing: "off" | "low" | "medium" | "high";
  windUnit: "kmh" | "ms";
}

interface Props {
  map: L.Map | null;
  series: WeatherMapSeries | null;
  metric: MetricValue;
  frame: number;
  mode: "current" | "radar" | "forecast" | "historical";
  layers: { clouds: boolean; rain: boolean; wind: boolean; temperature: boolean; humidity: boolean; aqi: boolean };
  settings: AnimSettings;
}

const RASTER_W = 192;
const RASTER_H = 192;

// Visual scaling for wind particles: km/h -> lat degrees per second.
const WIND_DEG_PER_KMH = 2.2e-4;
const RAIN_FALL_DEG = 1.6e-4;
const CLOUD_DRIFT_SCALE = 9e-4;

interface Particle {
  lat: number;
  lon: number;
  life: number;
  maxLife: number;
  prevLat: number;
  prevLon: number;
}

function clamp(v: number, lo: number, hi: number): number {
  return Math.min(Math.max(v, lo), hi);
}

function lerp(a: number, b: number, f: number): number {
  return a + (b - a) * f;
}

function windVector(
  series: WeatherMapSeries,
  lat: number,
  lon: number,
  frame: number
): { u: number; v: number; speed: number } {
  const grid = series.grid;
  if (grid.length === 0) return { u: 0, v: 0, speed: 0 };
  const lats = [...new Set(grid.map((p) => p.lat))].sort((a, b) => a - b);
  const lons = [...new Set(grid.map((p) => p.lon))].sort((a, b) => a - b);
  const rows = lats.length;
  const cols = lons.length;
  const fr = ((lat - lats[0]) / Math.max(lats[rows - 1] - lats[0], 1e-9)) * (rows - 1);
  const fc = ((lon - lons[0]) / Math.max(lons[cols - 1] - lons[0], 1e-9)) * (cols - 1);
  const i0 = clamp(Math.floor(fr), 0, rows - 2);
  const j0 = clamp(Math.floor(fc), 0, cols - 2);
  const di = fr - i0;
  const dj = fc - j0;

  const k0 = Math.floor(frame);
  const f = frame - k0;
  const maxK = (grid[0]?.hourly.wind_speed_10m.length ?? 1) - 1;
  const k1 = Math.min(k0 + 1, maxK);

  const get = (i: number, j: number, k: number): { v: number; dir: number } => {
    const p = grid[i * cols + j];
    if (!p) return { v: 0, dir: 0 };
    return {
      v: p.hourly.wind_speed_10m[k] ?? 0,
      dir: p.hourly.wind_direction_10m[k] ?? 0,
    };
  };

  const interp = (k: number) => {
    const v00 = get(i0, j0, k);
    const v01 = get(i0, j0 + 1, k);
    const v10 = get(i0 + 1, j0, k);
    const v11 = get(i0 + 1, j0 + 1, k);
    const v =
      v00.v * (1 - di) * (1 - dj) +
      v01.v * (1 - di) * dj +
      v10.v * di * (1 - dj) +
      v11.v * di * dj;
    const dir =
      v00.dir * (1 - di) * (1 - dj) +
      v01.dir * (1 - di) * dj +
      v10.dir * di * (1 - dj) +
      v11.dir * di * dj;
    return { v, dir };
  };

  const a = interp(k0);
  const b = k1 !== k0 ? interp(k1) : a;
  const speed = lerp(a.v, b.v, f);
  const dir = lerp(a.dir, b.dir, f);
  // Meteorological direction is the direction wind comes FROM; flow is opposite.
  const to = ((dir + 180) * Math.PI) / 180;
  const u = Math.sin(to) * speed * WIND_DEG_PER_KMH;
  const v = Math.cos(to) * speed * WIND_DEG_PER_KMH;
  return { u, v, speed };
}

type HourlyKey =
  | "temperature_2m"
  | "apparent_temperature"
  | "relative_humidity_2m"
  | "precipitation"
  | "cloud_cover"
  | "wind_speed_10m"
  | "us_aqi";

const METRIC_KEY: Record<Exclude<Metric, "wind">, HourlyKey> = {
  temperature: "temperature_2m",
  rain: "precipitation",
  humidity: "relative_humidity_2m",
  clouds: "cloud_cover",
  aqi: "us_aqi",
};

function gridAxes(grid: WeatherMapSeries["grid"]): { lats: number[]; lons: number[] } {
  const lats = [...new Set(grid.map((p) => p.lat))].sort((a, b) => a - b);
  const lons = [...new Set(grid.map((p) => p.lon))].sort((a, b) => a - b);
  return { lats, lons };
}

function sampleHourly(
  series: WeatherMapSeries,
  key: HourlyKey,
  lat: number,
  lon: number,
  frame: number
): number | null {
  const grid = series.grid;
  if (grid.length === 0) return null;
  const { lats, lons } = gridAxes(grid);
  const rows = lats.length;
  const cols = lons.length;
  const fr = ((lat - lats[0]) / Math.max(lats[rows - 1] - lats[0], 1e-9)) * (rows - 1);
  const fc = ((lon - lons[0]) / Math.max(lons[cols - 1] - lons[0], 1e-9)) * (cols - 1);
  const i0 = clamp(Math.floor(fr), 0, rows - 2);
  const j0 = clamp(Math.floor(fc), 0, cols - 2);
  const di = fr - i0;
  const dj = fc - j0;
  const get = (i: number, j: number, k: number): number | null => {
    const p = grid[i * cols + j];
    if (!p) return null;
    return (p.hourly[key] as number[])[k] ?? null;
  };
  const k0 = Math.floor(frame);
  const f = frame - k0;
  const maxK = ((grid[0]?.hourly[key] as number[] | undefined)?.length ?? 1) - 1;
  const k1 = Math.min(k0 + 1, maxK);
  const valAt = (k: number) => {
    const vals = [get(i0, j0, k), get(i0, j0 + 1, k), get(i0 + 1, j0, k), get(i0 + 1, j0 + 1, k)];
    const known = vals.filter((v): v is number => v !== null);
    if (known.length === 0) return null;
    if (known.length === 4) {
      return (
        vals[0]! * (1 - di) * (1 - dj) +
        vals[1]! * (1 - di) * dj +
        vals[2]! * di * (1 - dj) +
        vals[3]! * di * dj
      );
    }
    return known.reduce((a, b) => a + b, 0) / known.length;
  };
  const va = valAt(k0);
  const vb = k1 !== k0 ? valAt(k1) : va;
  if (va === null && vb === null) return null;
  if (va === null) return vb;
  if (vb === null) return va;
  return lerp(va, vb, f);
}

function sampleField(
  series: WeatherMapSeries,
  metric: Exclude<Metric, "wind">,
  lat: number,
  lon: number,
  frame: number
): number | null {
  return sampleHourly(series, METRIC_KEY[metric], lat, lon, frame);
}

export interface SampledWeather {
  temperature_2m: number | null;
  apparent_temperature: number | null;
  relative_humidity_2m: number | null;
  precipitation: number | null;
  cloud_cover: number | null;
  us_aqi: number | null;
  wind_speed_10m: number | null;
  weather_code: number | null;
}

/** Interpolated conditions at an arbitrary point/time — drives the hover tooltip. */
export function sampleWeatherAt(
  series: WeatherMapSeries,
  lat: number,
  lon: number,
  frame: number
): SampledWeather {
  const grid = series.grid;
  let weather_code: number | null = null;
  if (grid.length > 0 && series.times.length > 0) {
    const { lats, lons } = gridAxes(grid);
    const fr = clamp(
      Math.round(((lat - lats[0]) / Math.max(lats[lats.length - 1] - lats[0], 1e-9)) * (lats.length - 1)),
      0,
      lats.length - 1
    );
    const fc = clamp(
      Math.round(((lon - lons[0]) / Math.max(lons[lons.length - 1] - lons[0], 1e-9)) * (lons.length - 1)),
      0,
      lons.length - 1
    );
    const p = grid[fr * lons.length + fc];
    if (p) {
      const codes = p.hourly.weather_code;
      const k = Math.max(0, Math.min(Math.round(frame), codes.length - 1));
      weather_code = codes[k] ?? null;
    }
  }
  return {
    temperature_2m: sampleHourly(series, "temperature_2m", lat, lon, frame),
    apparent_temperature: sampleHourly(series, "apparent_temperature", lat, lon, frame),
    relative_humidity_2m: sampleHourly(series, "relative_humidity_2m", lat, lon, frame),
    precipitation: sampleHourly(series, "precipitation", lat, lon, frame),
    cloud_cover: sampleHourly(series, "cloud_cover", lat, lon, frame),
    us_aqi: sampleHourly(series, "us_aqi", lat, lon, frame),
    wind_speed_10m: sampleHourly(series, "wind_speed_10m", lat, lon, frame),
    weather_code,
  };
}

function rasterCanvas(
  series: WeatherMapSeries,
  metric: Exclude<Metric, "wind">,
  frame: number,
  smoothing: AnimSettings["smoothing"]
): HTMLCanvasElement | null {
  const { bounds } = series;
  const canvas = document.createElement("canvas");
  canvas.width = RASTER_W;
  canvas.height = RASTER_H;
  const ctx = canvas.getContext("2d");
  if (!ctx) return null;

  const sub = smoothing !== "off" ? 2 : 1;
  const W = Math.max(16, Math.floor(RASTER_W / sub));
  const H = Math.max(16, Math.floor(RASTER_H / sub));
  const img = ctx.createImageData(W, H);
  const stops = STOPS[metric];
  const latSpan = bounds.max_lat - bounds.min_lat;
  const lonSpan = bounds.max_lon - bounds.min_lon;

  for (let y = 0; y < H; y++) {
    const lat = bounds.max_lat - (y / H) * latSpan;
    for (let x = 0; x < W; x++) {
      const lon = bounds.min_lon + (x / W) * lonSpan;
      const v = sampleField(series, metric, lat, lon, frame);
      const idx = (y * W + x) * 4;
      if (v === null) {
        img.data[idx + 3] = 0;
        continue;
      }
      if (metric === "clouds") {
        const a = Math.min(1, Math.max(0, v / 100)) * 0.85;
        img.data[idx] = 255;
        img.data[idx + 1] = 255;
        img.data[idx + 2] = 255;
        img.data[idx + 3] = Math.round(a * 255);
        continue;
      }
      const [r, g, b] = scaleColor(stops, v);
      img.data[idx] = r;
      img.data[idx + 1] = g;
      img.data[idx + 2] = b;
      img.data[idx + 3] = 150;
    }
  }
  ctx.putImageData(img, 0, 0);
  if (sub > 1) {
    const tmp = document.createElement("canvas");
    tmp.width = W;
    tmp.height = H;
    tmp.getContext("2d")?.drawImage(canvas, 0, 0);
    const big = document.createElement("canvas");
    big.width = RASTER_W;
    big.height = RASTER_H;
    const bigCtx = big.getContext("2d");
    if (bigCtx) {
      bigCtx.imageSmoothingEnabled = true;
      bigCtx.drawImage(tmp, 0, 0, W, H, 0, 0, RASTER_W, RASTER_H);
    }
    return big;
  }
  return canvas;
}

function drawTransform(
  ctx: CanvasRenderingContext2D,
  bounds: SeriesBounds,
  map: L.Map,
  w: number,
  h: number
): boolean {
  const p00 = map.latLngToContainerPoint(L.latLng(bounds.max_lat, bounds.min_lon));
  const p10 = map.latLngToContainerPoint(L.latLng(bounds.max_lat, bounds.max_lon));
  const p01 = map.latLngToContainerPoint(L.latLng(bounds.min_lat, bounds.min_lon));
  const a = (p10.x - p00.x) / w;
  const b = (p10.y - p00.y) / w;
  const c = (p01.x - p00.x) / h;
  const d = (p01.y - p00.y) / h;
  if (!Number.isFinite(a + b + c + d)) return false;
  ctx.setTransform(a, b, c, d, p00.x, p00.y);
  return true;
}

export default function WeatherAnimation({
  map,
  series,
  metric,
  frame,
  mode,
  layers,
  settings,
}: Props) {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const rafRef = useRef<number>(0);
  const particlesRef = useRef<Particle[]>([]);
  const dropsRef = useRef<Particle[]>([]);
  const driftRef = useRef(0);

  const densityFactor = settings.density === "low" ? 0.5 : settings.density === "high" ? 2.4 : 1;

  const windCount = Math.round(220 * densityFactor);
  const rainMax = Math.round(180 * densityFactor);

  const reseed = useCallback((count: number, bounds: SeriesBounds) => {
    const particles: Particle[] = [];
    for (let i = 0; i < count; i++) {
      particles.push({
        lat: bounds.min_lat + Math.random() * (bounds.max_lat - bounds.min_lat),
        lon: bounds.min_lon + Math.random() * (bounds.max_lon - bounds.min_lon),
        life: Math.random(),
        maxLife: 1,
        prevLat: 0,
        prevLon: 0,
      });
    }
    return particles;
  }, []);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas || !map || !series) return;
    if (series.grid.length === 0 || series.times.length === 0) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const resize = () => {
      const el = map.getContainer();
      const dpr = window.devicePixelRatio || 1;
      canvas.width = el.clientWidth * dpr;
      canvas.height = el.clientHeight * dpr;
    };
    resize();
    map.on("resize move zoom", resize);

    if (particlesRef.current.length === 0) {
      particlesRef.current = reseed(windCount, series.bounds);
    }

    let last = performance.now();

    const render = (now: number) => {
      rafRef.current = requestAnimationFrame(render);
      const dt = Math.min((now - last) / 1000, 0.1);
      last = now;
      const bounds = series.bounds;
      ctx.setTransform(1, 0, 0, 1, 0, 0);
      ctx.clearRect(0, 0, canvas.width, canvas.height);
      const animating = settings.enabled;

      const frameIdx = Math.max(0, Math.min(frame, (series.times.length - 1) || 0));
      const globalOpacity = settings.opacity;

      // Raster layers (temperature, humidity, rain/radar, clouds).
      if (metric && metric !== "none") {
        const m = metric as Exclude<Metric, "wind">;
        if ((m !== "temperature" || layers.temperature) &&
            (m !== "humidity" || layers.humidity) &&
            (m !== "rain" || layers.rain || mode === "radar") &&
            (m !== "clouds" || layers.clouds) &&
            (m !== "aqi" || layers.aqi)) {
          const r = rasterCanvas(series, m, frameIdx, settings.smoothing);
          if (r && drawTransform(ctx, bounds, map, r.width, r.height)) {
            ctx.globalAlpha = globalOpacity;
            ctx.drawImage(r, 0, 0);
            ctx.globalAlpha = 1;
          }
        }
      }

      // Cloud drift (clouds move with wind when cloud layer enabled).
      if (layers.clouds && metric !== "clouds") {
        const r = rasterCanvas(series, "clouds", frameIdx, settings.smoothing);
        if (r && drawTransform(ctx, bounds, map, r.width, r.height)) {
          const wv = windVector(series, bounds.min_lat + (bounds.max_lat - bounds.min_lat) / 2, bounds.min_lon + (bounds.max_lon - bounds.min_lon) / 2, frameIdx);
          driftRef.current = (driftRef.current + wv.u * dt * CLOUD_DRIFT_SCALE * 60) % 1;
          const dx = wv.u * CLOUD_DRIFT_SCALE * 60 * dt * 30;
          const dy = wv.v * CLOUD_DRIFT_SCALE * 60 * dt * 30;
          ctx.setTransform(1, 0, 0, 1, 0, 0);
          const scale = 1.3;
          const offX = (canvas.width * (scale - 1)) / 2 + dx;
          const offY = (canvas.height * (scale - 1)) / 2 + dy;
          ctx.globalAlpha = globalOpacity * 0.9;
          // Draw drifted cloud field using approximate screen-space mapping.
          const p00 = map.latLngToContainerPoint(L.latLng(bounds.max_lat, bounds.min_lon));
          const p10 = map.latLngToContainerPoint(L.latLng(bounds.max_lat, bounds.max_lon));
          const p01 = map.latLngToContainerPoint(L.latLng(bounds.min_lat, bounds.min_lon));
          const a = (p10.x - p00.x) / r.width;
          const b = (p10.y - p00.y) / r.width;
          const c = (p01.x - p00.x) / r.height;
          const d = (p01.y - p00.y) / r.height;
          ctx.setTransform(a * scale, b * scale, c * scale, d * scale, p00.x - offX, p00.y - offY);
          ctx.drawImage(r, 0, 0);
          ctx.globalAlpha = 1;
        }
      }

      // Wind particles.
      if (layers.wind && animating) {
        ctx.setTransform(1, 0, 0, 1, 0, 0);
        ctx.lineWidth = 1;
        const particles = particlesRef.current;
        if (particles.length !== windCount) {
          particlesRef.current = reseed(windCount, bounds);
        }
        for (const p of particles) {
          const wv = windVector(series, p.lat, p.lon, frameIdx);
          const speedKmh = wv.speed;
          if (speedKmh < 0.5) {
            p.life += dt * 0.5;
          } else {
            p.prevLat = p.lat;
            p.prevLon = p.lon;
            p.lat += wv.u * dt;
            p.lon += wv.v * dt;
            p.life += dt * (0.2 + speedKmh / 120);
          }
          if (p.life >= p.maxLife || p.lat < bounds.min_lat || p.lat > bounds.max_lat ||
              p.lon < bounds.min_lon || p.lon > bounds.max_lon) {
            p.lat = bounds.min_lat + Math.random() * (bounds.max_lat - bounds.min_lat);
            p.lon = bounds.min_lon + Math.random() * (bounds.max_lon - bounds.min_lon);
            p.life = 0;
            p.maxLife = 0.5 + Math.random() * 1.5;
            p.prevLat = p.lat;
            p.prevLon = p.lon;
          }
          const pt = map.latLngToContainerPoint(L.latLng(p.lat, p.lon));
          const prev = map.latLngToContainerPoint(L.latLng(p.prevLat, p.prevLon));
          const alpha = Math.min(1, p.life / p.maxLife) * (0.35 + Math.min(1, speedKmh / 40) * 0.6);
          ctx.strokeStyle = `rgba(255,255,255,${alpha.toFixed(3)})`;
          ctx.beginPath();
          ctx.moveTo(prev.x, prev.y);
          ctx.lineTo(pt.x, pt.y);
          ctx.stroke();
        }
      }

      // Rain particles.
      if (layers.rain && animating && mode !== "radar") {
        ctx.setTransform(1, 0, 0, 1, 0, 0);
        const drops = dropsRef.current;
        if (drops.length !== rainMax) {
          dropsRef.current = reseed(rainMax, bounds);
        }
        let active = 0;
        for (const p of drops) {
          const precip = sampleField(series, "rain", p.lat, p.lon, frameIdx) ?? 0;
          const wv = windVector(series, p.lat, p.lon, frameIdx);
          const cat = rainCategory(precip);
          if (cat.key === "none") {
            p.life += dt;
            if (p.life > 0.2) {
              p.lat = bounds.min_lat + Math.random() * (bounds.max_lat - bounds.min_lat);
              p.lon = bounds.min_lon + Math.random() * (bounds.max_lon - bounds.min_lon);
              p.life = 0;
            }
            continue;
          }
          active++;
          p.prevLat = p.lat;
          p.prevLon = p.lon;
          p.lat += (wv.u + Math.random() * 4e-5) * dt * 8;
          p.lon += (wv.v + Math.random() * 4e-5) * dt * 8;
          p.lat -= RAIN_FALL_DEG * dt * 6;
          p.life += dt;
          if (p.life > 1.5 || p.lat < bounds.min_lat || p.lat > bounds.max_lat ||
              p.lon < bounds.min_lon || p.lon > bounds.max_lon) {
            p.lat = bounds.min_lat + Math.random() * (bounds.max_lat - bounds.min_lat);
            p.lon = bounds.min_lon + Math.random() * (bounds.max_lon - bounds.min_lon);
            p.life = 0;
          }
          const [r, g, b] = cat.color;
          const pt = map.latLngToContainerPoint(L.latLng(p.lat, p.lon));
          const prev = map.latLngToContainerPoint(L.latLng(p.prevLat, p.prevLon));
          const intensity = Math.min(1, Math.max(0.25, precip / 8));
          ctx.strokeStyle = `rgba(${r},${g},${b},${(intensity * 0.85).toFixed(3)})`;
          ctx.lineWidth = Math.max(1, intensity * 2);
          ctx.beginPath();
          ctx.moveTo(prev.x, prev.y);
          ctx.lineTo(pt.x, pt.y);
          ctx.stroke();
        }
        if (active === 0 && mode === "forecast") {
          ctx.setTransform(1, 0, 0, 1, 0, 0);
          ctx.fillStyle = "rgba(15, 40, 120, 0.15)";
          // faint indication only where precipitation is actually present
        }
      }
    };

    rafRef.current = requestAnimationFrame(render);
    return () => {
      cancelAnimationFrame(rafRef.current);
      map.off("resize move zoom", resize);
    };
  }, [map, series, metric, mode, layers.clouds, layers.rain, layers.wind, layers.temperature, layers.humidity, layers.aqi, settings.enabled, settings.opacity, settings.density, settings.trail, settings.smoothing, windCount, rainMax, reseed]);

  return <canvas ref={canvasRef} className="pointer-events-none absolute inset-0 z-[420]" />;
}