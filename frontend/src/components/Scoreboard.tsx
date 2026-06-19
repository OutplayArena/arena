import { memo } from "react";
import type { AnimatedScores } from "../hooks/useCanvasRenderer";
import { useApp } from "../hooks/useApp";

interface ScoreboardProps {
  scores: AnimatedScores;
}

export const Scoreboard = memo(function Scoreboard({ scores }: ScoreboardProps) {
  const { state } = useApp();
  const round = state.activeMatch?.history[state.activeRoundIndex] ?? null;

  const scoreA = Math.abs(scores.displayedScoreA - (round?.total_score_a ?? 0)) < 0.03
    ? (round?.total_score_a ?? 0)
    : scores.displayedScoreA.toFixed(1);
  const scoreB = Math.abs(scores.displayedScoreB - (round?.total_score_b ?? 0)) < 0.03
    ? (round?.total_score_b ?? 0)
    : scores.displayedScoreB.toFixed(1);

  const roundNum = state.activeMatch ? state.activeRoundIndex + 1 : 0;
  const totalRounds = state.activeMatch?.num_rounds ?? state.pendingGame?.numRounds ?? 0;

  return (
    <div className="flex flex-col gap-1.5 mt-auto">
      {/* Agent A */}
      <div className="flex items-center justify-between px-3 py-2.5 rounded-[var(--radius-card)] border border-line bg-surface">
        <span className="text-[10px] font-mono font-medium text-muted uppercase tracking-wide">Agent A</span>
        <strong className="text-xl font-bold tabular-nums text-agent-a">{scoreA}</strong>
      </div>

      {/* Round counter */}
      <div className="flex items-center justify-between px-3 py-2 rounded-[var(--radius-chip)] bg-surface-container">
        <span className="text-[10px] font-mono text-muted uppercase tracking-wide">Round</span>
        <span className="text-xs font-mono font-semibold text-ink">
          {totalRounds > 0 ? `${roundNum} / ${totalRounds}` : "—"}
        </span>
      </div>

      {/* Agent B */}
      <div className="flex items-center justify-between px-3 py-2.5 rounded-[var(--radius-card)] border border-line bg-surface">
        <span className="text-[10px] font-mono font-medium text-muted uppercase tracking-wide">Agent B</span>
        <strong className="text-xl font-bold tabular-nums text-agent-b">{scoreB}</strong>
      </div>
    </div>
  );
});
