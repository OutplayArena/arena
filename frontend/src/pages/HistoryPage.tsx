import { useEffect, useRef, useState } from "react";
import { useSearchParams, useNavigate } from "react-router-dom";
import { listSessions, listGames, deleteSession, setSessionVisibility } from "../api";
import { outcomeBadge, statusBadge } from "../components/badges";
import type { SessionSummary, GameEntry } from "../types";

const filterInput =
  "h-9 text-ink bg-surface border border-line rounded-[var(--radius-input)] px-3 text-sm outline-none transition-colors " +
  "hover:border-line-strong focus:border-accent focus:shadow-[0_0_0_3px_var(--color-accent-soft)]";

const GlobeIcon = () => (
  <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <circle cx="12" cy="12" r="10"/><line x1="2" y1="12" x2="22" y2="12"/>
    <path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"/>
  </svg>
);

const LockIcon = () => (
  <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <rect x="3" y="11" width="18" height="11" rx="2" ry="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/>
  </svg>
);

const CopyIcon = () => (
  <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <rect x="9" y="9" width="13" height="13" rx="2" ry="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/>
  </svg>
);

const TrashIcon = () => (
  <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <polyline points="3 6 5 6 21 6"/><path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6"/><path d="M10 11v6"/><path d="M14 11v6"/><path d="M9 6V4a1 1 0 0 1 1-1h4a1 1 0 0 1 1 1v2"/>
  </svg>
);

const DotsIcon = () => (
  <svg width="3" height="15" viewBox="0 0 3 15" fill="currentColor">
    <circle cx="1.5" cy="1.5" r="1.5"/>
    <circle cx="1.5" cy="7.5" r="1.5"/>
    <circle cx="1.5" cy="13.5" r="1.5"/>
  </svg>
);

