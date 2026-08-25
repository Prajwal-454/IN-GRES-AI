import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";

import {
  listNotifications,
  markAllNotificationsRead,
  markNotificationRead,
  type UserNotification,
} from "@/services/notifications";

interface ToastItem {
  id: number;
  kind: "success" | "error" | "info";
  message: string;
}

interface NotificationContextValue {
  notifications: UserNotification[];
  unread: number;
  toasts: ToastItem[];
  refresh: () => Promise<void>;
  markAllRead: () => Promise<void>;
  markRead: (id: number) => Promise<void>;
  toast: (message: string, kind?: ToastItem["kind"]) => void;
  dismissToast: (id: number) => void;
}

const NotificationContext = createContext<NotificationContextValue | null>(null);

let toastId = 0;

export function NotificationProvider({ children }: { children: ReactNode }) {
  const [notifications, setNotifications] = useState<UserNotification[]>([]);
  const [unread, setUnread] = useState(0);
  const [toasts, setToasts] = useState<ToastItem[]>([]);

  const refresh = useCallback(async () => {
    try {
      const data = await listNotifications(50);
      setNotifications(data.notifications);
      setUnread(data.unread);
    } catch {
      /* not authenticated or backend offline */
    }
  }, []);

  useEffect(() => {
    refresh();
    const interval = window.setInterval(refresh, 60000);
    return () => window.clearInterval(interval);
  }, [refresh]);

  const markAllRead = useCallback(async () => {
    await markAllNotificationsRead();
    setUnread(0);
    setNotifications((prev) => prev.map((n) => ({ ...n, read: true })));
  }, []);

  const markRead = useCallback(async (id: number) => {
    await markNotificationRead(id);
    setNotifications((prev) =>
      prev.map((n) => (n.id === id ? { ...n, read: true } : n))
    );
    setUnread((prev) => Math.max(0, prev - 1));
  }, []);

  const dismissToast = useCallback((id: number) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
  }, []);

  const toast = useCallback(
    (message: string, kind: ToastItem["kind"] = "info") => {
      const id = ++toastId;
      setToasts((prev) => [...prev, { id, kind, message }]);
      window.setTimeout(() => dismissToast(id), 4000);
    },
    [dismissToast]
  );

  const value = useMemo(
    () => ({
      notifications,
      unread,
      toasts,
      refresh,
      markAllRead,
      markRead,
      toast,
      dismissToast,
    }),
    [notifications, unread, toasts, refresh, markAllRead, markRead, toast, dismissToast]
  );

  return (
    <NotificationContext.Provider value={value}>
      {children}
    </NotificationContext.Provider>
  );
}

export function useNotifications(): NotificationContextValue {
  const ctx = useContext(NotificationContext);
  if (!ctx) throw new Error("useNotifications must be used within NotificationProvider");
  return ctx;
}
