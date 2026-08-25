import { api } from "./api";

export interface ImportResponse {
  dataset_id: number | null;
  rows_parsed: number;
  rows_imported: number;
  states_created: string[];
  districts_created: string[];
  units_created: string[];
  warnings: string[];
  alerts_triggered: number;
}

export async function importDataset(
  file: File,
  opts?: { name?: string; source?: string; year?: number }
): Promise<ImportResponse> {
  const form = new FormData();
  form.append("file", file);
  if (opts?.name) form.append("name", opts.name);
  if (opts?.source) form.append("source", opts.source);
  if (opts?.year) form.append("year", String(opts.year));
  const { data } = await api.post<ImportResponse>("/admin/datasets/import", form, {
    headers: { "Content-Type": "multipart/form-data" },
  });
  return data;
}

export async function downloadImportTemplate(): Promise<Blob> {
  const { data } = await api.get<Blob>("/admin/datasets/import/template", {
    responseType: "blob",
  });
  return data;
}

export function triggerBlobDownload(blob: Blob, filename: string): void {
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  URL.revokeObjectURL(url);
}
