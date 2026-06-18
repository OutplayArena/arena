import { useEffect } from "react";
import { useInteractivePlay } from "@frontend/hooks/useInteractivePlay";
import { useApp } from "@frontend/hooks/useApp";
import { PlayScoreHeader } from "@frontend/components/play/PlayScoreHeader";
import { RoundResultBanner } from "@frontend/components/play/RoundResultBanner";

const MOVES = ["rock", "paper", "scissors"] as const;
const EMOJI: Record<string, string> = { rock: "🪨", paper: "📄", scissors: "✂️" };
const COLOR: Record<string, string> = {
  rock: "border-amber-300 bg-amber-50 hover:bg-amber-100 dark:border-amber-700 dark:bg-amber-950/30 dark:hover:bg-amber-900/40 text-amber-700 dark:text-amber-300",
  paper: "border-sky-300 bg-sky-50 hover:bg-sky-100 dark:border-sky-700 dark:bg-sky-950/30 dark:hover:bg-sky-900/40 text-sky-700 dark:text-sky-300",
  scissors: "border-rose-300 bg-rose-50 hover:bg-rose-100 dark:border-rose-700 dark:bg-rose-950/30 dark:hover:bg-rose-900/40 text-rose-700 dark:text-rose-300",
};

interface Props {
  onGameEnd: () => void;
}

export default function RPSPlayView({ onGameEnd }: Props) {
  const { humanPlayer, isMyTurn, isComplete, isSubmitting, hasSubmittedThisRound, submitError, lastRoundResult, round, roundTotal, submitMove } = useInteractivePlay();
  const { state } = useApp();
  const match = state.activeMatch;

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
          <p className="text-xs font-semibold text-muted">Choose your move:</p>
        )}

        <div className="flex gap-4 flex-wrap justify-center">
          {MOVES.map((move) => (
            <button
              key={move}
              type="button"
              onClick={() => submitMove(move)}
              disabled={!isMyTurn || isSubmitting || hasSubmittedThisRound}
              className={`flex flex-col items-center gap-2 w-28 py-5 rounded-2xl border-2 font-bold text-sm transition-all duration-150 disabled:opacity-40 disabled:cursor-not-allowed hover:not-disabled:-translate-y-0.5 hover:not-disabled:shadow-lg active:not-disabled:translate-y-0 ${COLOR[move]}`}
            >
              <span className="text-4xl">{EMOJI[move]}</span>
              <span className="capitalize">{move}</span>
            </button>
          ))}
        </div>

        {isSubmitting && (
          <p className="text-xs text-muted animate-pulse">Submitting...</p>
        )}
        {hasSubmittedThisRound && !isSubmitting && (
          <p className="text-xs text-muted animate-pulse">Move submitted — waiting for next round...</p>
        )}
        {!isMyTurn && !hasSubmittedThisRound && !isComplete && (
          <p className="text-xs text-muted">Waiting for opponent...</p>
        )}
        {isComplete && (
          <p className="text-xs text-muted">Game over. Redirecting...</p>
        )}
      </div>
    </div>
  );
}
