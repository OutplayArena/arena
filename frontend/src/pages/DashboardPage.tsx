import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { getDashboard, createExperiment, getState, submitAction, getResults, listGames, deleteSession } from "../api";
import { buildBattlefields, resultToMatch } from "../components/utils";
import { chooseAction } from "../agents";
import { randomAgentName } from "../components/names";
import type { DashboardResponse, RunConfig, GameEntry } from "../types";

const outcomeBadge = (winner: string | null) => {
  if (!winner) return null;
  const color = winner === "A" ? "text-agent-a bg-agent-a/10" : winner === "B" ? "text-agent-b bg-agent-b/10" : "text-muted bg-ink/6";
  return <span className={`text-[11px] font-extrabold px-2 py-0.5 rounded-chip ${color}`}>{winner === "Tie" ? "Tie" : `Agent ${winner}`}</span>;
};

const statusBadge = (status: string) => {
  const map: Record<string, string> = {
    ready: "bg-[#d4edda] text-[#155724]",
    running: "bg-[#cce5ff] text-[#004085] animate-pulse",
    completed: "bg-[#1e7e34] text-white",
    failed: "bg-[#f8d7da] text-[#721c24]",
  };
  const cls = map[status] || "bg-ink/8 text-muted";
  return <span className={`text-[11px] font-extrabold px-2 py-0.5 rounded-chip ${cls}`}>{status}</span>;
};

