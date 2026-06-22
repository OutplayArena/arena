import { useEffect, useState } from "react";
import { useInteractivePlay } from "@frontend/hooks/useInteractivePlay";
import { useApp } from "@frontend/hooks/useApp";
import { PlayScoreHeader } from "@frontend/components/play/PlayScoreHeader";
import { RoundResultBanner } from "@frontend/components/play/RoundResultBanner";

interface Props {
  onGameEnd: () => void;
  sessionConfig?: Record<string, unknown> | null;
}

export default function CournotPlayView({ onGameEnd, sessionConfig }: Props) {
  const { humanPlayer, isMyTurn, isComplete, isSubmitting, hasSubmittedThisRound, submitError, lastRoundResult, round, roundTotal, submitMove } = useInteractivePlay();
  const { state } = useApp();
  const match = state.activeMatch;

  const a = (sessionConfig?.demand_a as number) ?? 120;
  const b = (sessionConfig?.demand_b as number) ?? 1;
  const c = (sessionConfig?.cost_per_unit as number) ?? 0;
  const maxQ = (sessionConfig?.max_quantity as number) ?? 120;

  // Nash equilibrium quantity: q* = (a - c) / (3b)
  const nashQ = Math.round((a - c) / (3 * b));

  const [quantity, setQuantity] = useState(nashQ);

  useEffect(() => {
    setQuantity(nashQ);
  }, [nashQ]);

  useEffect(() => {
    if (isComplete) onGameEnd();
  }, [isComplete, onGameEnd]);

  // Estimate profit assuming opponent plays Nash
  const totalQ = quantity + nashQ;
  const price = Math.max(0, a - b * totalQ);
  const estimatedProfit = Math.max(0, (price - c) * quantity);

  return (
    <div className="flex flex-col h-full bg-surface-soft">
      <PlayScoreHeader match={match} humanPlayer={humanPlayer} isMyTurn={isMyTurn} round={round} roundTotal={roundTotal} />

      {lastRoundResult && <RoundResultBanner result={lastRoundResult} humanPlayer={humanPlayer} />}
      {submitError && (
        <div className="shrink-0 mx-4 mt-2 px-3 py-2 rounded-lg bg-red-50 dark:bg-red-950/30 border border-red-200 dark:border-red-800/40 text-xs text-red-600 dark:text-red-400">
          {submitError}
        </div>
      )}

      <div className="flex-1 flex flex-col items-center justify-center gap-5 p-6">
        {/* Quantity slider */}
        <div className="w-full max-w-sm">
          <div className="flex justify-between text-xs text-muted mb-2">
            <span>0</span>
            <div className="text-center">
              <div className="text-2xl font-black text-ink tabular-nums">{quantity}</div>
              <div className="text-[10px]">units</div>
            </div>
            <span>{maxQ}</span>
          </div>

          <div className="relative">
            {/* Nash equilibrium marker */}
            <div
              className="absolute top-0 -translate-x-1/2 -translate-y-1 w-0.5 h-4 bg-amber-400"
              style={{ left: `${(nashQ / maxQ) * 100}%` }}
              title={`Nash: ${nashQ}`}
            />
            <input
              type="range"
              min={0}
              max={maxQ}
              value={quantity}
              onChange={(e) => setQuantity(Number(e.target.value))}
              disabled={!isMyTurn || isSubmitting || hasSubmittedThisRound}
              className="w-full accent-accent"
            />
          </div>

          <div className="flex items-center gap-1.5 mt-1">
            <div className="w-0.5 h-3 bg-amber-400 shrink-0" />
            <span className="text-[10px] text-muted">Nash equilibrium ({nashQ} units)</span>
          </div>
        </div>

        {/* Profit estimate */}
        <div className="rounded-[var(--radius-card)] border border-line bg-surface p-4 w-full max-w-sm">
          <div className="text-[10px] font-extrabold uppercase tracking-widest text-muted mb-2">Profit estimate (if opp plays Nash)</div>
          <div className="grid grid-cols-3 gap-2 text-center text-xs">
            <div>
              <div className="font-black text-ink tabular-nums">{quantity}</div>
              <div className="text-muted">Your Q</div>
            </div>
            <div>
              <div className="font-black text-ink tabular-nums">{price.toFixed(1)}</div>
              <div className="text-muted">Price</div>
            </div>
            <div>
              <div className={`font-black tabular-nums ${estimatedProfit > 0 ? "text-emerald-600 dark:text-emerald-400" : "text-red-500"}`}>
                {estimatedProfit.toFixed(0)}
              </div>
              <div className="text-muted">Profit</div>
            </div>
          </div>
        </div>

        <button
          type="button"
          onClick={() => submitMove(quantity)}
          disabled={!isMyTurn || isSubmitting || hasSubmittedThisRound}
          className="w-full max-w-sm py-3 rounded-[var(--radius-button)] bg-accent text-white font-extrabold text-sm hover:bg-accent/90 disabled:opacity-40 disabled:cursor-not-allowed transition-all hover:not-disabled:-translate-y-0.5 hover:not-disabled:shadow-lg"
        >
          {isSubmitting ? "Producing..." : hasSubmittedThisRound ? "Production set..." : `Produce ${quantity} units`}
        </button>

        {hasSubmittedThisRound && !isSubmitting && <p className="text-xs text-muted animate-pulse">Quantity submitted — waiting for next round...</p>}
        {!isMyTurn && !hasSubmittedThisRound && !isComplete && (
          <p className="text-xs text-muted">Waiting for opponent...</p>
        )}
      </div>
    </div>
  );
}
