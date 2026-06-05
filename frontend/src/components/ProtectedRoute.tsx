import { Navigate } from "react-router-dom";
import { useAuth } from "../hooks/useAuth";
import { LoadingSpinner } from "./LoadingSpinner";

export function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const { user, loading, hasProviders, sessionExpired } = useAuth();

  if (loading) {
    return (
      <div className="flex-1 flex items-center justify-center">
        <LoadingSpinner />
      </div>
    );
  }

  if (!hasProviders) return <>{children}</>;

  if (!user) return <Navigate to="/login" replace state={{ sessionExpired }} />;
  return <>{children}</>;
}