export function DashboardPage() {
  const [data, setData] = useState<DashboardResponse | null>(null);
  const [gamesMeta, setGamesMeta] = useState<GameEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [quickStarting, setQuickStarting] = useState(false);
  const [deleting, setDeleting] = useState<string | null>(null);
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
        if (!cancelled) {
          setData(d);
          setGamesMeta(g);
        }
      } catch (err) {
        if (!cancelled) setError(err instanceof Error ? err.message : String(err));
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => { cancelled = true; };
  }, []);

  const handleDelete = async (e: React.MouseEvent, sessionId: string) => {
    e.stopPropagation();
    setDeleting(sessionId);
    try {
      await deleteSession(sessionId);
      await refreshDashboard();
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setDeleting(null);
    }
  };

  const handleUseAsTemplate = (e: React.MouseEvent, s: DashboardResponse["games"][string][0]) => {
    e.stopPropagation();
    const params = new URLSearchParams();
    if (s.agent_a) params.set("agent_a", s.agent_a);
    if (s.agent_b) params.set("agent_b", s.agent_b);
    if (s.rounds) params.set("rounds", String(s.rounds));
    if (s.num_battlefields) params.set("fields", String(s.num_battlefields));
    if (s.resources) params.set("resources", String(s.resources));
    const slug = s.game_slug || "blotto";
    navigate(`/play/${slug}?${params.toString()}`);
  };

  const doQuickStart = async () => {
    setQuickStarting(true);
    try {
      const agentNameA = randomAgentName();
      const agentNameB = randomAgentName();
      const config = {
        game: "blotto",
        variant: "classic",
        players: 2,
        budget: [100, 100] as [number, number],
        battlefields: buildBattlefields(5),
        rounds: 5,
        seed: null,
        agents: { A: agentNameA, B: agentNameB },
      };
      const payload: RunConfig = {
        agent_a: "uniform",
        agent_b: "greedy",
        num_rounds: 5,
        num_battlefields: 5,
        total_resources: 100,
      };

      const created = await createExperiment(config);
      payload.session_id = created.session_id;
      let gameState = await getState(created.session_id);

      while (gameState.phase !== "complete") {
        for (const player of ["A", "B"] as const) {
          if (!gameState.awaiting.includes(player)) continue;
          const agent = player === "A" ? payload.agent_a : payload.agent_b;
          const action = chooseAction(agent, player, gameState);
          gameState = await submitAction(created.session_id, action, created.player_tokens[player]);
        }
      }

      const result = await getResults(created.session_id);
      const match = resultToMatch(result, payload);
      navigate(`/play/blotto/${created.session_id}`, { state: { match } });
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setQuickStarting(false);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-[calc(100dvh-56px)] text-muted text-sm">
        Loading...
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex items-center justify-center h-[calc(100dvh-56px)] text-muted text-sm">
        {error}
      </div>
    );
  }

  const gameSlugs = Object.keys(data?.games ?? {});

  return (
    <div className="max-w-4xl mx-auto px-6 py-8">
      <div className="mb-8">
        <h1 className="text-2xl font-black text-ink tracking-tight mb-1">Dashboard</h1>
        <p className="text-sm text-muted">
          {data?.total_games ?? 0} game{data?.total_games !== 1 ? "s" : ""} played
        </p>
      </div>

      <div className="mb-8">
        <button
          type="button"
          onClick={doQuickStart}
          disabled={quickStarting}
          className="inline-flex items-center justify-center min-h-[46px] px-6 text-white bg-accent border-accent rounded-button font-extrabold text-sm shadow-elevation-3 transition-[transform,background,box-shadow] duration-200 hover:-translate-y-px hover:shadow-elevation-4 active:translate-y-0.5 disabled:cursor-not-allowed disabled:bg-line/50 disabled:border-line/50 disabled:text-quiet disabled:shadow-none mr-3"
        >
          {quickStarting ? "Starting..." : "Quick Start"}
        </button>
        <Link
          to="/play"
          className="inline-flex items-center justify-center min-h-[46px] px-6 text-ink border border-line/40 rounded-button font-semibold text-sm shadow-elevation-1 transition-[transform,background,box-shadow] duration-200 hover:-translate-y-px hover:shadow-elevation-2 hover:bg-surface active:translate-y-0.5"
        >
          New Game
        </Link>
      </div>

      {gameSlugs.length === 0 ? (
        <div className="p-8 text-center border border-line/20 rounded-card">
          <p className="text-sm text-muted">No games played yet.</p>
          <p className="text-xs text-quiet mt-1">Start a new game above to see your history.</p>
        </div>
      ) : (
        gameSlugs.map((slug) => {
          const sessions = data?.games[slug] ?? [];
          const meta = gamesMeta.find((g) => g.name === slug);
          return (
            <div key={slug} className="mb-8">
              <div className="flex items-center justify-between mb-3">
                <h2 className="text-lg font-extrabold text-ink capitalize">{meta?.name ?? slug}</h2>
                <Link
                  to={`/history?game=${slug}`}
                  className="text-xs font-semibold text-accent hover:underline"
                >
                  View all &rarr;
                </Link>
              </div>
              {meta?.description && (
                <p className="text-xs text-muted mb-3 -mt-1">{meta.description}</p>
              )}
              <div className="rounded-card border border-line/40 overflow-hidden">
                <table className="w-full text-left text-sm">
                  <thead>
                    <tr className="border-b border-line/40 bg-surface-container/50">
                      <th className="px-4 py-2.5 text-[11px] font-extrabold text-muted">Date</th>
                      <th className="px-4 py-2.5 text-[11px] font-extrabold text-muted">Agent A</th>
                      <th className="px-4 py-2.5 text-[11px] font-extrabold text-muted">Agent B</th>
                      <th className="px-4 py-2.5 text-[11px] font-extrabold text-muted">Status</th>
                      <th className="px-4 py-2.5 text-[11px] font-extrabold text-muted">Outcome</th>
                      <th className="px-3 py-2.5 w-0" />
                    </tr>
                  </thead>
                  <tbody>
                    {sessions.map((s) => (
                      <tr
                        key={s.id}
                        onClick={() => navigate(`/play/${s.game_slug || "blotto"}/${s.id}`)}
                        className="border-b border-line/20 last:border-b-0 hover:bg-ink/[0.03] cursor-pointer transition-colors group"
                      >
                        <td className="px-4 py-2.5 text-xs text-muted whitespace-nowrap">
                          {s.created_at ? new Date(s.created_at).toLocaleDateString() : "-"}
                        </td>
                        <td className="px-4 py-2.5 text-xs text-ink font-medium">
                          {s.agent_a || "Unknown"}
                        </td>
                        <td className="px-4 py-2.5 text-xs text-ink font-medium">
                          {s.agent_b || "Unknown"}
                        </td>
                        <td className="px-4 py-2.5">{statusBadge(s.status)}</td>
                        <td className="px-4 py-2.5">{outcomeBadge(s.winner)}</td>
                        <td className="px-2 py-2.5">
                          <div className="flex items-center gap-0.5 opacity-0 group-hover:opacity-100 transition-opacity">
                            {s.locked && (
                              <span title="Created via programmatic API" className="w-7 h-7 flex items-center justify-center text-muted">
                                <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                                  <rect x="3" y="11" width="18" height="11" rx="2" ry="2" />
                                  <path d="M7 11V7a5 5 0 0 1 10 0v4" />
                                </svg>
                              </span>
                            )}
                            {!s.locked && (
                              <button
                                type="button"
                                onClick={(e) => handleUseAsTemplate(e, s)}
                                title="Use as template"
                                className="w-7 h-7 flex items-center justify-center rounded-md text-muted hover:text-accent hover:bg-accent/[0.12] cursor-pointer transition-colors"
                              >
                                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                                  <rect x="9" y="9" width="13" height="13" rx="2" ry="2" />
                                  <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1" />
                                </svg>
                              </button>
                            )}
                            <button
                              type="button"
                              onClick={(e) => handleDelete(e, s.id)}
                              disabled={deleting === s.id}
                              title="Delete"
                              className="w-7 h-7 flex items-center justify-center rounded-md text-muted hover:text-red-500 hover:bg-red-500/15 cursor-pointer transition-colors disabled:opacity-30 disabled:cursor-not-allowed"
                            >
                              {deleting === s.id ? (
                                <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="animate-spin">
                                  <circle cx="12" cy="12" r="10" strokeDasharray="31.4" strokeDashoffset="10" />
                                </svg>
                              ) : (
                                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                                  <line x1="18" y1="6" x2="6" y2="18" />
                                  <line x1="6" y1="6" x2="18" y2="18" />
                                </svg>
                              )}
                            </button>
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <div className="mt-3">
                  <Link
                    to={`/play/${slug}`}
                    className="text-xs font-semibold text-accent hover:underline"
                  >
                    + Configure new Game
                  </Link>
              </div>
            </div>
          );
        })
      )}
    </div>
  );
}
