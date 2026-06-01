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

interface GamePlayViewProps {
  game: GameMetadata;
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

function GamePlayViewInner({ game, locked, sessionStatus, replayMatch, sessionConfig, createdAt }: GamePlayViewProps) {
  const { setMatch, setSessionMeta } = useApp();
  const hasLiveView = game.ui?.live_view ?? false;

  const tabs = [
    { id: "config", label: "Config" },
    ...(hasLiveView ? [{ id: "live", label: "Live View" }] : []),
    { id: "history", label: "History" },
  ];

  const defaultTab = "config";
  const [activeTab, setActiveTab] = useState(defaultTab);
  const [CustomLiveView, setCustomLiveView] = useState<ComponentType<Record<string, unknown>> | null>(null);
  const [CustomConfigForm, setCustomConfigForm] = useState<ComponentType<Record<string, unknown>> | null>(null);
  const [CustomHistoryView, setCustomHistoryView] = useState<ComponentType<Record<string, unknown>> | null>(null);
  const [canvasCollapsed, setCanvasCollapsed] = useState(false);
  const loadedRef = useRef(false);

  useEffect(() => {
    if (loadedRef.current) return;
    loadedRef.current = true;
    if (hasLiveView) {
      loadLiveView(game.name).then((mod) => {
        if (mod) setCustomLiveView(() => mod.default as ComponentType<Record<string, unknown>>);
      }).catch(() => {});
    }
    if (game.ui?.custom_config) {
      loadConfigForm(game.name).then((mod) => {
        if (mod) setCustomConfigForm(() => mod.default as ComponentType<Record<string, unknown>>);
      }).catch(() => {});
    }
    if (game.ui?.custom_history) {
      loadHistoryView(game.name).then((mod) => {
        if (mod) setCustomHistoryView(() => mod.default as ComponentType<Record<string, unknown>>);
      }).catch(() => {});
    }
  }, [game.name, game.ui, hasLiveView]);

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
      setCanvasCollapsed(false);
      setMatch(replayMatch);
    }
  }, [replayMatch, setMatch]);

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
    <div className="flex flex-col h-full">
      <GameHeader game={game} locked={locked} status={sessionStatus} createdAt={createdAt} />
      <TabBar tabs={tabs} activeTab={activeTab} onTabChange={setActiveTab} />
      <div className="flex-1 flex flex-col min-h-0">
        {activeTab === "config" && (
          <div className="flex-1 overflow-y-auto">
            {CustomConfigForm ? (
              <CustomConfigForm
                gameSlug={game.name}
                schema={schema}
                locked={locked}
                sessionStatus={sessionStatus}
                initialValues={initialValues}
              />
            ) : (
              <AutoConfigForm
                gameSlug={game.name}
                schema={schema}
                locked={locked}
                sessionStatus={sessionStatus}
                initialValues={initialValues}
              />
            )}
          </div>
        )}
        {activeTab === "live" && CustomLiveView && (
          <div className="flex-1 min-h-0 flex flex-col">
            <CustomLiveView onScores={handleScores} onToggleCollapse={() => setCanvasCollapsed(true)} createdAt={createdAt || null} />
          </div>
        )}
        {activeTab === "history" && (
          <div className="flex-1 overflow-y-auto">
            {CustomHistoryView ? (
              <CustomHistoryView
                hasMatch={hasMatch}
                canvasCollapsed={canvasCollapsed}
                onExpandCanvas={() => setCanvasCollapsed(false)}
              />
            ) : (
              <AutoHistoryView
                hasMatch={hasMatch}
                canvasCollapsed={canvasCollapsed}
                onExpandCanvas={() => setCanvasCollapsed(false)}
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
