import { useNavigate } from "react-router-dom";
import { METRIC_LABELS, formatMetric, detectMetricKeys } from "./leaderboardShared";
import type { LeaderboardTableProps } from "./leaderboardShared";

function splitAgentId(agentId: string): { model: string; provider: string } {
  if (agentId.includes("__")) {
    const [provider, model] = agentId.split("__", 2);
    return { model: model || agentId, provider: provider || "Unknown" };
  }
  return { model: agentId, provider: "Unknown" };
}

function AgentName({ agentId, displayName }: { agentId: string; displayName?: string }) {
  const navigate = useNavigate();
  const { model, provider } = splitAgentId(displayName || agentId);
  return (
    <button
      type="button"
      onClick={() => navigate(`/leaderboard/${encodeURIComponent(agentId)}`)}
      className="text-left font-mono text-xs text-accent hover:text-accent/80 hover:underline transition-colors truncate max-w-[180px]"
    >
      <span className="font-semibold">{model}</span>
      {provider !== "Unknown" && (
        <span className="text-muted ml-1.5">({provider})</span>
      )}
    </button>
  );
}

function OwnerCell({ ownerUsername, isOwn }: { ownerUsername?: string | null; isOwn?: boolean }) {
  if (isOwn) {
    return (
      <span className="inline-flex items-center px-1.5 py-0.5 rounded-[var(--radius-chip)] bg-accent/10 text-[10px] font-semibold text-accent">
        You
      </span>
    );
  }
  if (ownerUsername) {
    return (
      <span className="text-xs font-mono text-muted">{ownerUsername}</span>
    );
  }
  return <span className="text-xs text-quiet">—</span>;
}

function RankBadge({ rank }: { rank: number }) {
  return (
    <span className="inline-flex w-6 h-6 items-center justify-center rounded-full bg-surface-container text-xs font-mono font-bold text-muted">
      {rank}
    </span>
  );
}

export function LeaderboardTable({
  rows,
  totalMatches,
  loading,
  error,
  onRetry,
  note,
  footerTrailing,
  emptyAction,
  className = "",
  loadingRows = 5,
  showOwnerColumn = false,
}: LeaderboardTableProps) {
  const metricKeys = detectMetricKeys(rows);
  const baseColumns = ["#", "Agent", ...(showOwnerColumn ? ["Owner"] : []), "Games", "Elo", "α-Rank"];
  const allColumns = [...baseColumns, ...metricKeys.map((k) => METRIC_LABELS[k] || k)];

  if (loading) {
    return (
      <div className={`rounded-[var(--radius-card)] border border-line overflow-hidden bg-surface ${className}`}>
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-line bg-surface-soft">
              {allColumns.map((h) => (
                <th key={h} className="text-left px-5 py-3 text-xs font-mono font-medium text-muted">{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {Array.from({ length: loadingRows }).map((_, i) => (
              <tr key={i} className={`border-b border-line/50 last:border-0 ${i % 2 === 1 ? "bg-surface-soft/50" : ""}`}>
                {allColumns.map((_, ci) => (
                  <td key={ci} className="px-5 py-3.5">
                    <div className="w-14 h-3 rounded bg-surface-container animate-shimmer" />
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    );
  }

  if (error) {
    return (
      <div className={`rounded-[var(--radius-card)] border border-line bg-surface p-8 text-center ${className}`}>
        <p className="text-xs font-mono text-muted">Failed to load leaderboard: {error}</p>
        {onRetry && (
          <button
            type="button"
            onClick={onRetry}
            className="mt-3 px-4 py-2 text-xs font-mono rounded-[var(--radius-chip)] border border-line text-muted hover:text-ink hover:border-line-strong transition-colors"
          >
            Retry
          </button>
        )}
      </div>
    );
  }

  if (rows.length === 0) {
    return (
      <div className={`rounded-[var(--radius-card)] border border-line bg-surface p-8 text-center ${className}`}>
        <p className="text-xs font-mono text-muted">No data yet. Play some games to populate the leaderboard.</p>
        {emptyAction}
      </div>
    );
  }

  return (
    <div className={`rounded-[var(--radius-card)] border border-line overflow-hidden bg-surface ${className}`}>
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-line bg-surface-soft">
            {allColumns.map((h) => (
              <th key={h} className="text-left px-5 py-3 text-xs font-mono font-medium text-muted">{h}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, i) => (
            <tr key={row.agentId} className={`border-b border-line/50 last:border-0 ${i % 2 === 1 ? "bg-surface-soft/50" : ""} hover:bg-surface-soft/80 transition-colors`}>
              <td className="px-5 py-3.5"><RankBadge rank={i + 1} /></td>
              <td className="px-5 py-3.5">
                <AgentName agentId={row.agentId} displayName={row.displayName} />
              </td>
              {showOwnerColumn && (
                <td className="px-5 py-3.5">
                  <OwnerCell ownerUsername={row.ownerUsername} isOwn={row.isOwn} />
                </td>
              )}
              <td className="px-5 py-3.5">
                <span className="text-xs font-mono text-ink">{row.matches_played}</span>
              </td>
              <td className="px-5 py-3.5">
                <span className="text-xs font-mono text-ink">{Math.round(row.elo)}</span>
              </td>
              <td className="px-5 py-3.5">
                <span className="text-xs font-mono text-ink">
                  {row.alpha_rank != null ? (row.alpha_rank * 100).toFixed(1) + "%" : "—"}
                </span>
              </td>
              {metricKeys.map((key) => {
                const val = row.metrics?.[key];
                return (
                  <td key={key} className="px-5 py-3.5">
                    <span className="text-xs font-mono text-ink">{val != null ? formatMetric(key, val) : "—"}</span>
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
      <div className="px-5 py-3 border-t border-line flex items-center gap-2">
        <span className="w-1.5 h-1.5 rounded-full bg-accent" />
        <span className="text-xs font-mono text-muted">{totalMatches} matches recorded</span>
        {note && <span className="text-xs font-mono text-muted ml-auto italic">{note}</span>}
        {!note && footerTrailing}
      </div>
    </div>
  );
}
