import { useEffect, useState } from "react";
import { useParams, Link } from "react-router-dom";
import { getAgentDetail, getAgentHistory } from "../api";
import { useGameNames, gameName } from "../hooks/useGameNames";
import type { AgentDetailResponse, RatingHistoryResponse } from "../types";

const METRIC_LABELS: Record<string, string> = {
  avg_payoff: "Avg Payoff",
  nash_gap: "Nash Gap",
  cumulative_regret: "Regret",
  strategy_entropy: "Entropy",
  behavioral_consistency: "Consistency",
  cooperation_rate: "Cooperation",
  payoff_volatility: "Volatility",
  action_concentration: "Concentration",
};

function MetricBadge({ label, value, format }: { label: string; value: number | null | undefined; format?: (v: number) => string }) {
  return (
    <div className="flex items-center justify-between px-4 py-2.5 rounded-[var(--radius-card)] border border-line bg-surface">
      <span className="text-xs font-mono text-muted">{label}</span>
      <span className="text-xs font-mono font-semibold text-ink">
        {value != null ? (format ? format(value) : value.toFixed(3)) : "—"}
      </span>
    </div>
  );
}

function RatingChart({ history }: { history: RatingHistoryResponse }) {
  if (history.history.length === 0) {
    return (
      <div className="rounded-[var(--radius-card)] border border-line bg-surface p-8 text-center">
        <p className="text-xs font-mono text-muted">No rating history available yet.</p>
      </div>
    );
  }

  const points = history.history;
  const minElo = Math.min(...points.map((p) => p.elo));
  const maxElo = Math.max(...points.map((p) => p.elo));
  const range = Math.max(maxElo - minElo, 50);
  const height = 180;
  const width = 600;

  const xs = points.map((_, i) => (i / Math.max(points.length - 1, 1)) * width);
  const ys = points.map((p) => height - ((p.elo - minElo) / range) * (height - 20) - 10);

  const pathD = xs.map((x, i) => `${i === 0 ? "M" : "L"}${x.toFixed(0)},${ys[i].toFixed(0)}`).join(" ");

  return (
    <div className="rounded-[var(--radius-card)] border border-line bg-surface p-5">
      <h3 className="text-xs font-mono font-semibold text-ink mb-3">Elo Rating History</h3>
      <svg viewBox={`0 0 ${width} ${height}`} className="w-full h-auto" preserveAspectRatio="xMidYMid meet">
        <path d={pathD} fill="none" stroke="var(--color-accent)" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
        <circle cx={xs[xs.length - 1]} cy={ys[ys.length - 1]} r="3" fill="var(--color-accent)" />
        <text x="0" y="10" className="text-[9px] font-mono" fill="var(--color-muted)">{Math.round(maxElo)}</text>
        <text x="0" y={height - 2} className="text-[9px] font-mono" fill="var(--color-muted)">{Math.round(minElo)}</text>
      </svg>
      <div className="mt-2 flex justify-between text-[10px] font-mono text-muted">
        <span>{points[0].timestamp.slice(0, 10)}</span>
        <span>{points[points.length - 1].timestamp.slice(0, 10)}</span>
      </div>
    </div>
  );
}

