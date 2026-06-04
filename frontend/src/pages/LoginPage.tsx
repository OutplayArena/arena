import { useAuth } from "../hooks/useAuth";
import { useSiteConfig } from "../hooks/useSiteConfig";
import { Navigate, useLocation } from "react-router-dom";
import { BlobBackground } from "../components/BlobBackground";
import { LoadingSpinner } from "../components/LoadingSpinner";
import { OAuthButton } from "../components/OAuthButton";

export function LoginPage() {
  const { user, providers, hasProviders, loading } = useAuth();
  const { privacy_notice_url } = useSiteConfig();
  const location = useLocation();
  const sessionExpired = (location.state as { sessionExpired?: boolean } | null)?.sessionExpired;

  if (loading) {
    return (
      <div className="relative flex-1 flex items-center justify-center">
        <LoadingSpinner />
      </div>
    );
  }

  if (!hasProviders || user) return <Navigate to="/dashboard" replace />;

  return (
    <div className="relative flex-1 flex flex-col items-center justify-center px-6">
      <BlobBackground />

      {sessionExpired && (
        <div className="relative z-10 mb-6 px-4 py-2.5 rounded-card border border-amber-200 dark:border-amber-800/50 bg-amber-50 dark:bg-amber-950/30 text-xs text-amber-700 dark:text-amber-300 font-semibold text-center max-w-sm">
          Your session has expired. Please sign in again.
        </div>
      )}

      <div className="relative z-10 flex flex-col items-center text-center max-w-sm mx-auto w-full gap-8">
        <div className="grid gap-2">
          <h1 className="text-2xl font-black text-ink tracking-tight">
            Welcome to NashArena
          </h1>
          <p className="text-sm text-muted leading-relaxed">
            Sign in to run experiments and track your results.
          </p>
        </div>

        <div className="grid gap-3 w-full">
          {providers.github && <OAuthButton provider="github" />}
          {providers.google && <OAuthButton provider="google" />}
        </div>

        <p className="text-[11px] text-quiet leading-relaxed">
          By signing in you agree to our{" "}
          <a
            href={privacy_notice_url}
            target="_blank"
            rel="noopener noreferrer"
            className="text-ink underline-offset-2 hover:underline"
          >
            terms
          </a>
          . We only access your public profile and email to create your account.
        </p>
      </div>
    </div>
  );
}
