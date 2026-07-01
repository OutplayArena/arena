import { useEffect, useState } from "react";
import { useSearchParams, useNavigate } from "react-router-dom";
import { listSessions, listGames, deleteSession } from "../api";
import { outcomeBadge, statusBadge } from "../components/badges";
import type { SessionSummary, GameEntry } from "../types";

const filterInput =
  "h-9 text-ink bg-surface border border-line rounded-[var(--radius-input)] px-3 text-sm outline-none transition-colors " +
  "hover:border-line-strong focus:border-accent focus:shadow-[0_0_0_3px_var(--color-accent-soft)]";

export function HistoryPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const navigate = useNavigate();
  const [sessions, setSessions] = useState<SessionSummary[]>([]);
  const [total, setTotal] = useState(0);
  const [games, setGames] = useState<GameEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [deleting, setDeleting] = useState<string | null>(null);

  const game = searchParams.get("game") || "";
  const agent = searchParams.get("agent") || "";
  const dateFrom = searchParams.get("date_from") || "";
  const dateTo = searchParams.get("date_to") || "";

  useEffect(() => {
    let cancelled = false;
    (async () => {
      setLoading(true);
      setError(null);
      try {
        const [sessionsResp, gamesResp] = await Promise.all([
          listSessions({ game: game || undefined, agent: agent || undefined, date_from: dateFrom || undefined, date_to: dateTo || undefined, limit: 100 }),
          listGames(),
        ]);
        if (!cancelled) { setSessions(sessionsResp.sessions); setTotal(sessionsResp.total); setGames(gamesResp); }
      } catch (err) {
        if (!cancelled) setError(err instanceof Error ? err.message : String(err));
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => { cancelled = true; };
  }, [game, agent, dateFrom, dateTo]);

  const applyFilter = (key: string, value: string) => {
    const next = new URLSearchParams(searchParams);
    if (value) next.set(key, value); else next.delete(key);
    setSearchParams(next);
  };

  const handleDelete = async (sessionId: string) => {
    setDeleting(sessionId);
    try {
      await deleteSession(sessionId);
      setSessions((prev) => prev.filter((s) => s.id !== sessionId));
      setTotal((prev) => prev - 1);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setDeleting(null);
    }
  };

  return (
    <div className="max-w-5xl mx-auto px-6 py-10">
      <div className="mb-6">
        <h1 className="text-xl font-bold text-ink tracking-tight">History</h1>
        <p className="text-xs text-muted mt-0.5">{total} session{total !== 1 ? "s" : ""}</p>
      </div>

      {/* Filter bar */}
      <div className="flex flex-wrap gap-3 mb-6 p-4 rounded-[var(--radius-card)] border border-line bg-surface-soft">
        <div className="flex flex-col gap-1">
          <label className="text-[10px] font-mono font-medium text-muted uppercase tracking-wider">Game</label>
          <select value={game} onChange={(e) => applyFilter("game", e.target.value)} className={filterInput}>
            <option value="">All games</option>
            {games.map((g) => <option key={g.slug} value={g.slug}>{g.name}</option>)}
          </select>
        </div>
        <div className="flex flex-col gap-1">
          <label className="text-[10px] font-mono font-medium text-muted uppercase tracking-wider">Agent</label>
          <input type="text" value={agent} onChange={(e) => applyFilter("agent", e.target.value)} placeholder="Filter by agent..." className={`${filterInput} w-44`} />
        </div>
        <div className="flex flex-col gap-1">
          <label className="text-[10px] font-mono font-medium text-muted uppercase tracking-wider">From</label>
          <input type="date" value={dateFrom} onChange={(e) => applyFilter("date_from", e.target.value)} className={filterInput} />
        </div>
        <div className="flex flex-col gap-1">
          <label className="text-[10px] font-mono font-medium text-muted uppercase tracking-wider">To</label>
          <input type="date" value={dateTo} onChange={(e) => applyFilter("date_to", e.target.value)} className={filterInput} />
        </div>
      </div>

      {loading ? (
        <div className="rounded-[var(--radius-card)] border border-line overflow-hidden">
          <div className="h-10 bg-surface-soft" />
          {Array.from({ length: 5 }).map((_, i) => (
            <div key={i} className="h-11 bg-surface animate-pulse border-b border-line last:border-b-0" />
          ))}
        </div>
      ) : error ? (
        <div className="py-12 text-center text-muted text-sm">{error}</div>
      ) : sessions.length === 0 ? (
        <div className="p-10 text-center rounded-[var(--radius-card)] border border-line bg-surface-soft">
          <p className="text-sm text-muted">No sessions found.</p>
          <p className="text-xs text-quiet mt-1">Try adjusting your filters.</p>
        </div>
      ) : (
        <div className="rounded-[var(--radius-card)] border border-line overflow-hidden bg-surface">
          <table className="w-full text-left text-sm">
            <thead>
              <tr className="border-b border-line bg-surface-soft">
                <th className="px-4 py-2.5 text-[11px] font-mono font-medium text-muted">Date</th>
                <th className="px-4 py-2.5 text-[11px] font-mono font-medium text-muted">Game</th>
                <th className="px-4 py-2.5 text-[11px] font-mono font-medium text-muted">Status</th>
                <th className="px-4 py-2.5 text-[11px] font-mono font-medium text-muted">Agent A</th>
                <th className="px-4 py-2.5 text-[11px] font-mono font-medium text-muted">Agent B</th>
                <th className="px-4 py-2.5 text-[11px] font-mono font-medium text-muted">Outcome</th>
                <th className="px-3 py-2.5 w-0" />
              </tr>
            </thead>
            <tbody>
              {sessions.map((s) => (
                <tr key={s.id} className="border-b border-line/50 last:border-0 hover:bg-surface-soft cursor-pointer transition-colors group">
                  <td className="px-4 py-2.5 text-xs text-muted whitespace-nowrap" onClick={() => navigate(`/play/${s.game_slug || games[0]?.slug || ""}/${s.id}`)}>
                    {s.created_at ? new Date(s.created_at).toLocaleDateString() : "—"}
                  </td>
                  <td className="px-4 py-2.5 text-xs text-ink font-medium" onClick={() => navigate(`/play/${s.game_slug || games[0]?.slug || ""}/${s.id}`)}>
                    {games.find((g) => g.slug === s.game_slug)?.name ?? s.game_slug}
                  </td>
                  <td className="px-4 py-2.5" onClick={() => navigate(`/play/${s.game_slug || games[0]?.slug || ""}/${s.id}`)}>{statusBadge(s.status)}</td>
                  <td className="px-4 py-2.5 text-xs text-ink font-medium" onClick={() => navigate(`/play/${s.game_slug || games[0]?.slug || ""}/${s.id}`)}>{s.agent_a || "Unknown"}</td>
                  <td className="px-4 py-2.5 text-xs text-ink font-medium" onClick={() => navigate(`/play/${s.game_slug || games[0]?.slug || ""}/${s.id}`)}>{s.agent_b || "Unknown"}</td>
                  <td className="px-4 py-2.5" onClick={() => navigate(`/play/${s.game_slug || games[0]?.slug || ""}/${s.id}`)}>{outcomeBadge(s.winner)}</td>
                  <td className="px-2 py-2.5">
                    <div className="flex items-center gap-0.5 opacity-0 group-hover:opacity-100 transition-opacity">
                      {s.locked ? (
                        <span title="Created via API" className="w-7 h-7 flex items-center justify-center text-muted">
                          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                            <rect x="3" y="11" width="18" height="11" rx="2" ry="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/>
                          </svg>
                        </span>
                      ) : (
                        <button type="button" onClick={(e) => { e.stopPropagation(); navigate(`/play/${s.game_slug || games[0]?.slug || ""}?agent_a=${s.agent_a || ""}&agent_b=${s.agent_b || ""}`); }} title="Use as template" className="w-7 h-7 flex items-center justify-center rounded text-muted hover:text-accent hover:bg-accent-soft transition-colors">
                          <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                            <rect x="9" y="9" width="13" height="13" rx="2" ry="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/>
                          </svg>
                        </button>
                      )}
                      <button type="button" onClick={(e) => { e.stopPropagation(); handleDelete(s.id); }} disabled={deleting === s.id} title="Delete" className="w-7 h-7 flex items-center justify-center rounded text-muted hover:text-danger hover:bg-danger/10 transition-colors disabled:opacity-30">
                        {deleting === s.id
                          ? <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="animate-spin"><circle cx="12" cy="12" r="10" strokeDasharray="31.4" strokeDashoffset="10"/></svg>
                          : <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
                        }
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
