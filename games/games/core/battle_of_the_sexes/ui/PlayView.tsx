import { useEffect } from "react";
import { useInteractivePlay } from "@frontend/hooks/useInteractivePlay";
import { useApp } from "@frontend/hooks/useApp";
import { PlayScoreHeader } from "@frontend/components/play/PlayScoreHeader";
import { RoundResultBanner } from "@frontend/components/play/RoundResultBanner";

interface Props {
  onGameEnd: () => void;
  sessionConfig?: Record<string, unknown> | null;
}

export default function BattleOfSexesPlayView({ onGameEnd, sessionConfig }: Props) {
  const { humanPlayer, isMyTurn, isComplete, isSubmitting, hasSubmittedThisRound, submitError, lastRoundResult, round, roundTotal, submitMove } = useInteractivePlay();
  const { state } = useApp();
  const match = state.activeMatch;

  const optionA = (sessionConfig?.option_a_label as string) ?? "Opera";
  const optionB = (sessionConfig?.option_b_label as string) ?? "Football";
  const prefA = (sessionConfig?.payoff_preferred_a as number) ?? 3;
  const prefB = (sessionConfig?.payoff_preferred_b as number) ?? 3;
  const nonPref = (sessionConfig?.payoff_nonpreferred as number) ?? 2;

  // Count coordination streak
  const history = match?.history ?? [];
  let coordStreak = 0;
  for (let i = history.length - 1; i >= 0; i--) {
    if (history[i].winner !== "Tie") coordStreak++;
    else break;
  }

  useEffect(() => {
    if (isComplete) onGameEnd();
  }, [isComplete, onGameEnd]);

  const preferred = humanPlayer === "A" ? optionA : optionB;

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
        {humanPlayer && (
          <p className="text-[11px] text-muted text-center">
            You prefer: <span className="font-extrabold text-ink">{preferred}</span>
          </p>
        )}

        <div className="flex gap-4 flex-wrap justify-center">
          <button
            type="button"
            onClick={() => submitMove(optionA.toLowerCase())}
            disabled={!isMyTurn || isSubmitting || hasSubmittedThisRound}
            className="flex flex-col items-center gap-2 w-36 py-6 rounded-2xl border-2 border-agent-a/40 bg-agent-a/5 hover:bg-agent-a/10 text-agent-a font-bold text-sm transition-all duration-150 disabled:opacity-40 disabled:cursor-not-allowed hover:not-disabled:-translate-y-0.5 hover:not-disabled:shadow-lg active:not-disabled:translate-y-0"
          >
            <span className="text-3xl">🎭</span>
            <span className="capitalize">{optionA}</span>
            <span className="text-[10px] opacity-70">+{prefA} if coordinated</span>
          </button>

          <button
            type="button"
            onClick={() => submitMove(optionB.toLowerCase())}
            disabled={!isMyTurn || isSubmitting || hasSubmittedThisRound}
            className="flex flex-col items-center gap-2 w-36 py-6 rounded-2xl border-2 border-agent-b/40 bg-agent-b/5 hover:bg-agent-b/10 text-agent-b font-bold text-sm transition-all duration-150 disabled:opacity-40 disabled:cursor-not-allowed hover:not-disabled:-translate-y-0.5 hover:not-disabled:shadow-lg active:not-disabled:translate-y-0"
          >
            <span className="text-3xl">🏈</span>
            <span className="capitalize">{optionB}</span>
            <span className="text-[10px] opacity-70">+{prefB} if coordinated</span>
          </button>
        </div>

        <p className="text-[11px] text-muted text-center">
          Coordination earns +{nonPref} for the non-preferred player
        </p>

        {coordStreak > 0 && (
          <p className="text-[11px] text-emerald-600 dark:text-emerald-400 font-semibold">
            🎯 Coordination streak: {coordStreak} round{coordStreak !== 1 ? "s" : ""}
          </p>
        )}

        {isSubmitting && <p className="text-xs text-muted animate-pulse">Submitting...</p>}
        {hasSubmittedThisRound && !isSubmitting && <p className="text-xs text-muted animate-pulse">Move submitted — waiting for next round...</p>}
        {!isMyTurn && !hasSubmittedThisRound && !isComplete && <p className="text-xs text-muted">Waiting for opponent...</p>}
      </div>
    </div>
  );
}
