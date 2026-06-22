import { useEffect, useState } from "react";
import { useInteractivePlay } from "@frontend/hooks/useInteractivePlay";
import { useApp } from "@frontend/hooks/useApp";
import { PlayScoreHeader } from "@frontend/components/play/PlayScoreHeader";
import { RoundResultBanner } from "@frontend/components/play/RoundResultBanner";

interface Props {
  onGameEnd: () => void;
  sessionConfig?: Record<string, unknown> | null;
}

export default function BlottoPlayView({ onGameEnd, sessionConfig }: Props) {
  const { humanPlayer, isMyTurn, isComplete, isSubmitting, hasSubmittedThisRound, submitError, lastRoundResult, round, roundTotal, submitMove, currentState } = useInteractivePlay();
  const { state } = useApp();
  const match = state.activeMatch;

  const numFields = (match?.num_battlefields) || (sessionConfig?.num_battlefields as number) || 5;
  const totalResources = (match?.total_resources) || (sessionConfig?.total_resources as number) || 100;

  const budgets = currentState?.budgets as Record<string, number> | undefined;
  const budget = humanPlayer && budgets ? (budgets[humanPlayer] ?? totalResources) : totalResources;

  const [allocations, setAllocations] = useState<number[]>(() => Array(numFields).fill(0));

  useEffect(() => {
    setAllocations(Array(numFields).fill(0));
  }, [numFields, round]);

  useEffect(() => {
    if (isComplete) onGameEnd();
  }, [isComplete, onGameEnd]);

  const total = allocations.reduce((s, v) => s + v, 0);
  const remaining = budget - total;
  const isValid = remaining === 0;

  const set = (i: number, v: number) => {
    setAllocations((prev) => {
      const next = [...prev];
      next[i] = Math.max(0, Math.min(v, budget));
      return next;
    });
  };

  const distributeEvenly = () => {
    const base = Math.floor(budget / numFields);
    const extra = budget - base * numFields;
    setAllocations(Array(numFields).fill(base).map((v, i) => i < extra ? v + 1 : v));
  };

  const handleSubmit = () => {
    submitMove(allocations);
  };

  return (
    <div className="flex flex-col h-full bg-surface-soft">
      <PlayScoreHeader match={match} humanPlayer={humanPlayer} isMyTurn={isMyTurn} round={round} roundTotal={roundTotal} />

      {lastRoundResult && <RoundResultBanner result={lastRoundResult} humanPlayer={humanPlayer} />}
      {submitError && (
        <div className="shrink-0 mx-4 mt-2 px-3 py-2 rounded-lg bg-red-50 dark:bg-red-950/30 border border-red-200 dark:border-red-800/40 text-xs text-red-600 dark:text-red-400">
          {submitError}
        </div>
      )}

      <div className="flex-1 flex flex-col min-h-0">
        {/* Resource tracker */}
        <div className={`shrink-0 mx-4 mt-3 rounded-lg border p-2.5 flex items-center justify-between ${
          remaining < 0 ? "border-red-400 bg-red-50 dark:border-red-700 dark:bg-red-950/20"
          : remaining === 0 ? "border-emerald-400 bg-emerald-50 dark:border-emerald-700 dark:bg-emerald-950/20"
          : "border-line bg-surface"
        }`}>
          <span className="text-xs font-bold text-muted">Resources allocated</span>
          <span className={`text-sm font-black tabular-nums ${remaining < 0 ? "text-red-500" : remaining === 0 ? "text-emerald-600 dark:text-emerald-400" : "text-ink"}`}>
            {total} / {budget}
            {remaining > 0 && <span className="text-muted font-normal text-xs ml-1">({remaining} left)</span>}
          </span>
        </div>

        {/* Battlefield inputs */}
        <div className="flex-1 overflow-y-auto p-4 space-y-2">
          {allocations.map((val, i) => (
            <div key={i} className="flex items-center gap-3">
              <span className="text-[11px] font-extrabold text-muted w-24 shrink-0">
                Field {i + 1}
              </span>
              <input
                type="range"
                min={0}
                max={budget}
                value={val}
                onChange={(e) => set(i, Number(e.target.value))}
                disabled={!isMyTurn || isSubmitting || hasSubmittedThisRound}
                className="flex-1 accent-accent"
              />
              <input
                type="number"
                value={val}
                min={0}
                max={budget}
                onChange={(e) => set(i, Number(e.target.value))}
                disabled={!isMyTurn || isSubmitting || hasSubmittedThisRound}
                className="w-16 text-center text-sm font-bold border border-line rounded-lg px-2 py-1 bg-surface text-ink focus:outline-none focus:border-accent/60 disabled:opacity-50"
              />
            </div>
          ))}
        </div>

        {/* Footer */}
        {isMyTurn && !hasSubmittedThisRound && (
          <div className="shrink-0 border-t border-line/30 p-3 flex gap-2">
            <button
              type="button"
              onClick={distributeEvenly}
              disabled={isSubmitting}
              className="px-3 py-2 rounded-lg border border-line text-xs font-semibold text-muted hover:bg-surface-soft disabled:opacity-40 transition-colors"
            >
              Distribute evenly
            </button>
            <button
              type="button"
              onClick={handleSubmit}
              disabled={isSubmitting || !isValid || !isMyTurn}
              className="flex-1 py-2 rounded-[var(--radius-button)] bg-accent text-white text-sm font-extrabold hover:bg-accent/90 disabled:opacity-40 disabled:cursor-not-allowed transition-all"
            >
              {isSubmitting ? "Submitting..." : "Deploy Forces"}
            </button>
          </div>
        )}
        {hasSubmittedThisRound && !isSubmitting && (
          <div className="shrink-0 p-3 text-center text-xs text-muted border-t border-line/30 animate-pulse">
            Forces deployed — waiting for next round...
          </div>
        )}
        {!isMyTurn && !hasSubmittedThisRound && !isComplete && (
          <div className="shrink-0 p-3 text-center text-xs text-muted border-t border-line/30">
            Waiting for opponent...
          </div>
        )}
      </div>
    </div>
  );
}
