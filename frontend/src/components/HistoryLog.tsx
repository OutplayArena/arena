import { useApp } from "../hooks/useApp";

export function HistoryLog() {
  const { state } = useApp();
  const { activeMatch, activeRoundIndex } = state;

  const rounds = activeMatch
    ? activeMatch.history
        .slice(0, activeRoundIndex + 1)
        .map((r, i) => ({ ...r, displayIndex: i }))
        .reverse()
    : [];

  return (
    <div className="grid gap-[8px]">
      <p className="text-accent text-[10px] font-extrabold uppercase tracking-widest m-0">
        history
      </p>
      <ol className="grid grid-cols-1 gap-2 p-0 m-0 list-none">
        {rounds.map((round) => (
          <li
            key={round.round}
            className={
              "min-h-[40px] p-[9px_10px] border rounded-input font-mono text-[11px] leading-relaxed text-muted shadow-elevation-1 " +
              (round.winner === "A"
                ? "border-agent-a/30 bg-gradient-to-br from-agent-a-soft to-surface-container"
                : round.winner === "B"
                  ? "border-agent-b/30 bg-gradient-to-br from-agent-b-soft to-surface-container"
                  : "border-line/40 bg-surface-container")
            }
          >
            round={round.round} winner={round.winner} score_a={round.score_a}{" "}
            score_b={round.score_b}
          </li>
        ))}
      </ol>
    </div>
  );
}
