import { api } from "./api";
import type { DailyWeather, HourlyWeather } from "./weather";
import type { SeriesBounds, WeatherGridPoint } from "@/lib/weatherLayer";

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

export async function searchLocations(q: string, limit = 8): Promise<MapSearchResult[]> {
  const { data } = await api.get<MapSearchResponse>("/gis/search", {
    params: { q, limit },
  });
  return data.results ?? [];
}

export async function fetchPointWeather(
  lat: number,
  lon: number,
  days = 1
): Promise<PointWeather> {
  const { data } = await api.get<PointWeather>("/weather/point", {
    params: { lat, lon, days },
  });
  return data;
}

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

export async function fetchWeatherMapSeries(
  opts: WeatherSeriesOptions = {}
): Promise<WeatherMapSeries> {
  const { data } = await api.get<WeatherMapSeries>("/weather/map/series", {
    params: {
      state: opts.state,
      district: opts.district,
      village: opts.village,
      max_points: opts.maxPoints ?? 30,
      hours: opts.hours ?? 24,
    },
  });
  return data;
}