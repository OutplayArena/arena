import { useEffect, useState, useRef } from "react";
import { Link, useNavigate } from "react-router-dom";
import { getDashboard, deleteSession, listGames, setSessionVisibility } from "../api";
import { outcomeBadge, statusBadge } from "../components/badges";
import type { DashboardResponse, GameEntry, SessionSummary } from "../types";

// ── tiny inline SVG icons ────────────────────────────────────────────────────

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
    <polyline points="3 6 5 6 21 6"/><path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6"/>
    <path d="M10 11v6"/><path d="M14 11v6"/>
    <path d="M9 6V4a1 1 0 0 1 1-1h4a1 1 0 0 1 1 1v2"/>
  </svg>
);

const DotsIcon = () => (
  <svg width="3" height="15" viewBox="0 0 3 15" fill="currentColor">
    <circle cx="1.5" cy="1.5" r="1.5"/>
    <circle cx="1.5" cy="7.5" r="1.5"/>
    <circle cx="1.5" cy="13.5" r="1.5"/>
  </svg>
);

// ── component ────────────────────────────────────────────────────────────────

export function DashboardPage() {
  const [data, setData] = useState<DashboardResponse | null>(null);
  const [gamesMeta, setGamesMeta] = useState<GameEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [deleting, setDeleting] = useState<string | null>(null);
  const [togglingVisibility, setTogglingVisibility] = useState<string | null>(null);
  const [collapsedGames, setCollapsedGames] = useState<Set<string>>(() => {
    try {
      const stored = localStorage.getItem("dashboard-collapsed-games");
      return stored ? new Set(JSON.parse(stored)) : new Set();
    } catch {
      return new Set();
    }
  });
  const [dropdownOpen, setDropdownOpen] = useState(false);
  const dropdownRef = useRef<HTMLDivElement>(null);

  // Per-row 3-dot menu
  const [openMenuId, setOpenMenuId] = useState<string | null>(null);
  const [menuAnchor, setMenuAnchor] = useState<{ top: number; right: number } | null>(null);
  const menuRef = useRef<HTMLDivElement>(null);

  const navigate = useNavigate();

  const refreshDashboard = async () => {
    try {
      const [d, g] = await Promise.all([getDashboard(), listGames()]);
      setData(d);
      setGamesMeta(g);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    }
  };

  useEffect(() => {
    let cancelled = false;
    (async () => {
      setLoading(true);
      try {
        const [d, g] = await Promise.all([getDashboard(), listGames()]);
        if (!cancelled) { setData(d); setGamesMeta(g); }
      } catch (err) {
        if (!cancelled) setError(err instanceof Error ? err.message : String(err));
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => { cancelled = true; };
  }, []);

  // Close "New Game" dropdown on outside click
  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(e.target as Node)) {
        setDropdownOpen(false);
      }
    };
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  // Close 3-dot session menu on outside click or scroll
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

  // Optimistic delete
  const handleDelete = async (sessionId: string) => {
    setOpenMenuId(null);
    setDeleting(sessionId);
    if (data) {
      const nextData = { ...data, games: { ...data.games } };
      for (const slug of Object.keys(nextData.games)) {
        nextData.games[slug] = {
          ...nextData.games[slug],
          sessions: nextData.games[slug].sessions.filter((s) => s.id !== sessionId),
        };
      }
      nextData.total_games = Math.max(0, nextData.total_games - 1);
      setData(nextData);
    }
    try {
      await deleteSession(sessionId);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
      await refreshDashboard();
    } finally {
      setDeleting(null);
    }
  };

  // Optimistic visibility toggle
  const handleToggleVisibility = async (sessionId: string, currentIsPublic: boolean) => {
    setOpenMenuId(null);
    setTogglingVisibility(sessionId);
    if (data) {
      const nextData = { ...data, games: { ...data.games } };
      for (const slug of Object.keys(nextData.games)) {
        nextData.games[slug] = {
          ...nextData.games[slug],
          sessions: nextData.games[slug].sessions.map((s) =>
            s.id === sessionId ? { ...s, is_public: !currentIsPublic } : s
          ),
        };
      }
      setData(nextData);
    }
    try {
      await setSessionVisibility(sessionId, !currentIsPublic);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
      await refreshDashboard();
    } finally {
      setTogglingVisibility(null);
    }
  };

  const handleReplay = (s: SessionSummary) => {
    setOpenMenuId(null);
    const params = new URLSearchParams();
    if (s.agent_a) params.set("agent_a", s.agent_a);
    if (s.agent_b) params.set("agent_b", s.agent_b);
    if (s.rounds) params.set("rounds", String(s.rounds));
    if (s.num_battlefields) params.set("fields", String(s.num_battlefields));
    if (s.resources) params.set("resources", String(s.resources));
    const slug = s.game_slug || gamesMeta[0]?.slug || "";
    navigate(`/play/${slug}?${params.toString()}`);
  };

  const handleNewGame = (slug: string) => { setDropdownOpen(false); navigate(`/play/${slug}`); };
  const toggleGame = (slug: string) => {
    setCollapsedGames((prev) => {
      const next = new Set(prev);
      if (next.has(slug)) next.delete(slug); else next.add(slug);
      localStorage.setItem("dashboard-collapsed-games", JSON.stringify([...next]));
      return next;
    });
  };

  // Find the session whose menu is open (may be in any game section)
  const menuSession: SessionSummary | undefined = openMenuId && data
    ? Object.values(data.games).flatMap((g) => g.sessions).find((s) => s.id === openMenuId)
    : undefined;

  if (loading) {
    return (
      <div className="max-w-5xl mx-auto px-6 py-10">
        <div className="mb-8 flex items-center justify-between">
          <div className="h-7 w-32 bg-surface-container rounded animate-pulse" />
          <div className="h-9 w-28 bg-surface-container rounded-[var(--radius-button)] animate-pulse" />
        </div>
        {[1, 2].map((i) => (
          <div key={i} className="mb-8">
            <div className="h-5 w-36 bg-surface-container rounded animate-pulse mb-4" />
            <div className="rounded-[var(--radius-card)] border border-line h-40 bg-surface-container/40 animate-pulse" />
          </div>
        ))}
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex items-center justify-center h-[calc(100dvh-48px)] text-muted text-sm">
        {error}
      </div>
    );
  }

  const gameSlugs = Object.keys(data?.games ?? {});

  return (
    <div className="max-w-5xl mx-auto px-6 py-10">
      {/* Page header */}
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-xl font-bold text-ink tracking-tight">Dashboard</h1>
          <p className="text-xs text-muted mt-0.5">
            {data?.total_games ?? 0} game{data?.total_games !== 1 ? "s" : ""} played
          </p>
        </div>

        {/* New Game dropdown */}
        <div className="relative" ref={dropdownRef}>
          <button
            type="button"
            onClick={() => setDropdownOpen((o) => !o)}
            className="inline-flex items-center gap-2 h-9 px-4 rounded-[var(--radius-button)] bg-accent text-white font-medium text-sm transition-opacity duration-150 hover:opacity-90"
          >
            New Game
            <svg
              className={`w-3.5 h-3.5 transition-transform ${dropdownOpen ? "rotate-180" : ""}`}
              fill="none" stroke="currentColor" strokeWidth="2.5" viewBox="0 0 24 24"
            >
              <path strokeLinecap="round" strokeLinejoin="round" d="M6 9l6 6 6-6" />
            </svg>
          </button>
          {dropdownOpen && (
            <div className="absolute right-0 top-full mt-1.5 w-[44rem] max-w-[calc(100vw-3rem)] rounded-[var(--radius-card)] border border-line bg-surface shadow-elevation-4 z-50 p-3">
              {gamesMeta.length === 0 ? (
                <p className="px-3 py-2 text-xs text-muted">No games registered.</p>
              ) : (
                <div className="grid grid-cols-1 sm:grid-cols-3 gap-1.5">
                  {gamesMeta.map((game) => (
                    <button
                      key={game.slug}
                      type="button"
                      onClick={() => handleNewGame(game.slug)}
                      className="text-left p-3 rounded-[var(--radius-chip)] hover:bg-surface-container transition-colors"
                    >
                      <span className="font-medium text-sm text-ink">{game.name}</span>
                      {game.description && (
                        <span className="block text-[11px] text-muted mt-1 leading-snug line-clamp-2">{game.description}</span>
                      )}
                    </button>
                  ))}
                </div>
              )}
            </div>
          )}
        </div>
      </div>

      {/* Game sections */}
      {gameSlugs.length === 0 ? (
        <div className="p-10 text-center rounded-[var(--radius-card)] border border-line bg-surface-soft">
          <p className="text-sm text-muted">No games played yet.</p>
          <p className="text-xs text-quiet mt-1">Select "New Game" above to start your first match.</p>
        </div>
      ) : (
        gameSlugs.map((slug) => {
          const sessions = data?.games[slug]?.sessions ?? [];
          const meta = gamesMeta.find((g) => g.slug === slug);
          const isCollapsed = collapsedGames.has(slug);
          return (
            <div key={slug} className="mb-8">
              <div className="flex items-center justify-between mb-3">
                <button
                  type="button"
                  onClick={() => toggleGame(slug)}
                  className="flex items-center gap-2 group"
                >
                  <svg
                    className={`w-3.5 h-3.5 text-muted transition-transform duration-200 ${isCollapsed ? "" : "rotate-90"}`}
                    fill="none" stroke="currentColor" strokeWidth="2.5" viewBox="0 0 24 24"
                  >
                    <path strokeLinecap="round" strokeLinejoin="round" d="M9 18l6-6-6-6" />
                  </svg>
                  <h2 className="text-sm font-semibold text-ink">{meta?.name ?? slug}</h2>
                  {isCollapsed && (
                    <span className="text-[11px] text-muted bg-surface-container px-2 py-0.5 rounded-full">
                      {data?.games[slug]?.count ?? 0}
                    </span>
                  )}
                </button>
                <Link to={`/history?game=${slug}`} className="text-xs text-accent hover:underline no-underline">
                  View all →
                </Link>
              </div>

              <div
                className="grid transition-[grid-template-rows] duration-300 ease-out"
                style={{ gridTemplateRows: isCollapsed ? "0fr" : "1fr" }}
              >
                <div className="overflow-hidden">
                  {meta?.description && (
                    <p className="text-xs text-muted mb-3">{meta.description}</p>
                  )}
                  <div className="rounded-[var(--radius-card)] border border-line overflow-hidden bg-surface">
                    <table className="w-full text-left text-sm">
                      <thead>
                        <tr className="border-b border-line bg-surface-soft">
                          <th className="px-4 py-2.5 text-[11px] font-mono font-medium text-muted">Date</th>
                          <th className="px-4 py-2.5 text-[11px] font-mono font-medium text-muted">Agent A</th>
                          <th className="px-4 py-2.5 text-[11px] font-mono font-medium text-muted">Agent B</th>
                          <th className="px-4 py-2.5 text-[11px] font-mono font-medium text-muted">Status</th>
                          <th className="px-4 py-2.5 text-[11px] font-mono font-medium text-muted">Outcome</th>
                          <th className="px-3 py-2.5 w-10" />
                        </tr>
                      </thead>
                      <tbody>
                        {sessions.map((s) => (
                          <tr
                            key={s.id}
                            onClick={() => navigate(`/play/${s.game_slug || slug}/${s.id}`)}
                            className="border-b border-line/50 last:border-0 hover:bg-surface-soft cursor-pointer transition-colors group"
                          >
                            <td className="px-4 py-2.5 text-xs text-muted whitespace-nowrap">
                              {s.created_at ? new Date(s.created_at).toLocaleDateString() : "—"}
                            </td>
                            <td className="px-4 py-2.5 text-xs text-ink font-medium">{s.agent_a || "Unknown"}</td>
                            <td className="px-4 py-2.5 text-xs text-ink font-medium">{s.agent_b || "Unknown"}</td>
                            <td className="px-4 py-2.5">{statusBadge(s.status)}</td>
                            <td className="px-4 py-2.5">
                              <div className="flex items-center gap-2">
                                {outcomeBadge(s.winner)}
                                {s.status === "completed" && s.is_public && (
                                  <span className="text-accent/60" title="Public — visible on leaderboard">
                                    <GlobeIcon />
                                  </span>
                                )}
                              </div>
                            </td>
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
                  <div className="mt-2.5">
                    <Link to={`/play/${slug}`} className="text-xs text-accent hover:underline no-underline">
                      + New {meta?.name ?? slug} match
                    </Link>
                  </div>
                </div>
              </div>
            </div>
          );
        })
      )}

      {/* Floating dropdown — rendered outside all tables to escape overflow:hidden */}
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
