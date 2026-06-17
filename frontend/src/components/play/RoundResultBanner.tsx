import type { PlayerSide } from "@frontend/types";
import type { RoundResult } from "@frontend/hooks/useInteractivePlay";

interface RoundResultBannerProps {
  result: RoundResult;
  humanPlayer: PlayerSide | null;
}

function formatMove(move: unknown): string {
  if (move === null || move === undefined) return "—";
  if (typeof move === "string") return move;
  if (typeof move === "number") return String(move);
  if (Array.isArray(move)) return `[${move.join(", ")}]`;
  if (typeof move === "object") {
    try { return JSON.stringify(move); } catch { return String(move); }
  }
  return String(move);
}

export function RoundResultBanner({ result, humanPlayer }: RoundResultBannerProps) {
  const isWin = humanPlayer && result.winner === humanPlayer;
  const isLoss = humanPlayer && result.winner !== humanPlayer && result.winner !== "Tie";
  const isDraw = result.winner === "Tie";

  const bgClass = isWin
    ? "bg-emerald-500/10 border-emerald-500/30 text-emerald-700 dark:text-emerald-400"
    : isLoss
      ? "bg-red-500/10 border-red-500/30 text-red-700 dark:text-red-400"
      : "bg-gold/10 border-gold/30 text-amber-700 dark:text-amber-400";

  const label = isWin ? "You won" : isLoss ? "Opponent won" : isDraw ? "Draw" : "Round over";
  const sign = result.scoreYou > 0 ? "+" : "";

  const yourMoveStr = formatMove(result.yourMove);
  const oppMoveStr = formatMove(result.oppMove);

  return (
    <div className={`mx-3 mt-2 px-3 py-2 rounded-lg border text-xs font-semibold flex items-center justify-between gap-3 transition-all ${bgClass}`}>
      <div className="flex items-center gap-2 min-w-0">
        <span className="font-extrabold">{label}</span>
        {result.scoreYou !== undefined && (
          <span className="text-[11px] opacity-70">{sign}{result.scoreYou} pts</span>
        )}
      </div>
      <div className="flex items-center gap-2 text-[10px] opacity-70 shrink-0">
        {yourMoveStr && <span>You: {yourMoveStr}</span>}
        {oppMoveStr && yourMoveStr && <span>·</span>}
        {oppMoveStr && <span>Opp: {oppMoveStr}</span>}
      </div>
    </div>
  );
}
