export type Metric = "temperature" | "rain" | "humidity" | "wind" | "clouds" | "aqi";

export type MetricValue = "none" | Metric;

export interface WeatherGridPoint {
  temperature_2m: number | null;
  apparent_temperature?: number | null;
  precipitation: number | null;
  relative_humidity_2m: number | null;
  wind_speed_10m: number | null;
  wind_direction_10m: number | null;
  cloud_cover: number | null;
  us_aqi?: number | null;
}

export const TEMP_STOPS: [number, [number, number, number]][] = [
  [-10, [19, 35, 90]],
  [0, [46, 92, 168]],
  [10, [80, 170, 190]],
  [18, [88, 190, 160]],
  [25, [180, 210, 80]],
  [30, [240, 220, 60]],
  [35, [255, 150, 40]],
  [40, [220, 40, 30]],
  [46, [150, 15, 25]],
];

export const RAIN_STOPS: [number, [number, number, number]][] = [
  [0, [255, 255, 255]],
  [1, [196, 226, 250]],
  [5, [120, 170, 240]],
  [15, [60, 120, 220]],
  [40, [30, 70, 190]],
  [80, [20, 40, 150]],
  [150, [10, 20, 100]],
];

export const HUMIDITY_STOPS: [number, [number, number, number]][] = [
  [20, [240, 200, 60]],
  [40, [180, 210, 80]],
  [60, [120, 190, 140]],
  [75, [80, 160, 200]],
  [90, [60, 110, 220]],
  [100, [40, 60, 180]],
];

export const WIND_STOPS: [number, [number, number, number]][] = [
  [0, [220, 235, 245]],
  [15, [150, 220, 150]],
  [30, [120, 200, 80]],
  [45, [240, 220, 60]],
  [60, [255, 160, 50]],
  [80, [220, 50, 50]],
  [120, [150, 20, 60]],
];

export const CLOUD_STOPS: [number, [number, number, number]][] = [
  [0, [255, 255, 255]],
  [100, [200, 210, 220]],
];

// US EPA AQI scale (Open-Meteo CAMS `us_aqi`).
export const AQI_STOPS: [number, [number, number, number]][] = [
  [0, [80, 200, 120]],
  [50, [230, 220, 70]],
  [100, [240, 150, 50]],
  [150, [225, 60, 50]],
  [200, [160, 50, 190]],
  [300, [130, 20, 60]],
  [500, [90, 10, 40]],
];

export const STOPS: Record<Metric, [number, [number, number, number]][]> = {
  temperature: TEMP_STOPS,
  rain: RAIN_STOPS,
  humidity: HUMIDITY_STOPS,
  wind: WIND_STOPS,
  clouds: CLOUD_STOPS,
  aqi: AQI_STOPS,
};

export const UNITS: Record<Metric, string> = {
  temperature: "°C",
  rain: "mm",
  humidity: "%",
  wind: "km/h",
  clouds: "%",
  aqi: "AQI",
};

export function scaleColor(
  stops: [number, [number, number, number]][],
  value: number
): [number, number, number] {
  if (value <= stops[0][0]) return stops[0][1];
  if (value >= stops[stops.length - 1][0]) return stops[stops.length - 1][1];
  for (let i = 1; i < stops.length; i++) {
    if (value <= stops[i][0]) {
      const [va, ca] = stops[i - 1];
      const [vb, cb] = stops[i];
      const f = (value - va) / (vb - va || 1);
      return [
        Math.round(ca[0] + (cb[0] - ca[0]) * f),
        Math.round(ca[1] + (cb[1] - ca[1]) * f),
        Math.round(ca[2] + (cb[2] - ca[2]) * f),
      ];
    }
  }
  return stops[stops.length - 1][1];
}

export function pointValue(p: WeatherGridPoint, metric: Metric): number | null {
  switch (metric) {
    case "temperature":
      return p.temperature_2m;
    case "rain":
      return p.precipitation;
    case "humidity":
      return p.relative_humidity_2m;
    case "wind":
      return p.wind_speed_10m;
    case "clouds":
      return p.cloud_cover;
    case "aqi":
      return p.us_aqi ?? null;
  }
}

export interface RainCategory {
  key: "none" | "light" | "moderate" | "heavy" | "very-heavy" | "extreme";
  label: string;
  max: number;
  color: [number, number, number];
}

export const RAIN_CATEGORIES: RainCategory[] = [
  { key: "none", label: "No precipitation", max: 0.1, color: [255, 255, 255] },
  { key: "light", label: "Light rain", max: 2.5, color: [160, 210, 250] },
  { key: "moderate", label: "Moderate rain", max: 7.6, color: [80, 140, 230] },
  { key: "heavy", label: "Heavy rain", max: 15.5, color: [40, 80, 200] },
  { key: "very-heavy", label: "Very heavy rain", max: 50, color: [20, 40, 160] },
  { key: "extreme", label: "Extreme precipitation", max: Infinity, color: [120, 20, 140] },
];

export function rainCategory(mmPerHour: number | null): RainCategory {
  if (mmPerHour === null || mmPerHour < 0.1) return RAIN_CATEGORIES[0];
  for (const c of RAIN_CATEGORIES) {
    if (mmPerHour <= c.max) return c;
  }
  return RAIN_CATEGORIES[RAIN_CATEGORIES.length - 1];
}

export function msPerHourToKmh(v: number): number {
  return v * 3.6;
}

export function kmhToMs(v: number): number {
  return v / 3.6;
}

export function formatWind(vKmh: number | null, unit: "kmh" | "ms"): string {
  if (vKmh === null) return "—";
  const value = unit === "ms" ? kmhToMs(vKmh) : vKmh;
  return `${value.toFixed(unit === "ms" ? 1 : 0)} ${unit === "ms" ? "m/s" : "km/h"}`;
}

export interface SeriesBounds {
  min_lat: number;
  min_lon: number;
  max_lat: number;
  max_lon: number;
}

// Compact WMO weather-interpretation code -> short English label (hover tooltip).
export function weatherLabel(code: number | null | undefined): string | null {
  if (code === null || code === undefined) return null;
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
  if (code === 80 || code === 81 || code === 82) return "Rain showers";
  if (code === 85 || code === 86) return "Snow showers";
  if (code === 95) return "Thunderstorm";
  if (code >= 96) return "Thunderstorm with hail";
  return null;
}

export function formatCoords(lat: number, lon: number): string {
  const ns = lat >= 0 ? "N" : "S";
  const ew = lon >= 0 ? "E" : "W";
  return `${Math.abs(lat).toFixed(2)}° ${ns}, ${Math.abs(lon).toFixed(2)}° ${ew}`;
}