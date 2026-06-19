import { useEffect, useState } from "react";
import { useInteractivePlay } from "@frontend/hooks/useInteractivePlay";
import { useApp } from "@frontend/hooks/useApp";
import { PlayScoreHeader } from "@frontend/components/play/PlayScoreHeader";
import { RoundResultBanner } from "@frontend/components/play/RoundResultBanner";

interface Props {
  onGameEnd: () => void;
  sessionConfig?: Record<string, unknown> | null;
}

const SUIT_SYMBOL: Record<string, string> = { s: "♠", h: "♥", d: "♦", c: "♣" };
const SUIT_COLOR: Record<string, string> = { s: "text-ink", h: "text-red-500", d: "text-red-500", c: "text-ink" };
const STREET_LABEL: Record<string, string> = { preflop: "Pre-Flop", flop: "Flop", turn: "Turn", river: "River" };

function CardDisplay({ card }: { card: string }) {
  const rank = card.slice(0, -1).toUpperCase();
  const suit = card.slice(-1).toLowerCase();
  return (
    <div className={`w-10 h-14 rounded-lg border-2 border-line bg-surface flex flex-col items-center justify-center shadow-sm ${SUIT_COLOR[suit] ?? "text-ink"}`}>
      <span className="text-xs font-black leading-none">{rank}</span>
      <span className="text-sm leading-none">{SUIT_SYMBOL[suit] ?? suit}</span>
    </div>
  );
}

function CardBack() {
  return (
    <div className="w-10 h-14 rounded-lg border-2 border-line bg-surface-container flex items-center justify-center shadow-sm">
      <span className="text-muted text-lg">🂠</span>
    </div>
  );
}

