import { ArrowDownRight, ArrowUpRight, Minus, type LucideIcon } from "lucide-react";

import { cn } from "@/lib/utils";

export type TrendDirection = "rising" | "falling" | "stable";

const ICONS: Record<TrendDirection, LucideIcon> = {
  rising: ArrowUpRight,
  falling: ArrowDownRight,
  stable: Minus,
};

interface TrendChipProps {
  direction: TrendDirection;
  /** Pre-translated word, e.g. t("Rising"). */
  label: string;
  /** Whether this direction is good news (drives the colour). */
  good?: boolean;
  className?: string;
}

/** Up/down indicator that pairs an arrow with words and a colour. */
export default function TrendChip({ direction, label, good, className }: TrendChipProps) {
  const Icon = ICONS[direction];
  const neutral = good === undefined;
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-full px-3 py-1 text-sm font-semibold",
        neutral
          ? "bg-muted text-muted-foreground"
          : good
            ? "bg-emerald-100 text-emerald-700 dark:bg-emerald-950 dark:text-emerald-300"
            : "bg-red-100 text-red-700 dark:bg-red-950 dark:text-red-300",
        className,
      )}
    >
      <Icon aria-hidden className="h-4 w-4" />
      {label}
    </span>
  );
}
