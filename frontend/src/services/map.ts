import { api } from "./api";
import type { DailyWeather, HourlyWeather } from "./weather";
import type { SeriesBounds, WeatherGridPoint } from "@/lib/weatherLayer";

const OPEN_METEO = "https://api.open-meteo.com/v1/forecast";

const OM_CURRENT = [
  "temperature_2m",
  "apparent_temperature",
  "relative_humidity_2m",
  "is_day",
  "precipitation",
  "weather_code",
  "wind_speed_10m",
  "wind_direction_10m",
  "pressure_msl",
  "cloud_cover",
].join(",");

const OM_HOURLY = [
  "temperature_2m",
  "apparent_temperature",
  "relative_humidity_2m",
  "precipitation_probability",
  "precipitation",
  "weather_code",
  "wind_speed_10m",
  "wind_direction_10m",
  "is_day",
  "cloud_cover",
].join(",");

const OM_DAILY = [
  "weather_code",
  "temperature_2m_max",
  "temperature_2m_min",
  "apparent_temperature_max",
  "apparent_temperature_min",
  "precipitation_probability_max",
  "precipitation_sum",
  "wind_speed_10m_max",
].join(",");

interface OmCurrentResponse {
  time: string | null;
  temperature_2m: number | null;
  apparent_temperature: number | null;
  relative_humidity_2m: number | null;
  is_day: number | null;
  precipitation: number | null;
  weather_code: number | null;
  wind_speed_10m: number | null;
  wind_direction_10m: number | null;
  pressure_msl: number | null;
  cloud_cover: number | null;
}

interface OmHourlyResponse {
  time: string[];
  temperature_2m: (number | null)[];
  apparent_temperature: (number | null)[];
  relative_humidity_2m: (number | null)[];
  precipitation_probability: (number | null)[];
  precipitation: (number | null)[];
  weather_code: (number | null)[];
  wind_speed_10m: (number | null)[];
  wind_direction_10m: (number | null)[];
  is_day: (number | null)[];
  cloud_cover: (number | null)[];
}

interface OmDailyResponse {
  time: string[];
  weather_code: (number | null)[];
  temperature_2m_max: (number | null)[];
  temperature_2m_min: (number | null)[];
  apparent_temperature_max: (number | null)[];
  apparent_temperature_min: (number | null)[];
  precipitation_probability_max: (number | null)[];
  precipitation_sum: (number | null)[];
  wind_speed_10m_max: (number | null)[];
}

interface OmResponse {
  current?: OmCurrentResponse;
  hourly?: OmHourlyResponse;
  daily?: OmDailyResponse;
  utc_offset_seconds?: number;
}

// ---------------------------------------------------------------------------
// Search — still uses the backend (custom Indian village/district DB)
// ---------------------------------------------------------------------------

export interface MapSearchResult {
  type: "state" | "district" | "village" | "assessment_unit";
  name: string;
  state: string | null;
  district: string | null;
  village: string | null;
  latitude: number | null;
  longitude: number | null;
}

export interface MapSearchResponse {
  query: string;
  results: MapSearchResult[];
}

export async function searchLocations(q: string, limit = 8): Promise<MapSearchResult[]> {
  const { data } = await api.get<MapSearchResponse>("/gis/search", {
    params: { q, limit },
  });
  return data.results ?? [];
}

// ---------------------------------------------------------------------------
// WMO weather-code → human label
// ---------------------------------------------------------------------------

function wmoLabel(code: number | null | undefined): string | null {
  if (code == null) return null;
  if (code === 0) return "Clear sky";
  if (code === 1) return "Mainly clear";
  if (code === 2) return "Partly cloudy";
  if (code === 3) return "Overcast";
  if (code === 45 || code === 48) return "Fog";
  if (code >= 51 && code <= 55) return "Drizzle";
  if (code >= 56 && code <= 57) return "Freezing drizzle";
  if (code >= 61 && code <= 65) return "Rain";
  if (code === 66 || code === 67) return "Freezing rain";
  if (code >= 71 && code <= 77) return "Snow";
  if (code >= 80 && code <= 82) return "Rain showers";
  if (code === 85 || code === 86) return "Snow showers";
  if (code === 95) return "Thunderstorm";
  if (code >= 96) return "Thunderstorm with hail";
  return null;
}

// ---------------------------------------------------------------------------
// Point weather (WeatherCard)
// ---------------------------------------------------------------------------

export interface PointWeather {
  latitude: number;
  longitude: number;
  timezone: string;
  current: {
    time: string | null;
    temperature_2m: number | null;
    apparent_temperature: number | null;
    relative_humidity_2m: number | null;
    is_day: number | null;
    precipitation: number | null;
    weather_code: number | null;
    weather_label: string | null;
    wind_speed_10m: number | null;
    pressure_msl: number | null;
    cloud_cover: number | null;
  } | null;
  hourly: HourlyWeather[];
  daily: DailyWeather[];
  source: string;
  official: boolean;
}

