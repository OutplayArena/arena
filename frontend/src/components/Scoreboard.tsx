import type { AnimatedScores } from "../hooks/useCanvasRenderer";
import { useApp } from "../hooks/useApp";

interface ScoreboardProps {
  scores: AnimatedScores;
}

export function Scoreboard({ scores }: ScoreboardProps) {
  const { state } = useApp();
  const round = state.activeMatch?.history[state.activeRoundIndex] ?? null;

  return (
    <div className="grid grid-cols-1 gap-[7px] mt-auto">
      <div className="grid grid-cols-[1fr_auto] items-center min-h-[50px] p-[10px_12px] border rounded-input bg-surface-container shadow-elevation-1 border-line/40 shadow-agent-a/8 dark:shadow-agent-a/10">
        <span className="text-muted text-[10px] font-extrabold uppercase tracking-wider">
          total_score_a
        </span>
        <strong className="text-[22px] leading-none font-black tabular-nums text-agent-a">
          {Math.abs(scores.displayedScoreA - (round?.total_score_a ?? 0)) < 0.03
            ? (round?.total_score_a ?? 0)
            : scores.displayedScoreA.toFixed(1)}
        </strong>
      </div>
      <div className="grid grid-cols-[1fr_auto] items-center min-h-[50px] p-[10px_12px] border rounded-input bg-surface-container shadow-elevation-1 border-line/40">
        <span className="text-muted text-[10px] font-extrabold uppercase tracking-wider">
          round
        </span>
        <strong className="text-[22px] leading-none font-black tabular-nums text-ink">
          {state.activeMatch
            ? `${state.activeRoundIndex + 1} / ${state.activeMatch.num_rounds}`
            : "0 / 0"}
        </strong>
      </div>
      <div className="grid grid-cols-[1fr_auto] items-center min-h-[50px] p-[10px_12px] border rounded-input bg-surface-container shadow-elevation-1 border-line/40 shadow-agent-b/8 dark:shadow-agent-b/10">
        <span className="text-muted text-[10px] font-extrabold uppercase tracking-wider">
          total_score_b
        </span>
        <strong className="text-[22px] leading-none font-black tabular-nums text-agent-b">
          {Math.abs(scores.displayedScoreB - (round?.total_score_b ?? 0)) < 0.03
            ? (round?.total_score_b ?? 0)
            : scores.displayedScoreB.toFixed(1)}
        </strong>
      </div>
    </div>
  );
}
