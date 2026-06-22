import { useAuth } from "../hooks/useAuth";
import { useSiteConfig } from "../hooks/useSiteConfig";
import { Navigate, useLocation } from "react-router-dom";
import { LoadingSpinner } from "../components/LoadingSpinner";
import { OAuthButton } from "../components/OAuthButton";


export function LoginPage() {
  const { user, providers, hasProviders, loading } = useAuth();
  const { privacy_notice_url } = useSiteConfig();
  const location = useLocation();
  const sessionExpired = (location.state as { sessionExpired?: boolean } | null)?.sessionExpired;

  if (loading) {
    return (
      <div className="flex-1 flex items-center justify-center">
        <LoadingSpinner />
      </div>
    );
  }

  if (!hasProviders || user) return <Navigate to="/dashboard" replace />;

  return (
    <div className="flex-1 flex items-center justify-center px-6 py-16 bg-bg dot-grid">
      {/* Faint radial glow */}
      <div
        className="pointer-events-none fixed inset-0"
        style={{ background: "radial-gradient(ellipse 60% 50% at 50% 40%, var(--color-accent-dim), transparent)" }}
      />

      <div className="relative z-10 w-full max-w-sm">
        <div className="rounded-[var(--radius-card)] border border-line bg-surface shadow-elevation-3 p-8 flex flex-col gap-6">
          {/* Logo */}
          <div className="flex flex-col items-center gap-3 text-center">
            <img src="/img/logo_only_outplaylabs_arena.png" alt="OutplayLabs Arena" className="h-10 w-auto" />
            <div>
              <h1 className="text-lg font-bold text-ink">Sign in to OutplayLabs Arena</h1>
              <p className="text-xs text-muted mt-1">Research-grade AI agent benchmarking</p>
            </div>
          </div>

          {/* Session expired warning */}
          {sessionExpired && (
            <div className="px-3 py-2.5 rounded-[var(--radius-chip)] border border-warning/30 bg-warning/8 text-xs text-warning font-medium text-center">
              Your session has expired. Please sign in again.
            </div>
          )}

          {/* OAuth buttons */}
          <div className="flex flex-col gap-2.5">
            {providers.github && <OAuthButton provider="github" />}
            {providers.google && <OAuthButton provider="google" />}
          </div>

          {/* Terms */}
          <p className="text-[11px] text-quiet text-center leading-relaxed">
            By signing in you agree to our{" "}
            {privacy_notice_url ? (
              <a
                href={privacy_notice_url}
                target="_blank"
                rel="noopener noreferrer"
                className="text-muted hover:text-ink transition-colors underline-offset-2 hover:underline"
              >
                Terms of Service
              </a>
            ) : (
              "Terms of Service"
            )}
            . We only access your public profile and email to create your account.
          </p>
        </div>
      </div>
    </div>
  );
}
