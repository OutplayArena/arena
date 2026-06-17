import { useEffect } from "react";
import { useInteractivePlay } from "@frontend/hooks/useInteractivePlay";
import { useApp } from "@frontend/hooks/useApp";
import { PlayScoreHeader } from "@frontend/components/play/PlayScoreHeader";
import { RoundResultBanner } from "@frontend/components/play/RoundResultBanner";

interface Props {
  onGameEnd: () => void;
  sessionConfig?: Record<string, unknown> | null;
}

export default function PDPlayView({ onGameEnd, sessionConfig }: Props) {
  const { humanPlayer, isMyTurn, isComplete, isSubmitting, hasSubmittedThisRound, submitError, lastRoundResult, round, roundTotal, submitMove } = useInteractivePlay();
  const { state } = useApp();
  const match = state.activeMatch;

  const T = (sessionConfig?.payoff_T as number) ?? 5;
  const R = (sessionConfig?.payoff_R as number) ?? 3;
  const P = (sessionConfig?.payoff_P as number) ?? 1;
  const S = (sessionConfig?.payoff_S as number) ?? 0;

  // Count cooperation streak
  const history = match?.history ?? [];
  let streak = 0;
  for (let i = history.length - 1; i >= 0; i--) {
    const myMove = humanPlayer === "A" ? history[i].action_a : history[i].action_b;
    if (myMove === "cooperate") streak++;
    else break;
  }

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
          <p className="text-xs font-semibold text-muted">What will you do?</p>
        )}

        <div className="flex gap-4 flex-wrap justify-center">
          <button
            type="button"
            onClick={() => submitMove("cooperate")}
            disabled={!isMyTurn || isSubmitting || hasSubmittedThisRound}
            className="flex flex-col items-center gap-2 w-36 py-6 rounded-2xl border-2 border-emerald-300 bg-emerald-50 hover:bg-emerald-100 dark:border-emerald-700 dark:bg-emerald-950/30 dark:hover:bg-emerald-900/40 text-emerald-700 dark:text-emerald-300 font-bold text-sm transition-all duration-150 disabled:opacity-40 disabled:cursor-not-allowed hover:not-disabled:-translate-y-0.5 hover:not-disabled:shadow-lg active:not-disabled:translate-y-0"
          >
            <span className="text-3xl">🤝</span>
            <span>Cooperate</span>
          </button>

          <button
            type="button"
            onClick={() => submitMove("defect")}
            disabled={!isMyTurn || isSubmitting || hasSubmittedThisRound}
            className="flex flex-col items-center gap-2 w-36 py-6 rounded-2xl border-2 border-red-300 bg-red-50 hover:bg-red-100 dark:border-red-700 dark:bg-red-950/30 dark:hover:bg-red-900/40 text-red-700 dark:text-red-300 font-bold text-sm transition-all duration-150 disabled:opacity-40 disabled:cursor-not-allowed hover:not-disabled:-translate-y-0.5 hover:not-disabled:shadow-lg active:not-disabled:translate-y-0"
          >
            <span className="text-3xl">🗡️</span>
            <span>Defect</span>
          </button>
        </div>

        {/* Payoff matrix reference */}
        <div className="mt-2 rounded-lg border border-line/30 bg-surface p-3 text-xs text-muted max-w-xs w-full">
          <div className="font-extrabold uppercase text-[10px] tracking-wider mb-2">Payoff reference</div>
          <div className="grid grid-cols-2 gap-1 text-[11px]">
            <span className="text-emerald-600 dark:text-emerald-400">Both cooperate: +{R}</span>
            <span className="text-amber-600 dark:text-amber-400">You defect, they coop: +{T}</span>
            <span className="text-red-500">Both defect: +{P}</span>
            <span className="text-red-400">You coop, they defect: +{S}</span>
          </div>
        </div>

        {streak > 0 && (
          <p className="text-[11px] text-emerald-600 dark:text-emerald-400 font-semibold">
            🤝 Cooperation streak: {streak} round{streak !== 1 ? "s" : ""}
          </p>
        )}

        {isSubmitting && <p className="text-xs text-muted animate-pulse">Submitting...</p>}
        {hasSubmittedThisRound && !isSubmitting && <p className="text-xs text-muted animate-pulse">Move submitted — waiting for next round...</p>}
        {!isMyTurn && !hasSubmittedThisRound && !isComplete && <p className="text-xs text-muted">Waiting for opponent...</p>}
      </div>
    </div>
  );
}
