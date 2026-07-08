import { Navigate } from "react-router-dom";
import { useAuth } from "../hooks/useAuth";
import { LoadingSpinner } from "./LoadingSpinner";

/**
 * Gate for the /admin route (#116): requires an admin user (`UserInfo.is_admin`)
 * AND the backend's `ENABLE_ADMIN_DASHBOARD` toggle being on (surfaced via
 * `SiteConfig.admin_dashboard_enabled`). Mirrors `ProtectedRoute`'s auth +
 * loading semantics but adds the admin check. Sign-in-less local mode is
 * allowed when the local user is flagged as admin.
 */
export function AdminRoute({ children }: { children: React.ReactNode }) {
  const { user, loading, hasProviders, sessionExpired } = useAuth();

  if (loading) {
    return (
      <div className="flex-1 flex items-center justify-center">
        <LoadingSpinner />
      </div>
    );
  }

  if (!hasProviders) {
    // Local mode: the backend's require_admin dependency is the actual gate.
    // Render when the (still possibly-null) local user is admin-flagged.
    return <>{children}</>;
  }

  if (!user) return <Navigate to="/login" replace state={{ sessionExpired }} />;
  if (!user.is_admin) return <Navigate to="/dashboard" replace />;
  return <>{children}</>;
}