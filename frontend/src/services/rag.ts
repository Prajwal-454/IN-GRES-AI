import { api } from "./api";

export interface RagStatus {
  enabled: boolean;
  available: boolean;
  chunks: number;
  indexed: number;
  mode: string;
  embedding_enabled: boolean;
  embedding_model: string;
  embedding_dim: number;
}

export interface RagReindexResponse {
  updated: number;
  chunks: number;
  indexed: number;
}

export interface KnowledgeDocumentInfo {
  id: number;
  title: string;
  source: string | null;
  author: string | null;
  status: string;
  file_path: string | null;
  chunk_count: number;
  created_at: string | null;
}

export interface RagSearchResult {
  content: string;
  score: number;
  section: string | null;
  document_id: number | null;
  document_title: string | null;
  source: string | null;
  file_path: string | null;
}

export interface RagDocumentsResponse {
  documents: KnowledgeDocumentInfo[];
}

export interface RagSearchResponse {
  query: string;
  results: RagSearchResult[];
}

export async function getRagStatus(): Promise<RagStatus> {
  const { data } = await api.get<RagStatus>("/rag/status");
  return data;
}

export async function reindexRag(): Promise<RagReindexResponse> {
  const { data } = await api.post<RagReindexResponse>("/rag/reindex");
  return data;
}

export async function fetchDocuments(): Promise<KnowledgeDocumentInfo[]> {
  const { data } = await api.get<RagDocumentsResponse>("/rag/documents");
  return data.documents;
}

export async function searchKnowledge(
  query: string,
  topK = 5
): Promise<RagSearchResult[]> {
  const { data } = await api.get<RagSearchResponse>("/rag/search", {
    params: { q: query, top_k: topK },
  });
  return data.results;
}

export async function uploadKnowledgeDocument(
  file: File
): Promise<{ title: string; documents: KnowledgeDocumentInfo[] }> {
  const form = new FormData();
  form.append("file", file);
  const { data } = await api.post("/rag/documents", form);
  return data;
}

export async function deleteKnowledgeDocument(
  documentId: number
): Promise<void> {
  await api.delete(`/rag/documents/${documentId}`);
}
