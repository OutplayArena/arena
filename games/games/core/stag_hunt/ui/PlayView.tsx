import { useEffect } from "react";
import { useInteractivePlay } from "@frontend/hooks/useInteractivePlay";
import { useApp } from "@frontend/hooks/useApp";
import { PlayScoreHeader } from "@frontend/components/play/PlayScoreHeader";
import { RoundResultBanner } from "@frontend/components/play/RoundResultBanner";

interface Props {
  onGameEnd: () => void;
  sessionConfig?: Record<string, unknown> | null;
}

export default function StagHuntPlayView({ onGameEnd, sessionConfig }: Props) {
  const { humanPlayer, isMyTurn, isComplete, isSubmitting, hasSubmittedThisRound, submitError, lastRoundResult, round, roundTotal, submitMove } = useInteractivePlay();
  const { state } = useApp();
  const match = state.activeMatch;

  const stagStag = (sessionConfig?.payoff_stag_stag as number) ?? 4;
  const hareHare = (sessionConfig?.payoff_hare_hare as number) ?? 2;
  const stagHare = (sessionConfig?.payoff_stag_hare as number) ?? 0;

  useEffect(() => {
    if (isComplete) onGameEnd();
  }, [isComplete, onGameEnd]);

  return (
    <div className="flex flex-col h-full bg-surface-soft">
      <PlayScoreHeader match={match} humanPlayer={humanPlayer} isMyTurn={isMyTurn} round={round} roundTotal={roundTotal} />

      {lastRoundResult && <RoundResultBanner result={lastRoundResult} humanPlayer={humanPlayer} />}
      {submitError && (
        <div className="shrink-0 mx-4 mt-2 px-3 py-2 rounded-lg bg-red-50 dark:bg-red-950/30 border border-red-200 dark:border-red-800/40 text-xs text-red-600 dark:text-red-400">
          {submitError}
        </div>
      )}

      <div className="flex-1 flex flex-col items-center justify-center gap-6 p-6">
        {isMyTurn && !isSubmitting && !hasSubmittedThisRound && (
          <p className="text-xs font-semibold text-muted">What will you hunt?</p>
        )}

        <div className="flex gap-4 flex-wrap justify-center">
          <button
            type="button"
            onClick={() => submitMove("stag")}
            disabled={!isMyTurn || isSubmitting || hasSubmittedThisRound}
            className="flex flex-col items-center gap-2 w-36 py-6 rounded-[var(--radius-card)] border-2 border-amber-300 bg-amber-50 hover:bg-amber-100 dark:border-amber-700 dark:bg-amber-950/30 dark:hover:bg-amber-900/40 text-amber-700 dark:text-amber-300 font-bold text-sm transition-all duration-150 disabled:opacity-40 disabled:cursor-not-allowed hover:not-disabled:-translate-y-0.5 hover:not-disabled:shadow-lg active:not-disabled:translate-y-0"
          >
            <span className="text-3xl">🦌</span>
            <span>Hunt Stag</span>
            <span className="text-[10px] opacity-70">+{stagStag} if both • +{stagHare} alone</span>
          </button>

          <button
            type="button"
            onClick={() => submitMove("hare")}
            disabled={!isMyTurn || isSubmitting || hasSubmittedThisRound}
            className="flex flex-col items-center gap-2 w-36 py-6 rounded-[var(--radius-card)] border-2 border-slate-300 bg-slate-50 hover:bg-slate-100 dark:border-slate-600 dark:bg-slate-900/30 dark:hover:bg-slate-800/40 text-slate-600 dark:text-slate-400 font-bold text-sm transition-all duration-150 disabled:opacity-40 disabled:cursor-not-allowed hover:not-disabled:-translate-y-0.5 hover:not-disabled:shadow-lg active:not-disabled:translate-y-0"
          >
            <span className="text-3xl">🐇</span>
            <span>Hunt Hare</span>
            <span className="text-[10px] opacity-70">+{hareHare} guaranteed</span>
          </button>
        </div>

        <div className="rounded-lg border border-line bg-surface p-3 text-xs text-muted max-w-xs w-full">
          <div className="font-extrabold uppercase text-[10px] tracking-wider mb-2">Risk vs reward</div>
          <div className="space-y-1 text-[11px]">
            <div className="flex justify-between">
              <span>Both hunt stag</span><span className="text-emerald-600 dark:text-emerald-400 font-bold">+{stagStag} each</span>
            </div>
            <div className="flex justify-between">
              <span>Both hunt hare</span><span className="text-amber-600 dark:text-amber-400 font-bold">+{hareHare} each</span>
            </div>
            <div className="flex justify-between">
              <span>You stag, they hare</span><span className="text-red-500 font-bold">+{stagHare} (risky!)</span>
            </div>
          </div>
        </div>

        {isSubmitting && <p className="text-xs text-muted animate-pulse">Submitting...</p>}
        {hasSubmittedThisRound && !isSubmitting && <p className="text-xs text-muted animate-pulse">Move submitted — waiting for next round...</p>}
        {!isMyTurn && !hasSubmittedThisRound && !isComplete && <p className="text-xs text-muted">Waiting for opponent...</p>}
      </div>
    </div>
  );
}