export default function TexasHoldEmPlayView({ onGameEnd }: Props) {
  const { humanPlayer, isMyTurn, isComplete, isSubmitting, hasSubmittedThisRound, submitError, lastRoundResult, round, roundTotal, submitMove, currentState } = useInteractivePlay();
  const { state } = useApp();
  const match = state.activeMatch;

  const [raiseAmount, setRaiseAmount] = useState(2);
  const [showRaise, setShowRaise] = useState(false);

  const street = (currentState?.street as string) ?? "preflop";
  const pot = (currentState?.pot as number) ?? 0;
  const chips = (currentState?.chips as Record<string, number>) ?? {};
  const myChips = humanPlayer ? (chips[humanPlayer] ?? 0) : 0;
  const communityCards = (currentState?.community_cards as string[]) ?? [];
  const playerCards = (currentState?.player_cards as string[]) ?? [];
  const validActions = (currentState?.valid_actions as string[]) ?? ["fold", "check", "call", "raise"];

  useEffect(() => {
    if (isComplete) onGameEnd();
  }, [isComplete, onGameEnd]);

  const handleAction = (action: string, amount?: number) => {
    if (action === "raise" && amount !== undefined) {
      submitMove({ action: "raise", raise_amount: amount });
    } else {
      submitMove(action);
    }
    setShowRaise(false);
  };

  const canFold = validActions.includes("fold");
  const canCheck = validActions.includes("check");
  const canCall = validActions.includes("call");
  const canRaise = validActions.includes("raise");

  return (
    <div className="flex flex-col h-full bg-surface-soft">
      <PlayScoreHeader match={match} humanPlayer={humanPlayer} isMyTurn={isMyTurn} round={round} roundTotal={roundTotal} />

      {lastRoundResult && <RoundResultBanner result={lastRoundResult} humanPlayer={humanPlayer} />}
      {submitError && (
        <div className="shrink-0 mx-4 mt-2 px-3 py-2 rounded-lg bg-red-50 dark:bg-red-950/30 border border-red-200 dark:border-red-800/40 text-xs text-red-600 dark:text-red-400">
          {submitError}
        </div>
      )}

      <div className="flex-1 flex flex-col gap-4 p-4 overflow-y-auto">
        {/* Street + pot info */}
        <div className="flex items-center justify-between px-4 py-2 rounded-lg border border-line bg-surface text-xs">
          <span className="font-extrabold uppercase tracking-wider text-muted">{STREET_LABEL[street] ?? street}</span>
          <span className="font-black text-ink">Pot: <span className="text-accent">{pot}</span></span>
          <span className="text-muted">Your chips: <span className="font-bold text-ink">{myChips}</span></span>
        </div>

        {/* Community cards */}
        <div>
          <div className="text-[10px] font-extrabold uppercase tracking-widest text-muted mb-2">Community</div>
          <div className="flex gap-1.5 flex-wrap">
            {communityCards.map((card, i) => <CardDisplay key={i} card={card} />)}
            {Array(5 - communityCards.length).fill(null).map((_, i) => <CardBack key={`back-${i}`} />)}
          </div>
        </div>

        {/* Your hole cards */}
        {playerCards.length > 0 && (
          <div>
            <div className="text-[10px] font-extrabold uppercase tracking-widest text-muted mb-2">Your Hand</div>
            <div className="flex gap-1.5">
              {playerCards.map((card, i) => <CardDisplay key={i} card={card} />)}
            </div>
          </div>
        )}

        {/* Action buttons */}
        <div className="mt-auto space-y-3">
          {isMyTurn && !isSubmitting && !hasSubmittedThisRound ? (
            <>
              <div className="flex gap-2">
                {canFold && (
                  <button
                    type="button"
                    onClick={() => handleAction("fold")}
                    className="flex-1 py-2.5 rounded-lg border-2 border-red-300 bg-red-50 text-red-700 dark:border-red-700 dark:bg-red-950/30 dark:text-red-300 font-bold text-sm transition-all hover:-translate-y-0.5 hover:shadow-md"
                  >
                    Fold
                  </button>
                )}
                {canCheck && (
                  <button
                    type="button"
                    onClick={() => handleAction("check")}
                    className="flex-1 py-2.5 rounded-lg border-2 border-slate-300 bg-slate-50 text-slate-700 dark:border-slate-600 dark:bg-slate-900/30 dark:text-slate-300 font-bold text-sm transition-all hover:-translate-y-0.5 hover:shadow-md"
                  >
                    Check
                  </button>
                )}
                {canCall && (
                  <button
                    type="button"
                    onClick={() => handleAction("call")}
                    className="flex-1 py-2.5 rounded-lg border-2 border-emerald-300 bg-emerald-50 text-emerald-700 dark:border-emerald-700 dark:bg-emerald-950/30 dark:text-emerald-300 font-bold text-sm transition-all hover:-translate-y-0.5 hover:shadow-md"
                  >
                    Call
                  </button>
                )}
                {canRaise && (
                  <button
                    type="button"
                    onClick={() => setShowRaise((v) => !v)}
                    className="flex-1 py-2.5 rounded-lg border-2 border-accent/50 bg-accent/5 text-accent font-bold text-sm transition-all hover:-translate-y-0.5 hover:shadow-md"
                  >
                    Raise
                  </button>
                )}
              </div>

              {showRaise && canRaise && (
                <div className="flex gap-2 items-center">
                  <input
                    type="number"
                    value={raiseAmount}
                    min={2}
                    max={myChips}
                    onChange={(e) => setRaiseAmount(Number(e.target.value))}
                    className="flex-1 px-3 py-2 rounded-lg border border-line bg-surface text-ink text-center font-bold focus:outline-none focus:border-accent/60"
                  />
                  <button
                    type="button"
                    onClick={() => handleAction("raise", raiseAmount)}
                    className="px-4 py-2 rounded-[var(--radius-button)] bg-accent text-white font-bold text-sm hover:bg-accent/90"
                  >
                    Raise {raiseAmount}
                  </button>
                </div>
              )}
            </>
          ) : (
            <p className="text-center text-xs text-muted py-4">
              {isSubmitting ? "Submitting..." : hasSubmittedThisRound ? "Action submitted — waiting for next street..." : isComplete ? "Hand over..." : "Waiting for opponent..."}
            </p>
          )}
        </div>
      </div>
    </div>
  );
}
