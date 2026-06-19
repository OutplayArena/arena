import { useEffect, useState } from "react";
import { useInteractivePlay } from "@frontend/hooks/useInteractivePlay";
import { useApp } from "@frontend/hooks/useApp";
import { PlayScoreHeader } from "@frontend/components/play/PlayScoreHeader";
import { RoundResultBanner } from "@frontend/components/play/RoundResultBanner";

interface Props {
  onGameEnd: () => void;
  sessionConfig?: Record<string, unknown> | null;
}

export default function UltimatumPlayView({ onGameEnd, sessionConfig }: Props) {
  const { humanPlayer, isMyTurn, isComplete, isSubmitting, hasSubmittedThisRound, submitError, lastRoundResult, round, roundTotal, submitMove, currentState } = useInteractivePlay();
  const { state } = useApp();
  const match = state.activeMatch;

  const total = (sessionConfig?.total as number) ?? 100;
  const minOffer = (sessionConfig?.min_offer as number) ?? 1;

  const phase = (currentState?.phase as string) ?? "awaiting_proposal";
  const proposer = (currentState?.proposer as string) ?? "A";
  const pendingOffer = currentState?.pending_offer as number | undefined;

  const isProposer = humanPlayer === proposer;
  const isResponder = humanPlayer !== proposer && isMyTurn;

  const [offerAmount, setOfferAmount] = useState(Math.round(total / 2));

  useEffect(() => {
    setOfferAmount(Math.round(total / 2));
  }, [total, round]);

  useEffect(() => {
    if (isComplete) onGameEnd();
  }, [isComplete, onGameEnd]);

  const keepAmount = total - offerAmount;

  const renderProposer = () => (
    <div className="flex flex-col items-center gap-5 p-6 w-full max-w-sm mx-auto">
      <p className="text-xs font-semibold text-muted">You are the Proposer — split {total} pts</p>

      <div className="w-full rounded-[var(--radius-card)] border border-line bg-surface p-4">
        <div className="flex justify-between text-sm font-bold mb-3">
          <span className="text-agent-a">You keep: <span className="text-lg tabular-nums">{keepAmount}</span></span>
          <span className="text-agent-b">Offer: <span className="text-lg tabular-nums">{offerAmount}</span></span>
        </div>

        {/* Visual split bar */}
        <div className="w-full h-4 rounded-full bg-line/20 overflow-hidden mb-3">
          <div
            className="h-full bg-agent-a rounded-full transition-all"
            style={{ width: `${(keepAmount / total) * 100}%` }}
          />
        </div>

        <input
          type="range"
          min={0}
          max={total}
          step={minOffer}
          value={offerAmount}
          onChange={(e) => setOfferAmount(Number(e.target.value))}
          disabled={isSubmitting}
          className="w-full accent-accent"
        />
        <div className="flex justify-between text-[10px] text-muted mt-1">
          <span>0</span>
          <span>{total}</span>
        </div>
      </div>

      <button
        type="button"
        onClick={() => submitMove({ offer: offerAmount })}
        disabled={isSubmitting || !isMyTurn || hasSubmittedThisRound}
        className="w-full py-3 rounded-[var(--radius-button)] bg-accent text-white font-extrabold text-sm hover:bg-accent/90 disabled:opacity-40 disabled:cursor-not-allowed transition-all hover:not-disabled:-translate-y-0.5 hover:not-disabled:shadow-lg"
      >
        {isSubmitting ? "Proposing..." : hasSubmittedThisRound ? "Proposal submitted..." : `Offer ${offerAmount} pts`}
      </button>
    </div>
  );

  const renderResponder = () => (
    <div className="flex flex-col items-center gap-5 p-6 w-full max-w-sm mx-auto">
      <p className="text-xs font-semibold text-muted">You are the Responder</p>

      {pendingOffer !== undefined ? (
        <>
          <div className="w-full rounded-[var(--radius-card)] border border-accent/30 bg-accent/5 p-5 text-center">
            <div className="text-xs text-muted mb-1">You were offered</div>
            <div className="text-4xl font-black text-accent tabular-nums">{pendingOffer}</div>
            <div className="text-xs text-muted mt-1">out of {total} pts</div>
            <div className="mt-2 text-xs text-muted">
              Opponent keeps {(total - pendingOffer).toFixed(0)} pts
            </div>
          </div>

          <div className="flex gap-3 w-full">
            <button
              type="button"
              onClick={() => submitMove({ accept: true })}
              disabled={isSubmitting || !isMyTurn || hasSubmittedThisRound}
              className="flex-1 py-3 rounded-[var(--radius-card)] border-2 border-emerald-400 bg-emerald-50 text-emerald-700 dark:border-emerald-600 dark:bg-emerald-950/30 dark:text-emerald-300 font-extrabold text-sm hover:bg-emerald-100 dark:hover:bg-emerald-900/40 disabled:opacity-40 disabled:cursor-not-allowed transition-all hover:not-disabled:-translate-y-0.5 hover:not-disabled:shadow-lg"
            >
              ✅ Accept
            </button>
            <button
              type="button"
              onClick={() => submitMove({ accept: false })}
              disabled={isSubmitting || !isMyTurn || hasSubmittedThisRound}
              className="flex-1 py-3 rounded-[var(--radius-card)] border-2 border-red-400 bg-red-50 text-red-700 dark:border-red-600 dark:bg-red-950/30 dark:text-red-300 font-extrabold text-sm hover:bg-red-100 dark:hover:bg-red-900/40 disabled:opacity-40 disabled:cursor-not-allowed transition-all hover:not-disabled:-translate-y-0.5 hover:not-disabled:shadow-lg"
            >
              ❌ Reject
            </button>
          </div>
        </>
      ) : (
        <p className="text-xs text-muted">Waiting for opponent's offer...</p>
      )}
    </div>
  );

  return (
    <div className="flex flex-col h-full bg-surface-soft">
      <PlayScoreHeader match={match} humanPlayer={humanPlayer} isMyTurn={isMyTurn} round={round} roundTotal={roundTotal} />

      {lastRoundResult && <RoundResultBanner result={lastRoundResult} humanPlayer={humanPlayer} />}
      {submitError && (
        <div className="shrink-0 mx-4 mt-2 px-3 py-2 rounded-lg bg-red-50 dark:bg-red-950/30 border border-red-200 dark:border-red-800/40 text-xs text-red-600 dark:text-red-400">
          {submitError}
        </div>
      )}

      <div className="flex-1 flex flex-col justify-center">
        {isComplete ? (
          <p className="text-center text-sm text-muted p-6">Game over. Redirecting...</p>
        ) : phase === "awaiting_proposal" && isProposer && isMyTurn ? (
          renderProposer()
        ) : phase === "awaiting_response" && isResponder ? (
          renderResponder()
        ) : (
          <p className="text-center text-xs text-muted p-6">
            {phase === "awaiting_proposal" ? "Opponent is making their proposal..." : "Waiting for opponent's response..."}
          </p>
        )}
      </div>
    </div>
  );
}
