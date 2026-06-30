import { useState } from "react";
import { useAuth } from "../hooks/useAuth";
import { acceptPrivacy } from "../api";

function SpinIcon() {
  return (
    <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="animate-spin">
      <circle cx="12" cy="12" r="10" strokeDasharray="31.4" strokeDashoffset="10" />
    </svg>
  );
}

/** Blocking first-login privacy notice.
 *
 * Renders a non-dismissable modal whenever the authenticated user has not
 * yet accepted the privacy notice (user.privacy_accepted === false).
 * Disappears permanently once the user clicks "I agree" and the backend
 * records the acceptance timestamp.
 */
export function PrivacyGate() {
  const { user, logout, refreshUser } = useAuth();
  const [accepting, setAccepting] = useState(false);

  // Only show for logged-in users who haven't accepted yet.
  if (!user || user.privacy_accepted) return null;

  const handleAccept = async () => {
    setAccepting(true);
    try {
      await acceptPrivacy();
      await refreshUser();
    } catch {
      // If the request fails the modal stays visible — user can retry.
      setAccepting(false);
    }
  };

  return (
    <div className="fixed inset-0 z-[100] flex items-center justify-center p-4 bg-black/50 backdrop-blur-sm">
      <div className="bg-surface rounded-[var(--radius-card)] shadow-elevation-5 border border-line w-full max-w-md">
        {/* Header */}
        <div className="px-6 pt-6 pb-4 border-b border-line/60">
          <h2 className="text-base font-bold text-ink">Before you continue</h2>
          <p className="text-xs text-muted mt-1">
            Please review how OutplayArena stores and handles your data.
          </p>
        </div>

        {/* Body */}
        <div className="px-6 py-5 space-y-4 text-xs text-muted leading-relaxed">
          <div className="space-y-2">
            <p>
              <span className="font-semibold text-ink">What we store: </span>
              your profile (name, email, OAuth provider), game sessions and
              results, API keys, and any third-party integration credentials you
              choose to add (such as a Weights &amp; Biases API key).
            </p>
            <p>
              <span className="font-semibold text-ink">How we protect it: </span>
              sensitive credentials are encrypted at rest and never returned by
              the API in plaintext. Game session tokens are one-way hashed.
            </p>
            <p>
              <span className="font-semibold text-ink">Third parties: </span>
              we do not sell or share your data. Results are only forwarded to
              third-party services (e.g. W&amp;B) if you explicitly enable that
              integration.
            </p>
          </div>

          {/* 90-day warning — visually prominent */}
          <div className="rounded-[var(--radius-chip)] border border-warning/30 bg-warning/5 px-4 py-3 flex gap-3">
            <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="text-warning shrink-0 mt-0.5">
              <path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/>
              <line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/>
            </svg>
            <p className="text-warning leading-relaxed">
              <span className="font-semibold">Inactivity deletion: </span>
              accounts with no login activity for <span className="font-semibold">90 days</span> are
              automatically and permanently deleted, including all game data. Log in at
              least once every 90 days to keep your account active. You can also
              export or delete your data at any time in <span className="font-semibold">Settings → Danger Zone</span>.
            </p>
          </div>
        </div>

        {/* Footer */}
        <div className="px-6 pb-6 flex items-center justify-between gap-3">
          <button
            type="button"
            onClick={logout}
            className="text-xs text-muted hover:text-ink transition-colors"
          >
            Log out instead
          </button>
          <button
            type="button"
            onClick={handleAccept}
            disabled={accepting}
            className="h-9 px-5 bg-accent text-white rounded-[var(--radius-button)] text-sm font-semibold transition-opacity hover:opacity-90 disabled:opacity-60 flex items-center gap-2"
          >
            {accepting && <SpinIcon />}
            I agree
          </button>
        </div>
      </div>
    </div>
  );
}