export function HistoryPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const navigate = useNavigate();
  const [sessions, setSessions] = useState<SessionSummary[]>([]);
  const [total, setTotal] = useState(0);
  const [games, setGames] = useState<GameEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [deleting, setDeleting] = useState<string | null>(null);
  const [togglingVisibility, setTogglingVisibility] = useState<string | null>(null);

  const [openMenuId, setOpenMenuId] = useState<string | null>(null);
  const [menuAnchor, setMenuAnchor] = useState<{ top: number; right: number } | null>(null);
  const menuRef = useRef<HTMLDivElement>(null);

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

  // Close dropdown on outside click or scroll
  useEffect(() => {
    if (!openMenuId) return;
    const closeOnClick = (e: MouseEvent) => {
      if (!menuRef.current?.contains(e.target as Node)) setOpenMenuId(null);
    };
    const closeOnScroll = () => setOpenMenuId(null);
    document.addEventListener("mousedown", closeOnClick, true);
    window.addEventListener("scroll", closeOnScroll, { capture: true, passive: true });
    return () => {
      document.removeEventListener("mousedown", closeOnClick, true);
      window.removeEventListener("scroll", closeOnScroll, { capture: true });
    };
  }, [openMenuId]);

  const openMenu = (e: React.MouseEvent, id: string) => {
    e.stopPropagation();
    if (openMenuId === id) { setOpenMenuId(null); setMenuAnchor(null); return; }
    const rect = (e.currentTarget as HTMLElement).getBoundingClientRect();
    setMenuAnchor({ top: rect.bottom + 4, right: window.innerWidth - rect.right });
    setOpenMenuId(id);
  };

  const applyFilter = (key: string, value: string) => {
    const next = new URLSearchParams(searchParams);
    if (value) next.set(key, value); else next.delete(key);
    setSearchParams(next);
  };

  const handleToggleVisibility = async (sessionId: string, currentIsPublic: boolean) => {
    setTogglingVisibility(sessionId);
    setOpenMenuId(null);
    try {
      await setSessionVisibility(sessionId, !currentIsPublic);
      setSessions((prev) => prev.map((s) =>
        s.id === sessionId ? { ...s, is_public: !currentIsPublic } : s
      ));
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setTogglingVisibility(null);
    }
  };

  const handleDelete = async (sessionId: string) => {
    setDeleting(sessionId);
    setOpenMenuId(null);
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

  const handleReplay = (s: SessionSummary) => {
    setOpenMenuId(null);
    navigate(`/play/${s.game_slug || games[0]?.slug || ""}?agent_a=${s.agent_a || ""}&agent_b=${s.agent_b || ""}`);
  };

  const openSession = (s: SessionSummary) =>
    navigate(`/play/${s.game_slug || games[0]?.slug || ""}/${s.id}`);

  // The current session whose menu is open (for rendering dropdown items)
  const menuSession = openMenuId ? sessions.find((s) => s.id === openMenuId) : null;

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
                <th className="px-3 py-2.5 w-10" />
              </tr>
            </thead>
            <tbody>
              {sessions.map((s) => (
                <tr
                  key={s.id}
                  className="border-b border-line/50 last:border-0 hover:bg-surface-soft cursor-pointer transition-colors group"
                >
                  <td className="px-4 py-2.5 text-xs text-muted whitespace-nowrap" onClick={() => openSession(s)}>
                    {s.created_at ? new Date(s.created_at).toLocaleDateString() : "—"}
                  </td>
                  <td className="px-4 py-2.5 text-xs text-ink font-medium" onClick={() => openSession(s)}>
                    {games.find((g) => g.slug === s.game_slug)?.name ?? s.game_slug}
                  </td>
                  <td className="px-4 py-2.5" onClick={() => openSession(s)}>{statusBadge(s.status)}</td>
                  <td className="px-4 py-2.5 text-xs text-ink font-medium" onClick={() => openSession(s)}>{s.agent_a || "Unknown"}</td>
                  <td className="px-4 py-2.5 text-xs text-ink font-medium" onClick={() => openSession(s)}>{s.agent_b || "Unknown"}</td>
                  <td className="px-4 py-2.5" onClick={() => openSession(s)}>
                    <div className="flex items-center gap-2">
                      {outcomeBadge(s.winner)}
                      {s.status === "completed" && s.is_public && (
                        <span className="text-accent/60" title="Public — visible on leaderboard">
                          <GlobeIcon />
                        </span>
                      )}
                    </div>
                  </td>
                  {/* 3-dot menu button */}
                  <td className="px-2 py-2.5" onClick={(e) => e.stopPropagation()}>
                    <button
                      type="button"
                      onClick={(e) => openMenu(e, s.id)}
                      className="w-7 h-7 flex items-center justify-center rounded text-muted hover:text-ink hover:bg-surface-container transition-colors opacity-0 group-hover:opacity-100 focus:opacity-100"
                      aria-label="Session actions"
                    >
                      <DotsIcon />
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Floating dropdown — rendered outside the table to escape overflow:hidden */}
      {openMenuId && menuAnchor && menuSession && (
        <div
          ref={menuRef}
          style={{ position: "fixed", top: menuAnchor.top, right: menuAnchor.right }}
          className="z-50 w-52 bg-surface border border-line rounded-[var(--radius-card)] shadow-lg overflow-hidden"
        >
          {menuSession.status === "completed" && (
            <button
              type="button"
              onClick={() => handleToggleVisibility(menuSession.id, menuSession.is_public)}
              disabled={togglingVisibility === menuSession.id}
              className="flex items-center gap-2.5 w-full px-3 py-2 text-xs text-ink hover:bg-surface-soft transition-colors text-left disabled:opacity-40"
            >
              <span className="shrink-0 text-muted">
                {menuSession.is_public ? <LockIcon /> : <GlobeIcon />}
              </span>
              {menuSession.is_public ? "Make private" : "Publish to leaderboard"}
            </button>
          )}
          {!menuSession.locked && (
            <button
              type="button"
              onClick={() => handleReplay(menuSession)}
              className="flex items-center gap-2.5 w-full px-3 py-2 text-xs text-ink hover:bg-surface-soft transition-colors text-left"
            >
              <span className="shrink-0 text-muted"><CopyIcon /></span>
              Replay with same agents
            </button>
          )}
          {(menuSession.status === "completed" || !menuSession.locked) && (
            <div className="border-t border-line my-0.5" />
          )}
          <button
            type="button"
            onClick={() => handleDelete(menuSession.id)}
            disabled={deleting === menuSession.id}
            className="flex items-center gap-2.5 w-full px-3 py-2 text-xs text-danger hover:bg-danger/10 transition-colors text-left disabled:opacity-40"
          >
            <span className="shrink-0"><TrashIcon /></span>
            {deleting === menuSession.id ? "Deleting…" : "Delete session"}
          </button>
        </div>
      )}
    </div>
  );
}
