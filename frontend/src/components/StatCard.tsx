import { Loader2, type LucideIcon } from "lucide-react";
import type { ReactNode } from "react";

import { cn } from "@/lib/utils";

export type Tone = "good" | "warn" | "bad" | "info" | "neutral";

const TONE_STYLES: Record<Tone, { ring: string; bg: string; text: string }> = {
  good: { ring: "", bg: "bg-emerald-100 dark:bg-emerald-950", text: "text-emerald-700 dark:text-emerald-300" },
  warn: { ring: "", bg: "bg-amber-100 dark:bg-amber-950", text: "text-amber-700 dark:text-amber-300" },
  bad: { ring: "", bg: "bg-red-100 dark:bg-red-950", text: "text-red-700 dark:text-red-300" },
  info: { ring: "", bg: "bg-sky-100 dark:bg-sky-950", text: "text-sky-700 dark:text-sky-300" },
  neutral: { ring: "", bg: "bg-slate-100 dark:bg-slate-800", text: "text-slate-600 dark:text-slate-300" },
};

export function ToneDot({ tone }: { tone: Tone }) {
  const cls =
    tone === "good"
      ? "bg-emerald-500"
      : tone === "warn"
        ? "bg-amber-500"
        : tone === "bad"
          ? "bg-red-500"
          : tone === "info"
            ? "bg-sky-500"
            : "bg-slate-400";
  return <span aria-hidden className={cn("inline-block h-2.5 w-2.5 shrink-0 rounded-full", cls)} />;
}

interface StatusChipProps {
  tone: Tone;
  children: ReactNode;
}

/** Coloured pill that always pairs colour with a dot + words (never colour alone). */
export function StatusChip({ tone, children }: StatusChipProps) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-2 rounded-full px-3 py-1 text-sm font-semibold",
        TONE_STYLES[tone].bg,
        TONE_STYLES[tone].text,
      )}
    >
      <ToneDot tone={tone} />
      {children}
    </span>
  );
}

interface StatCardProps {
  icon: LucideIcon;
  label: string;
  /** Preformatted big value, e.g. "42 mm" or "1,234". */
  value: ReactNode;
  sub?: ReactNode;
  /** Optional status pill rendered under the value. */
  status?: { tone: Tone; text: ReactNode };
  loading?: boolean;
  className?: string;
}

/**
 * Village-friendly information card: big icon, short title, very large
 * number, optional status pill and a one-line explanation.
 */
export default function StatCard({
  icon: Icon,
  label,
  value,
  sub,
  status,
  loading,
  className,
}: StatCardProps) {
  return (
    <div className={cn("rounded-xl border bg-card p-5", className)}>
      <div className="flex items-start gap-4">
        <div
          aria-hidden
          className={cn(
            "flex h-14 w-14 shrink-0 items-center justify-center rounded-full",
            TONE_STYLES[status?.tone ?? "info"].bg,
          )}
        >
          <Icon className={cn("h-7 w-7", TONE_STYLES[status?.tone ?? "info"].text)} />
        </div>
        <div className="min-w-0">
          <div className="text-sm font-medium text-muted-foreground">{label}</div>
          {loading ? (
            <div className="mt-1 flex items-center gap-2 text-muted-foreground">
              <Loader2 className="h-6 w-6 animate-spin" />
            </div>
          ) : (
            <div className="mt-0.5 truncate text-4xl font-bold leading-tight tracking-tight">
              {value}
            </div>
          )}
          {status && !loading && (
            <div className="mt-2">
              <StatusChip tone={status.tone}>{status.text}</StatusChip>
            </div>
          )}
        </div>
      </div>
      {sub && (
        <div className="mt-3 border-t pt-2 text-sm text-muted-foreground">{sub}</div>
      )}
    </div>
  );
}
