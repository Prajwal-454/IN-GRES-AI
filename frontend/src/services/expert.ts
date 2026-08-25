import { api } from "./api";

export interface ExpertRequest {
  id: number;
  user_id: number;
  user_name: string | null;
  conversation_id: number | null;
  question: string;
  language: string | null;
  location: string | null;
  intent: string | null;
  status: "NEW" | "IN_PROGRESS" | "RESOLVED" | "CLOSED";
  priority: "LOW" | "MEDIUM" | "HIGH" | "URGENT" | null;
  resolution: string | null;
  assigned_expert_id: number | null;
  assigned_expert_name: string | null;
  resolved_at: string | null;
  created_at: string;
}

export async function createExpertRequest(data: {
  question: string;
  conversation_id?: number | null;
  language?: string | null;
  location?: string | null;
  intent?: string | null;
}): Promise<ExpertRequest> {
  const { data: res } = await api.post<ExpertRequest>("/expert/requests", data);
  return res;
}

export async function listExpertRequests(status?: string): Promise<ExpertRequest[]> {
  const { data } = await api.get<ExpertRequest[]>("/expert/requests", {
    params: { status },
  });
  return data;
}

export async function updateExpertRequest(
  id: number,
  data: { status?: string; priority?: string; resolution?: string }
): Promise<ExpertRequest> {
  const { data: res } = await api.patch<ExpertRequest>(`/expert/requests/${id}`, data);
  return res;
}