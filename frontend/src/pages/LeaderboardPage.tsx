import { useEffect, useState } from "react";
import { useSearchParams, useNavigate } from "react-router-dom";
import { getLeaderboard, getBenchmarkGames } from "../api";
import { InfoTooltip } from "../components/InfoTooltip";
import type { LeaderboardResponse, LeaderboardEntry } from "../types";

const PAGE_SIZE = 50;

const METRIC_LABELS: Record<string, string> = {
  avg_payoff: "Avg Payoff",
  nash_gap: "Nash Gap",
  cumulative_regret: "Regret",
  strategy_entropy: "Entropy",
  behavioral_consistency: "Consistency",
  cooperation_rate: "Cooperation",
};

const SORTABLE_COLUMNS = [
  { key: "matches_played", label: "Games" },
  { key: "elo", label: "Elo" },
  { key: "alpha_rank", label: "α-Rank" },
  { key: "avg_payoff", label: "Avg Payoff" },
  { key: "nash_gap", label: "Nash Gap" },
  { key: "cumulative_regret", label: "Regret" },
  { key: "strategy_entropy", label: "Entropy" },
  { key: "behavioral_consistency", label: "Consistency" },
  { key: "cooperation_rate", label: "Cooperation" },
] as const;

function formatMetric(key: string, val: number): string {
  if (key === "cooperation_rate") return (val * 100).toFixed(0) + "%";
  if (key === "nash_gap" || key === "cumulative_regret") return val.toFixed(3);
  return val.toFixed(2);
}

function detectMetricKeys(agents: LeaderboardEntry[]): string[] {
  for (const agent of agents) {
    const m = agent.metrics;
    if (m) return Object.keys(m).filter((k) => METRIC_LABELS[k]);
  }
  return [];
}

function SortIcon({ active, direction }: { active: boolean; direction: "asc" | "desc" }) {
  return (
    <span className={`inline-block ml-1 transition-opacity ${active ? "opacity-100" : "opacity-30 group-hover:opacity-60"}`}>
      {direction === "asc" ? "▲" : "▼"}
    </span>
  );
}

function AgentName({ agentId }: { agentId: string }) {
  const navigate = useNavigate();
  const [modelName, providerName] = agentId.includes("__")
    ? [agentId.split("__")[1] || agentId, agentId.split("__")[0] || "Unknown"]
    : [agentId, "Unknown"];

  return (
    <button
      type="button"
      onClick={() => navigate(`/leaderboard/${encodeURIComponent(agentId)}`)}
      className="text-left font-mono text-xs text-accent hover:text-accent/80 hover:underline transition-colors"
    >
      <span className="font-semibold">{modelName}</span>
      <span className="text-muted ml-1.5">({providerName})</span>
    </button>
  );
}

function Pagination({
  page,
  total,
  pageSize,
  onChange,
}: {
  page: number;
  total: number;
  pageSize: number;
  onChange: (p: number) => void;
}) {
  const totalPages = Math.max(1, Math.ceil(total / pageSize));
  const pages: (number | "...")[] = [];
  if (totalPages <= 7) {
    for (let i = 1; i <= totalPages; i++) pages.push(i);
  } else {
    pages.push(1);
    if (page > 3) pages.push("...");
    for (let i = Math.max(2, page - 1); i <= Math.min(totalPages - 1, page + 1); i++) {
      pages.push(i);
    }
    if (page < totalPages - 2) pages.push("...");
    pages.push(totalPages);
  }

  return (
    <div className="flex items-center justify-between pt-4">
      <span className="text-xs text-muted">
        Showing {Math.min((page - 1) * pageSize + 1, total)}–{Math.min(page * pageSize, total)} of {total}
      </span>
      <div className="flex items-center gap-1">
        <button
          type="button"
          disabled={page <= 1}
          onClick={() => onChange(page - 1)}
          className="px-2 py-1 text-xs font-mono rounded-[var(--radius-chip)] border border-line text-muted hover:text-ink hover:border-line-strong disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
        >
          ◀
        </button>
        {pages.map((p, i) =>
          p === "..." ? (
            <span key={`e${i}`} className="px-1 text-xs text-muted">…</span>
          ) : (
            <button
              key={p}
              type="button"
              onClick={() => onChange(p)}
              className={`px-2.5 py-1 text-xs font-mono rounded-[var(--radius-chip)] transition-colors ${
                p === page
                  ? "bg-accent text-white"
                  : "border border-line text-muted hover:text-ink hover:border-line-strong"
              }`}
            >
              {p}
            </button>
          ),
        )}
        <button
          type="button"
          disabled={page >= totalPages}
          onClick={() => onChange(page + 1)}
          className="px-2 py-1 text-xs font-mono rounded-[var(--radius-chip)] border border-line text-muted hover:text-ink hover:border-line-strong disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
        >
          ▶
        </button>
      </div>
    </div>
  );
}

