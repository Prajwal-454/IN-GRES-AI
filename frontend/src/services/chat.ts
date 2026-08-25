import { api } from "./api";
import type { IndiaMapData, MapFeature } from "./gis";

export interface Conversation {
  id: number;
  title: string | null;
  language: string;
  created_at: string;
}

export interface CategoryCounts {
  Safe?: number;
  "Semi-critical"?: number;
  Critical?: number;
  "Over-exploited"?: number;
  [key: string]: number | undefined;
}

export interface RankingRow {
  name: string;
  stage: number;
  category: string | null;
}

export interface DataSection {
  scope: string;
  year: number | null;
  assessment_units: number;
  recharge: number | null;
  extraction: number | null;
  stage: number | null;
  resource: number | null;
  category: string | null;
  category_counts: CategoryCounts;
  ranking: RankingRow[];
}

export interface MapSection {
  features: MapFeature[];
  india: IndiaMapData | null;
  metric: string;
  year: number;
  state: string | null;
  district: string | null;
  village: string | null;
}

export interface SeriesPoint {
  year: number;
  value: number;
}

export interface ForecastPoint {
  year: number;
  value: number;
  lower: number;
  upper: number;
}

export interface GraphSection {
  metric: string;
  unit: string;
  series: SeriesPoint[];
  comparison: SeriesPoint[] | null;
  forecast: ForecastPoint[] | null;
  scenario_forecast: ForecastPoint[] | null;
}

export interface PredictionSection {
  scope: string;
  metric: string;
  unit: string;
  direction: string;
  pct_change: number | null;
  r2: number | null;
  method: string | null;
  risk: string | null;
  years_to_threshold: number | null;
  last_value: number | null;
  last_year: number | null;
  end_value: number | null;
  points: ForecastPoint[];
}

export interface RichSections {
  mode: "data" | "forecast" | "scenario" | "recommend";
  data: DataSection;
  map?: MapSection;
  graph?: GraphSection;
  prediction?: PredictionSection;
  explanation: string;
  recommendation: string[];
}

export interface ChatMessage {
  id: number;
  conversation_id: number;
  role: "user" | "assistant";
  content: string;
  language: string | null;
  intent: string | null;
  location: string | null;
  sources: string[] | null;
  response_type: string | null;
  is_demo: boolean;
  sections: RichSections | null;
  rating?: number | null;
  rating_note?: string | null;
  followups?: string[] | null;
  created_at: string;
}

export interface ChatResponse {
  conversation_id: number;
  user_message: ChatMessage;
  assistant_message: ChatMessage;
  intent: string | null;
  language: string | null;
  location: string | null;
  latency_ms: number | null;
}

export async function listConversations(): Promise<Conversation[]> {
  const { data } = await api.get<Conversation[]>("/chat/conversations");
  return data;
}

export async function createConversation(): Promise<Conversation> {
  const { data } = await api.post<Conversation>("/chat/conversations", {});
  return data;
}

export async function listMessages(conversationId: number): Promise<ChatMessage[]> {
  const { data } = await api.get<ChatMessage[]>(
    `/chat/conversations/${conversationId}/messages`
  );
  return data;
}

export async function sendMessage(
  message: string,
  conversationId?: number
): Promise<ChatResponse> {
  const { data } = await api.post<ChatResponse>("/chat/messages", {
    message,
    conversation_id: conversationId ?? null,
  });
  return data;
}

export interface VoiceChatResponse extends ChatResponse {
  transcript: string;
  detected_language: string;
  stt_confidence: number;
  stt_provider: string;
  tts_provider: string;
  tts_has_audio: boolean;
  audio_format: string | null;
  audio_base64: string | null;
}

export async function sendVoiceMessage(
  audio: Blob,
  conversationId?: number,
  voice?: "male" | "female"
): Promise<VoiceChatResponse> {
  const form = new FormData();
  form.append("audio", audio, "recording.webm");
  if (conversationId != null) form.append("conversation_id", String(conversationId));
  if (voice) form.append("voice", voice);
  const { data } = await api.post<VoiceChatResponse>("/chat/voice", form, {
    headers: { "Content-Type": undefined },
  });
  return data;
}

export async function deleteConversation(conversationId: number): Promise<void> {
  await api.delete(`/chat/conversations/${conversationId}`);
}

export async function bulkDeleteConversations(ids: number[]): Promise<number[]> {
  const { data } = await api.post<{ deleted: number[]; count: number }>(
    "/chat/conversations/bulk-delete",
    { ids }
  );
  return data.deleted;
}

export async function rateMessage(
  messageId: number,
  rating: 1 | -1,
  note?: string
): Promise<ChatMessage> {
  const { data } = await api.post<ChatMessage>(
    `/chat/messages/${messageId}/feedback`,
    { rating, note: note ?? null }
  );
  return data;
}

export interface RegenerateResponse {
  conversation_id: number;
  assistant_message: ChatMessage;
  intent: string | null;
  language: string | null;
  location: string | null;
  latency_ms: number | null;
}

export async function regenerateAnswer(
  conversationId: number
): Promise<RegenerateResponse> {
  const { data } = await api.post<RegenerateResponse>(
    `/chat/conversations/${conversationId}/regenerate`
  );
  return data;
}

export async function exportConversation(conversationId: number): Promise<Blob> {
  const { data } = await api.get<Blob>(
    `/chat/conversations/${conversationId}/export`,
    { responseType: "blob" }
  );
  return data;
}

export interface Transcription {
  text: string;
  language: string;
  confidence: number;
  provider: string;
}

/** Mic dictation: audio -> recognised text only (no answer yet). */
export async function transcribeAudio(audio: Blob): Promise<Transcription> {
  const form = new FormData();
  form.append("audio", audio, "recording.webm");
  const { data } = await api.post<Transcription>("/chat/transcribe", form, {
    headers: { "Content-Type": undefined },
  });
  return data;
}