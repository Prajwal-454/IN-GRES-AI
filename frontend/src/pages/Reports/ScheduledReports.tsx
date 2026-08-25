import { CalendarClock, Download, Loader2, Play, Plus, Trash2 } from "lucide-react";
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
import { useLanguage } from "@/contexts/LanguageContext";
import { useNotifications } from "@/contexts/NotificationContext";
import { getApiError } from "@/services/api";
import { fetchDistricts, fetchStates, fetchVillages } from "@/services/groundwater";
import {
  createSchedule,
  deleteSchedule,
  downloadLatestDigest,
  listSchedules,
  runScheduleNow,
  updateSchedule,
  type ReportSchedule,
  type ScheduleFrequency,
} from "@/services/reports";
import type { GroundwaterDistrict, GroundwaterState, GroundwaterVillage } from "@/types";

function fmtDate(value: string | null): string {
  if (!value) return "—";
  return new Date(value).toLocaleString();
}

export default function ScheduledReports() {
  const { t } = useLanguage();
  const { toast } = useNotifications();

  const [schedules, setSchedules] = useState<ReportSchedule[] | null>(null);
  const [busyId, setBusyId] = useState<number | null>(null);

  const [states, setStates] = useState<GroundwaterState[]>([]);
  const [districts, setDistricts] = useState<GroundwaterDistrict[]>([]);
  const [villages, setVillages] = useState<GroundwaterVillage[]>([]);

  const [name, setName] = useState("");
  const [stateSel, setStateSel] = useState("");
  const [districtSel, setDistrictSel] = useState("");
  const [villageSel, setVillageSel] = useState("");
  const [frequency, setFrequency] = useState<ScheduleFrequency>("weekly");
  const [recipients, setRecipients] = useState("");
  const [creating, setCreating] = useState(false);

  const load = useCallback(async () => {
    try {
      setSchedules(await listSchedules());
    } catch {
      setSchedules([]);
    }
  }, []);

  useEffect(() => {
    void load();
    fetchStates()
      .then(setStates)
      .catch(() => undefined);
  }, [load]);

  useEffect(() => {
    if (!stateSel) {
      setDistricts([]);
      return;
    }
    let active = true;
    fetchDistricts(stateSel)
      .then((rows) => active && setDistricts(rows))
      .catch(() => active && setDistricts([]));
    return () => {
      active = false;
    };
  }, [stateSel]);

  useEffect(() => {
    if (!stateSel || !districtSel) {
      setVillages([]);
      return;
    }
    let active = true;
    fetchVillages(stateSel, districtSel)
      .then((rows) => active && setVillages(rows))
      .catch(() => active && setVillages([]));
    return () => {
      active = false;
    };
  }, [stateSel, districtSel]);

  async function handleCreate() {
    if (!name.trim()) {
      toast(t("Give this schedule a name."), "error");
      return;
    }
    setCreating(true);
    try {
      await createSchedule({
        name: name.trim(),
        state: stateSel || null,
        district: districtSel || null,
        village: villageSel || null,
        frequency,
        recipients: recipients
          .split(",")
          .map((r) => r.trim())
          .filter(Boolean),
      });
      setName("");
      setRecipients("");
      toast(t("Schedule created. The first issue is generated right away."), "success");
      await load();
    } catch (err) {
      toast(getApiError(err), "error");
    } finally {
      setCreating(false);
    }
  }

  async function withBusy(id: number, action: () => Promise<void>) {
    setBusyId(id);
    try {
      await action();
      await load();
    } catch (err) {
      toast(getApiError(err), "error");
    } finally {
      setBusyId(null);
    }
  }

  function statusVariant(status: string | null) {
    switch (status) {
      case "sent":
      case "generated":
        return "success" as const;
      case "failed":
        return "destructive" as const;
      default:
        return "secondary" as const;
    }
  }

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-sm">
            <Plus className="h-4 w-4" />
            {t("New scheduled report")}
          </CardTitle>
          <CardDescription>
            {t(
              "Receive a PDF digest of any region weekly or monthly. Emails are sent when SMTP is configured; generated files can always be downloaded here."
            )}
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            <div className="space-y-1.5">
              <label className="text-sm font-medium">{t("Name")}</label>
              <Input value={name} onChange={(e) => setName(e.target.value)} placeholder={t("Weekly Telangana digest") ?? ""} />
            </div>
            <div className="space-y-1.5">
              <label className="text-sm font-medium">{t("state")}</label>
              <Select
                value={stateSel}
                onChange={(e) => {
                  setStateSel(e.target.value);
                  setDistrictSel("");
                  setVillageSel("");
                }}
              >
                <option value="">{t("all_states")}</option>
                {states.map((s) => (
                  <option key={s.id} value={s.name}>
                    {s.name}
                  </option>
                ))}
              </Select>
            </div>
            <div className="space-y-1.5">
              <label className="text-sm font-medium">{t("district")}</label>
              <Select
                value={districtSel}
                onChange={(e) => {
                  setDistrictSel(e.target.value);
                  setVillageSel("");
                }}
                disabled={!stateSel}
              >
                <option value="">{t("all_districts")}</option>
                {districts.map((d) => (
                  <option key={d.id} value={d.name}>
                    {d.name}
                  </option>
                ))}
              </Select>
            </div>
            <div className="space-y-1.5">
              <label className="text-sm font-medium">{t("Village")}</label>
              <Select
                value={villageSel}
                onChange={(e) => setVillageSel(e.target.value)}
                disabled={!districtSel}
              >
                <option value="">{t("All villages")}</option>
                {villages.map((v) => (
                  <option key={v.id} value={v.name}>
                    {v.name}
                  </option>
                ))}
              </Select>
            </div>
            <div className="space-y-1.5">
              <label className="text-sm font-medium">{t("Frequency")}</label>
              <Select value={frequency} onChange={(e) => setFrequency(e.target.value as ScheduleFrequency)}>
                <option value="weekly">{t("Weekly")}</option>
                <option value="monthly">{t("Monthly")}</option>
              </Select>
            </div>
            <div className="space-y-1.5 lg:col-span-2">
              <label className="text-sm font-medium">{t("Recipients (comma-separated emails)")}</label>
              <Input
                value={recipients}
                onChange={(e) => setRecipients(e.target.value)}
                placeholder="officer@example.com, collector@example.gov.in"
              />
            </div>
            <div className="flex items-end">
              <Button onClick={() => void handleCreate()} disabled={creating} className="w-full sm:w-auto">
                {creating ? <Loader2 className="h-4 w-4 animate-spin" /> : <CalendarClock className="h-4 w-4" />}
                {t("Schedule")}
              </Button>
            </div>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-sm">{t("Your schedules")}</CardTitle>
        </CardHeader>
        <CardContent className="overflow-x-auto">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>{t("Name")}</TableHead>
                <TableHead>{t("Scope")}</TableHead>
                <TableHead>{t("Frequency")}</TableHead>
                <TableHead>{t("Next run")}</TableHead>
                <TableHead>{t("Last run")}</TableHead>
                <TableHead>{t("Actions")}</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {(schedules ?? []).map((s) => (
                <TableRow key={s.id}>
                  <TableCell className="font-medium">
                    {s.name}
                    {!s.enabled && (
                      <Badge variant="secondary" className="ml-2 text-[10px]">
                        {t("paused")}
                      </Badge>
                    )}
                    {s.recipients.length > 0 && (
                      <div className="mt-0.5 max-w-[200px] truncate text-[11px] text-muted-foreground" title={s.recipients.join(", ")}>
                        ✉ {s.recipients.join(", ")}
                      </div>
                    )}
                  </TableCell>
                  <TableCell>{s.scope_label}</TableCell>
                  <TableCell>
                    <Badge variant="outline">{t(s.frequency === "monthly" ? "Monthly" : "Weekly")}</Badge>
                  </TableCell>
                  <TableCell className="whitespace-nowrap text-xs text-muted-foreground">
                    {fmtDate(s.next_run_at)}
                  </TableCell>
                  <TableCell>
                    {s.last_status ? (
                      <Badge variant={statusVariant(s.last_status)}>{s.last_status}</Badge>
                    ) : (
                      <span className="text-muted-foreground">—</span>
                    )}
                    <div className="mt-0.5 whitespace-nowrap text-[11px] text-muted-foreground">
                      {fmtDate(s.last_run_at)}
                    </div>
                  </TableCell>
                  <TableCell>
                    <div className="flex flex-wrap items-center gap-1">
                      <Button
                        size="sm"
                        variant="outline"
                        disabled={busyId === s.id}
                        onClick={() =>
                          void withBusy(s.id, async () => {
                            const res = await runScheduleNow(s.id);
                            toast(
                              res.status === "failed"
                                ? t("Digest generation failed: {error}", { error: res.error ?? "" })
                                : t("Digest generated ({status}).", { status: res.status }),
                              res.status === "failed" ? "error" : "success"
                            );
                          })
                        }
                      >
                        {busyId === s.id ? (
                          <Loader2 className="h-3.5 w-3.5 animate-spin" />
                        ) : (
                          <Play className="h-3.5 w-3.5" />
                        )}
                        {t("Run now")}
                      </Button>
                      {s.has_file && (
                        <Button
                          size="sm"
                          variant="ghost"
                          onClick={() =>
                            void downloadLatestDigest(s.id, `ingres-digest-${s.id}.pdf`)
                          }
                        >
                          <Download className="h-3.5 w-3.5" />
                          {t("download_pdf")}
                        </Button>
                      )}
                      <Button
                        size="sm"
                        variant="ghost"
                        disabled={busyId === s.id}
                        onClick={() =>
                          void withBusy(s.id, async () => {
                            await updateSchedule(s.id, { enabled: !s.enabled });
                            toast(s.enabled ? t("Schedule paused.") : t("Schedule resumed."), "info");
                          })
                        }
                      >
                        {s.enabled ? t("Pause") : t("Resume")}
                      </Button>
                      <Button
                        size="sm"
                        variant="ghost"
                        disabled={busyId === s.id}
                        onClick={() =>
                          void withBusy(s.id, async () => {
                            await deleteSchedule(s.id);
                            toast(t("Schedule deleted."), "info");
                          })
                        }
                      >
                        <Trash2 className="h-3.5 w-3.5" />
                      </Button>
                    </div>
                  </TableCell>
                </TableRow>
              ))}
              {schedules?.length === 0 && (
                <TableRow>
                  <TableCell colSpan={6} className="h-16 text-center text-muted-foreground">
                    {t("No scheduled reports yet — create one above.")}
                  </TableCell>
                </TableRow>
              )}
            </TableBody>
          </Table>
        </CardContent>
      </Card>
    </div>
  );
}
