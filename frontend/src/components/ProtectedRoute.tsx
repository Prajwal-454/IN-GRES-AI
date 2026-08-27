import { Navigate, Outlet, useLocation } from "react-router-dom";

import IngresLoader from "@/components/IngresLoader";
import { useAuth } from "@/contexts/AuthContext";

export default function ProtectedRoute() {
  const { isAuthenticated, isLoading } = useAuth();
  const location = useLocation();

  if (isLoading) {
    return (
      <IngresLoader
        variant="page"
        size="md"
        message="Authenticating…"
        submessage="Securing your IN-GRES AI session"
      />
    );
  }

  if (!isAuthenticated) {
    return <Navigate to="/login" state={{ from: location }} replace />;
  }

  return <Outlet />;
}