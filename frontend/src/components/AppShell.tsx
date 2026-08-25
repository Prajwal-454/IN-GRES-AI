import {
  BarChart3,
  Bell,
  BookOpen,
  Bot,
  CloudSun,
  FileText,
  FlaskConical,
  GitCompareArrows,
  Globe,
  History,
  LayoutDashboard,
  LogOut,
  Map as MapIcon,
  Menu,
  MessageSquareText,
  ShieldCheck,
  TrendingUp,
  Users,
  Waves,
  X,
} from "lucide-react";
import { useState } from "react";
import { NavLink, Outlet, useLocation, useNavigate } from "react-router-dom";

import NotificationBell from "@/components/NotificationBell";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { useAuth } from "@/contexts/AuthContext";
import { useLanguage, type Language } from "@/contexts/LanguageContext";
import { cn } from "@/lib/utils";

const LANGS: { code: Language; label: string }[] = [
  { code: "en", label: "English" },
  { code: "te", label: "తెలుగు" },
  { code: "hi", label: "हिन्दी" },
];

interface NavGroup {
  label: string;
  items: {
    label: string;
    icon: typeof Bot;
    href: string;
    role?: string;
  }[];
}

const NAV_GROUPS: NavGroup[] = [
  {
    label: "Explore",
    items: [
      { label: "Groundwater", icon: BarChart3, href: "/groundwater" },
      { label: "Compare", icon: GitCompareArrows, href: "/compare" },
      { label: "Forecast", icon: TrendingUp, href: "/forecast" },
      { label: "Scenario Studio", icon: FlaskConical, href: "/studio" },
      { label: "Interactive Map", icon: CloudSun, href: "/weather" },
      { label: "Knowledge", icon: BookOpen, href: "/knowledge" },
      { label: "GIS Map", icon: MapIcon, href: "/gis" },
      { label: "Reports", icon: FileText, href: "/reports" },
    ],
  },
  {
    label: "Workspace",
    items: [
      { label: "Overview", icon: LayoutDashboard, href: "/dashboard" },
      { label: "History", icon: History, href: "/history" },
      { label: "Notifications", icon: Bell, href: "/notifications" },
    ],
  },
  {
    label: "Support & Admin",
    items: [
      { label: "Expert Desk", icon: Users, href: "/expert", role: "expert" },
      { label: "Admin", icon: ShieldCheck, href: "/admin", role: "admin" },
    ],
  },
];