export async function fetchPointWeather(
  lat: number,
  lon: number,
  days = 7
): Promise<PointWeather> {
  const params = new URLSearchParams({
    latitude: String(lat),
    longitude: String(lon),
    current: OM_CURRENT,
    hourly: OM_HOURLY,
    daily: OM_DAILY,
    timezone: "auto",
    forecast_days: String(days),
  });
  const res = await fetch(`${OPEN_METEO}?${params}`);
  if (!res.ok) throw new Error(`Open-Meteo ${res.status}`);
  const om: OmResponse = await res.json();

  const cur = om.current ?? null;
  const current = cur
    ? {
        time: cur.time ?? null,
        temperature_2m: cur.temperature_2m ?? null,
        apparent_temperature: cur.apparent_temperature ?? null,
        relative_humidity_2m: cur.relative_humidity_2m ?? null,
        is_day: cur.is_day ?? null,
        precipitation: cur.precipitation ?? null,
        weather_code: cur.weather_code ?? null,
        weather_label: wmoLabel(cur.weather_code),
        wind_speed_10m: cur.wind_speed_10m ?? null,
        pressure_msl: cur.pressure_msl ?? null,
        cloud_cover: cur.cloud_cover ?? null,
      }
    : null;

  const oh = om.hourly;
  const hourly: HourlyWeather[] = oh
    ? oh.time.map((t, i) => ({
        time: t,
        temperature_2m: oh.temperature_2m[i] ?? null,
        apparent_temperature: oh.apparent_temperature[i] ?? null,
        relative_humidity_2m: oh.relative_humidity_2m[i] ?? null,
        precipitation_probability: oh.precipitation_probability[i] ?? null,
        weather_code: oh.weather_code[i] ?? null,
        weather_label: wmoLabel(oh.weather_code[i]),
        wind_speed_10m: oh.wind_speed_10m[i] ?? null,
        pressure_msl: null,
        is_day: oh.is_day[i] ?? null,
      }))
    : [];

  const od = om.daily;
  const daily: DailyWeather[] = od
    ? od.time.map((t, i) => ({
        date: t,
        weather_code: od.weather_code[i] ?? null,
        weather_label: wmoLabel(od.weather_code[i]),
        temperature_2m_max: od.temperature_2m_max[i] ?? null,
        temperature_2m_min: od.temperature_2m_min[i] ?? null,
        apparent_temperature_max: od.apparent_temperature_max[i] ?? null,
        apparent_temperature_min: od.apparent_temperature_min[i] ?? null,
        precipitation_probability_max: od.precipitation_probability_max[i] ?? null,
        precipitation_sum: od.precipitation_sum[i] ?? null,
        wind_speed_10m_max: od.wind_speed_10m_max[i] ?? null,
      }))
    : [];

  return {
    latitude: lat,
    longitude: lon,
    timezone: "auto",
    current,
    hourly,
    daily,
    source: "Open-Meteo",
    official: false,
  };
}

// ---------------------------------------------------------------------------
// Map grid series (weather animation overlay)
// ---------------------------------------------------------------------------

export interface WeatherSeriesPoint extends WeatherGridPoint {
  lat: number;
  lon: number;
  weather_code: number | null;
  hourly: {
    temperature_2m: number[];
    apparent_temperature: number[];
    relative_humidity_2m: number[];
    precipitation: number[];
    cloud_cover: number[];
    wind_speed_10m: number[];
    wind_direction_10m: number[];
    weather_code: number[];
    us_aqi: number[];
  };
}

export interface WeatherMapSeries {
  scope: string;
  bounds: SeriesBounds;
  grid: WeatherSeriesPoint[];
  times: string[];
  time: string | null;
  source: string;
  official: boolean;
  available?: boolean;
  detail?: string;
}

export interface WeatherSeriesOptions {
  state?: string;
  district?: string;
  village?: string;
  maxPoints?: number;
  hours?: number;
}

/** Generate a grid of lat/lon points covering India. */
function indiaGrid(count: number): [number, number][] {
  const MIN_LAT = 6.5;
  const MAX_LAT = 37.5;
  const MIN_LON = 68.0;
  const MAX_LON = 97.5;
  const aspect = (MAX_LON - MIN_LON) / (MAX_LAT - MIN_LAT);
  const cols = Math.max(2, Math.round(Math.sqrt(count * aspect)));
  const rows = Math.max(2, Math.round(count / cols));
  const points: [number, number][] = [];
  for (let r = 0; r < rows; r++) {
    for (let c = 0; c < cols; c++) {
      const lat = MIN_LAT + ((r + 0.5) / rows) * (MAX_LAT - MIN_LAT);
      const lon = MIN_LON + ((c + 0.5) / cols) * (MAX_LON - MIN_LON);
      points.push([Math.round(lat * 100) / 100, Math.round(lon * 100) / 100]);
    }
  }
  return points;
}