export function AgentDetailPage() {
  const { agentId } = useParams<{ agentId: string }>();
  const [detail, setDetail] = useState<AgentDetailResponse | null>(null);
  const [history, setHistory] = useState<RatingHistoryResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const decodedId = agentId ? decodeURIComponent(agentId) : "";

  useEffect(() => {
    if (!decodedId) return;
    let cancelled = false;
    Promise.all([
      getAgentDetail(decodedId),
      getAgentHistory(decodedId),
    ])
      .then(([d, h]) => {
        if (!cancelled) { setDetail(d); setHistory(h); }
      })
      .catch((e) => { if (!cancelled) setError(e.message ?? "Unknown error"); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [decodedId]);

  const gameNames = useGameNames();

  if (loading) {
    return (
      <div className="flex-1 flex flex-col items-center justify-center py-20">
        <div className="w-8 h-8 border-2 border-accent border-t-transparent rounded-full animate-spin" />
        <p className="text-xs font-mono text-muted mt-3">Loading agent details…</p>
      </div>
    );
  }

  if (error || !detail) {
    return (
      <div className="flex-1 flex flex-col items-center justify-center py-20">
        <p className="text-xs font-mono text-muted">{error || "Agent not found"}</p>
        <Link to="/leaderboard" className="mt-3 text-xs font-mono text-accent hover:underline">
          ← Back to Leaderboard
        </Link>
      </div>
    );
  }

  const [modelName, providerName] = decodedId.includes("__")
    ? [decodedId.split("__")[1] || decodedId, decodedId.split("__")[0] || "Unknown"]
    : [decodedId, "Unknown"];

  const metricKeys = detail.overall?.metrics
    ? Object.keys(detail.overall.metrics).filter((k) => METRIC_LABELS[k])
    : [];

  const gameEntries = Object.entries(detail.per_game);

  return (
    <div className="flex-1 flex flex-col">
      <div className="max-w-4xl mx-auto w-full px-6 py-10">
        <Link
          to="/leaderboard"
          className="inline-flex items-center gap-1 text-xs font-mono text-muted hover:text-ink transition-colors mb-6"
        >
          ← Back to Leaderboard
        </Link>

        <div className="mb-8">
          <h1 className="text-2xl font-bold text-ink tracking-tight">{modelName}</h1>
          <p className="text-sm text-muted mt-0.5">{providerName}</p>
        </div>

        {/* Overall stats */}
        {detail.overall && (
          <div className="mb-8">
            <h2 className="text-sm font-semibold text-ink mb-3">Overall</h2>
            <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-2">
              <MetricBadge label="Elo" value={detail.overall.elo} format={(v) => Math.round(v).toString()} />
              <MetricBadge
                label="α-Rank"
                value={detail.overall.alpha_rank}
                format={(v) => (v * 100).toFixed(1) + "%"}
              />
              <MetricBadge label="Matches" value={detail.overall.matches_played} format={(v) => v.toString()} />
              <MetricBadge
                label="Population"
                value={detail.overall.total_agents}
                format={(v) => v + " agents"}
              />
              {metricKeys.map((key) => (
                <MetricBadge
                  key={key}
                  label={METRIC_LABELS[key]}
                  value={detail.overall!.metrics[key]}
                />
              ))}
            </div>
          </div>
        )}

        {/* Rating history chart */}
        {history && (
          <div className="mb-8">
            <RatingChart history={history} />
          </div>
        )}

        {/* Per-game breakdown */}
        {gameEntries.length > 0 && (
          <div>
            <h2 className="text-sm font-semibold text-ink mb-3">Per-Game Performance</h2>
            <div className="space-y-3">
              {gameEntries.map(([gameSlug, entry]) => {
                const gameMetricKeys = entry.metrics
                  ? Object.keys(entry.metrics).filter((k) => METRIC_LABELS[k])
                  : [];
                return (
                  <div
                    key={gameSlug}
                    className="rounded-[var(--radius-card)] border border-line bg-surface p-4"
                  >
                    <div className="flex items-center justify-between mb-3">
                      <h3 className="text-xs font-mono font-semibold text-ink">{gameName(gameSlug, gameNames)}</h3>
                      <span className="text-[10px] font-mono text-muted">
                        {entry.matches_played} matches · {entry.total_agents} agents in pool
                      </span>
                    </div>
                    <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-2">
                      <MetricBadge label="Elo" value={entry.elo} format={(v) => Math.round(v).toString()} />
                      <MetricBadge
                        label="α-Rank"
                        value={entry.alpha_rank}
                        format={(v) => (v * 100).toFixed(1) + "%"}
                      />
                      <MetricBadge label="Matches" value={entry.matches_played} format={(v) => v.toString()} />
                      {gameMetricKeys.map((key) => (
                        <MetricBadge
                          key={key}
                          label={METRIC_LABELS[key]}
                          value={entry.metrics[key]}
                        />
                      ))}
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        )}

        {!detail.overall && gameEntries.length === 0 && (
          <div className="rounded-[var(--radius-card)] border border-line bg-surface p-8 text-center">
            <p className="text-xs font-mono text-muted">No data found for this agent.</p>
          </div>
        )}
      </div>
    </div>
  );
}
