export const METRIC_LABELS: Record<string, string> = {
  avg_payoff: "Avg Payoff",
  nash_gap: "Nash Gap",
  cumulative_regret: "Regret",
  strategy_entropy: "Entropy",
  behavioral_consistency: "Consistency",
  cooperation_rate: "Cooperation",
};

export function formatMetric(key: string, val: number): string {
  if (key === "cooperation_rate") return (val * 100).toFixed(0) + "%";
  if (key === "nash_gap" || key === "cumulative_regret") return val.toFixed(3);
  return val.toFixed(2);
}

export function detectMetricKeys(rows: Array<{ metrics?: Record<string, number> }>): string[] {
  for (const row of rows) {
    const m = row.metrics;
    if (m) return Object.keys(m).filter((k) => METRIC_LABELS[k]);
  }
  return [];
}

export interface LeaderboardTableRow {
  agentId: string;
  /** Display name (model name without @username suffix). */
  displayName?: string;
  /** Public handle of the owning user, shown as attribution in public scope. */
  ownerUsername?: string | null;
  /** Whether this row belongs to the currently logged-in user. */
  isOwn?: boolean;
  matches_played: number;
  elo: number;
  alpha_rank: number | null;
  metrics?: Record<string, number>;
}

export interface LeaderboardTableProps {
  rows: LeaderboardTableRow[];
  /** Total matches recorded (shown in the footer). */
  totalMatches: number;
  loading: boolean;
  error: string | null;
  onRetry?: () => void;
  note?: string;
  /** Shown to the right of the matches count in the footer. */
  footerTrailing?: React.ReactNode;
  /** Shown beneath the empty message. */
  emptyAction?: React.ReactNode;
  /** Optional CSS class for the table wrapper. */
  className?: string;
  /** Number of shimmer rows to show while loading. */
  loadingRows?: number;
  /** Show a dedicated "Owner" column with attribution (use for public/all scopes). */
  showOwnerColumn?: boolean;
  /** Show the "You" badge on the viewer's own rows (personal display preference, default off/hidden). */
  showOwnBadge?: boolean;
}

