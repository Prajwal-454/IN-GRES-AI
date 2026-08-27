import { RefreshCw, Waves, WifiOff } from "lucide-react";

import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

const NETWORK_LOTTIE_SRC =
  "https://lottie.host/embed/be6bfb4f-5f99-4668-ab16-4f75046eebf2/PyObZ9ShoJ.lottie";

type Variant = "page" | "card" | "inline";
type Size = "sm" | "md" | "lg";

interface IngresNetworkErrorProps {
  variant?: Variant;
  size?: Size;
  title?: string;
  description?: string;
  detail?: string;
  onRetry?: () => void;
  className?: string;
  showBranding?: boolean;
}

const sizeMap: Record<Size, { wrap: string; iframe: string }> = {
  sm: { wrap: "h-[160px] w-[160px] rounded-2xl", iframe: "h-[160px] w-[160px]" },
  md: { wrap: "h-[220px] w-[220px] rounded-[22px]", iframe: "h-[220px] w-[220px]" },
  lg: { wrap: "h-[280px] w-[280px] rounded-[26px]", iframe: "h-[280px] w-[280px]" },
};

export default function IngresNetworkError({
  variant = "card",
  size = "md",
  title,
  description,
  detail,
  onRetry,
  className,
  showBranding = true,
}: IngresNetworkErrorProps) {
  const { wrap, iframe } = sizeMap[size];

  const lottieFrame = (
    <div
      className={cn(
        "relative overflow-hidden border bg-card shadow-sm",
        "bg-gradient-to-br from-primary/[0.08] via-background to-accent/60",
        wrap
      )}
    >
      <div className="pointer-events-none absolute inset-0 bg-gradient-to-br from-primary/10 via-transparent to-sky-500/10" />
      <div className="pointer-events-none absolute -top-10 -right-10 h-28 w-28 rounded-full bg-primary/10 blur-2xl" />
      <div className="pointer-events-none absolute -bottom-10 -left-10 h-28 w-28 rounded-full bg-sky-500/10 blur-2xl" />
      <iframe
        src={NETWORK_LOTTIE_SRC}
        title="Network error animation"
        loading="eager"
        allow="autoplay; fullscreen"
        allowFullScreen
        className={cn("relative z-10 block border-0 bg-transparent scale-[1.02]", iframe)}
        style={{ border: "none", background: "transparent" }}
      />
      <div className="pointer-events-none absolute inset-0 rounded-[inherit] ring-1 ring-inset ring-primary/10" />
      <div className="pointer-events-none absolute inset-x-0 bottom-0 h-[3px] bg-gradient-to-r from-primary via-sky-500 to-primary opacity-80" />
      {/* corner wifi badge */}
      <div className="absolute right-2 top-2 z-20 flex h-7 w-7 items-center justify-center rounded-full bg-background/90 shadow-sm ring-1 ring-primary/10 backdrop-blur">
        <WifiOff className="h-3.5 w-3.5 text-primary" />
      </div>
    </div>
  );

  const branding = showBranding ? (
    <div className="flex items-center gap-2">
      <span className="flex h-7 w-7 items-center justify-center rounded-full bg-primary text-primary-foreground shadow-sm">
        <Waves className="h-4 w-4" />
      </span>
      <span className="bg-gradient-to-r from-primary to-sky-600 bg-clip-text text-[13px] font-bold tracking-wide text-transparent">
        IN-GRES AI
      </span>
      <span className="rounded-full bg-accent px-2 py-0.5 text-[10px] font-semibold tracking-widest text-accent-foreground">
        GROUNDWATER
      </span>
    </div>
  ) : null;

  const content = (
    <div className={cn("flex flex-col items-center gap-5 text-center", className)}>
      {branding}
      {lottieFrame}
      <div className="max-w-sm space-y-2">
        <h3 className="text-base font-semibold tracking-tight text-foreground">
          {title ?? "Connection lost"}
        </h3>
        <p className="text-sm leading-relaxed text-muted-foreground">
          {description ??
            "We couldn't reach the IN-GRES AI servers. Check your internet, then try again."}
        </p>
        {detail && (
          <p className="rounded-md bg-muted/60 px-3 py-2 text-xs text-muted-foreground">
            {detail}
          </p>
        )}
      </div>
      {onRetry && (
        <Button onClick={onRetry} size="sm" className="mt-1 gap-2 shadow-sm">
          <RefreshCw className="h-4 w-4" />
          Try again
        </Button>
      )}
      {!onRetry && (
        <div className="flex items-center gap-1 pt-1">
          <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-primary [animation-delay:-0.3s]" />
          <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-sky-500 [animation-delay:-0.15s]" />
          <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-primary" />
        </div>
      )}
      <p className="text-[11px] text-muted-foreground/70">
        If this persists, the IN-GRES backend may be waking up — retry in 15s.
      </p>
    </div>
  );

  if (variant === "inline") {
    return <div className="flex justify-center py-6">{content}</div>;
  }

  if (variant === "page") {
    return (
      <div className="flex min-h-[60vh] items-center justify-center bg-gradient-to-b from-accent/30 via-background to-background px-6 py-12">
        <div className="pointer-events-none absolute inset-0 overflow-hidden">
          <div className="absolute -top-24 right-1/2 h-72 w-[36rem] -translate-x-1/2 rounded-full bg-primary/5 blur-3xl" />
          <div className="absolute bottom-0 left-1/2 h-64 w-[42rem] -translate-x-1/2 rounded-full bg-sky-500/5 blur-3xl" />
        </div>
        <div className="relative rounded-2xl border bg-card/80 p-8 shadow-sm backdrop-blur supports-[backdrop-filter]:bg-card/60">
          {content}
        </div>
      </div>
    );
  }

  // card (default) — perfect for in-page error states like Groundwater/Forecast/GIS
  return (
    <div className="flex justify-center py-8">
      <div className="w-full max-w-md rounded-2xl border bg-card p-6 shadow-sm sm:p-8">
        {content}
      </div>
    </div>
  );
}

export { NETWORK_LOTTIE_SRC };
