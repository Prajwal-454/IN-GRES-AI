const OPEN_METEO = "https://api.open-meteo.com/v1/forecast";

// ---------------------------------------------------------------------------
// Types (unchanged — consumers don't need to know about the provider)
// ---------------------------------------------------------------------------

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

export interface WeatherMapFilters {
  maxPoints?: number;
}

// ---------------------------------------------------------------------------
// Helpers
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
// fetchWeatherForecast — direct Open-Meteo
// ---------------------------------------------------------------------------

export async function fetchWeatherForecast(
  filters: WeatherFilters
): Promise<WeatherForecast> {
  // Resolve lat/lon from village/district/state using backend geocoding
  let lat = 22.0;
  let lon = 80.0;
  const q = filters.village ?? filters.district ?? filters.state;
  if (q) {
    try {
      const { api } = await import("./api");
      const { data } = await await api.get<{ results: Array<{ latitude: number; longitude: number }> }>("/gis/search", {
        params: { q, limit: 1 },
      });
      if (data.results?.[0]) {
        lat = data.results[0].latitude ?? lat;
        lon = data.results[0].longitude ?? lon;
      }
    } catch {
      // fall back to default center
    }
  }

  const days = filters.days ?? 7;
  const params = new URLSearchParams({
    latitude: String(lat),
    longitude: String(lon),
    current: "temperature_2m,apparent_temperature,relative_humidity_2m,is_day,precipitation,weather_code,wind_speed_10m,pressure_msl,cloud_cover",
    hourly: "temperature_2m,apparent_temperature,relative_humidity_2m,precipitation_probability,weather_code,wind_speed_10m,is_day",
    daily: "weather_code,temperature_2m_max,temperature_2m_min,apparent_temperature_max,apparent_temperature_min,precipitation_probability_max,precipitation_sum,wind_speed_10m_max",
    timezone: "auto",
    forecast_days: String(days),
  });

  const res = await fetch(`${OPEN_METEO}?${params}`);
  if (!res.ok) throw new Error(`Open-Meteo ${res.status}`);
  const om = await res.json();

  const cur = om.current;
  const current: CurrentWeather | null = cur
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
    ? oh.time.map((t: string, i: number) => ({
        time: t,
        temperature_2m: oh.temperature_2m?.[i] ?? null,
        apparent_temperature: oh.apparent_temperature?.[i] ?? null,
        relative_humidity_2m: oh.relative_humidity_2m?.[i] ?? null,
        precipitation_probability: oh.precipitation_probability?.[i] ?? null,
        weather_code: oh.weather_code?.[i] ?? null,
        weather_label: wmoLabel(oh.weather_code?.[i]),
        wind_speed_10m: oh.wind_speed_10m?.[i] ?? null,
        pressure_msl: null,
        is_day: oh.is_day?.[i] ?? null,
      }))
    : [];

  const od = om.daily;
  const daily: DailyWeather[] = od
    ? od.time.map((t: string, i: number) => ({
        date: t,
        weather_code: od.weather_code?.[i] ?? null,
        weather_label: wmoLabel(od.weather_code?.[i]),
        temperature_2m_max: od.temperature_2m_max?.[i] ?? null,
        temperature_2m_min: od.temperature_2m_min?.[i] ?? null,
        apparent_temperature_max: od.apparent_temperature_max?.[i] ?? null,
        apparent_temperature_min: od.apparent_temperature_min?.[i] ?? null,
        precipitation_probability_max: od.precipitation_probability_max?.[i] ?? null,
        precipitation_sum: od.precipitation_sum?.[i] ?? null,
        wind_speed_10m_max: od.wind_speed_10m_max?.[i] ?? null,
      }))
    : [];

  return {
    scope: filters.village ? "village" : filters.district ? "district" : "state",
    state: filters.state ?? null,
    district: filters.district ?? null,
    village: filters.village ?? null,
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
// fetchWeatherMap — direct Open-Meteo (simplified grid)
// ---------------------------------------------------------------------------

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

export async function fetchWeatherMap(
  filters: WeatherMapFilters = {}
): Promise<WeatherMapData> {
  const count = filters.maxPoints ?? 44;
  const points = indiaGrid(count);

  const results: WeatherMapPoint[] = [];
  for (let i = 0; i < points.length; i += 6) {
    const batch = points.slice(i, i + 6);
    const batchResults = await Promise.all(
      batch.map(async ([lat, lon]) => {
        try {
          const params = new URLSearchParams({
            latitude: String(lat),
            longitude: String(lon),
            current: "temperature_2m,relative_humidity_2m,precipitation,weather_code,wind_speed_10m,wind_direction_10m",
            timezone: "auto",
          });
          const res = await fetch(`${OPEN_METEO}?${params}`);
          if (!res.ok) return null;
          const om = await res.json();
          const c = om.current;
          return {
            lat,
            lon,
            temperature_2m: c?.temperature_2m ?? null,
            relative_humidity_2m: c?.relative_humidity_2m ?? null,
            precipitation: c?.precipitation ?? null,
            weather_code: c?.weather_code ?? null,
            wind_speed_10m: c?.wind_speed_10m ?? null,
            wind_direction_10m: c?.wind_direction_10m ?? null,
          } as WeatherMapPoint;
        } catch {
          return null;
        }
      })
    );
    for (const r of batchResults) {
      if (r) results.push(r);
    }
  }

  const lats = results.map((p) => p.lat);
  const lons = results.map((p) => p.lon);

  return {
    scope: "india",
    bounds: {
      min_lat: Math.min(...lats),
      max_lat: Math.max(...lats),
      min_lon: Math.min(...lons),
      max_lon: Math.max(...lons),
    },
    grid: results,
    time: new Date().toISOString(),
    source: "Open-Meteo",
    official: false,
  };
}
