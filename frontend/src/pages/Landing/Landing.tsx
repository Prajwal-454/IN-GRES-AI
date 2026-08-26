import {
  BarChart3,
  Bot,
  Database,
  Globe,
  Languages,
  Map as MapIcon,
  ShieldCheck,
  Sparkles,
  Users,
  Waves,
} from "lucide-react";
import { Link } from "react-router-dom";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { useLanguage } from "@/contexts/LanguageContext";

const features = [
  {
    icon: Languages,
    title: "Multilingual AI",
    description: "Ask in English, Telugu or Hindi — the assistant understands code-switching and answers back in your language.",
  },
  {
    icon: BarChart3,
    title: "Groundwater Analytics",
    description: "Structured queries over recharge, extraction, availability and stage-of-extraction data with charts and trends.",
  },
  {
    icon: MapIcon,
    title: "Interactive GIS",
    description: "Explore states, districts and assessment units on maps, coloured by assessment category.",
  },
  {
    icon: Database,
    title: "Trusted Knowledge",
    description: "Retrieval-augmented answers grounded in documented sources — no invented numbers.",
  },
  {
    icon: Users,
    title: "Expert Assistance",
    description: "When AI confidence is low, your question is escalated to a groundwater expert.",
  },
];

const steps = [
  {
    step: "01",
    title: "Ask",
    description: "Type or speak a question about groundwater resources in India.",
  },
  {
    step: "02",
    title: "Understand",
    description: "IN-GRES AI detects language, intent, location and the metric you care about.",
  },
  {
    step: "03",
    title: "Answer",
    description: "Get a clear answer with values, units, year, sources, charts and maps.",
  },
];

