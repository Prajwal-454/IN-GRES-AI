import { lazy, Suspense } from "react";
import { Navigate, Route, Routes } from "react-router-dom";

import AppShell from "@/components/AppShell";
import IngresLoader from "@/components/IngresLoader";
import ProtectedRoute from "@/components/ProtectedRoute";
import Toaster from "@/components/Toaster";
import { AuthProvider } from "@/contexts/AuthContext";
import { LanguageProvider } from "@/contexts/LanguageContext";
import { NotificationProvider } from "@/contexts/NotificationContext";

const Admin = lazy(() => import("@/pages/Admin"));
const Assistant = lazy(() => import("@/pages/Assistant"));
const Compare = lazy(() => import("@/pages/Compare"));
const Dashboard = lazy(() => import("@/pages/Dashboard"));
const Expert = lazy(() => import("@/pages/Expert"));
const Forecast = lazy(() => import("@/pages/Forecast"));
const GIS = lazy(() => import("@/pages/GIS"));
const Groundwater = lazy(() => import("@/pages/Groundwater"));
const History = lazy(() => import("@/pages/History"));
const Knowledge = lazy(() => import("@/pages/Knowledge"));
const Landing = lazy(() => import("@/pages/Landing"));
const Login = lazy(() => import("@/pages/Login"));
const Notifications = lazy(() => import("@/pages/Notifications"));
const Register = lazy(() => import("@/pages/Register"));
const Reports = lazy(() => import("@/pages/Reports"));
const Studio = lazy(() => import("@/pages/Studio"));
const Weather = lazy(() => import("@/pages/Weather"));

function PageFallback() {
  return (
    <IngresLoader
      variant="page"
      size="md"
      message="Loading IN-GRES AI…"
      submessage="Preparing your groundwater intelligence workspace"
    />
  );
}

export default function App() {
  return (
    <AuthProvider>
      <NotificationProvider>
        <LanguageProvider>
          <Suspense fallback={<PageFallback />}>
            <Routes>
            <Route path="/" element={<Landing />} />
            <Route path="/login" element={<Login />} />
            <Route path="/register" element={<Register />} />
            <Route element={<ProtectedRoute />}>
              <Route element={<AppShell />}>
                <Route index element={<Navigate to="/assistant" replace />} />
                <Route path="/assistant" element={<Assistant />} />
                <Route path="/dashboard" element={<Dashboard />} />
                <Route path="/groundwater" element={<Groundwater />} />
                <Route path="/compare" element={<Compare />} />
                <Route path="/forecast" element={<Forecast />} />
                <Route path="/studio" element={<Studio />} />
                <Route path="/weather" element={<Weather />} />
                <Route path="/knowledge" element={<Knowledge />} />
                <Route path="/gis" element={<GIS />} />
                <Route path="/reports" element={<Reports />} />
                <Route path="/history" element={<History />} />
                <Route path="/expert" element={<Expert />} />
                <Route path="/notifications" element={<Notifications />} />
                <Route path="/admin" element={<Admin />} />
              </Route>
            </Route>
            <Route path="*" element={<Navigate to="/" replace />} />
            </Routes>
          </Suspense>
        </LanguageProvider>
        <Toaster />
      </NotificationProvider>
    </AuthProvider>
  );
}