export default function AppShell() {
  const { user, logout } = useAuth();
  const { lang, setLang, t } = useLanguage();
  const navigate = useNavigate();
  const location = useLocation();
  const [open, setOpen] = useState(false);

  function handleLogout() {
    logout();
    navigate("/");
  }

  const visibleGroups = NAV_GROUPS.map((group) => ({
    ...group,
    items: group.items.filter((item) => !item.role || item.role === user?.role),
  })).filter((group) => group.items.length > 0);

  const assistantLink = (
    <NavLink
      to="/assistant"
      onClick={() => setOpen(false)}
      className={({ isActive }) =>
        cn(
          "flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-semibold transition-all",
          isActive
            ? "bg-primary text-primary-foreground shadow-sm"
            : "bg-gradient-to-r from-primary to-sky-500 text-primary-foreground shadow-sm hover:brightness-105"
        )
      }
    >
      <MessageSquareText className="h-5 w-5" />
      Ask IN-GRES
      <Badge className="ml-auto bg-white/20 text-primary-foreground">AI</Badge>
    </NavLink>
  );

  const nav = (
    <nav className="flex-1 space-y-4 overflow-y-auto p-3">
      {assistantLink}
      {visibleGroups.map((group) => (
        <div key={group.label}>
          <div className="px-3 pb-1 text-[11px] font-semibold uppercase tracking-wider text-muted-foreground/70">
            {t(group.label)}
          </div>
          <div className="space-y-1">
            {group.items.map((item) => (
              <NavLink
                key={item.href}
                to={item.href}
                onClick={() => setOpen(false)}
                className={({ isActive }) =>
                  cn(
                    "flex items-center gap-3 rounded-md px-3 py-2 text-sm font-medium transition-colors",
                    isActive
                      ? "bg-accent text-accent-foreground"
                      : "text-muted-foreground hover:bg-accent/50 hover:text-foreground"
                  )
                }
              >
                <item.icon className="h-4 w-4" />
                {t(item.label)}
              </NavLink>
            ))}
          </div>
        </div>
      ))}
    </nav>
  );

  const userFooter = (
    <div className="border-t p-4">
      <div className="flex items-center gap-3">
        <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-primary text-sm font-semibold text-primary-foreground">
          {user?.full_name.charAt(0).toUpperCase() ?? "U"}
        </div>
        <div className="min-w-0 flex-1">
          <div className="truncate text-sm font-medium">{user?.full_name}</div>
          <div className="truncate text-xs text-muted-foreground">{user?.email}</div>
        </div>
        <Button variant="ghost" size="icon" onClick={handleLogout} title={t("sign_out")}>
          <LogOut className="h-4 w-4" />
        </Button>
      </div>
    </div>
  );

  const brand = (
    <div className="flex h-16 items-center gap-2 border-b px-6">
      <Waves className="h-6 w-6 text-primary" />
      <span className="font-semibold">IN-GRES AI</span>
    </div>
  );

  const languageSwitcher = (
    <div className="flex items-center gap-1 rounded-md border p-1">
      <Globe className="ml-1 h-3.5 w-3.5 text-muted-foreground" />
      {LANGS.map((l) => (
        <button
          key={l.code}
          onClick={() => setLang(l.code)}
          className={cn(
            "rounded px-2 py-1 text-xs font-medium transition-colors",
            lang === l.code
              ? "bg-primary text-primary-foreground"
              : "text-muted-foreground hover:text-foreground"
          )}
        >
          {l.label}
        </button>
      ))}
    </div>
  );

  return (
    <div className="flex min-h-screen bg-muted/30">
      <aside className="hidden w-60 flex-col border-r bg-background md:flex">
        {brand}
        {nav}
        <div className="px-4 pb-2">{languageSwitcher}</div>
        {userFooter}
      </aside>

      {open && (
        <div className="fixed inset-0 z-50 md:hidden">
          <div
            className="absolute inset-0 bg-background/80 backdrop-blur-sm"
            onClick={() => setOpen(false)}
          />
          <aside className="absolute inset-y-0 left-0 flex w-72 flex-col bg-background shadow-lg">
            <div className="flex items-center justify-between pr-3">
              {brand}
              <Button variant="ghost" size="icon" onClick={() => setOpen(false)}>
                <X className="h-4 w-4" />
              </Button>
            </div>
            {nav}
            <div className="px-4 pb-2">{languageSwitcher}</div>
            {userFooter}
          </aside>
        </div>
      )}

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="flex h-16 items-center justify-between border-b bg-background px-6">
          <div className="flex items-center gap-3">
            <Button
              variant="ghost"
              size="icon"
              className="md:hidden"
              onClick={() => setOpen(true)}
              title={t("Menu")}
            >
              <Menu className="h-5 w-5" />
            </Button>
            <Waves className="h-6 w-6 text-primary md:hidden" />
            <h1 className="text-lg font-semibold">
              {location.pathname === "/assistant"
                ? "IN-GRES Assistant"
                : visibleGroups
                    .flatMap((g) => g.items)
                    .find((i) => i.href === location.pathname)?.label ?? "IN-GRES AI"}
            </h1>
          </div>
          <div className="flex items-center gap-3">
            <NotificationBell />
            <div className="hidden sm:block">{languageSwitcher}</div>
            <Badge variant="secondary">
              <ShieldCheck className="mr-1 h-3 w-3" />
              {user?.role}
            </Badge>
          </div>
        </header>

        <main className="flex-1 overflow-auto p-6">
          <Outlet />
        </main>
      </div>
    </div>
  );
}