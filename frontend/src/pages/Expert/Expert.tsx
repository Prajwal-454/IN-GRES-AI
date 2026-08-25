import { Loader2, Send, Users } from "lucide-react";
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
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { useAuth } from "@/contexts/AuthContext";
import { useLanguage } from "@/contexts/LanguageContext";
import { cn } from "@/lib/utils";
import {
  createExpertRequest,
  listExpertRequests,
  updateExpertRequest,
  type ExpertRequest,
} from "@/services/expert";

const STATUS_VARIANTS: Record<string, "secondary" | "warning" | "success" | "destructive"> = {
  NEW: "warning",
  IN_PROGRESS: "secondary",
  RESOLVED: "success",
  CLOSED: "secondary",
};

const STATUS_OPTIONS = ["NEW", "IN_PROGRESS", "RESOLVED", "CLOSED"];
const PRIORITY_OPTIONS = ["LOW", "MEDIUM", "HIGH", "URGENT"];

export default function Expert() {
  const { user } = useAuth();
  const { t } = useLanguage();
  const canManage = user?.role === "expert" || user?.role === "admin";

  const [requests, setRequests] = useState<ExpertRequest[]>([]);
  const [statusFilter, setStatusFilter] = useState("");
  const [question, setQuestion] = useState("");
  const [location, setLocation] = useState("");
  const [creating, setCreating] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      setRequests(await listExpertRequests(statusFilter || undefined));
    } catch {
      setError(t("Failed to load expert requests."));
    } finally {
      setLoading(false);
    }
  }, [statusFilter]);

  useEffect(() => {
    load();
  }, [load]);

  async function handleCreate() {
    if (!question.trim()) return;
    setCreating(true);
    try {
      await createExpertRequest({
        question: question.trim(),
        location: location.trim() || null,
      });
      setQuestion("");
      setLocation("");
      await load();
    } catch {
      setError(t("Failed to create the request."));
    } finally {
      setCreating(false);
    }
  }

  async function handleUpdate(id: number, patch: { status?: string; priority?: string; resolution?: string }) {
    try {
      await updateExpertRequest(id, patch);
      await load();
    } catch {
      setError(t("Update failed — requires expert or admin role."));
    }
  }

  return (
    <div className="mx-auto max-w-6xl space-y-6">
      <section>
        <h2 className="flex items-center gap-2 text-2xl font-bold">
          <Users className="h-6 w-6 text-primary" />
          {t("Expert Desk")}
        </h2>
        <p className="mt-1 text-muted-foreground">
          {t("Escalate complex groundwater questions to domain experts.")}
        </p>
      </section>

      <Card>
        <CardHeader>
          <CardTitle className="text-sm">{t("Escalate a question")}</CardTitle>
          <CardDescription>
            {t("Create a request when the assistant cannot answer conclusively.")}
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          <Input
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            placeholder={t(
              "e.g. Why is stage of extraction rising in Yadadri despite monsoon recharge?"
            )}
          />
          <div className="flex flex-wrap items-center gap-3">
            <Input
              value={location}
              onChange={(e) => setLocation(e.target.value)}
              placeholder={t("Location (e.g. Yadadri Bhuvanagiri, Telangana)")}
              className="max-w-sm"
            />
            <Button onClick={handleCreate} disabled={creating || !question.trim()}>
              {creating ? <Loader2 className="h-4 w-4 animate-spin" /> : <Send className="h-4 w-4" />}
              {t("Create request")}
            </Button>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader className="flex-row items-center justify-between space-y-0">
          <div>
            <CardTitle className="text-sm">{t("Requests")}</CardTitle>
            <CardDescription>
              {canManage
                ? t("Manage status, priority and resolutions.")
                : t("Track your escalations.")}
            </CardDescription>
          </div>
          <Select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            className="w-40"
          >
            <option value="">{t("All statuses")}</option>
            {STATUS_OPTIONS.map((s) => (
              <option key={s} value={s}>
                {s}
              </option>
            ))}
          </Select>
        </CardHeader>
        <CardContent>
          {error && (
            <div className="mb-4 rounded-md border border-destructive/30 bg-destructive/10 p-3 text-sm text-destructive">
              {error}
            </div>
          )}
          {loading ? (
            <div className="flex items-center justify-center gap-2 py-10 text-sm text-muted-foreground">
              <Loader2 className="h-4 w-4 animate-spin" />
              {t("loading")}
            </div>
          ) : requests.length === 0 ? (
            <div className="py-10 text-center text-sm text-muted-foreground">
              {t("No requests {withStatus}.", {
                withStatus: statusFilter
                  ? t("with status {status}", { status: statusFilter })
                  : t("yet"),
              })}
            </div>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>{t("ID")}</TableHead>
                  <TableHead>{t("Question")}</TableHead>
                  <TableHead>{t("From")}</TableHead>
                  <TableHead>{t("Location")}</TableHead>
                  <TableHead>{t("Priority")}</TableHead>
                  <TableHead>{t("Status")}</TableHead>
                  <TableHead className="text-right">{t("Actions")}</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {requests.map((r) => (
                  <TableRow key={r.id}>
                    <TableCell className="align-top font-medium">#{r.id}</TableCell>
                    <TableCell className="max-w-md align-top">
                      <div className="whitespace-pre-line">{r.question}</div>
                      {r.resolution && (
                        <div className="mt-1 text-xs text-muted-foreground">
                          {t("Resolution: {resolution}", { resolution: r.resolution })}
                        </div>
                      )}
                      {r.resolved_at && (
                        <div className="mt-0.5 text-xs text-muted-foreground">
                          {t("Resolved {date}", {
                            date: new Date(r.resolved_at).toLocaleString(),
                          })}
                        </div>
                      )}
                    </TableCell>
                    <TableCell className="align-top">
                      {r.user_name ?? t("user #{id}", { id: r.user_id })}
                    </TableCell>
                    <TableCell className="align-top">{r.location ?? "—"}</TableCell>
                    <TableCell className="align-top">
                      {canManage ? (
                        <Select
                          value={r.priority ?? ""}
                          onChange={(e) =>
                            handleUpdate(r.id, { priority: e.target.value || undefined })
                          }
                          className="h-8 w-28"
                        >
                          <option value="">—</option>
                          {PRIORITY_OPTIONS.map((p) => (
                            <option key={p} value={p}>
                              {p}
                            </option>
                          ))}
                        </Select>
                      ) : (
                        <span className={cn("text-sm", r.priority === "URGENT" && "font-semibold text-destructive")}>
                          {r.priority ?? "—"}
                        </span>
                      )}
                    </TableCell>
                    <TableCell className="align-top">
                      {canManage ? (
                        <Select
                          value={r.status}
                          onChange={(e) => handleUpdate(r.id, { status: e.target.value })}
                          className="h-8 w-36"
                        >
                          {STATUS_OPTIONS.map((s) => (
                            <option key={s} value={s}>
                              {s}
                            </option>
                          ))}
                        </Select>
                      ) : (
                        <Badge variant={STATUS_VARIANTS[r.status] ?? "secondary"}>{r.status}</Badge>
                      )}
                    </TableCell>
                    <TableCell className="align-top text-right">
                      {canManage && r.status !== "RESOLVED" && r.status !== "CLOSED" && (
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() =>
                            handleUpdate(r.id, {
                              status: "RESOLVED",
                              resolution: t("Addressed by expert desk."),
                            })
                          }
                        >
                          {t("Resolve")}
                        </Button>
                      )}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>
    </div>
  );
}