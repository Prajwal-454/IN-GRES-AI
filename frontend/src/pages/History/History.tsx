import { History as HistoryIcon, Loader2, MessageSquare, Users } from "lucide-react";
import { useEffect, useState } from "react";

import { Badge } from "@/components/ui/badge";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { cn } from "@/lib/utils";
import { useLanguage } from "@/contexts/LanguageContext";
import { listExpertRequests, type ExpertRequest } from "@/services/expert";
import { listConversations, listMessages, type Conversation } from "@/services/chat";

const TABS = [
  { key: "conversations", label: "Chat conversations", icon: MessageSquare },
  { key: "expert", label: "Expert requests", icon: Users },
] as const;

type TabKey = (typeof TABS)[number]["key"];

export default function History() {
  const { t } = useLanguage();
  const [tab, setTab] = useState<TabKey>("conversations");
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [openId, setOpenId] = useState<number | null>(null);
  const [messages, setMessages] = useState<Record<number, { role: string; content: string }[]>>({});
  const [requests, setRequests] = useState<ExpertRequest[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let active = true;
    Promise.all([
      listConversations(),
      listExpertRequests(),
    ])
      .then(([convs, reqRows]) => {
        if (!active) return;
        setConversations(convs);
        setRequests(reqRows);
      })
      .catch(() => undefined)
      .finally(() => active && setLoading(false));
    return () => {
      active = false;
    };
  }, []);

  async function openConversation(id: number) {
    setOpenId(id);
    if (messages[id]) return;
    try {
      const rows = await listMessages(id);
      setMessages((prev) => ({
        ...prev,
        [id]: rows.map((m) => ({ role: m.role, content: m.content })),
      }));
    } catch {
      /* ignore */
    }
  }

  function badge(status: string) {
    return <Badge variant="secondary">{status}</Badge>;
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center gap-2 py-16 text-sm text-muted-foreground">
        <Loader2 className="h-4 w-4 animate-spin" />
        {t("Loading history…")}
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-6xl space-y-6">
      <section>
        <h2 className="flex items-center gap-2 text-2xl font-bold">
          <HistoryIcon className="h-6 w-6 text-primary" />
          {t("History")}
        </h2>
        <p className="mt-1 text-muted-foreground">
          {t("Past conversations and expert requests.")}
        </p>
      </section>

      <div className="flex gap-2">
        {TABS.map((item) => (
          <button
            key={item.key}
            className={cn(
              "flex items-center gap-2 rounded-md border px-3 py-2 text-sm font-medium transition-colors",
              tab === item.key
                ? "border-primary bg-primary text-primary-foreground"
                : "hover:bg-accent"
            )}
            onClick={() => setTab(item.key)}
          >
            <item.icon className="h-4 w-4" />
            {t(item.label)}
          </button>
        ))}
      </div>

      {tab === "conversations" && (
        <div className="space-y-3">
          {conversations.length === 0 && (
            <Card>
              <CardContent className="py-10 text-center text-sm text-muted-foreground">
                {t("No chat conversations yet.")}
              </CardContent>
            </Card>
          )}
          {conversations.map((c) => (
            <Card key={c.id}>
              <CardHeader className="cursor-pointer py-3" onClick={() => openConversation(c.id)}>
                <div className="flex items-center justify-between">
                  <CardTitle className="text-sm">{c.title || t("new_chat")}</CardTitle>
                  <div className="flex items-center gap-2 text-xs text-muted-foreground">
                    {badge(c.language)}
                    <span>{new Date(c.created_at).toLocaleString()}</span>
                  </div>
                </div>
              </CardHeader>
              {openId === c.id && messages[c.id] && (
                <CardContent className="space-y-2 border-t">
                  {messages[c.id].map((m, i) => (
                    <div
                      key={i}
                      className={cn(
                        "rounded-md px-3 py-2 text-sm whitespace-pre-line",
                        m.role === "user"
                          ? "bg-primary/10"
                          : "bg-muted"
                      )}
                    >
                      <span className="mr-2 text-xs font-semibold uppercase text-muted-foreground">
                        {m.role}
                      </span>
                      {m.content}
                    </div>
                  ))}
                </CardContent>
              )}
            </Card>
          ))}
        </div>
      )}

      {tab === "expert" && (
        <div className="space-y-3">
          {requests.length === 0 && (
            <Card>
              <CardContent className="py-10 text-center text-sm text-muted-foreground">
                {t("No expert requests yet.")}
              </CardContent>
            </Card>
          )}
          {requests.map((r) => (
            <Card key={r.id}>
              <CardHeader className="py-3">
                <CardDescription className="flex items-center justify-between gap-2">
                  <span>
                    #{r.id} · {r.user_name ?? t("user {id}", { id: r.user_id })} · {r.status} ·{" "}
                    {r.priority ?? t("no priority")}
                  </span>
                  <span className="text-xs">{new Date(r.created_at).toLocaleString()}</span>
                </CardDescription>
                <CardTitle className="text-sm font-medium">{r.question}</CardTitle>
              </CardHeader>
              {(r.location || r.resolution) && (
                <CardContent className="space-y-1 border-t text-sm text-muted-foreground">
                  {r.location && <p>{t("Location: {location}", { location: r.location })}</p>}
                  {r.resolution && (
                    <p>{t("Resolution: {resolution}", { resolution: r.resolution })}</p>
                  )}
                </CardContent>
              )}
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}