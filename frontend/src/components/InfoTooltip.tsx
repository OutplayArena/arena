const DESCRIPTIONS: Record<string, string> = {
  elo: "Pairwise rating updated after each match. Multiplayer Elo formula, baseline 1200.",
  alpha_rank: "Evolutionary dominance ranking — stationary distribution of the response graph. Higher mass = more strategically robust.",
  avg_payoff: "Average payoff per round. Higher = better per-round performance.",
  nash_gap: "Distance from best-response payoff. Lower = closer to Nash equilibrium.",
  cumulative_regret: "Payoff lost by not always playing the optimal response. Lower = better.",
  strategy_entropy: "Action diversity (Shannon entropy). Higher = more unpredictable.",
  behavioral_consistency: "How similar actions are across repeated rounds. Higher = more consistent.",
  cooperation_rate: "Fraction of cooperative actions. Only relevant for cooperative games.",
};

export function InfoTooltip({ metricKey }: { metricKey: string }) {
  const desc = DESCRIPTIONS[metricKey];
  if (!desc) return null;

  return (
    <span className="group relative inline-flex items-center ml-1">
      <svg
        width="12"
        height="12"
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
        className="text-muted/50 group-hover:text-muted transition-colors cursor-help"
      >
        <circle cx="12" cy="12" r="10" />
        <line x1="12" y1="16" x2="12" y2="12" />
        <line x1="12" y1="8" x2="12.01" y2="8" />
      </svg>
      <div className="absolute z-20 top-full right-0 mt-1 w-56 px-3 py-2 rounded-[var(--radius-card)] border border-line bg-surface shadow-elevation-4 text-[11px] text-ink leading-relaxed opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none">
        {desc}
      </div>
    </span>
  );
}
