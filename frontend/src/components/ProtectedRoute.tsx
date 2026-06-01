import { Navigate } from "react-router-dom";
import { useAuth } from "../hooks/useAuth";

export function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const { user, loading, hasProviders } = useAuth();

  if (loading) {
    return (
      <div className="flex items-center justify-center h-[calc(100dvh-56px)] text-muted text-sm">
        Loading...
      </div>
    );
  }

  if (!hasProviders) return <>{children}</>;

  if (!user) return <Navigate to="/login" replace />;
  return <>{children}</>;
}