export default function Landing() {
  const { t } = useLanguage();
  return (
    <div className="flex min-h-screen flex-col">
      <header className="border-b bg-background/80 backdrop-blur">
        <div className="mx-auto flex h-16 max-w-6xl items-center justify-between px-4 sm:px-6">
          <Link to="/" className="flex items-center gap-2 text-lg font-semibold">
            <Waves className="h-6 w-6 text-primary" />
            IN-GRES AI
          </Link>
          <nav className="flex items-center gap-2">
            <Button asChild variant="ghost" size="sm">
              <Link to="/login">{t("Sign in")}</Link>
            </Button>
            <Button asChild size="sm">
              <Link to="/register">{t("Get started")}</Link>
            </Button>
          </nav>
        </div>
      </header>

      <main className="flex-1">
        <section className="bg-gradient-to-b from-accent/50 to-background">
          <div className="mx-auto max-w-4xl px-4 py-20 text-center sm:px-6 sm:py-28">
            <Badge variant="secondary" className="mb-6">
              {t("Indian Groundwater Resource Estimation System")}
            </Badge>
            <h1 className="text-4xl font-bold tracking-tight sm:text-6xl">
              {t("AI-Powered Groundwater Intelligence")}
            </h1>
            <p className="mx-auto mt-6 max-w-2xl text-lg text-muted-foreground">
              {t(
                "Ask questions about India's groundwater resources using text or voice — in English, Telugu or Hindi."
              )}
            </p>
            <div className="mt-10 flex flex-wrap items-center justify-center gap-3">
              <Button asChild size="lg">
                <Link to="/register">
                  <Sparkles className="h-4 w-4" />
                  {t("Start Asking")}
                </Link>
              </Button>
              <Button asChild size="lg" variant="outline">
                <Link to="/register">
                  <MapIcon className="h-4 w-4" />
                  {t("Explore Groundwater")}
                </Link>
              </Button>
            </div>
            <div className="mt-12 grid gap-4 sm:grid-cols-3">
              <div className="rounded-lg border bg-card p-4 text-left">
                <div className="text-sm font-medium">{t("Example")}</div>
                <div className="mt-1 text-sm text-muted-foreground">
                  &quot;What is the groundwater extraction status of Andhra Pradesh?&quot;
                </div>
              </div>
              <div className="rounded-lg border bg-card p-4 text-left">
                <div className="text-sm font-medium">{t("Example (Telugu)")}</div>
                <div className="mt-1 text-sm text-muted-foreground">
                  &quot;ఆంధ్రప్రదేశ్‌లో భూగర్భ జలాల పరిస్థితి ఎలా ఉంది?&quot;
                </div>
              </div>
              <div className="rounded-lg border bg-card p-4 text-left">
                <div className="text-sm font-medium">{t("Example (Hindi)")}</div>
                <div className="mt-1 text-sm text-muted-foreground">
                  &quot;आंध्र प्रदेश में भूजल की स्थिति कैसी है?&quot;
                </div>
              </div>
            </div>
          </div>
        </section>

        <section className="border-t bg-background">
          <div className="mx-auto max-w-6xl px-4 py-20 sm:px-6">
            <h2 className="text-center text-3xl font-bold">{t("How it works")}</h2>
            <div className="mt-12 grid gap-6 md:grid-cols-3">
              {steps.map((item) => (
                <Card key={item.step}>
                  <CardHeader>
                    <div className="text-sm font-semibold text-primary">{item.step}</div>
                    <CardTitle>{t(item.title)}</CardTitle>
                  </CardHeader>
                  <CardContent>
                    <p className="text-sm text-muted-foreground">{t(item.description)}</p>
                  </CardContent>
                </Card>
              ))}
            </div>
          </div>
        </section>

        <section className="border-t bg-muted/40">
          <div className="mx-auto max-w-6xl px-4 py-20 sm:px-6">
            <div className="mb-12 flex items-center gap-3">
              <Bot className="h-8 w-8 text-primary" />
              <h2 className="text-3xl font-bold">{t("Built for groundwater research")}</h2>
            </div>
            <div className="grid gap-6 sm:grid-cols-2 lg:grid-cols-3">
              {features.map((feature) => (
                <Card key={feature.title} className="flex flex-col">
                  <CardHeader>
                    <feature.icon className="h-7 w-7 text-primary" />
                    <CardTitle>{t(feature.title)}</CardTitle>
                  </CardHeader>
                  <CardContent>
                    <p className="text-sm text-muted-foreground">{t(feature.description)}</p>
                  </CardContent>
                </Card>
              ))}
            </div>
          </div>
        </section>

        <section className="border-t bg-gradient-to-b from-background to-accent/40">
          <div className="mx-auto max-w-3xl px-4 py-20 text-center sm:px-6">
            <Globe className="mx-auto h-10 w-10 text-primary" />
            <h2 className="mt-4 text-3xl font-bold">
              {t("An assistant you can trust with data")}
            </h2>
            <p className="mt-4 text-muted-foreground">
              {t(
                "Answers are computed from the IN-GRES national assessment dataset � sources, years and confidence are shown for every figure, and uncertain questions are escalated to human groundwater experts."
              )}
            </p>
            <div className="mt-8 flex items-center justify-center gap-2 text-sm text-muted-foreground">
              <ShieldCheck className="h-4 w-4 text-primary" />
              {t("Data trust · Source transparency · Expert escalation")}
            </div>
          </div>
        </section>
      </main>

      <footer className="border-t bg-background">
        <div className="mx-auto flex max-w-6xl flex-col items-center gap-2 px-4 py-8 text-center text-sm text-muted-foreground sm:flex-row sm:justify-between sm:px-6 sm:text-left">
          <div className="flex items-center gap-2 font-medium text-foreground">
            <Waves className="h-4 w-4 text-primary" />
            IN-GRES AI
          </div>
          <div>
            {t("Indian Groundwater Resource Estimation System — AI Virtual Assistant")}
          </div>
          <div><div>Phase 1 prototype � IN-GRES Assessment Dataset</div></div>
        </div>
      </footer>
    </div>
  );
}