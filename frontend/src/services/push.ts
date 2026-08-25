import { api } from "./api";

export interface PushConfig {
  enabled: boolean;
  public_key: string | null;
  supported: boolean;
}

export async function getPushConfig(): Promise<PushConfig> {
  const { data } = await api.get<PushConfig>("/push/config");
  return data;
}

export async function subscribeToPush(subscription: PushSubscription): Promise<void> {
  const json = subscription.toJSON() as {
    endpoint: string;
    keys?: { p256dh: string; auth: string };
  };
  if (!json.endpoint || !json.keys) {
    throw new Error("Incomplete push subscription");
  }
  await api.post("/push/subscribe", {
    endpoint: json.endpoint,
    keys: json.keys,
  });
}

export async function unsubscribeFromPush(endpoint: string): Promise<boolean> {
  const { data } = await api.delete<{ removed: boolean }>("/push/subscribe", {
    data: { endpoint, keys: { p256dh: "", auth: "" } },
  });
  return data.removed;
}

export async function urlBase64ToUint8Array(
  base64: string
): Promise<Uint8Array<ArrayBuffer>> {
  const padding = "=".repeat((4 - (base64.length % 4)) % 4);
  const raw = atob((base64 + padding).replace(/-/g, "+").replace(/_/g, "/"));
  const bytes = new Uint8Array(raw.length);
  for (let i = 0; i < raw.length; i++) bytes[i] = raw.charCodeAt(i);
  return bytes;
}

export function isPushSupported(): boolean {
  return (
    typeof window !== "undefined" &&
    "serviceWorker" in navigator &&
    "PushManager" in window &&
    "Notification" in window
  );
}