/** Fetch weather for one grid point (compact hourly only — no daily). */
async function fetchGridPoint(
  lat: number,
  lon: number,
  hours: number
): Promise<{ lat: number; lon: number; data: OmResponse } | null> {
  try {
    const params = new URLSearchParams({
      latitude: String(lat),
      longitude: String(lon),
      current: "temperature_2m,relative_humidity_2m,precipitation,weather_code,wind_speed_10m,wind_direction_10m,cloud_cover",
      hourly: "temperature_2m,apparent_temperature,relative_humidity_2m,precipitation,cloud_cover,wind_speed_10m,wind_direction_10m,weather_code",
      timezone: "auto",
      forecast_hours: String(hours),
    });
    const res = await fetch(`${OPEN_METEO}?${params}`);
    if (!res.ok) return null;
    const data: OmResponse = await res.json();
    return { lat, lon, data };
  } catch {
    return null;
  }
}

/** Batch-fetch grid points with controlled concurrency. */
async function fetchGridBatch(
  points: [number, number][],
  hours: number,
  concurrency = 8
): Promise<{ lat: number; lon: number; data: OmResponse }[]> {
  const results: { lat: number; lon: number; data: OmResponse }[] = [];
  for (let i = 0; i < points.length; i += concurrency) {
    const batch = points.slice(i, i + concurrency);
    const batchResults = await Promise.all(
      batch.map(([lat, lon]) => fetchGridPoint(lat, lon, hours))
    );
    for (const r of batchResults) {
      if (r) results.push(r);
    }
  }
  return results;
}

function valArr(arr: (number | null)[] | undefined, len: number): number[] {
  if (!arr) return new Array(len).fill(0);
  return arr.map((v) => v ?? 0);
}

export async function fetchWeatherMapSeries(
  opts: WeatherSeriesOptions = {}
): Promise<WeatherMapSeries> {
  const maxPoints = opts.maxPoints ?? 44;
  const hours = opts.hours ?? 24;

  const points = indiaGrid(maxPoints);
  const gridData = await fetchGridBatch(points, hours);

  if (gridData.length === 0) {
    return {
      scope: "india",
      bounds: { min_lat: 6.5, max_lat: 37.5, min_lon: 68, max_lon: 97.5 },
      grid: [],
      times: [],
      time: null,
      source: "Open-Meteo",
      official: false,
      available: false,
      detail: "Weather data temporarily unavailable.",
    };
  }

  // Collect all unique times from the first point's hourly data
  const firstHourly = gridData[0].data.hourly;
  const times = firstHourly?.time ?? [];
  const now = new Date().toISOString();

  const grid: WeatherSeriesPoint[] = gridData.map(({ lat, lon, data }) => {
    const h = data.hourly;
    const len = h?.time?.length ?? 0;
    return {
      lat,
      lon,
      temperature_2m: data.current?.temperature_2m ?? null,
      relative_humidity_2m: data.current?.relative_humidity_2m ?? null,
      precipitation: data.current?.precipitation ?? null,
      weather_code: data.current?.weather_code ?? null,
      wind_speed_10m: data.current?.wind_speed_10m ?? null,
      wind_direction_10m: (data.current as Record<string, unknown> as { wind_direction_10m?: number | null })?.wind_direction_10m ?? null,
      hourly: {
        temperature_2m: valArr(h?.temperature_2m, len),
        apparent_temperature: valArr(h?.apparent_temperature, len),
        relative_humidity_2m: valArr(h?.relative_humidity_2m, len),
        precipitation: valArr(h?.precipitation, len),
        cloud_cover: valArr(h?.cloud_cover, len),
        wind_speed_10m: valArr(h?.wind_speed_10m, len),
        wind_direction_10m: valArr(h?.wind_direction_10m, len),
        weather_code: valArr(h?.weather_code, len),
        us_aqi: [],
      },
    };
  });

  // Compute bounds from grid
  const lats = grid.map((p) => p.lat);
  const lons = grid.map((p) => p.lon);
  const bounds: SeriesBounds = {
    min_lat: Math.min(...lats),
    max_lat: Math.max(...lats),
    min_lon: Math.min(...lons),
    max_lon: Math.max(...lons),
  };

  return {
    scope: "india",
    bounds,
    grid,
    times,
    time: now,
    source: "Open-Meteo",
    official: false,
  };
}
