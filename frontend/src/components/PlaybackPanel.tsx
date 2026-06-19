import { useCallback, useEffect, useRef } from "react";
import { useApp } from "../hooks/useApp";

export function PlaybackPanel() {
  const {
    state,
    showRound,
    prevRound,
    nextRound,
    togglePlay,
    stopPlay,
    setStatus,
    currentRound,
  } = useApp();

  const { activeMatch, activeRoundIndex, isPlaying, roundDuration } = state;
  const lastIndex = activeMatch ? activeMatch.history.length - 1 : 0;
  const hasMatch = Boolean(activeMatch);
  const isAtEnd = activeRoundIndex >= lastIndex;

  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const indexRef = useRef(activeRoundIndex);

  useEffect(() => {
    indexRef.current = activeRoundIndex;
  }, [activeRoundIndex]);

  const advance = useCallback(() => {
    if (!activeMatch) return;
    if (indexRef.current >= activeMatch.history.length - 1) {
      stopPlay();
      setStatus(
        `match_winner=${activeMatch.match_winner} | total_score_a=${activeMatch.total_score_a} | total_score_b=${activeMatch.total_score_b}`,
      );
      return;
    }
    nextRound();
  }, [activeMatch, nextRound, stopPlay, setStatus]);

  useEffect(() => {
    if (timerRef.current) {
      clearTimeout(timerRef.current);
      timerRef.current = null;
    }
    if (!isPlaying || !activeMatch) return;
    if (activeRoundIndex >= activeMatch.history.length - 1) {
      setStatus(
        `match_winner=${activeMatch.match_winner} | total_score_a=${activeMatch.total_score_a} | total_score_b=${activeMatch.total_score_b}`,
      );
      stopPlay();
      return;
    }
    timerRef.current = setTimeout(advance, roundDuration);
    return () => {
      if (timerRef.current) clearTimeout(timerRef.current);
    };
  }, [isPlaying, activeRoundIndex, activeMatch, advance, roundDuration, stopPlay, setStatus]);

  const round = currentRound();
  const roundStatus = round
    ? `round=${round.round} | winner=${round.winner} | action_a=[${(round.action_a as number[]).join(", ")}] | action_b=[${(round.action_b as number[]).join(", ")}]`
    : state.status;

  useEffect(() => {
    if (round) {
      setStatus(roundStatus);
    }
  }, [round, roundStatus, setStatus]);

  return (
    <div className="flex flex-wrap items-center justify-between gap-3 px-5 py-3">
      <div className="flex items-center gap-3 min-w-[180px] flex-1">
        <span className="text-[11px] font-extrabold text-muted uppercase tracking-wider shrink-0">
          Round
        </span>
        <input
          type="range"
          min={1}
          max={hasMatch ? activeMatch!.history.length : 1}
          value={activeRoundIndex + 1}
          disabled={!hasMatch}
          onChange={(e) => {
            stopPlay();
            showRound(Number(e.target.value) - 1);
          }}
          className="flex-1 h-1.5 rounded-full bg-line/60 appearance-none cursor-pointer [&::-webkit-slider-thumb]:appearance-none [&::-webkit-slider-thumb]:w-4 [&::-webkit-slider-thumb]:h-4 [&::-webkit-slider-thumb]:rounded-full [&::-webkit-slider-thumb]:bg-accent [&::-webkit-slider-thumb]:cursor-pointer [&::-webkit-slider-thumb]:shadow-elevation-2 [&::-webkit-slider-thumb]:transition-transform [&::-webkit-slider-thumb]:duration-150 hover:[&::-webkit-slider-thumb]:scale-110 disabled:opacity-40"
          aria-label="Select round"
        />
        <span className="tabular-nums text-xs font-extrabold text-quiet shrink-0 w-8 text-right">
          {activeRoundIndex + 1}/{activeMatch?.history.length ?? 1}
        </span>
      </div>

      <div className="flex items-center gap-2">
        <button
          type="button"
          aria-label="Previous round"
          disabled={!hasMatch || activeRoundIndex <= 0}
          onClick={() => {
            stopPlay();
            prevRound();
          }}
          className="w-9 h-9 flex items-center justify-center rounded-[var(--radius-button)] border border-line bg-surface text-ink text-sm font-medium shadow-elevation-1 transition-all duration-150 disabled:cursor-not-allowed disabled:opacity-30 hover:not-disabled:bg-surface-soft hover:not-disabled:shadow-elevation-2 active:not-disabled:scale-95"
        >
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
            <polyline points="15 18 9 12 15 6" />
          </svg>
        </button>

        <button
          type="button"
          disabled={!hasMatch}
          onClick={togglePlay}
          className="min-w-[72px] h-9 px-4 flex items-center justify-center gap-1.5 rounded-[var(--radius-button)] bg-accent text-white text-sm font-medium shadow-elevation-2 transition-all duration-150 disabled:cursor-not-allowed disabled:opacity-40 hover:not-disabled:opacity-90 active:not-disabled:scale-95"
        >
          {isPlaying ? (
            <>
              <svg width="12" height="12" viewBox="0 0 24 24" fill="currentColor">
                <rect x="6" y="4" width="4" height="16" rx="1" />
                <rect x="14" y="4" width="4" height="16" rx="1" />
              </svg>
              Pause
            </>
          ) : (
            <>
              <svg width="12" height="12" viewBox="0 0 24 24" fill="currentColor">
                <polygon points="6 4 20 12 6 20" />
              </svg>
              Play
            </>
          )}
        </button>

        <button
          type="button"
          aria-label="Next round"
          disabled={!hasMatch || isAtEnd}
          onClick={() => {
            stopPlay();
            nextRound();
          }}
          className="w-9 h-9 flex items-center justify-center rounded-[var(--radius-button)] border border-line bg-surface text-ink text-sm font-medium shadow-elevation-1 transition-all duration-150 disabled:cursor-not-allowed disabled:opacity-30 hover:not-disabled:bg-surface-soft hover:not-disabled:shadow-elevation-2 active:not-disabled:scale-95"
        >
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
            <polyline points="9 18 15 12 9 6" />
          </svg>
        </button>
      </div>
    </div>
  );
}
