import { api } from "./api";

export interface MapFeature {
  type: "Feature";
  properties: {
    id: number;
    name: string;
    state: string;
    district: string;
    year: number;
    metric: string;
    metric_value: number | null;
    stage_of_extraction: number | null;
    category: string | null;
    is_demo: boolean;
    latitude: number | null;
    longitude: number | null;
  };
  geometry: {
    type: "Polygon";
    coordinates: number[][][];
  };
}

export interface MapData {
  type: "FeatureCollection";
  features: MapFeature[];
  meta: {
    metric: string;
    year: number;
    years: number[];
    states: string[];
    metrics: string[];
  };
}

export interface CompareProperties {
  id: number;
  name: string;
  state: string;
  district: string;
  year: number;
  metric: string;
  metric_value: number | null;
  metric_value_a: number | null;
  metric_value_b: number | null;
  delta: number | null;
  stage_of_extraction: number | null;
  category: string | null;
  category_a: string | null;
  category_b: string | null;
  category_changed: boolean;
  is_demo: boolean;
  latitude: number | null;
  longitude: number | null;
}

export interface CompareFeature {
  type: "Feature";
  properties: CompareProperties;
  geometry: MapFeature["geometry"];
}

export interface CompareData {
  type: "FeatureCollection";
  features: CompareFeature[];
  meta: {
    metric: string;
    year_a: number;
    year_b: number;
    years: number[];
    states: string[];
    metrics: string[];
  };
}

export interface IndiaCompareFeature {
  type: "Feature";
  properties: Omit<CompareProperties, "id" | "district" | "latitude" | "longitude"> & {
    name: string;
    has_data: boolean;
    unit_count: number;
  };
  geometry: IndiaFeature["geometry"];
}

export interface IndiaCompareData {
  type: "FeatureCollection";
  features: IndiaCompareFeature[];
  meta: CompareData["meta"];
}

export async function getMap(
  params: {
    state?: string;
    district?: string;
    village?: string;
    year?: number;
    metric?: string;
  } = {}
): Promise<MapData> {
  const { data } = await api.get<MapData>("/gis/map", { params });
  return data;
}

export async function getCompare(
  params: {
    state?: string;
    district?: string;
    village?: string;
    year_a?: number;
    year_b?: number;
    metric?: string;
  } = {}
): Promise<CompareData> {
  const { data } = await api.get<CompareData>("/gis/compare", { params });
  return data;
}

export async function getIndiaCompare(
  params: { year_a?: number; year_b?: number; metric?: string } = {}
): Promise<IndiaCompareData> {
  const { data } = await api.get<IndiaCompareData>("/gis/compare/india", { params });
  return data;
}

export interface IndiaFeature {
  type: "Feature";
  properties: {
    name: string;
    has_data: boolean;
    unit_count: number;
    metric_value: number | null;
    stage_of_extraction: number | null;
    category: string | null;
    is_demo: boolean;
    year: number;
    metric: string;
  };
  geometry: {
    type: "MultiPolygon" | "Polygon";
    coordinates: number[][][][] | number[][][];
  };
}

export interface IndiaMapData {
  type: "FeatureCollection";
  features: IndiaFeature[];
  units: MapData;
  meta: MapData["meta"];
}

export async function getIndiaMap(
  params: { year?: number; metric?: string } = {}
): Promise<IndiaMapData> {
  const { data } = await api.get<IndiaMapData>("/gis/india", { params });
  return data;
}

export interface BasinFeature {
  type: "Feature";
  properties: {
    id: number;
    name: string;
    basin: string;
    states: string[];
    unit_count: number;
    district_count: number;
    metric_value: number | null;
    stage_of_extraction: number | null;
    category: string | null;
    is_demo: boolean;
    year: number;
    metric: string;
  };
  geometry: {
    type: "MultiPolygon" | "Polygon";
    coordinates: number[][][][] | number[][][];
  };
}

export interface BasinMapData {
  type: "FeatureCollection";
  features: BasinFeature[];
  meta: MapData["meta"];
}

export async function getBasinMap(
  params: { basin?: string; year?: number; metric?: string } = {}
): Promise<BasinMapData> {
  const { data } = await api.get<BasinMapData>("/gis/basins", { params });
  return data;
}

export interface Station {
  id: number;
  name: string;
  state: string;
  district: string;
  latitude: number;
  longitude: number;
}

export interface LocationAnalysis {
  location: string | null;
  district: string | null;
  state: string | null;
  year: number | null;
  stage: number | null;
  category: string | null;
  water_level: {
    value: number | null;
    unit: string;
    trend_per_year: number | null;
  };
  risk: string | null;
  prediction: {
    target_year: number;
    value: number | null;
    unit: string;
    stage: number | null;
    category: string | null;
  } | null;
  recommendation: string[];
  is_demo: boolean;
  error?: string;
}

export async function getStations(
  params: { state?: string; district?: string; village?: string } = {}
): Promise<Station[]> {
  const { data } = await api.get<Station[]>("/gis/stations", { params });
  return data;
}

export async function getPrediction(
  params: {
    state?: string;
    district?: string;
    village?: string;
    year?: number;
    target_year?: number;
    metric?: string;
  } = {}
): Promise<MapData> {
  const { data } = await api.get<MapData>("/gis/prediction", { params });
  return data;
}

export async function analyzeLocation(
  lat: number,
  lon: number,
  params: { year?: number; target_year?: number } = {}
): Promise<LocationAnalysis> {
  const { data } = await api.get<LocationAnalysis>("/gis/analyze", {
    params: { lat, lon, ...params },
  });
  return data;
}