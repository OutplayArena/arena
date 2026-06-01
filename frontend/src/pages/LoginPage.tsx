import { useAuth } from "../hooks/useAuth";
import { Navigate } from "react-router-dom";
import { BlobBackground } from "../components/BlobBackground";
import { OAuthButton } from "../components/OAuthButton";

export function LoginPage() {
  const { user, providers, hasProviders, loading } = useAuth();

  if (loading) {
    return (
      <div className="relative min-h-[calc(100dvh-56px)] flex items-center justify-center">
        <p className="text-muted text-sm">Loading...</p>
      </div>
    );
  }

  if (!hasProviders || user) return <Navigate to="/dashboard" replace />;

  return (
    <div className="relative min-h-[calc(100dvh-56px)] flex flex-col items-center justify-center px-6">
      <BlobBackground />

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
          By signing in you agree to our terms. We only access your public
          profile and email to create your account.
        </p>
      </div>
    </div>
  );
}
