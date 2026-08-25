import L from "leaflet";
import { useEffect, useState } from "react";

import { sampleWeatherAt } from "@/components/WeatherAnimation";
import type { WeatherMapSeries } from "@/services/map";

// Curated reference cities, ranked by prominence. Lower rank = bigger city.
// Labels are thinned by zoom so the map never looks crowded (req: clean map).
const CITIES: { name: string; lat: number; lon: number; rank: number }[] = [
  { name: "Delhi", lat: 28.61, lon: 77.21, rank: 1 },
  { name: "Mumbai", lat: 19.08, lon: 72.88, rank: 1 },
  { name: "Kolkata", lat: 22.57, lon: 88.36, rank: 1 },
  { name: "Chennai", lat: 13.08, lon: 80.27, rank: 1 },
  { name: "Bengaluru", lat: 12.97, lon: 77.59, rank: 1 },
  { name: "Hyderabad", lat: 17.39, lon: 78.49, rank: 1 },
  { name: "Ahmedabad", lat: 23.02, lon: 72.57, rank: 2 },
  { name: "Pune", lat: 18.52, lon: 73.86, rank: 2 },
  { name: "Jaipur", lat: 26.91, lon: 75.79, rank: 2 },
  { name: "Lucknow", lat: 26.85, lon: 80.95, rank: 2 },
  { name: "Bhopal", lat: 23.26, lon: 77.41, rank: 3 },
  { name: "Nagpur", lat: 21.15, lon: 79.09, rank: 3 },
  { name: "Patna", lat: 25.59, lon: 85.14, rank: 3 },
  { name: "Guwahati", lat: 26.14, lon: 91.74, rank: 3 },
  { name: "Thiruvananthapuram", lat: 8.52, lon: 76.94, rank: 3 },
  { name: "Srinagar", lat: 34.08, lon: 74.8, rank: 4 },
  { name: "Colombo", lat: 6.93, lon: 79.85, rank: 4 },
  { name: "Kathmandu", lat: 27.72, lon: 85.32, rank: 4 },
  { name: "Dhaka", lat: 23.81, lon: 90.41, rank: 4 },
  { name: "Nay Pyi Taw", lat: 19.75, lon: 96.1, rank: 5 },
  { name: "Bangkok", lat: 13.76, lon: 100.5, rank: 5 },
  { name: "Karachi", lat: 24.86, lon: 67.0, rank: 5 },
  { name: "Lahore", lat: 31.55, lon: 74.34, rank: 5 },
  { name: "Islamabad", lat: 33.69, lon: 73.06, rank: 5 },
];

// How many label ranks are visible per zoom level. Zoomed out -> only major
// metros; zoomed in -> progressively more detail.
function maxRankForZoom(zoom: number): number {
  if (zoom < 4.5) return 1;
  if (zoom < 5.5) return 2;
  if (zoom < 6.5) return 3;
  if (zoom < 7.5) return 4;
  return 5;
}

interface Props {
  map: L.Map | null;
  series: WeatherMapSeries | null;
  frame: number;
}

/** Geographically anchored city labels (name + live temperature), density-aware. */
export default function CityLabels({ map, series, frame }: Props) {
  const [zoom, setZoom] = useState(map ? map.getZoom() : 4.2);

  useEffect(() => {
    if (!map) return;
    const onZoom = () => setZoom(map.getZoom());
    map.on("zoomend zoom", onZoom);
    return () => {
      map.off("zoomend zoom", onZoom);
    };
  }, [map]);

  useEffect(() => {
    if (!map) return;
    const pane = map.getPane("cityLabels");
    if (!pane) return;
    const group = L.layerGroup().addTo(map);
    if (series && series.grid.length && series.times.length) {
      const b = series.bounds;
      const maxRank = maxRankForZoom(zoom);
      const k = Math.max(0, Math.min(Math.round(frame), series.times.length - 1));
      for (const c of CITIES) {
        if (c.rank > maxRank) continue;
        if (c.lat < b.min_lat || c.lat > b.max_lat || c.lon < b.min_lon || c.lon > b.max_lon) continue;
        const w = sampleWeatherAt(series, c.lat, c.lon, k);
        if (w.temperature_2m === null) continue;
        const icon = L.divIcon({
          className: "",
          html:
            `<div class="ingres-city-label">` +
            `<div class="city-name">${c.name}</div>` +
            `<div class="city-temp">${Math.round(w.temperature_2m)}°C</div>` +
            `</div>`,
          iconSize: [0, 0],
        });
        L.marker([c.lat, c.lon], {
          icon,
          interactive: false,
          keyboard: false,
          pane: "cityLabels",
        }).addTo(group);
      }
    }
    return () => {
      group.remove();
    };
  }, [map, series, Math.round(frame), zoom]);

  return null;
}
