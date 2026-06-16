import { useCallback, useEffect, useRef, useState, type ComponentType } from "react";
import { GameHeader } from "./GameHeader";
import { TabBar } from "./TabBar";
import { AutoConfigForm } from "./AutoConfigForm";
import { AutoHistoryView } from "./AutoHistoryView";
import { loadLiveView, loadConfigForm, loadHistoryView } from "../games/registry";
import type { GameMetadata, Match } from "../types";
import { useApp } from "../hooks/useApp";
import { AppProvider } from "../state";
import type { AnimatedScores } from "../hooks/useCanvasRenderer";
import { getState, submitAction, getResults } from "../api";
import { chooseAction } from "../agents";
import { resultToMatch, copyToClipboard } from "./utils";
import { LoadingSpinner } from "./LoadingSpinner";
import { InteractiveAgentPanel } from "./InteractiveAgentPanel";
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
  const hasLiveView = game.ui?.live_view ?? false;

  const tabs = [
    { id: "config", label: "Config" },
    ...(hasLiveView ? [{ id: "live", label: "Live View" }] : []),
    { id: "history", label: "History" },
  ];

  const isActiveSession = sessionStatus === "ready" || sessionStatus === "running";
  const initialTab = replayMatch || isActiveSession || state.pendingGame ? "live" : "config";
  const [activeTab, setActiveTab] = useState(initialTab);
  const [prevReplayMatch, setPrevReplayMatch] = useState(replayMatch);
  if (prevReplayMatch !== replayMatch) {
    setPrevReplayMatch(replayMatch);
    if (replayMatch) setActiveTab("live");
  }
  const [customUIMod, setCustomUIMod] = useState<{ live?: ComponentType<Record<string, unknown>>; config?: ComponentType<Record<string, unknown>>; history?: ComponentType<Record<string, unknown>> }>({});
  const [canvasCollapsed, setCanvasCollapsed] = useState(false);
  const loadedRef = useRef(false);
  const gameLoopRef = useRef(false);
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const completedRef = useRef(false);
  const sessionRef = useRef<string | null>(null);
  const backoffRef = useRef(0);

  useEffect(() => {
    const pg = state.pendingGame;
    if (!pg || gameLoopRef.current) return;
    gameLoopRef.current = true;
    completedRef.current = false;
    sessionRef.current = pg.sessionId;
    backoffRef.current = 1000;
    setActiveTab("live");

    const buildMatch = (gs: Record<string, unknown>) => ({
      agent_a: pg.playerNames?.A ?? pg.agentAName,
      agent_b: pg.playerNames?.B ?? pg.agentBName,
      session_id: pg.sessionId,
      config_hash: (gs.config_hash as string) || "",
      num_rounds: pg.numRounds,
      num_battlefields: pg.numFields,
      total_resources: pg.totalResources,
      total_score_a: ((gs.total_scores as Record<string, number>)?.A) || 0,
      total_score_b: ((gs.total_scores as Record<string, number>)?.B) || 0,
      match_winner: undefined as PlayerSide | "Tie" | undefined,
      history: ((gs.history as Array<Record<string, unknown>>) || []).map((r) => {
        const moves = (r.allocations || r.actions || r.quantities || {}) as Record<string, unknown>;
        const scores = (r.payoffs || r.round_payoffs || r.scores || {}) as Record<string, number>;
        const totals = (r.total_scores || {}) as Record<string, number>;
        return {
          round: (r.round as number) || 0,
          agent_a: pg.agentAName,
          agent_b: pg.agentBName,
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
    });

    const tokens = pg.tokens;

    const scheduleTick = () => {
      timerRef.current = setTimeout(async () => {
        if (!gameLoopRef.current || completedRef.current) return;
        if (sessionRef.current !== pg.sessionId) return;
        try {
          let gameState = await getState(pg.sessionId);

          const allPlayers = (pg.agentIds ? Object.keys(pg.agentIds) : ["A", "B"]) as PlayerSide[];
          for (const player of allPlayers) {
            if (!gameState.awaiting.includes(player)) continue;
            const agentId = pg.agentIds?.[player] ?? (player === "A" ? pg.agentAId : pg.agentBId);
            if (agentId === "remote" || agentId === "interactive") continue;
            const action = chooseAction(agentId, player, gameState, pg.gameSlug);
            const updated = await submitAction(pg.sessionId, action, tokens[player]);
            gameState = updated;
          }

          gameState = await getState(pg.sessionId);
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
            endGame();
            return;
          }

          backoffRef.current = 1000;
          scheduleTick();
        } catch (err) {
          if (!gameLoopRef.current || sessionRef.current !== pg.sessionId) return;
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
  }, [state.pendingGame, setMatch, stopPlay, endGame]);

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
  }, [game.name, game.slug, game.ui, hasLiveView]);

  useEffect(() => {
    if (sessionConfig) {
      setSessionMeta(locked, sessionStatus, locked ? {
        agent_a: sessionConfig.agent_a,
        agent_b: sessionConfig.agent_b,
        num_rounds: sessionConfig.rounds,
        num_battlefields: sessionConfig.num_battlefields,
        total_resources: sessionConfig.resources,
      } : null);
    } else {
      setSessionMeta(false, "", null);
    }
  }, [sessionConfig, sessionStatus, locked, setSessionMeta]);

  useEffect(() => {
    if (replayMatch) {
      // eslint-disable-next-line react-hooks/set-state-in-effect
      setCanvasCollapsed(false);
      setMatch(replayMatch);
    }
  }, [replayMatch, setMatch]);

  // Fetch state for active sessions without pendingGame (read-only mode)
  useEffect(() => {
    if (!sessionId || state.pendingGame || replayMatch) return;
    if (sessionStatus !== "ready" && sessionStatus !== "running") return;

    const fetchState = async () => {
      try {
        const gameState = await getState(sessionId);
        const match = {
          agent_a: sessionConfig?.agent_a ?? "Player A",
          agent_b: sessionConfig?.agent_b ?? "Player B",
          session_id: sessionId,
          config_hash: (gameState.config_hash as string) || "",
          num_rounds: gameState.round_total,
          num_battlefields: (gameState.battlefields as Array<Record<string, unknown>> | undefined)?.length ?? 0,
          total_resources: (gameState.budgets as Record<string, number> | undefined)?.A ?? 0,
          total_score_a: ((gameState.total_scores as Record<string, number>)?.A) || 0,
          total_score_b: ((gameState.total_scores as Record<string, number>)?.B) || 0,
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
        };
        setMatch(match);
      } catch (err) {
        console.error("Failed to fetch session state:", err);
      }
    };

    fetchState();
  }, [sessionId, sessionStatus, state.pendingGame, replayMatch, sessionConfig, setMatch]);

  const hasMatch = !!replayMatch;
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

  return (
    <div className="flex flex-col flex-1 min-h-0">
      <GameHeader game={game} locked={locked} status={sessionStatus} createdAt={createdAt} />
      {state.pendingGame?.remoteKeys && Object.keys(state.pendingGame.remoteKeys).length > 0 && (
        <div className="shrink-0 mx-4 mt-3 p-3 rounded-card border border-accent/30 bg-accent/5">
          <h3 className="text-xs font-extrabold text-ink mb-1.5">Remote Agent Keys</h3>
          <p className="text-[11px] text-muted mb-2">
            Pass these to your LLM agents as <code className="bg-ink/8 px-1 rounded text-[10px]">NASH_ARENA_KEY</code>.
          </p>
          {Object.entries(state.pendingGame.remoteKeys).map(([player, key]) => (
            <div key={player} className="flex items-center gap-2 mt-1">
              <span className="text-[10px] font-extrabold text-muted uppercase shrink-0">Player {player}</span>
              <span className="text-xs text-ink font-medium truncate max-w-[120px]">{player === "A" ? state.pendingGame!.agentAName : state.pendingGame!.agentBName}</span>
              <code className="flex-1 text-[10px] bg-ink/6 px-2 py-1 rounded text-ink break-all font-mono">{key}</code>
              <button
                type="button"
                onClick={() => copyToClipboard(key)}
                title="Copy key"
                className="w-6 h-6 flex items-center justify-center rounded-md text-muted hover:text-accent hover:bg-accent/[0.12] cursor-pointer transition-colors shrink-0"
              >
                <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <rect x="9" y="9" width="13" height="13" rx="2" ry="2" />
                  <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1" />
                </svg>
              </button>
            </div>
          ))}
        </div>
      )}
      <TabBar tabs={tabs} activeTab={activeTab} onTabChange={setActiveTab} />
      <div className="flex-1 flex flex-col min-h-0">
        {activeTab === "config" && (
          <div className="flex-1 overflow-y-auto overflow-x-visible">
            {customUIMod.config ? (
              <customUIMod.config
                gameSlug={game.slug || game.name}
                schema={schema}
                locked={locked}
                sessionStatus={sessionStatus}
                initialValues={initialValues}
              />
            ) : (
              <AutoConfigForm
                gameSlug={game.slug || game.name}
                schema={schema}
                locked={locked}
                sessionStatus={sessionStatus}
                initialValues={initialValues}
              />
            )}
          </div>
        )}
        {activeTab === "live" && hasLiveView && (
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
            {state.pendingGame && (state.pendingGame.agentAId === "interactive" || state.pendingGame.agentBId === "interactive") && (
              <InteractiveAgentPanel />
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
    </div>
  );
}

export function GamePlayView(props: GamePlayViewProps) {
  return (
    <AppProvider>
      <GamePlayViewInner {...props} />
    </AppProvider>
  );
}
