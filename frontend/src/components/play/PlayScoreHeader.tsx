import type { Match, PlayerSide } from "@frontend/types";

interface PlayScoreHeaderProps {
  match: Match | null;
  humanPlayer: PlayerSide | null;
  isMyTurn: boolean;
  round: number;
  roundTotal: number;
}

function agentInitial(name: string): string {
  return (name?.trim().charAt(0) || "?").toUpperCase();
}

export function PlayScoreHeader({ match, humanPlayer, isMyTurn, round, roundTotal }: PlayScoreHeaderProps) {
  const nameA = match?.agent_a ?? "Player A";
  const nameB = match?.agent_b ?? "Player B";
  const scoreA = match?.total_score_a ?? 0;
  const scoreB = match?.total_score_b ?? 0;

  const youSide = humanPlayer;
  const oppSide: PlayerSide | null = humanPlayer === "A" ? "B" : humanPlayer === "B" ? "A" : null;

  const youName = youSide === "A" ? nameA : youSide === "B" ? nameB : null;
  const oppName = oppSide === "A" ? nameA : oppSide === "B" ? nameB : null;
  const youScore = youSide === "A" ? scoreA : youSide === "B" ? scoreB : 0;
  const oppScore = oppSide === "A" ? scoreA : oppSide === "B" ? scoreB : 0;

  return (
    <div className="shrink-0 border-b border-line/40 bg-surface/90 backdrop-blur-sm">
      {/* Players + scores */}
      <div className="flex items-center justify-between px-4 py-2.5 gap-3">
        <div className="flex items-center gap-2 min-w-0">
          <div className="w-7 h-7 rounded-full bg-agent-a/12 border border-agent-a/40 flex items-center justify-center shrink-0">
            <span className="text-[10px] font-black text-agent-a">
              {agentInitial(youSide === "A" ? nameA : nameB)}
            </span>
          </div>
          <div className="min-w-0">
            <div className="text-[11px] font-extrabold text-muted uppercase tracking-wider truncate">
              {youSide ? "You" : "Player A"}
            </div>
            <div className="text-[10px] text-muted/70 truncate">{youName ?? nameA}</div>
          </div>
        </div>

        <div className="flex flex-col items-center gap-0.5 shrink-0">
          <div className="flex items-center gap-2">
            <span className="tabular-nums text-lg font-black text-agent-a">{youSide ? youScore : scoreA}</span>
            <span className="text-xs text-muted">—</span>
            <span className="tabular-nums text-lg font-black text-agent-b">{youSide ? oppScore : scoreB}</span>
          </div>
          <div className="text-[10px] text-muted">
            Round{" "}
            <span className="font-bold text-ink">
              {Math.max(round, match?.history.length ?? 0)}
            </span>
            {" / "}
            <span className="font-bold">{roundTotal || match?.num_rounds}</span>
          </div>
        </div>

        <div className="flex items-center gap-2 min-w-0">
          <div className="min-w-0 text-right">
            <div className="text-[11px] font-extrabold text-muted uppercase tracking-wider truncate">
              {oppSide ? "Opponent" : "Player B"}
            </div>
            <div className="text-[10px] text-muted/70 truncate">{oppName ?? nameB}</div>
          </div>
          <div className="w-7 h-7 rounded-full bg-agent-b/12 border border-agent-b/40 flex items-center justify-center shrink-0">
            <span className="text-[10px] font-black text-agent-b">
              {agentInitial(oppSide === "B" ? nameB : nameA)}
            </span>
          </div>
        </div>
      </div>

      {/* Turn indicator */}
      <div className={`px-4 py-1.5 text-center text-[11px] font-bold border-t border-line/20 transition-colors ${
        isMyTurn
          ? "bg-accent/8 text-accent"
          : "bg-surface-soft/60 text-muted"
      }`}>
        {isMyTurn ? (
          <span className="flex items-center justify-center gap-1.5">
            <span className="w-1.5 h-1.5 rounded-full bg-accent animate-pulse" />
            Your turn — make your move
          </span>
        ) : (
          <span>Waiting for opponent...</span>
        )}
      </div>
    </div>
  );
}