const FILTER_INPUT_CLS =
  "h-9 text-ink bg-surface border border-line rounded-[var(--radius-input)] px-3 text-sm outline-none transition-colors " +
  "hover:border-line-strong focus:border-accent focus:shadow-[0_0_0_3px_var(--color-accent-soft)]";

export function LeaderboardPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const navigate = useNavigate();

  const game = searchParams.get("game") || "";
  const sortBy = searchParams.get("sort_by") || "alpha_rank";
  const sortDir = searchParams.get("sort_dir") || "desc";
  const page = parseInt(searchParams.get("page") || "1", 10);
  const dateFrom = searchParams.get("date_from") || "";
  const dateTo = searchParams.get("date_to") || "";

  const [data, setData] = useState<LeaderboardResponse | null>(null);
  const [games, setGames] = useState<string[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [retry, setRetry] = useState(0);

  useEffect(() => {
    getBenchmarkGames().then((res) => setGames(res.games)).catch(() => {});
  }, []);

  useEffect(() => {
    let cancelled = false;
    getLeaderboard({
      game: game || undefined,
      sort_by: sortBy,
      sort_dir: sortDir,
      page,
      page_size: PAGE_SIZE,
      date_from: dateFrom || undefined,
      date_to: dateTo || undefined,
    })
      .then((res) => { if (!cancelled) setData(res); })
      .catch((e) => { if (!cancelled) setError(e.message ?? "Unknown error"); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [game, sortBy, sortDir, page, dateFrom, dateTo, retry]);

  const updateParams = (updates: Record<string, string>) => {
    const next = new URLSearchParams(searchParams);
    for (const [key, value] of Object.entries(updates)) {
      if (value) next.set(key, value);
      else next.delete(key);
    }
    if (!updates.page) next.set("page", "1");
    setSearchParams(next);
  };

  const toggleSort = (key: string) => {
    if (sortBy === key) {
      updateParams({ sort_by: key, sort_dir: sortDir === "asc" ? "desc" : "asc" });
    } else {
      updateParams({ sort_by: key, sort_dir: "desc" });
    }
  };

  const metricKeys = data ? detectMetricKeys(data.agents) : [];
  const visibleColumns = SORTABLE_COLUMNS.filter(
    (col) => {
      if (col.key === "matches_played") return true;
      if (col.key === "elo") return true;
      if (col.key === "alpha_rank") return true;
      return metricKeys.includes(col.key);
    },
  );

  return (
    <div className="flex-1 flex flex-col">
      <div className="max-w-6xl mx-auto w-full px-6 py-10">
        <div className="mb-8">
          <h1 className="text-3xl md:text-4xl font-bold text-ink tracking-tight">Leaderboard</h1>
          <p className="text-sm text-muted mt-1">
            Agent rankings computed via Elo and α-Rank with per-game breakdowns.
          </p>
        </div>

        {/* Filters bar */}
        <div className="flex flex-wrap items-center gap-3 mb-6">
          {/* Game filter */}
          <div className="flex items-center gap-1.5">
            <label className="text-xs font-mono text-muted">Game:</label>
            <select
              value={game}
              onChange={(e) => updateParams({ game: e.target.value })}
              className={FILTER_INPUT_CLS + " min-w-[130px]"}
            >
              <option value="">Overall</option>
              {games.map((g) => (
                <option key={g} value={g}>{g}</option>
              ))}
            </select>
          </div>

          {/* Date range */}
          <div className="flex items-center gap-1.5">
            <label className="text-xs font-mono text-muted">From:</label>
            <input
              type="date"
              value={dateFrom}
              onChange={(e) => updateParams({ date_from: e.target.value })}
              className={FILTER_INPUT_CLS}
            />
          </div>
          <div className="flex items-center gap-1.5">
            <label className="text-xs font-mono text-muted">To:</label>
            <input
              type="date"
              value={dateTo}
              onChange={(e) => updateParams({ date_to: e.target.value })}
              className={FILTER_INPUT_CLS}
            />
          </div>

          {(dateFrom || dateTo || game) && (
            <button
              type="button"
              onClick={() => setSearchParams({})}
              className="px-3 py-1.5 text-xs font-mono rounded-[var(--radius-chip)] border border-line text-muted hover:text-ink hover:border-line-strong transition-colors"
            >
              Clear filters
            </button>
          )}
        </div>

        {/* Loading */}
        {loading && (
          <div className="rounded-[var(--radius-card)] border border-line overflow-hidden bg-surface">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-line bg-surface-soft">
                  <th className="text-left px-5 py-3 text-xs font-mono font-medium text-muted">#</th>
                  <th className="text-left px-5 py-3 text-xs font-mono font-medium text-muted">Agent</th>
                  {visibleColumns.map((col) => (
                    <th key={col.key} className="text-right px-4 py-3 text-xs font-mono font-medium text-muted">{col.label}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {Array.from({ length: 8 }).map((_, i) => (
                  <tr key={i} className={`border-b border-line/50 last:border-0 ${i % 2 === 1 ? "bg-surface-soft/50" : ""}`}>
                    <td className="px-5 py-3.5"><div className="w-6 h-3 rounded bg-surface-container animate-shimmer" /></td>
                    <td className="px-5 py-3.5"><div className="w-32 h-3 rounded bg-surface-container animate-shimmer" /></td>
                    {visibleColumns.map((_, ci) => (
                      <td key={ci} className="px-4 py-3.5"><div className="w-10 h-3 rounded bg-surface-container animate-shimmer ml-auto" /></td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {/* Error */}
        {!loading && error && (
          <div className="rounded-[var(--radius-card)] border border-line bg-surface p-8 text-center">
            <p className="text-xs font-mono text-muted">Failed to load leaderboard: {error}</p>
            <button
              type="button"
              onClick={() => { setLoading(true); setError(null); setRetry((r) => r + 1); }}
              className="mt-3 px-4 py-2 text-xs font-mono rounded-[var(--radius-chip)] border border-line text-muted hover:text-ink hover:border-line-strong transition-colors"
            >
              Retry
            </button>
          </div>
        )}

        {/* Empty */}
        {!loading && !error && (!data || data.agents.length === 0) && (
          <div className="rounded-[var(--radius-card)] border border-line bg-surface p-8 text-center">
            <p className="text-xs font-mono text-muted">No data yet. Play some games to populate the leaderboard.</p>
            <button
              type="button"
              onClick={() => navigate("/dashboard")}
              className="mt-3 px-4 py-2 text-xs font-mono rounded-[var(--radius-chip)] bg-accent text-white transition-colors hover:opacity-90"
            >
              Go to Dashboard
            </button>
          </div>
        )}

        {/* Table */}
        {!loading && !error && data && data.agents.length > 0 && (
          <>
            <div className="rounded-[var(--radius-card)] border border-line overflow-hidden bg-surface">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-line bg-surface-soft">
                    <th className="text-left px-5 py-3 text-xs font-mono font-medium text-muted w-10">#</th>
                    <th className="text-left px-5 py-3 text-xs font-mono font-medium text-muted">Agent</th>
                    {visibleColumns.map((col) => {
                      const active = sortBy === col.key;
                      return (
                        <th
                          key={col.key}
                          className="text-right px-4 py-3 text-xs font-mono font-medium text-muted cursor-pointer select-none group hover:text-ink transition-colors"
                          onClick={() => toggleSort(col.key)}
                        >
                          {col.label}
                          <InfoTooltip metricKey={col.key} />
                          <SortIcon active={active} direction={active ? (sortDir as "asc" | "desc") : "desc"} />
                        </th>
                      );
                    })}
                  </tr>
                </thead>
                <tbody>
                  {data.agents.map((agent, i) => {
                    const rank = (page - 1) * PAGE_SIZE + i + 1;
                    return (
                      <tr
                        key={agent.agent_id}
                        className={`border-b border-line/50 last:border-0 ${i % 2 === 1 ? "bg-surface-soft/50" : ""} hover:bg-surface-soft/80 transition-colors`}
                      >
                        <td className="px-5 py-3.5">
                          <span className="inline-flex w-6 h-6 items-center justify-center rounded-full bg-surface-container text-xs font-mono font-bold text-muted">
                            {rank}
                          </span>
                        </td>
                        <td className="px-5 py-3.5">
                          <AgentName agentId={agent.agent_id} />
                        </td>
                        <td className="px-4 py-3.5 text-right">
                          <span className="text-xs font-mono text-ink">{agent.matches_played}</span>
                        </td>
                        <td className="px-4 py-3.5 text-right">
                          <span className="text-xs font-mono text-ink">{Math.round(agent.elo)}</span>
                        </td>
                        <td className="px-4 py-3.5 text-right">
                          <span className="text-xs font-mono text-ink">
                            {agent.alpha_rank != null ? (agent.alpha_rank * 100).toFixed(1) + "%" : "—"}
                          </span>
                        </td>
                        {metricKeys.map((key) => {
                          const val = agent.metrics?.[key];
                          return (
                            <td key={key} className="px-4 py-3.5 text-right">
                              <span className="text-xs font-mono text-ink">{val != null ? formatMetric(key, val) : "—"}</span>
                            </td>
                          );
                        })}
                      </tr>
                    );
                  })}
                </tbody>
              </table>

              <div className="px-5 py-3 border-t border-line flex items-center gap-2">
                <span className="w-1.5 h-1.5 rounded-full bg-accent" />
                <span className="text-xs font-mono text-muted">{data.total_matches} matches recorded</span>
                {data.note && (
                  <span className="text-xs font-mono text-muted ml-auto italic">{data.note}</span>
                )}
              </div>
            </div>

            <Pagination
              page={data.page}
              total={data.total}
              pageSize={data.page_size}
              onChange={(p) => updateParams({ page: String(p) })}
            />
          </>
        )}
      </div>
    </div>
  );
}
