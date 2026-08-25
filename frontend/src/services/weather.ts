import { api } from "./api";

export interface CurrentWeather {
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
}

export interface HourlyWeather {
  time: string;
  temperature_2m: number | null;
  apparent_temperature: number | null;
  relative_humidity_2m: number | null;
  precipitation_probability: number | null;
  weather_code: number | null;
  weather_label: string | null;
  wind_speed_10m: number | null;
  pressure_msl: number | null;
  is_day: number | null;
}

export interface DailyWeather {
  date: string;
  weather_code: number | null;
  weather_label: string | null;
  temperature_2m_max: number | null;
  temperature_2m_min: number | null;
  apparent_temperature_max: number | null;
  apparent_temperature_min: number | null;
  precipitation_probability_max: number | null;
  precipitation_sum: number | null;
  wind_speed_10m_max: number | null;
}

export interface WeatherForecast {
  scope: string;
  state: string | null;
  district: string | null;
  village: string | null;
  latitude: number;
  longitude: number;
  timezone: string;
  current: CurrentWeather | null;
  hourly: HourlyWeather[];
  daily: DailyWeather[];
  source: string;
  official: boolean;
}

export interface WeatherFilters {
  state?: string;
  district?: string;
  village?: string;
  days?: number;
}

export interface WeatherMapPoint {
  lat: number;
  lon: number;
  temperature_2m: number | null;
  relative_humidity_2m: number | null;
  precipitation: number | null;
  weather_code: number | null;
  wind_speed_10m: number | null;
  wind_direction_10m: number | null;
}

export interface WeatherMapBounds {
  min_lat: number;
  min_lon: number;
  max_lat: number;
  max_lon: number;
}

export interface WeatherMapData {
  scope: string;
  bounds: WeatherMapBounds;
  grid: WeatherMapPoint[];
  time: string | null;
  source: string;
  official: boolean;
}

export async function fetchWeatherForecast(filters: WeatherFilters): Promise<WeatherForecast> {
  const { data } = await api.get<WeatherForecast>("/weather/forecast", { params: filters });
  return data;
}

export interface WeatherMapFilters {
  maxPoints?: number;
}

export async function fetchWeatherMap(filters: WeatherMapFilters = {}): Promise<WeatherMapData> {
  const { data } = await api.get<WeatherMapData>("/weather/map", {
    params: { max_points: filters.maxPoints },
  });
  return data;
}