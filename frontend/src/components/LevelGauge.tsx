import { cn } from "@/lib/utils";
import { useLanguage } from "@/contexts/LanguageContext";

export interface StageStatus {
  tone: "good" | "warn" | "bad";
  key: string;
}

/**
 * Meaning of a stage-of-extraction percentage, using the official CGWB
 * categories already encoded in the backend (safe <70, semi-critical <90,
 * critical <=100, over-exploited >100). Returns a tone plus a translation
 * KEY so callers render it through t().
 */
export function stageStatus(stage: number | null | undefined): StageStatus {
  if (stage == null) return { tone: "good", key: "level_unknown" };
  if (stage < 70) return { tone: "good", key: "level_safe" };
  if (stage < 90) return { tone: "warn", key: "level_attention" };
  return { tone: "bad", key: "level_critical" };
}

interface LevelGaugeProps {
  /** Percentage (0–100+). Values above 100 clamp the bar but keep the number. */
  value: number | null | undefined;
  className?: string;
  /** Hide the big number + status row when embedded elsewhere. */
  compact?: boolean;
}

/**
 * Simple water-level style bar: green up to 70%, amber to 90%, red beyond.
 * Colour is always paired with position and words so meaning survives
 * colour-blindness and grayscale screens.
 */
export default function LevelGauge({ value, className, compact }: LevelGaugeProps) {
  const { t } = useLanguage();
  const pct = value == null ? null : Math.max(0, Math.round(value));
  const fillPct = pct == null ? 0 : Math.min(pct, 100);
  const status = stageStatus(value);

  const fillCls =
    status.tone === "good"
      ? "bg-emerald-500"
      : status.tone === "warn"
        ? "bg-amber-500"
        : "bg-red-500";

  return (
    <div className={cn("w-full", className)}>
      {!compact && (
        <div className="mb-2 flex items-end justify-between gap-3">
          <span className="text-4xl font-bold leading-none tracking-tight">
            {pct == null ? "—" : `${pct}%`}
          </span>
          <span
            className={cn(
              "inline-flex items-center gap-2 rounded-full px-3 py-1 text-sm font-semibold",
              status.tone === "good" && "bg-emerald-100 text-emerald-700 dark:bg-emerald-950 dark:text-emerald-300",
              status.tone === "warn" && "bg-amber-100 text-amber-700 dark:bg-amber-950 dark:text-amber-300",
              status.tone === "bad" && "bg-red-100 text-red-700 dark:bg-red-950 dark:text-red-300",
            )}
          >
            <span aria-hidden className="inline-block h-2.5 w-2.5 rounded-full bg-current" />
            {t(status.key)}
          </span>
        </div>
      )}
      <div
        role="meter"
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={pct ?? undefined}
        aria-label={t("Water usage level")}
        className="relative h-4 w-full overflow-hidden rounded-full bg-muted"
      >
        {/* Zone boundaries at the official 70 / 90 / 100 thresholds. */}
        <span aria-hidden className="absolute inset-y-0 left-[70%] w-px bg-background/80" />
        <span aria-hidden className="absolute inset-y-0 left-[90%] w-px bg-background/80" />
        <div
          className={cn("h-full rounded-full transition-all", fillCls)}
          style={{ width: `${fillPct}%` }}
        />
      </div>
      <div className="mt-1 flex justify-between text-[11px] font-medium text-muted-foreground">
        <span>{t("level_safe_short")}</span>
        <span className="hidden sm:inline">{t("level_attention_short")}</span>
        <span>{t("level_critical_short")}</span>
      </div>
    </div>
  );
}
