import { Waves } from "lucide-react";

import { cn } from "@/lib/utils";

const LOTTIE_SRC = "https://lottie.host/embed/711ab754-fd7e-4164-8770-d3aa7eccb854/hvZZsyFE0b.lottie";

type Variant = "page" | "overlay" | "inline" | "card";
type Size = "sm" | "md" | "lg";

interface IngresLoaderProps {
  variant?: Variant;
  size?: Size;
  message?: string;
  submessage?: string;
  className?: string;
  showBranding?: boolean;
}

const sizeMap: Record<Size, { wrap: string; iframe: string }> = {
  sm: { wrap: "h-[140px] w-[140px] rounded-2xl", iframe: "h-[140px] w-[140px]" },
  md: { wrap: "h-[220px] w-[220px] rounded-[22px]", iframe: "h-[220px] w-[220px]" },
  lg: { wrap: "h-[300px] w-[300px] rounded-[26px]", iframe: "h-[300px] w-[300px]" },
};

export default function IngresLoader({
  variant = "page",
  size = "md",
  message,
  submessage,
  className,
  showBranding = true,
}: IngresLoaderProps) {
  const { wrap, iframe } = sizeMap[size];

  const lottieFrame = (
    <div
      className={cn(
        "relative overflow-hidden border bg-card shadow-sm",
        "bg-gradient-to-br from-primary/[0.08] via-background to-accent/60",
        wrap
      )}
    >
      {/* subtle primary glow behind the animation */}
      <div className="pointer-events-none absolute inset-0 bg-gradient-to-br from-primary/10 via-transparent to-sky-500/10" />
      <div className="pointer-events-none absolute -top-10 -right-10 h-28 w-28 rounded-full bg-primary/10 blur-2xl" />
      <div className="pointer-events-none absolute -bottom-10 -left-10 h-28 w-28 rounded-full bg-sky-500/10 blur-2xl" />

      <iframe
        src={LOTTIE_SRC}
        title="Loading animation"
        loading="eager"
        allow="autoplay; fullscreen"
        allowFullScreen
        className={cn(
          "relative z-10 block border-0 bg-transparent",
          // scale slightly to remove default lottie.host padding/letterbox if present
          "scale-[1.02]",
          iframe
        )}
        style={{ border: "none", background: "transparent" }}
      />

      {/* inner ring to match IN-GRES card style */}
      <div className="pointer-events-none absolute inset-0 rounded-[inherit] ring-1 ring-inset ring-primary/10" />
      {/* bottom accent line */}
      <div className="pointer-events-none absolute inset-x-0 bottom-0 h-[3px] bg-gradient-to-r from-primary via-sky-500 to-primary opacity-80" />
    </div>
  );

  const branding = showBranding ? (
    <div className="flex flex-col items-center gap-2 text-center">
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

      <div className="space-y-1">
        <p className="text-sm font-medium text-foreground">
          {message ?? "Loading groundwater intelligence…"}
        </p>
        <p className="text-xs text-muted-foreground">
          {submessage ?? "Fetching IN-GRES assessment data"}
        </p>
      </div>

      {/* animated dots */}
      <div className="flex items-center gap-1 pt-1">
        <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-primary [animation-delay:-0.3s]" />
        <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-sky-500 [animation-delay:-0.15s]" />
        <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-primary" />
      </div>
    </div>
  ) : null;

  const content = (
    <div className={cn("flex flex-col items-center gap-5", className)}>
      {lottieFrame}
      {branding}
    </div>
  );

  if (variant === "inline") {
    return <div className="flex justify-center py-8">{content}</div>;
  }

  if (variant === "card") {
    return (
      <div className="flex justify-center py-6">
        <div className="rounded-2xl border bg-card/80 p-8 shadow-sm backdrop-blur supports-[backdrop-filter]:bg-card/60">
          {content}
        </div>
      </div>
    );
  }

  if (variant === "overlay") {
    return (
      <div className="absolute inset-0 z-20 flex items-center justify-center bg-background/70 backdrop-blur-sm">
        {content}
      </div>
    );
  }

  // page — full screen, matches IN-GRES AI theme (accent wash + subtle gradient like Landing hero)
  return (
    <div className="flex min-h-screen items-center justify-center bg-gradient-to-b from-accent/40 via-background to-background px-6 py-16">
      {/* decorative blurred blobs like Landing section */}
      <div className="pointer-events-none absolute inset-0 overflow-hidden">
        <div className="absolute -top-24 right-1/2 h-72 w-[36rem] -translate-x-1/2 rounded-full bg-primary/5 blur-3xl" />
        <div className="absolute bottom-0 left-1/2 h-64 w-[42rem] -translate-x-1/2 rounded-full bg-sky-500/5 blur-3xl" />
      </div>
      <div className="relative">{content}</div>
    </div>
  );
}

// Lightweight inline row loader for buttons / small areas — reuses same lottie at tiny size
export function IngresInlineLoader({ className }: { className?: string }) {
  return (
    <span className={cn("inline-flex items-center gap-2", className)}>
      <span className="relative h-7 w-7 overflow-hidden rounded-full border bg-card shadow-sm">
        <iframe
          src={LOTTIE_SRC}
          title="Loading"
          loading="eager"
          className="h-7 w-7 scale-[1.35] border-0"
          style={{ border: "none" }}
          tabIndex={-1}
          aria-hidden="true"
        />
      </span>
      <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-primary [animation-delay:-0.3s]" />
      <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-primary/70 [animation-delay:-0.15s]" />
    </span>
  );
}
