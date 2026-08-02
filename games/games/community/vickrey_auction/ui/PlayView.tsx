import { useEffect, useState } from "react";
import { useInteractivePlay } from "@frontend/hooks/useInteractivePlay";
import { useApp } from "@frontend/hooks/useApp";
import { RoundResultBanner } from "@frontend/components/play/RoundResultBanner";

interface Props {
  onGameEnd: () => void;
  sessionConfig?: Record<string, unknown> | null;
}

const PLAYER_COLORS: Record<string, string> = {
  A: "text-agent-a",
  B: "text-agent-b",
  C: "text-violet-500",
  D: "text-amber-500",
  E: "text-rose-500",
  F: "text-sky-500",
  G: "text-teal-500",
  H: "text-orange-500",
};

export default function VickreyAuctionPlayView({ onGameEnd, sessionConfig }: Props) {
  const { humanPlayer, opponentPlayers, currentState, isMyTurn, isComplete, isSubmitting, hasSubmittedThisRound, submitError, lastRoundResult, totalScores, round, roundTotal, submitMove, awaiting } = useInteractivePlay();
  const { state } = useApp();
  const match = state.activeMatch;

  const maxBid = (sessionConfig?.max_bid as number) ?? 200;
  const privateValues = (currentState?.private_values as Record<string, number> | undefined) ?? {};
  const myValue = humanPlayer ? (privateValues[humanPlayer] ?? 0) : 0;

  const [bid, setBid] = useState(myValue);

  useEffect(() => {
    setBid(myValue);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [myValue, round]);

  useEffect(() => {
    if (isComplete) onGameEnd();
  }, [isComplete, onGameEnd]);

  const waitingFor = awaiting.filter((p) => p !== humanPlayer);
  const estimatedSurplus = myValue - bid >= 0 ? myValue - bid : 0;

  return (
    <div className="flex flex-col h-full bg-surface-soft">
      <div className="shrink-0 border-b border-line bg-surface/90 backdrop-blur-sm">
        <div className="grid grid-cols-2 gap-2 px-4 py-2.5">
          <div className="flex items-center gap-2">
            <div className="w-7 h-7 rounded-full bg-accent/12 border border-accent/40 flex items-center justify-center shrink-0">
              <span className="text-[10px] font-black text-accent">{humanPlayer ?? "?"}</span>
            </div>
            <div className="min-w-0">
              <div className="text-[11px] font-extrabold text-muted uppercase tracking-wider">You</div>
              <div className="text-lg font-black text-accent tabular-nums">{(totalScores[humanPlayer ?? ""] ?? 0).toFixed(1)}</div>
            </div>
          </div>
          <div className="flex flex-col gap-0.5">
            {opponentPlayers.map((pid) => (
              <div key={pid} className="flex items-center gap-1.5">
                <span className={`w-5 h-5 rounded-full flex items-center justify-center text-[8px] font-black border border-line/30 ${PLAYER_COLORS[pid] ?? "text-muted"}`}>{pid}</span>
                <span className="text-[10px] font-mono text-muted tabular-nums">{(totalScores[pid] ?? 0).toFixed(1)}</span>
              </div>
            ))}
          </div>
        </div>
        <div className="flex items-center justify-between px-4 pb-2">
          <div className="text-[10px] text-muted">
            Round <span className="font-bold text-ink">{Math.max(round, match?.history.length ?? 0)}</span>
            {" / "}
            <span className="font-bold">{roundTotal || match?.num_rounds}</span>
          </div>
        </div>
        <div className={`px-4 py-1.5 text-center text-[11px] font-bold border-t border-line/50 transition-colors ${
          isMyTurn ? "bg-accent/8 text-accent" : "bg-surface-soft/60 text-muted"
        }`}>
          {isMyTurn ? (
            <span className="flex items-center justify-center gap-1.5">
              <span className="w-1.5 h-1.5 rounded-full bg-accent animate-pulse" />
              Your turn — submit your sealed bid
            </span>
          ) : (
            <span>Waiting for {waitingFor.length > 0 ? `player${waitingFor.length > 1 ? "s" : ""} ${waitingFor.join(", ")}` : "other bidders"}...</span>
          )}
        </div>
      </div>

      {lastRoundResult && <RoundResultBanner result={lastRoundResult} humanPlayer={humanPlayer} />}
      {submitError && (
        <div className="shrink-0 mx-4 mt-2 px-3 py-2 rounded-lg bg-red-50 dark:bg-red-950/30 border border-red-200 dark:border-red-800/40 text-xs text-red-600 dark:text-red-400">
          {submitError}
        </div>
      )}

      <div className="flex-1 flex flex-col items-center justify-center gap-5 p-6">
        <div className="w-full max-w-sm rounded-[var(--radius-card)] border border-line bg-surface p-4">
          <div className="text-[10px] font-extrabold uppercase tracking-widest text-muted mb-3">
            Your private value this round: <span className="text-accent">{myValue.toFixed(1)}</span>
          </div>

          <div className="flex justify-between text-xs mb-2">
            <span className="text-muted">Your bid: <span className="font-black text-ink tabular-nums">{bid.toFixed(1)}</span></span>
            <span className="text-muted">Bid ceiling: <span className="font-black tabular-nums">{maxBid.toFixed(1)}</span></span>
          </div>

          <input
            type="range"
            min={0}
            max={maxBid}
            step={0.5}
            value={bid}
            onChange={(e) => setBid(Number(e.target.value))}
            disabled={!isMyTurn || isSubmitting || hasSubmittedThisRound}
            className="w-full accent-accent"
          />
          <div className="flex justify-between text-[10px] text-muted mt-1">
            <span>0</span>
            <span>{maxBid.toFixed(0)}</span>
          </div>
          <button
            type="button"
            onClick={() => setBid(myValue)}
            disabled={!isMyTurn || isSubmitting || hasSubmittedThisRound}
            className="mt-2 text-[10px] font-bold text-accent hover:underline disabled:opacity-40 disabled:cursor-not-allowed"
          >
            Bid my true value ({myValue.toFixed(1)})
          </button>
        </div>

        <div className="rounded-[var(--radius-card)] border border-line bg-surface p-4 w-full max-w-sm">
          <div className="text-[10px] font-extrabold uppercase tracking-widest text-muted mb-2">
            If you win at a price equal to your bid
          </div>
          <div className="grid grid-cols-2 gap-2 text-center text-xs">
            <div>
              <div className="font-black text-ink tabular-nums">{myValue.toFixed(1)}</div>
              <div className="text-muted">Your value</div>
            </div>
            <div>
              <div className={`font-black tabular-nums ${estimatedSurplus > 0 ? "text-emerald-600 dark:text-emerald-400" : "text-amber-600 dark:text-amber-400"}`}>
                {(myValue - bid).toFixed(1)}
              </div>
              <div className="text-muted">Worst-case surplus</div>
            </div>
          </div>
          <div className="text-[10px] text-muted mt-2 text-center">
            You actually pay the second-highest bid, so your real surplus if you win is usually higher than this.
          </div>
        </div>

        <button
          type="button"
          onClick={() => submitMove(bid)}
          disabled={!isMyTurn || isSubmitting || hasSubmittedThisRound}
          className="w-full max-w-sm py-3 rounded-[var(--radius-button)] bg-accent text-white font-extrabold text-sm hover:bg-accent/90 disabled:opacity-40 disabled:cursor-not-allowed transition-all hover:not-disabled:-translate-y-0.5 hover:not-disabled:shadow-lg"
        >
          {isSubmitting ? "Bidding..." : hasSubmittedThisRound ? "Bid submitted..." : `Bid ${bid.toFixed(1)}`}
        </button>

        {hasSubmittedThisRound && !isSubmitting && <p className="text-xs text-muted animate-pulse">Bid submitted — waiting for next round...</p>}
      </div>
    </div>
  );
}
