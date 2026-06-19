import { memo } from "react";
import { useApp } from "../hooks/useApp";

export const StatusBanner = memo(function StatusBanner() {
  const { state, setStatus } = useApp();

  if (!state.status) return null;

  const match = state.activeMatch;
  const round = match?.history.length ?? 0;
  const total = match?.num_rounds ?? state.pendingGame?.numRounds ?? 0;
  const progress = total > 0 ? `Round ${Math.min(round + 1, total)} / ${total}` : "";

  return (
    <div className="flex items-center gap-2 absolute top-4 left-1/2 w-[min(720px,calc(100%-32px))] -translate-x-1/2 px-3.5 py-2.5 text-ink bg-surface/90 border rounded-[var(--radius-card)] border-line shadow-elevation-4 backdrop-blur-md z-40" role="status" aria-live="polite">
      <span className="flex-1 text-center font-mono text-xs font-extrabold truncate">
        {state.status}
      </span>
      {progress && (
        <span className="text-[10px] text-muted font-mono whitespace-nowrap">{progress}</span>
      )}
      <button
        type="button"
        onClick={() => setStatus("")}
        className="w-5 h-5 flex items-center justify-center rounded text-muted hover:text-ink hover:bg-ink/[0.08] transition-colors shrink-0"
        aria-label="Dismiss"
      >
        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round">
          <path d="M18 6L6 18M6 6l12 12" />
        </svg>
      </button>
    </div>
  );
});
