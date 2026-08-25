import { BellRing, Loader2, Smartphone } from "lucide-react";
import { useCallback, useEffect, useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { useLanguage } from "@/contexts/LanguageContext";
import { useNotifications } from "@/contexts/NotificationContext";
import {
  getPushConfig,
  isPushSupported,
  subscribeToPush,
  unsubscribeFromPush,
  urlBase64ToUint8Array,
} from "@/services/push";

type PushState = "loading" | "unsupported" | "disabled" | "enabled" | "error";

export default function PushNotificationsCard() {
  const { t } = useLanguage();
  const { toast } = useNotifications();
  const [state, setState] = useState<PushState>("loading");
  const [working, setWorking] = useState(false);

  const refresh = useCallback(async () => {
    if (!isPushSupported()) {
      setState("unsupported");
      return;
    }
    try {
      const config = await getPushConfig();
      if (!config.enabled) {
        setState("unsupported");
        return;
      }
      const reg = await navigator.serviceWorker.ready;
      const existing = await reg.pushManager.getSubscription();
      setState(existing ? "enabled" : "disabled");
    } catch {
      setState("unsupported");
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  async function enable() {
    setWorking(true);
    try {
      const config = await getPushConfig();
      if (!config.enabled || !config.public_key) {
        toast(t("Web push is not enabled on the server."), "error");
        setState("unsupported");
        return;
      }
      const permission = await Notification.requestPermission();
      if (permission !== "granted") {
        toast(t("Notification permission was denied."), "error");
        return;
      }
      const reg = await navigator.serviceWorker.ready;
      const subscription = await reg.pushManager.subscribe({
        userVisibleOnly: true,
        applicationServerKey: await urlBase64ToUint8Array(config.public_key),
      });
      await subscribeToPush(subscription);
      setState("enabled");
      toast(t("Push notifications enabled for this device."), "success");
    } catch {
      toast(t("Could not enable push notifications."), "error");
      setState("error");
    } finally {
      setWorking(false);
    }
  }

  async function disable() {
    setWorking(true);
    try {
      const reg = await navigator.serviceWorker.ready;
      const subscription = await reg.pushManager.getSubscription();
      if (subscription) {
        const endpoint = subscription.endpoint;
        await subscription.unsubscribe();
        try {
          await unsubscribeFromPush(endpoint);
        } catch {
          /* already removed server-side */
        }
      }
      setState("disabled");
      toast(t("Push notifications disabled."), "info");
    } catch {
      toast(t("Could not disable push notifications."), "error");
    } finally {
      setWorking(false);
    }
  }

  const enabled = state === "enabled";

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-sm">
          <Smartphone className="h-4 w-4" />
          {t("Push notifications")}
        </CardTitle>
        <CardDescription>
          {t(
            "Get groundwater alerts on this device even when the app is closed (installable PWA)."
          )}
        </CardDescription>
      </CardHeader>
      <CardContent className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-2">
          {state === "loading" && <Loader2 className="h-4 w-4 animate-spin" />}
          {state === "enabled" && <Badge variant="success">{t("Enabled")}</Badge>}
          {state === "disabled" && <Badge variant="secondary">{t("Available")}</Badge>}
          {state === "unsupported" && (
            <Badge variant="secondary">
              {t("Not available")} — {t("requires HTTPS and a supported browser")}
            </Badge>
          )}
          <span className="text-sm text-muted-foreground">
            {enabled
              ? t("This device is registered to receive alerts.")
              : t("Allow alerts to be delivered to this device.")}
          </span>
        </div>
        {state === "enabled" ? (
          <Button variant="outline" size="sm" disabled={working} onClick={() => void disable()}>
            {working && <Loader2 className="h-4 w-4 animate-spin" />}
            {t("Disable")}
          </Button>
        ) : state === "disabled" ? (
          <Button size="sm" disabled={working} onClick={() => void enable()}>
            {working && <Loader2 className="h-4 w-4 animate-spin" />}
            <BellRing className="h-4 w-4" />
            {t("Enable")}
          </Button>
        ) : null}
      </CardContent>
    </Card>
  );
}