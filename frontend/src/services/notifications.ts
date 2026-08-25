import { api } from "./api";

export interface UserNotification {
  id: number;
  kind: string;
  title: string;
  body: string | null;
  payload: Record<string, unknown> | null;
  read: boolean;
  created_at: string;
}

export interface NotificationsResponse {
  notifications: UserNotification[];
  unread: number;
}

export interface AlertRule {
  id: number;
  name: string;
  metric: "stage" | "recharge" | "extraction" | "resource";
  operator: "gt" | "gte" | "lt" | "lte";
  threshold: number;
  state: string | null;
  district: string | null;
  village: string | null;
  year: number | null;
  channels: string[];
  cooldown_minutes: number;
  enabled: boolean;
  last_triggered_at: string | null;
  created_at: string;
}

export type RulePayload = Partial<AlertRule> &
  Pick<AlertRule, "name" | "metric" | "operator" | "threshold">;

export async function listNotifications(limit = 50, unreadOnly = false): Promise<NotificationsResponse> {
  const { data } = await api.get<NotificationsResponse>("/notifications", {
    params: { limit, unread_only: unreadOnly },
  });
  return data;
}

export async function markNotificationRead(id: number): Promise<void> {
  await api.patch(`/notifications/${id}/read`);
}

export async function markAllNotificationsRead(): Promise<{ marked: number }> {
  const { data } = await api.post("/notifications/read-all");
  return data;
}

export async function listAlertRules(): Promise<AlertRule[]> {
  const { data } = await api.get<AlertRule[]>("/notifications/rules");
  return data;
}

export async function createAlertRule(payload: RulePayload): Promise<AlertRule> {
  const { data } = await api.post<AlertRule>("/notifications/rules", payload);
  return data;
}

export async function updateAlertRule(id: number, payload: Partial<AlertRule>): Promise<AlertRule> {
  const { data } = await api.patch<AlertRule>(`/notifications/rules/${id}`, payload);
  return data;
}

export async function deleteAlertRule(id: number): Promise<void> {
  await api.delete(`/notifications/rules/${id}`);
}

export async function runAlertCheck(): Promise<{ created: number }> {
  const { data } = await api.post("/notifications/check");
  return data;
}
