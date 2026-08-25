import { Lightbulb } from "lucide-react";
import type { ReactNode } from "react";

import { useLanguage } from "@/contexts/LanguageContext";
import { cn } from "@/lib/utils";

interface ExplainStripProps {
  /** One or more short, plain-language sentences derived from the data. */
  children: ReactNode;
  className?: string;
}

/**
 * "What does this mean?" explanation shown under important charts.
 * Callers must pass sentences already computed from real data and wrapped
 * in t() so they translate.
 */
export default function ExplainStrip({ children, className }: ExplainStripProps) {
  const { t } = useLanguage();
  return (
    <div
      className={cn(
        "mt-4 flex items-start gap-3 rounded-xl border border-sky-200 bg-sky-50 p-3.5 dark:border-sky-900 dark:bg-sky-950/40",
        className,
      )}
    >
      <span
        aria-hidden
        className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-sky-100 text-sky-700 dark:bg-sky-900 dark:text-sky-300"
      >
        <Lightbulb className="h-4 w-4" />
      </span>
      <div>
        <div className="text-sm font-bold text-sky-900 dark:text-sky-200">
          {t("What does this mean?")}
        </div>
        <div className="mt-0.5 text-[15px] leading-relaxed text-sky-900/90 dark:text-sky-100/90">
          {children}
        </div>
      </div>
    </div>
  );
}
