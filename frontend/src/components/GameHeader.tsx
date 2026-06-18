import { useApp } from "../hooks/useApp";
import { statusBadge, downloadJSON } from "./badges";
import type { GameMetadata } from "../types";

interface GameHeaderProps {
  game: GameMetadata;
  locked: boolean;
  status: string;
  createdAt?: string | null;
}

export function GameHeader({ game, locked, status, createdAt }: GameHeaderProps) {
  const { state, useAsTemplate } = useApp();
  const activeMatch = state.activeMatch;
  const effectiveLocked = locked || state.sessionLocked;
  const effectiveStatus = status || state.sessionStatus;

  return (
    <header className="flex items-center justify-between px-4 py-3 border-b border-line/40 bg-surface-container/30 shrink-0">
      <div className="flex items-center gap-3">
        <div className="flex items-center gap-2">
          <span className="w-7 h-7 rounded-md bg-accent/15 flex items-center justify-center">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="text-accent">
              <polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2" />
            </svg>
          </span>
          <h1 className="text-base font-extrabold text-ink capitalize">{game.name}</h1>
          {game.version && (
            <span className="text-[10px] text-muted font-medium">v{game.version}</span>
          )}
        </div>
        {effectiveStatus && statusBadge(effectiveStatus)}
        {effectiveLocked && (
          <span title="Created via programmatic API — configuration cannot be changed" className="flex items-center gap-1 text-[11px] font-semibold text-amber-600">
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <rect x="3" y="11" width="18" height="11" rx="2" ry="2" />
              <path d="M7 11V7a5 5 0 0 1 10 0v4" />
            </svg>
            Locked — created via API
          </span>
        )}
      </div>
      <div className="flex items-center gap-3">
        {createdAt && (
          <span className="text-[11px] text-quiet font-mono">
            {new Date(createdAt).toLocaleString(undefined, {
              year: "numeric",
              month: "short",
              day: "numeric",
              hour: "2-digit",
              minute: "2-digit",
            })}
          </span>
        )}
        {activeMatch && (
          <button
            type="button"
            onClick={useAsTemplate}
            title="Use current config as template for a new experiment"
            className="w-7 h-7 flex items-center justify-center rounded-lg text-muted hover:text-accent hover:bg-accent/10 cursor-pointer transition-colors"
          >
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <rect x="9" y="9" width="13" height="13" rx="2" ry="2" />
              <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1" />
            </svg>
          </button>
        )}
        {activeMatch && (
          <button
            type="button"
            onClick={() => downloadJSON(activeMatch, `${activeMatch.session_id || "match"}.json`)}
            title="Download match data as JSON"
            className="w-7 h-7 flex items-center justify-center rounded-lg text-muted hover:text-accent hover:bg-accent/10 cursor-pointer transition-colors"
          >
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
              <polyline points="7 10 12 15 17 10" />
              <line x1="12" y1="15" x2="12" y2="3" />
            </svg>
          </button>
        )}
      </div>
    </header>
  );
}
