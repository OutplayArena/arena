import { useEffect } from "react";
import { useInteractivePlay } from "@frontend/hooks/useInteractivePlay";
import { useApp } from "@frontend/hooks/useApp";
import { PlayScoreHeader } from "@frontend/components/play/PlayScoreHeader";
import { RoundResultBanner } from "@frontend/components/play/RoundResultBanner";

interface Props {
  onGameEnd: () => void;
  sessionConfig?: Record<string, unknown> | null;
}

export default function CentipedePlayView({ onGameEnd, sessionConfig }: Props) {
  const { humanPlayer, isMyTurn, isComplete, isSubmitting, hasSubmittedThisRound, submitError, lastRoundResult, round, roundTotal, submitMove, currentState } = useInteractivePlay();
  const { state } = useApp();
  const match = state.activeMatch;

  const maxSteps = (sessionConfig?.max_steps as number) ?? 6;
  const potA = (currentState?.pot_a as number) ?? (sessionConfig?.initial_pot_a as number) ?? 4;
  const potB = (currentState?.pot_b as number) ?? (sessionConfig?.initial_pot_b as number) ?? 1;
  const step = (currentState?.step as number) ?? 0;
  const currentPlayer = (currentState?.current_player as string) ?? "A";

  const myPot = humanPlayer === "A" ? potA : potB;
  const oppPot = humanPlayer === "A" ? potB : potA;

  useEffect(() => {
    if (isComplete) onGameEnd();
  }, [isComplete, onGameEnd]);

  const isMyActualTurn = isMyTurn && currentPlayer === humanPlayer && !hasSubmittedThisRound;

  return (
    <div className="flex flex-col h-full bg-surface-soft">
      <PlayScoreHeader match={match} humanPlayer={humanPlayer} isMyTurn={isMyActualTurn} round={round} roundTotal={roundTotal} />

      {lastRoundResult && <RoundResultBanner result={lastRoundResult} humanPlayer={humanPlayer} />}
      {submitError && (
        <div className="shrink-0 mx-4 mt-2 px-3 py-2 rounded-lg bg-red-50 dark:bg-red-950/30 border border-red-200 dark:border-red-800/40 text-xs text-red-600 dark:text-red-400">
          {submitError}
        </div>
      )}

      <div className="flex-1 flex flex-col items-center justify-center gap-6 p-6">
        {/* Pot visualization */}
        <div className="rounded-[var(--radius-card)] border border-line bg-surface p-4 w-full max-w-xs">
          <div className="text-[10px] font-extrabold uppercase tracking-widest text-muted mb-3 text-center">
            Step {step} / {maxSteps}
          </div>
          <div className="flex justify-center gap-8">
            <div className="text-center">
              <div className="text-2xl font-black text-agent-a tabular-nums">{myPot.toFixed(0)}</div>
              <div className="text-[10px] text-muted mt-0.5">Your pot</div>
            </div>
            <div className="text-center">
              <div className="text-2xl font-black text-agent-b tabular-nums">{oppPot.toFixed(0)}</div>
              <div className="text-[10px] text-muted mt-0.5">Opp pot</div>
            </div>
          </div>
          <div className="text-[10px] text-muted text-center mt-2">
            Passing doubles both pots
          </div>
        </div>

        {/* Action buttons */}
        {isMyActualTurn && !isSubmitting ? (
          <div className="flex gap-4">
            <button
              type="button"
              onClick={() => submitMove("take")}
              disabled={isSubmitting}
              className="flex flex-col items-center gap-2 w-32 py-5 rounded-[var(--radius-card)] border-2 border-amber-300 bg-amber-50 hover:bg-amber-100 dark:border-amber-700 dark:bg-amber-950/30 text-amber-700 dark:text-amber-300 font-bold text-sm transition-all disabled:opacity-40 hover:not-disabled:-translate-y-0.5 hover:not-disabled:shadow-lg"
            >
              <span className="text-3xl">💰</span>
              <span>Take</span>
              <span className="text-[10px] opacity-70">Secure {myPot.toFixed(0)}</span>
            </button>

            <button
              type="button"
              onClick={() => submitMove("pass")}
              disabled={isSubmitting}
              className="flex flex-col items-center gap-2 w-32 py-5 rounded-[var(--radius-card)] border-2 border-emerald-300 bg-emerald-50 hover:bg-emerald-100 dark:border-emerald-700 dark:bg-emerald-950/30 text-emerald-700 dark:text-emerald-300 font-bold text-sm transition-all disabled:opacity-40 hover:not-disabled:-translate-y-0.5 hover:not-disabled:shadow-lg"
            >
              <span className="text-3xl">🤝</span>
              <span>Pass</span>
              <span className="text-[10px] opacity-70">Risk for more</span>
            </button>
          </div>
        ) : (
          <div className="text-center text-sm text-muted">
            {isSubmitting
              ? "Submitting..."
              : hasSubmittedThisRound
                ? "Move submitted — waiting for next step..."
                : isComplete
                  ? "Game over. Redirecting..."
                  : `Opponent's turn (step ${step})...`}
          </div>
        )}
      </div>
    </div>
  );
}
