import { useCallback, useEffect, useRef, useState, type ComponentType } from "react";
import { useNavigate } from "react-router-dom";
import { GameHeader } from "./GameHeader";
import { TabBar } from "./TabBar";
import { AutoConfigForm } from "./AutoConfigForm";
import { AutoHistoryView } from "./AutoHistoryView";
import { GameInstructionsPanel } from "./GameInstructionsPanel";
import { loadLiveView, loadConfigForm, loadHistoryView, loadPlayView } from "../games/registry";
import type { GameMetadata, Match, MailboxMessage } from "../types";
import { useApp } from "../hooks/useApp";
import { AppProvider } from "../state";
import type { AnimatedScores } from "../hooks/useCanvasRenderer";
import { getState, submitAction, getResults, getInteractiveState, ApiError } from "../api";
import { chooseAction } from "../agents";
import { copyToClipboard, resultToMatch } from "./utils";
import { LoadingSpinner } from "./LoadingSpinner";
import { SchemaPlayPanel } from "./SchemaPlayPanel";
import { MailboxPanel } from "./MailboxPanel";
import type { RunConfig, PlayerSide } from "../types";

interface GamePlayViewProps {
  game: GameMetadata;
  sessionId?: string | null;
  locked: boolean;
  sessionStatus: string;
  replayMatch: Match | null;
  sessionConfig: {
    agent_a: string;
    agent_b: string;
    rounds: number;
    num_battlefields: number;
    resources: number;
    seed?: number | null;
  } | null;
  createdAt?: string | null;
}

