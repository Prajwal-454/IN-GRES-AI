import { Bell, BellRing, Plus, RefreshCw, Trash2 } from "lucide-react";
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
import PushNotificationsCard from "@/components/PushNotificationsCard";
import { Select } from "@/components/ui/select";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { useNotifications } from "@/contexts/NotificationContext";
import { useLanguage } from "@/contexts/LanguageContext";
import {
  createAlertRule,
  deleteAlertRule,
  listAlertRules,
  runAlertCheck,
  updateAlertRule,
  type AlertRule,
} from "@/services/notifications";
import {
  fetchDistricts,
  fetchStates,
  fetchVillages,
} from "@/services/groundwater";
import type { GroundwaterDistrict, GroundwaterState, GroundwaterVillage } from "@/types";

const METRICS = [
  { value: "stage", label: "Stage of extraction" },
  { value: "recharge", label: "Recharge" },
  { value: "extraction", label: "Extraction" },
  { value: "resource", label: "Extractable resource" },
];

const OPERATORS = [
  { value: "gt", label: "> (greater than)" },
  { value: "gte", label: "≥ (greater or equal)" },
  { value: "lt", label: "< (less than)" },
  { value: "lte", label: "≤ (less or equal)" },
];

export default function Notifications() {
  const { notifications, unread, refresh, markAllRead, markRead, toast } = useNotifications();
  const { t } = useLanguage();
  const [rules, setRules] = useState<AlertRule[]>([]);
  const [checking, setChecking] = useState(false);

  const [name, setName] = useState("");
  const [metric, setMetric] = useState("stage");
  const [operator, setOperator] = useState("gt");
  const [threshold, setThreshold] = useState("100");
  const [state, setState] = useState("");
  const [district, setDistrict] = useState("");
  const [village, setVillage] = useState("");
  const [states, setStates] = useState<GroundwaterState[]>([]);
  const [districts, setDistricts] = useState<GroundwaterDistrict[]>([]);
  const [villages, setVillages] = useState<GroundwaterVillage[]>([]);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    fetchStates()
      .then(setStates)
      .catch(() => undefined);
  }, []);

  useEffect(() => {
    if (!state) {
      setDistricts([]);
      setVillages([]);
      return;
    }
    let active = true;
    fetchDistricts(state)
      .then((rows) => active && setDistricts(rows))
      .catch(() => active && setDistricts([]));
    return () => {
      active = false;
    };
  }, [state]);

  useEffect(() => {
    if (!state || !district) {
      setVillages([]);
      return;
    }
    let active = true;
    fetchVillages(state, district)
      .then((rows) => active && setVillages(rows))
      .catch(() => active && setVillages([]));
    return () => {
      active = false;
    };
  }, [state, district]);

  const loadRules = useCallback(async () => {
    try {
      setRules(await listAlertRules());
    } catch {
      /* ignore */
    }
  }, []);

  useEffect(() => {
    loadRules();
  }, [loadRules]);

  async function handleCreate() {
    const value = Number(threshold);
    if (!name.trim() || Number.isNaN(value)) return;
    setSaving(true);
    try {
      await createAlertRule({
        name: name.trim(),
        metric: metric as AlertRule["metric"],
        operator: operator as AlertRule["operator"],
        threshold: value,
        state: state || null,
        district: district || null,
        village: village || null,
        channels: ["in_app"],
        cooldown_minutes: 0,
        enabled: true,
      });
      setName("");
      setState("");
      setDistrict("");
      setVillage("");
      await loadRules();
      toast(t("Alert rule created."), "success");
    } catch {
      toast(t("Could not create alert rule."), "error");
    } finally {
      setSaving(false);
    }
  }

  async function handleToggle(rule: AlertRule) {
    try {
      await updateAlertRule(rule.id, { enabled: !rule.enabled });
      await loadRules();
    } catch {
      toast(t("Could not update rule."), "error");
    }
  }

  async function handleDelete(id: number) {
    try {
      await deleteAlertRule(id);
      await loadRules();
    } catch {
      toast(t("Could not delete rule."), "error");
    }
  }

  async function handleCheck() {
    setChecking(true);
    try {
      const res = await runAlertCheck();
      await refresh();
      toast(t("{count} alert{s} triggered.", { count: res.created }), "info");
    } catch {
      toast(t("Could not run alert check."), "error");
    } finally {
      setChecking(false);
    }
  }

  return (
    <div className="mx-auto max-w-6xl space-y-6">
      <section className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="flex items-center gap-2 text-2xl font-bold">
            <BellRing className="h-6 w-6 text-primary" />
            {t("Notifications")}
          </h2>
          <p className="mt-1 text-muted-foreground">
            {t("Alerts when groundwater metrics cross thresholds, plus your alert rules.")}
          </p>
        </div>
        <Button variant="outline" onClick={handleCheck} disabled={checking}>
          <RefreshCw className={`h-4 w-4 ${checking ? "animate-spin" : ""}`} />
          {t("Run alert check")}
        </Button>
      </section>

      <PushNotificationsCard />

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-sm">
            <Bell className="h-4 w-4" />
            {t("Recent notifications ({unread} unread)", { unread })}
          </CardTitle>
          {unread > 0 && (
            <CardDescription>
              <button
                className="text-xs text-primary hover:underline"
                onClick={markAllRead}
              >
                {t("Mark all read")}
              </button>
            </CardDescription>
          )}
        </CardHeader>
        <CardContent className="space-y-2">
          {notifications.length === 0 && (
            <p className="py-6 text-center text-sm text-muted-foreground">
              {t(
                "No notifications yet. Create an alert rule below to be notified when a metric crosses a threshold."
              )}
            </p>
          )}
          {notifications.map((n) => (
            <button
              key={n.id}
              onClick={() => !n.read && markRead(n.id)}
              className={`block w-full rounded-md border px-4 py-3 text-left transition-colors ${
                n.read ? "border-border" : "border-primary/40 bg-accent/30"
              }`}
            >
              <div className="flex items-center justify-between gap-2">
                <span className="text-sm font-medium">{n.title}</span>
                <span className="text-xs text-muted-foreground">
                  {new Date(n.created_at).toLocaleString()}
                </span>
              </div>
              {n.body && <p className="mt-1 text-sm text-muted-foreground">{n.body}</p>}
            </button>
          ))}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="text-sm">{t("Create alert rule")}</CardTitle>
          <CardDescription>
            {t(
              "Evaluated against assessment data; a notification is created whenever a unit matches."
            )}
          </CardDescription>
        </CardHeader>
        <CardContent className="grid gap-4 sm:grid-cols-2 lg:grid-cols-6">
          <Input
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder={t("Rule name")}
            className="lg:col-span-2"
          />
          <Select value={metric} onChange={(e) => setMetric(e.target.value)}>
            {METRICS.map((m) => (
              <option key={m.value} value={m.value}>
                {t(m.label)}
              </option>
            ))}
          </Select>
          <Select value={operator} onChange={(e) => setOperator(e.target.value)}>
            {OPERATORS.map((o) => (
              <option key={o.value} value={o.value}>
                {t(o.label)}
              </option>
            ))}
          </Select>
          <Input
            value={threshold}
            onChange={(e) => setThreshold(e.target.value)}
            placeholder={t("Threshold")}
            type="number"
            inputMode="decimal"
          />
          <Button onClick={handleCreate} disabled={saving || !name.trim() || !threshold}>
            <Plus className="h-4 w-4" />
            {t("Add rule")}
          </Button>
          <div className="space-y-1.5 lg:col-span-2">
            <label className="text-sm font-medium">{t("State (optional)")}</label>
            <Select
              value={state}
              onChange={(e) => {
                setState(e.target.value);
                setDistrict("");
                setVillage("");
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
          <div className="space-y-1.5 lg:col-span-2">
            <label className="text-sm font-medium">{t("District (optional)")}</label>
            <Select
              value={district}
              onChange={(e) => {
                setDistrict(e.target.value);
                setVillage("");
              }}
              disabled={!state}
            >
              <option value="">{t("all_districts")}</option>
              {districts.map((d) => (
                <option key={d.id} value={d.name}>
                  {d.name}
                </option>
              ))}
            </Select>
          </div>
          <div className="space-y-1.5 lg:col-span-2">
            <label className="text-sm font-medium">{t("Village (optional)")}</label>
            <Select
              value={village}
              onChange={(e) => setVillage(e.target.value)}
              disabled={!district}
            >
              <option value="">{t("All villages")}</option>
              {villages.map((v) => (
                <option key={v.id} value={v.name}>
                  {v.name}
                </option>
              ))}
            </Select>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="text-sm">
          {t("Your alert rules ({count})", { count: rules.length })}
        </CardTitle>
        </CardHeader>
        <CardContent>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>{t("Name")}</TableHead>
                <TableHead>{t("Condition")}</TableHead>
                <TableHead>{t("Scope")}</TableHead>
                <TableHead>{t("Status")}</TableHead>
                <TableHead>{t("Last triggered")}</TableHead>
                <TableHead className="text-right">{t("Actions")}</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {rules.map((rule) => (
                <TableRow key={rule.id}>
                  <TableCell className="font-medium">{rule.name}</TableCell>
                  <TableCell>
                    {rule.metric} {rule.operator} {rule.threshold}
                  </TableCell>
                  <TableCell className="text-muted-foreground">
                    {rule.village
                      ? `${rule.village}, ${rule.district}, ${rule.state}`
                      : rule.district
                        ? `${rule.district}, ${rule.state}`
                        : rule.state ?? t("all_states")}
                  </TableCell>
                  <TableCell>
                    <Badge variant={rule.enabled ? "success" : "secondary"}>
                      {rule.enabled ? t("Enabled") : t("Disabled")}
                    </Badge>
                  </TableCell>
                  <TableCell className="text-muted-foreground">
                    {rule.last_triggered_at
                      ? new Date(rule.last_triggered_at).toLocaleString()
                      : t("never")}
                  </TableCell>
                  <TableCell className="text-right">
                    <div className="flex justify-end gap-2">
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => handleToggle(rule)}
                      >
                        {rule.enabled ? t("Disable") : t("Enable")}
                      </Button>
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => handleDelete(rule.id)}
                        className="text-destructive"
                      >
                        <Trash2 className="h-4 w-4" />
                      </Button>
                    </div>
                  </TableCell>
                </TableRow>
              ))}
              {rules.length === 0 && (
                <TableRow>
                  <TableCell
                    colSpan={6}
                    className="h-20 text-center text-muted-foreground"
                  >
                    {t("No alert rules yet. Create one above.")}
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