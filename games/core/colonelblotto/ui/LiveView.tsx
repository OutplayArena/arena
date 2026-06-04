import { useCallback, useEffect, useRef, useState } from "react";
import { useApp } from "@frontend/hooks/useApp";
import { useCanvasRenderer } from "@frontend/hooks/useCanvasRenderer";
import type { AnimatedScores } from "@frontend/hooks/useCanvasRenderer";
import { PlaybackPanel } from "@frontend/components/PlaybackPanel";

interface LiveViewProps {
  onScores?: (scores: AnimatedScores) => void;
  onToggleCollapse: () => void;
  createdAt?: string | null;
}

export default function LiveView({ onScores, onToggleCollapse, createdAt }: LiveViewProps) {
  const { state } = useApp();
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const hasMatch = Boolean(state.activeMatch);
  const isGameRunning = Boolean(state.pendingGame);
  const [canvasError, setCanvasError] = useState(false);

  console.log("[LiveView] rendering, hasMatch:", hasMatch, "isGameRunning:", isGameRunning, "canvasError:", canvasError);

  const handleRenderError = useCallback((_err: Error) => {
    setCanvasError(true);
  }, []);

  const scores = useCanvasRenderer(
    canvasRef,
    state.activeMatch,
    state.activeRoundIndex,
    handleRenderError,
  );

  useEffect(() => {
    if (onScores) onScores(scores);
  }, [scores, onScores]);

  const match = state.activeMatch;
  const round = match?.history[state.activeRoundIndex] ?? null;
  const totalRounds = match?.num_rounds ?? 0;
  const currentRound = round?.round ?? 0;

  return (
    <div className="flex flex-col h-full bg-surface-soft">
      {/* Score bar — sticky at top */}
      <div className="shrink-0 sticky top-0 z-10 flex flex-wrap items-center justify-between gap-2 px-5 py-3 border-b border-line/40 bg-surface/80 backdrop-blur-sm">
        <div className="flex items-center gap-3 min-w-0">
          <div className="flex items-center gap-2">
            <span className="w-2.5 h-2.5 rounded-full bg-agent-a shrink-0" />
            <span className="text-xs font-extrabold text-muted uppercase tracking-wider">Agent A</span>
          </div>
          <span className="text-sm font-extrabold text-ink truncate max-w-[140px]">
            {match?.agent_a ?? "—"}
          </span>
          <span className="tabular-nums text-lg font-black text-agent-a">
            {Math.round(scores.displayedScoreA)}
          </span>
        </div>

        <div className="flex items-center gap-3 px-4 py-1.5 rounded-full bg-accent/8 border border-accent/20">
          <span className="text-[11px] font-extrabold text-muted uppercase tracking-wider">Round</span>
          <span className="tabular-nums text-sm font-black text-accent">
            {currentRound}
          </span>
          <span className="text-xs text-quiet">/</span>
          <span className="tabular-nums text-sm font-bold text-quiet">
            {totalRounds}
          </span>
          {match?.match_winner && (
            <span className="ml-1 text-[11px] font-extrabold text-gold bg-gold/10 px-2 py-0.5 rounded-full">
              {match.match_winner === "Tie" ? "Draw" : `Won by ${match.match_winner === "A" ? match.agent_a : match.agent_b}`}
            </span>
          )}
          {match?.match_winner && createdAt && (
            <span className="text-[10px] font-medium text-quiet tracking-wide">
              {new Date(createdAt).toLocaleDateString(undefined, { year: "numeric", month: "short", day: "numeric" })}
            </span>
          )}
        </div>

        <div className="flex items-center gap-3 min-w-0">
          <span className="tabular-nums text-lg font-black text-agent-b">
            {Math.round(scores.displayedScoreB)}
          </span>
          <span className="text-sm font-extrabold text-ink truncate max-w-[140px]">
            {match?.agent_b ?? "—"}
          </span>
          <div className="flex items-center gap-2">
            <span className="text-xs font-extrabold text-muted uppercase tracking-wider">Agent B</span>
            <span className="w-2.5 h-2.5 rounded-full bg-agent-b shrink-0" />
          </div>
        </div>

        <button
          type="button"
          onClick={onToggleCollapse}
          title="Hide battlefield"
          className="w-8 h-8 flex items-center justify-center rounded-lg text-muted hover:text-ink hover:bg-surface-container/80 cursor-pointer transition-colors shrink-0"
        >
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <polyline points="6 9 12 15 18 9" />
          </svg>
        </button>
      </div>

      {/* Playback controls — under score bar */}
      {hasMatch && (
        <div className="shrink-0 border-b border-line/40 bg-surface/80 backdrop-blur-sm">
          <PlaybackPanel />
        </div>
      )}

      {/* Canvas */}
      <div className="flex-1 min-h-0 relative overflow-hidden">
        {canvasError && (
          <div className="absolute inset-0 flex items-center justify-center bg-surface-soft z-10">
            <div className="text-center px-6">
              <p className="text-sm font-semibold text-red-500">Canvas rendering failed</p>
              <p className="text-xs text-muted mt-1.5">Check the browser console for details.</p>
            </div>
          </div>
        )}
        <canvas
          ref={canvasRef}
          className={`block w-full h-full ${hasMatch ? "" : "hidden"}`}
          width={1200}
          height={800}
        />
        {!hasMatch && !canvasError && (
          <div className="absolute inset-0 flex items-center justify-center">
            <div className="text-center px-6">
              <div className="w-16 h-16 mx-auto mb-4 rounded-2xl bg-surface-container flex items-center justify-center">
                {isGameRunning ? (
                  <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" className="text-accent/70 animate-spin">
                    <path d="M21 12a9 9 0 1 1-6.219-8.56" />
                  </svg>
                ) : (
                  <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" className="text-muted/60">
                    <rect x="3" y="3" width="7" height="7" rx="1" />
                    <rect x="14" y="3" width="7" height="7" rx="1" />
                    <rect x="3" y="14" width="7" height="7" rx="1" />
                    <rect x="14" y="14" width="7" height="7" rx="1" />
                  </svg>
                )}
              </div>
              {isGameRunning ? (
                <>
                  <p className="text-sm font-semibold text-muted">Waiting for first round...</p>
                  <p className="text-xs text-quiet mt-1.5">Agents are computing their moves. Battle data will appear shortly.</p>
                </>
              ) : (
                <>
                  <p className="text-sm font-semibold text-muted">No battle data yet</p>
                  <p className="text-xs text-quiet mt-1.5">Start a game from the Config tab to visualize the battlefield.</p>
                </>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