function GamePlayViewInner({ game, sessionId, locked, sessionStatus, replayMatch, sessionConfig, createdAt }: GamePlayViewProps) {
  const { state, setMatch, setSessionMeta, stopPlay, endGame } = useApp();
  const navigate = useNavigate();
  const hasLiveView = game.ui?.live_view ?? false;
  const hasInteractivePlay = game.ui?.interactive_play ?? false;
  const isInteractiveGame = state.pendingGame?.interactive ?? false;
  const effectiveLocked = locked || state.sessionLocked;
  const effectiveStatus = sessionStatus || state.sessionStatus;
  const isGameComplete = !!replayMatch || effectiveStatus === "completed";

  const showPlayTab = isInteractiveGame && !isGameComplete;
  const showLiveViewTab = hasLiveView && (isGameComplete || !isInteractiveGame);

  const tabs = [
    { id: "config", label: "Config" },
    ...(showPlayTab ? [{ id: "play", label: "Play" }] : []),
    ...(showLiveViewTab ? [{ id: "live", label: "Live View" }] : []),
    { id: "history", label: "History" },
  ];

  // Only default to "live" if we have something to show/play: a completed replay or an active token.
  // When the session is running but the token is gone, start on "config" so the user can start fresh.
  const initialTab = (replayMatch || state.pendingGame) ? (hasLiveView ? "live" : "history") : "config";
  const [activeTab, setActiveTab] = useState(initialTab);
  const [showKeyModal, setShowKeyModal] = useState(false);
  const [instructionsCollapsed, setInstructionsCollapsed] = useState(false);
  const [copiedKey, setCopiedKey] = useState<string | null>(null);
  const keyModalShownRef = useRef(false);
  const [prevReplayMatch, setPrevReplayMatch] = useState(replayMatch);
  if (prevReplayMatch !== replayMatch) {
    setPrevReplayMatch(replayMatch);
    if (replayMatch) setActiveTab(hasLiveView ? "live" : "history");
  }
  const [customUIMod, setCustomUIMod] = useState<{ live?: ComponentType<Record<string, unknown>>; config?: ComponentType<Record<string, unknown>>; history?: ComponentType<Record<string, unknown>>; play?: ComponentType<Record<string, unknown>> }>({});
  const [canvasCollapsed, setCanvasCollapsed] = useState(false);
  const [mailboxCollapsed, setMailboxCollapsed] = useState(false);
  const loadedRef = useRef(false);
  const gameLoopRef = useRef(false);
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const completedRef = useRef(false);
  const sessionRef = useRef<string | null>(null);
  const backoffRef = useRef(0);
  const prevSessionIdRef = useRef<string | null | undefined>(sessionId);

  // Auto-open key modal when remote keys first become available
  useEffect(() => {
    const keys = state.pendingGame?.remoteKeys;
    if (keys && !keyModalShownRef.current) {
      keyModalShownRef.current = true;
      setShowKeyModal(true);
    }
  }, [state.pendingGame?.remoteKeys]);

  // Clear pending game only when navigating away from a session (sessionId goes from present to absent)
  useEffect(() => {
    const prevId = prevSessionIdRef.current;
    if (prevId && !sessionId && state.pendingGame) {
      endGame();
    }
    prevSessionIdRef.current = sessionId;
  }, [sessionId, state.pendingGame, endGame]);

  useEffect(() => {
    const pg = state.pendingGame;
    if (!pg || gameLoopRef.current) return;
    gameLoopRef.current = true;
    completedRef.current = false;
    sessionRef.current = pg.sessionId;
    backoffRef.current = 0;
    // Switch to Play tab for interactive games, Live View for agent-only games
    const isInteractive = pg.interactive === true;
    setActiveTab(isInteractive ? "play" : "live");

    const buildMatch = (gs: Record<string, unknown>) => {
      const allPlayerIds = pg.agentIds ? Object.keys(pg.agentIds) : ["A", "B"];
      const totalScores = (gs.total_scores as Record<string, number>) ?? {};
      return {
        agent_a: pg.playerNames?.A ?? pg.agentAName,
        agent_b: pg.playerNames?.B ?? pg.agentBName,
        session_id: pg.sessionId,
        config_hash: (gs.config_hash as string) || "",
        num_rounds: pg.numRounds,
        num_battlefields: pg.numFields,
        total_resources: pg.totalResources,
        total_score_a: totalScores.A ?? 0,
        total_score_b: totalScores.B ?? 0,
        match_winner: undefined as PlayerSide | "Tie" | undefined,
        history: ((gs.history as Array<Record<string, unknown>>) || []).map((r) => {
          const moves = (r.allocations || r.actions || r.quantities || {}) as Record<string, unknown>;
          const scores = (r.payoffs || r.round_payoffs || r.scores || {}) as Record<string, number>;
          const totals = (r.total_scores || {}) as Record<string, number>;
          return {
            round: (r.round as number) || 0,
            agent_a: pg.playerNames?.A ?? pg.agentAName,
            agent_b: pg.playerNames?.B ?? pg.agentBName,
            action_a: moves.A,
            action_b: moves.B,
            score_a: scores.A ?? 0,
            score_b: scores.B ?? 0,
            total_score_a: totals.A ?? 0,
            total_score_b: totals.B ?? 0,
            winner: (r.winner as string || "Tie") as "A" | "B" | "Tie",
            raw: r,
          };
        }),
        metrics: {},
        currentState: gs,
        agents: pg.playerNames,
        total_scores: totalScores,
        player_ids: allPlayerIds,
      };
    };

    const tokens = pg.tokens;
    const isInteractiveGame = pg.interactive === true;
    let humanPlayer: string | null = null;
    if (pg.agentIds) {
      for (const [player, agentId] of Object.entries(pg.agentIds)) {
        if (agentId === "interactive") { humanPlayer = player; break; }
      }
    }
    if (!humanPlayer) {
      humanPlayer = pg.agentAId === "interactive" ? "A" : pg.agentBId === "interactive" ? "B" : null;
    }
    const fetchState = () => isInteractiveGame && humanPlayer
      ? getInteractiveState(pg.sessionId, humanPlayer)
      : getState(pg.sessionId);

    const scheduleTick = () => {
      timerRef.current = setTimeout(async () => {
        if (!gameLoopRef.current || completedRef.current) return;
        if (sessionRef.current !== pg.sessionId) return;
        try {
          let gameState = await fetchState();

          const allPlayers = (pg.agentIds ? Object.keys(pg.agentIds) : ["A", "B"]) as PlayerSide[];
          for (const player of allPlayers) {
            if (!gameState.awaiting.includes(player)) continue;
            const agentId = pg.agentIds?.[player] ?? (player === "A" ? pg.agentAId : pg.agentBId);
            if (agentId === "remote" || agentId === "interactive") continue;
            const action = chooseAction(agentId, player, gameState, pg.gameSlug);
            const updated = await submitAction(pg.sessionId, action, tokens[player]);
            gameState = updated;
          }

          gameState = await fetchState();
          if (sessionRef.current !== pg.sessionId) return;
          setMatch(buildMatch(gameState));

          if (gameState.phase === "complete") {
            completedRef.current = true;
            const result = await getResults(pg.sessionId);
            if (sessionRef.current !== pg.sessionId) return;
            const payload: RunConfig = {
              agent_a: pg.agentAName,
              agent_b: pg.agentBName,
              num_rounds: pg.numRounds,
              num_battlefields: pg.numFields,
              total_resources: pg.totalResources,
              session_id: pg.sessionId,
            };
            setMatch(resultToMatch(result as never, payload));
            stopPlay();
            gameLoopRef.current = false;
            setActiveTab("history");
            endGame();
            // Navigate to the session URL so the page has a stable, reloadable URL
            // for the completed session. This also ensures the dashboard/history page
            // can link back to this session.
            navigate(`/play/${pg.gameSlug}/${pg.sessionId}`, { replace: true });
            return;
          }

          backoffRef.current = 1000;
          scheduleTick();
        } catch (err) {
          if (!gameLoopRef.current || sessionRef.current !== pg.sessionId) return;
          // Session deleted or not found — stop the loop and clear pending state
          if (err instanceof ApiError && (err.status === 404 || err.status === 410)) {
            completedRef.current = true;
            gameLoopRef.current = false;
            endGame();
            return;
          }
          console.error("Game poll error:", err);
          backoffRef.current = Math.min(backoffRef.current * 2, 16000);
          scheduleTick();
        }
      }, backoffRef.current);
    };

    scheduleTick();

    return () => {
      gameLoopRef.current = false;
      sessionRef.current = null;
      if (timerRef.current) clearTimeout(timerRef.current);
    };
  }, [state.pendingGame, setMatch, stopPlay, endGame, navigate]);

  const [dynamicLoadError, setDynamicLoadError] = useState(false);

  useEffect(() => {
    if (loadedRef.current) return;
    loadedRef.current = true;
    const slug = game.slug || game.name;
    if (hasLiveView) {
      loadLiveView(slug).then((mod) => {
        if (mod) setCustomUIMod(prev => ({ ...prev, live: mod.default as ComponentType<Record<string, unknown>> }));
        else setDynamicLoadError(true);
      }).catch((err) => {
        console.error("Failed to load LiveView:", err);
        setDynamicLoadError(true);
      });
    }
    if (game.ui?.custom_config) {
      loadConfigForm(slug).then((mod) => {
        if (mod) setCustomUIMod(prev => ({ ...prev, config: mod.default as ComponentType<Record<string, unknown>> }));
      }).catch((err) => {
        console.error("Failed to load ConfigForm:", err);
      });
    }
    if (game.ui?.custom_history) {
      loadHistoryView(slug).then((mod) => {
        if (mod) setCustomUIMod(prev => ({ ...prev, history: mod.default as ComponentType<Record<string, unknown>> }));
      }).catch((err) => {
        console.error("Failed to load HistoryView:", err);
      });
    }
    if (hasInteractivePlay) {
      loadPlayView(slug).then((mod) => {
        if (mod) setCustomUIMod(prev => ({ ...prev, play: mod.default as ComponentType<Record<string, unknown>> }));
        // null = no PlayView.tsx; SchemaPlayPanel is used as fallback
      }).catch((err) => {
        console.error("Failed to load PlayView:", err);
      });
    }
  }, [game.name, game.slug, game.ui, hasLiveView, hasInteractivePlay]);

  useEffect(() => {
    if (sessionConfig) {
      setSessionMeta(effectiveLocked, effectiveStatus, effectiveLocked ? {
        agent_a: sessionConfig.agent_a,
        agent_b: sessionConfig.agent_b,
        num_rounds: sessionConfig.rounds,
        num_battlefields: sessionConfig.num_battlefields,
        total_resources: sessionConfig.resources,
      } : null);
    } else {
      setSessionMeta(false, "", null);
    }
  }, [sessionConfig, effectiveStatus, effectiveLocked, setSessionMeta]);

  useEffect(() => {
    if (replayMatch) {
      // eslint-disable-next-line react-hooks/set-state-in-effect
      setCanvasCollapsed(false);
      setMatch(replayMatch);
    }
  }, [replayMatch, setMatch]);

  // Fetch state for active sessions without pendingGame (read-only mode) with polling
  useEffect(() => {
    if (!sessionId || state.pendingGame || replayMatch) return;
    if (sessionStatus !== "ready" && sessionStatus !== "running") return;

    let active = true;
    let timer: ReturnType<typeof setTimeout> | null = null;

    const buildMatch = (gameState: Record<string, unknown>) => {
      const totalScores = (gameState.total_scores as Record<string, number>) ?? {};
      return {
        agent_a: sessionConfig?.agent_a ?? "Player A",
        agent_b: sessionConfig?.agent_b ?? "Player B",
        session_id: sessionId,
        config_hash: (gameState.config_hash as string) || "",
        num_rounds: (gameState.round_total as number) ?? 10,
        num_battlefields: (gameState.battlefields as Array<Record<string, unknown>> | undefined)?.length ?? 0,
        total_resources: (gameState.budgets as Record<string, number> | undefined)?.A ?? 0,
        total_score_a: totalScores.A ?? 0,
        total_score_b: totalScores.B ?? 0,
        match_winner: undefined as PlayerSide | "Tie" | undefined,
        history: ((gameState.history as unknown as Array<Record<string, unknown>>) || []).map((r) => {
          const moves = (r.allocations || r.actions || r.quantities || {}) as Record<string, unknown>;
          const scores = (r.payoffs || r.round_payoffs || r.scores || {}) as Record<string, number>;
          const totals = (r.total_scores || {}) as Record<string, number>;
          return {
            round: (r.round as number) || 0,
            agent_a: sessionConfig?.agent_a ?? "Player A",
            agent_b: sessionConfig?.agent_b ?? "Player B",
            action_a: moves.A,
            action_b: moves.B,
            score_a: scores.A ?? 0,
            score_b: scores.B ?? 0,
            total_score_a: totals.A ?? 0,
            total_score_b: totals.B ?? 0,
            winner: (r.winner as string || "Tie") as "A" | "B" | "Tie",
            raw: r,
          };
        }),
        metrics: {},
        currentState: gameState,
        total_scores: totalScores,
      } as Match;
    };

    const poll = async () => {
      if (!active) return;
      try {
        const gameState = await getState(sessionId);
        if (!active) return;
        setMatch(buildMatch(gameState));

        if (gameState.phase === "complete") {
          const result = await getResults(sessionId);
          if (!active) return;
          const payload: RunConfig = {
            agent_a: sessionConfig?.agent_a ?? "Player A",
            agent_b: sessionConfig?.agent_b ?? "Player B",
            num_rounds: gameState.round_total,
            num_battlefields: ((gameState.battlefields as Array<Record<string, unknown>> | undefined) ?? []).length,
            total_resources: (gameState.budgets as Record<string, number> | undefined)?.A ?? 0,
            session_id: sessionId,
          };
          setMatch(resultToMatch(result as never, payload));
          return;
        }

        timer = setTimeout(poll, 1000);
      } catch (err) {
        console.error("Read-only poll error:", err);
        if (active) timer = setTimeout(poll, 2000);
      }
    };

    poll();

    return () => {
      active = false;
      if (timer) clearTimeout(timer);
    };
  }, [sessionId, sessionStatus, state.pendingGame, replayMatch, sessionConfig, setMatch]);

  const hasMatch = !!replayMatch || !!state.activeMatch;
  const scoresRef = useRef<AnimatedScores>({ displayedScoreA: 0, displayedScoreB: 0 });

  const handleScores = useCallback((s: AnimatedScores) => {
    scoresRef.current = s;
  }, []);

  const initialValues = sessionConfig ? {
    rounds: sessionConfig.rounds,
    num_battlefields: sessionConfig.num_battlefields,
    total_resources: sessionConfig.resources,
    seed: sessionConfig.seed ?? undefined,
    agent_a: sessionConfig.agent_a,
    agent_b: sessionConfig.agent_b,
  } : undefined;

  const schema = (game.config_schema as Record<string, unknown>) ?? {};

  const remoteKeys = state.pendingGame?.remoteKeys;
  const hasRemoteKeys = !!remoteKeys && Object.keys(remoteKeys).length > 0;

  const handleAbandonGame = () => {
    if (window.confirm("Leave this game? The session will remain on the server but you won't be able to resume it from here.")) {
      gameLoopRef.current = false;
      if (timerRef.current) clearTimeout(timerRef.current);
      endGame();
      setActiveTab("config");
    }
  };

  return (
    <div className="flex flex-col flex-1 min-h-0">
      <GameHeader game={game} locked={effectiveLocked} status={effectiveStatus} createdAt={createdAt} />
      <TabBar tabs={tabs} activeTab={activeTab} onTabChange={setActiveTab} />

      {/* Session key modal */}
      {showKeyModal && hasRemoteKeys && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/40 backdrop-blur-sm" onClick={() => setShowKeyModal(false)}>
          <div className="bg-surface rounded-[var(--radius-card)] shadow-elevation-5 border border-line w-full max-w-sm p-5" onClick={(e) => e.stopPropagation()}>
            <div className="flex items-center justify-between mb-4">
              <h2 className="font-extrabold text-ink text-sm">Remote Agent Keys</h2>
              <button type="button" onClick={() => setShowKeyModal(false)} className="w-7 h-7 flex items-center justify-center rounded-lg hover:bg-surface-container text-muted hover:text-ink transition-colors">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
              </button>
            </div>
            <p className="text-xs text-muted mb-4">Pass these as the <code className="bg-ink/8 px-1 rounded text-[10px]">OUTPLAYARENA_KEY</code> environment variable to your agent(s).</p>
            {Object.entries(remoteKeys!).map(([side, key]) => (
              <div key={side} className="mb-3">
                <div className="text-[10px] font-extrabold text-muted uppercase tracking-wider mb-1.5">Player {side}</div>
                <div className="flex items-center gap-2 bg-surface-soft border border-line rounded-[var(--radius-chip)] px-3 py-2">
                  <code className="flex-1 text-[11px] font-mono text-ink break-all leading-relaxed">{key}</code>
                  <button
                    type="button"
                    onClick={async () => {
                      const ok = await copyToClipboard(key);
                      if (ok) {
                        setCopiedKey(side);
                        setTimeout(() => setCopiedKey(null), 1500);
                      }
                    }}
                    title={copiedKey === side ? "Copied!" : "Copy"}
                    className="shrink-0 w-7 h-7 flex items-center justify-center rounded hover:bg-accent/10 text-muted hover:text-accent transition-colors"
                  >
                    {copiedKey === side ? (
                      <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                        <polyline points="20 6 9 17 4 12" />
                      </svg>
                    ) : (
                      <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                        <rect x="9" y="9" width="13" height="13" rx="2" ry="2" />
                        <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1" />
                      </svg>
                    )}
                  </button>
                </div>
              </div>
            ))}
            <button
              type="button"
              onClick={() => setShowKeyModal(false)}
              className="mt-2 w-full py-2.5 rounded-xl bg-accent text-white text-sm font-bold hover:bg-accent/90 transition-colors"
            >
              Got it
            </button>
          </div>
        </div>
      )}

      <div className="flex-1 flex flex-row min-h-0">
        <div className="flex-1 flex flex-col min-h-0 min-w-0">
        {activeTab === "config" && (
          <div className="flex-1 overflow-y-auto overflow-x-visible">
            {customUIMod.config ? (
              <customUIMod.config
                gameSlug={game.slug || game.name}
                schema={schema}
                locked={effectiveLocked}
                sessionStatus={effectiveStatus}
                initialValues={initialValues}
              />
            ) : (
              <AutoConfigForm
                gameSlug={game.slug || game.name}
                schema={schema}
                locked={effectiveLocked}
                sessionStatus={effectiveStatus}
                initialValues={initialValues}
              />
            )}
          </div>
        )}
        {activeTab === "play" && showPlayTab && (
          <div className="flex-1 min-h-0 flex flex-col">
            {/* Play tab toolbar: abandon + key access */}
            <div className="shrink-0 border-b border-line bg-surface-soft flex items-center justify-end gap-1 px-2 py-1">
              {hasRemoteKeys && (
                <button
                  type="button"
                  onClick={() => setShowKeyModal(true)}
                  title="Show API keys"
                  className="flex items-center gap-1 px-2 py-1 rounded-lg text-[11px] font-semibold text-muted hover:text-accent hover:bg-accent/8 transition-colors"
                >
                  <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <circle cx="7" cy="17" r="3"/><path d="M10.85 13.15 21 3"/><path d="M19 5l2 2"/><path d="M15 9l2 2"/>
                  </svg>
                  API Keys
                </button>
              )}
              <button
                type="button"
                onClick={handleAbandonGame}
                title="Leave game"
                className="flex items-center gap-1 px-2 py-1 rounded-lg text-[11px] font-semibold text-muted hover:text-red-500 hover:bg-red-500/8 transition-colors"
              >
                <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"/><polyline points="16 17 21 12 16 7"/><line x1="21" y1="12" x2="9" y2="12"/>
                </svg>
                Leave
              </button>
            </div>
            {customUIMod.play ? (
              <customUIMod.play
                gameSlug={game.slug || game.name}
                game={game}
                sessionConfig={sessionConfig}
                onGameEnd={() => setActiveTab("history")}
              />
            ) : (
              <SchemaPlayPanel onGameEnd={() => setActiveTab("history")} />
            )}
            {isInteractiveGame && state.pendingGame && (() => {
              const pg = state.pendingGame;
              const humanPlayer = Object.entries(pg.agentIds ?? {}).find(([, id]) => id === "interactive")?.[0]
                ?? (pg.agentAId === "interactive" ? "A" : pg.agentBId === "interactive" ? "B" : null);
              const allPlayers = pg.agentIds ? Object.keys(pg.agentIds) : ["A", "B"];
              const messages = (state.activeMatch?.currentState?.messages as MailboxMessage[]) ?? [];
              const token = humanPlayer && pg.tokens ? pg.tokens[humanPlayer] : null;
              if (!humanPlayer || !token) return null;
              return (
                <MailboxPanel
                  sessionId={pg.sessionId}
                  playerToken={token}
                  humanPlayer={humanPlayer}
                  allPlayers={allPlayers}
                  messages={messages}
                  disabled={isGameComplete}
                  collapsed={mailboxCollapsed}
                  onToggleCollapse={() => setMailboxCollapsed((c) => !c)}
                />
              );
            })()}
          </div>
        )}
        {activeTab === "live" && showLiveViewTab && (
          <div className="flex-1 min-h-0 flex flex-col">
            {customUIMod.live ? (
              <customUIMod.live onScores={handleScores} onToggleCollapse={() => setCanvasCollapsed(true)} createdAt={createdAt || null} />
            ) : dynamicLoadError ? (
              <div className="flex items-center justify-center flex-1 text-muted text-sm">
                Failed to load Live View. Check the browser console for details.
              </div>
            ) : (
              <LoadingSpinner className="flex-1" />
            )}
          </div>
        )}
        {activeTab === "history" && (
          <div className="flex-1 overflow-y-auto">
            {customUIMod.history ? (
              <customUIMod.history
                hasMatch={hasMatch}
                canvasCollapsed={canvasCollapsed}
                onExpandCanvas={() => setCanvasCollapsed(false)}
                gameSlug={game.slug}
              />
            ) : (
              <AutoHistoryView
                hasMatch={hasMatch}
                canvasCollapsed={canvasCollapsed}
                onExpandCanvas={() => setCanvasCollapsed(false)}
                gameSlug={game.slug}
              />
            )}
          </div>
        )}
        </div>
        <GameInstructionsPanel
          gameSlug={game.slug || game.name}
          collapsed={instructionsCollapsed}
          onToggle={() => setInstructionsCollapsed((c) => !c)}
        />
      </div>
    </div>
  );
}

export function GamePlayView(props: GamePlayViewProps) {
  const slug = props.game.slug || props.game.name;
  return (
    <AppProvider gameSlug={slug}>
      <GamePlayViewInner {...props} />
    </AppProvider>
  );
}
