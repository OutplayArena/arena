import { useEffect, useRef, useState } from "react";
import { useSearchParams, useNavigate } from "react-router-dom";
import { getLeaderboard } from "../api";
import { useAuth } from "../hooks/useAuth";
import { LeaderboardFilters, type LeaderboardFiltersValue } from "../components/LeaderboardFilters";
import { LeaderboardTable } from "../components/LeaderboardTable";
import type { LeaderboardTableRow } from "../components/leaderboardShared";
import { InfoTooltip } from "../components/InfoTooltip";
import type { LeaderboardResponse } from "../types";

const PAGE_SIZE = 50;

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

function SortIcon({ active, direction }: { active: boolean; direction: "asc" | "desc" }) {
  return (
    <span className={`inline-block ml-1 transition-opacity ${active ? "opacity-100" : "opacity-30 group-hover:opacity-60"}`}>
      {direction === "asc" ? "▲" : "▼"}
    </span>
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

export function LeaderboardPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const navigate = useNavigate();
  const { user } = useAuth();

  const game = searchParams.get("game") || "";
  const sortBy = searchParams.get("sort_by") || "alpha_rank";
  const sortDir = searchParams.get("sort_dir") || "desc";
  const page = parseInt(searchParams.get("page") || "1", 10);
  const dateFrom = searchParams.get("date_from") || "";
  const dateTo = searchParams.get("date_to") || "";

  // scope: "personal" (my results) | "public" (others' public) | "all" (both)
  // Logged-in users default to personal; anonymous users always get public.
  const [scope, setScope] = useState<"personal" | "public" | "all">(
    user ? "personal" : "public"
  );

  const [data, setData] = useState<LeaderboardResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [retry, setRetry] = useState(0);
  // Track whether we've already auto-populated the date range from the data.
  // We only do this once on the first response so the user's clear is preserved.
  const dateInitDone = useRef(false);

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
      scope: user ? scope : undefined,
    })
      .then((res) => {
        if (cancelled) return;
        setData(res);
        setError(null);
      })
      .catch((e) => { if (!cancelled) setError(e.message ?? "Unknown error"); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [game, sortBy, sortDir, page, dateFrom, dateTo, retry, scope, user]);

  // Auto-populate the URL with the data's min/max dates so the date pickers
  // default to the first / last match date on first load. Runs exactly once,
  // only when the data arrives, only if the URL has no date params.
  const dataMin = data?.date_range?.min_date;
  const dataMax = data?.date_range?.max_date;
  useEffect(() => {
    if (dateInitDone.current) return;
    if (!dataMin || !dataMax) return;
    dateInitDone.current = true;
    if (searchParams.get("date_from") || searchParams.get("date_to")) return;
    const next = new URLSearchParams(searchParams);
    next.set("date_from", dataMin);
    next.set("date_to", dataMax);
    setSearchParams(next, { replace: true });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [dataMin, dataMax]);

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

  const metricKeys = data
    ? Object.keys(data.agents[0]?.metrics || {}).filter(
        (k) => SORTABLE_COLUMNS.find((c) => c.key === k),
      )
    : [];

  const visibleColumns = SORTABLE_COLUMNS.filter((col) => {
    if (col.key === "matches_played") return true;
    if (col.key === "elo") return true;
    if (col.key === "alpha_rank") return true;
    return metricKeys.includes(col.key);
  });

  const rows: LeaderboardTableRow[] = (data?.agents || []).map((a) => ({
    agentId: a.agent_id,
    displayName: a.display_name,
    ownerUsername: a.owner_username,
    isOwn: a.is_own,
    matches_played: a.matches_played,
    elo: a.elo,
    alpha_rank: a.alpha_rank,
    metrics: a.metrics,
  }));

  const dataRange = data?.date_range ?? { min_date: null, max_date: null };
  const filters: LeaderboardFiltersValue = { game, dateFrom, dateTo };

  const handleFiltersChange = (next: LeaderboardFiltersValue) => {
    updateParams({
      game: next.game,
      date_from: next.dateFrom,
      date_to: next.dateTo,
    });
  };

  const handleClear = () => {
    setSearchParams({});
  };

  return (
    <div className="flex-1 flex flex-col">
      <div className="max-w-6xl mx-auto w-full px-6 py-10">
        <div className="mb-8 flex items-start justify-between gap-4 flex-wrap">
          <div>
            <h1 className="text-3xl md:text-4xl font-bold text-ink tracking-tight">Leaderboard</h1>
            <p className="text-sm text-muted mt-1">
              Agent rankings computed via Elo and α-Rank with per-game breakdowns.
            </p>
          </div>

          {/* Scope toggle — only shown to logged-in users */}
          {user && (
            <div className="flex items-center gap-1 rounded-[var(--radius-chip)] border border-line bg-surface-soft p-0.5 shrink-0">
              {(["personal", "public", "all"] as const).map((s) => (
                <button
                  key={s}
                  type="button"
                  onClick={() => setScope(s)}
                  className={`px-3 py-1.5 text-xs font-semibold rounded-[var(--radius-chip)] transition-colors ${
                    scope === s
                      ? "bg-accent text-white shadow-sm"
                      : "text-muted hover:text-ink"
                  }`}
                >
                  {s === "personal" ? "My results" : s === "public" ? "Public results" : "All"}
                </button>
              ))}
            </div>
          )}
        </div>

        {/* Filters bar */}
        <div className="mb-4">
          <LeaderboardFilters
            value={filters}
            onChange={handleFiltersChange}
            onClear={handleClear}
            dateRange={dataRange}
          />
        </div>

        {/* Sort chips (leaderboard-only — landing page has just 10 rows) */}
        {!loading && !error && data && data.agents.length > 0 && (
          <div className="mb-3 flex flex-wrap items-center gap-2">
            <span className="text-xs font-mono text-muted">Sort by:</span>
            {visibleColumns.map((col) => {
              const active = sortBy === col.key;
              return (
                <button
                  key={col.key}
                  type="button"
                  onClick={() => toggleSort(col.key)}
                  className={`inline-flex items-center px-2.5 py-1 text-xs font-mono rounded-[var(--radius-chip)] transition-colors ${
                    active
                      ? "bg-accent-soft text-accent border border-accent/30"
                      : "border border-line text-muted hover:text-ink hover:border-line-strong"
                  }`}
                >
                  {col.label}
                  <InfoTooltip metricKey={col.key} />
                  <SortIcon active={active} direction={active ? (sortDir as "asc" | "desc") : "desc"} />
                </button>
              );
            })}
          </div>
        )}

        {/* Table (shared) */}
        <LeaderboardTable
          rows={rows}
          totalMatches={data?.total_matches ?? 0}
          loading={loading}
          error={error}
          note={data?.note}
          loadingRows={8}
          showOwnerColumn={!!user && scope !== "personal"}
          onRetry={() => { setLoading(true); setError(null); setRetry((r) => r + 1); }}
          emptyAction={
            <button
              type="button"
              onClick={() => navigate("/dashboard")}
              className="mt-3 px-4 py-2 text-xs font-mono rounded-[var(--radius-chip)] bg-accent text-white transition-colors hover:opacity-90"
            >
              Go to Dashboard
            </button>
          }
        />

        {/* Pagination */}
        {!loading && !error && data && data.agents.length > 0 && (
          <Pagination
            page={data.page}
            total={data.total}
            pageSize={data.page_size}
            onChange={(p) => updateParams({ page: String(p) })}
          />
        )}
      </div>
    </div>
  );
}
