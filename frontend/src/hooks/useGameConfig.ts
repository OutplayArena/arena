import { useEffect, useRef, useState } from "react";
import { createExperiment, getGameAgents } from "../api";
import { randomAgentName } from "../components/names";
import { useApp } from "./useApp";
import { useWandbLoggingConfig } from "./useWandbLoggingConfig";
import type { GameAgent } from "../types";
import type { PlayerSetupValue } from "../components/LobbyConfigShell";

interface UseGameConfigOptions {
  gameSlug: string;
  locked: boolean;
  sessionStatus?: string;
  initialValues?: Record<string, unknown>;
  defaultAgents?: string[];
  minPlayers?: number;
  maxPlayers?: number;
  numFields?: number;
  totalResources?: number;
}

const PLAYER_IDS = ["A", "B", "C", "D", "E", "F", "G", "H", "I", "J"];

export function useGameConfig({
  gameSlug,
  locked,
  sessionStatus,
  initialValues,
  defaultAgents,
  minPlayers = 2,
  maxPlayers = 2,
  numFields = 0,
  totalResources = 0,
}: UseGameConfigOptions) {
  const { state, startGame } = useApp();
  const initRanRef = useRef(false);

  const buildInitialPlayers = (): PlayerSetupValue[] => {
    const count = Math.max(defaultAgents?.length ?? 0, minPlayers);
    return Array.from({ length: count }, (_, i) => {
      const agentId = defaultAgents?.[i] ?? (i === 0 ? "interactive" : "remote");
      const side = PLAYER_IDS[i];
      const name = agentId === "interactive" ? "You" : agentId === "remote" ? `Remote ${side}` : randomAgentName();
      return { agentId, name };
    });
  };

  const [players, setPlayers] = useState<PlayerSetupValue[]>(buildInitialPlayers);
  const [agents, setAgents] = useState<GameAgent[]>([]);
  const [remoteKeys, setRemoteKeys] = useState<Record<string, string> | null>(null);
  const [status, setStatus] = useState("");
  const [running, setRunning] = useState(false);
  const wandbLogging = useWandbLoggingConfig();

  const effectiveLocked = locked || state.sessionLocked;
  const effectiveStatus = sessionStatus || state.sessionStatus;
  const hasActiveToken = state.pendingGame !== null;
  const isReplay =
    effectiveLocked ||
    effectiveStatus === "completed" ||
    (effectiveStatus === "running" && hasActiveToken);
  const formDisabled =
    effectiveLocked ||
    running ||
    state.pendingGame !== null ||
    effectiveStatus === "completed";

  useEffect(() => {
    getGameAgents(gameSlug).then((data) => setAgents(data.agents)).catch(() => {});
  }, [gameSlug]);

  useEffect(() => {
    if (initRanRef.current || !isReplay || !initialValues) return;
    initRanRef.current = true;
    setPlayers((prev) =>
      prev.map((p, i) => {
        const side = PLAYER_IDS[i];
        const agentKey = `agent_${side.toLowerCase()}` as string;
        const agentIdKey = `agent_${side.toLowerCase()}_id` as string;
        return {
          agentId: (initialValues[agentIdKey] as string) ?? p.agentId,
          name: (initialValues[agentKey] as string) ?? p.name,
        };
      })
    );
  }, [isReplay, initialValues]);

  const handleStartGame = async (
    e: React.FormEvent,
    getExtraConfig: () => Record<string, unknown>,
    getStartGameOverrides?: () => Partial<Parameters<typeof startGame>[0]>,
  ) => {
    e.preventDefault();
    if (running) return;

    const extra = getExtraConfig();
    const overrides = getStartGameOverrides?.() ?? {};

    setRunning(true);
    setRemoteKeys(null);
    setStatus("Starting...");

    const isInteractive = players.some((p) => p.agentId === "interactive");

    const agentsDict: Record<string, string> = {};
    const playerNames: Record<string, string> = {};
    const agentIds: Record<string, string> = {};
    players.forEach((p, i) => {
      const side = PLAYER_IDS[i];
      agentsDict[side] = p.name.trim();
      playerNames[side] = p.name.trim();
      agentIds[side] = p.agentId;
    });

    const config = {
      game: gameSlug,
      variant: "classic",
      rounds: 10,
      players: players.length,
      agents: agentsDict,
      interactive: isInteractive,
      ...extra,
      ...wandbLogging.toConfigFields(),
    };

    try {
      const created = await createExperiment(config);

      const keys: Record<string, string> = {};
      players.forEach((p, i) => {
        if (p.agentId === "remote") {
          keys[PLAYER_IDS[i]] = created.player_tokens[PLAYER_IDS[i]];
        }
      });
      const hasRemoteKeys = Object.keys(keys).length > 0;
      if (hasRemoteKeys) setRemoteKeys(keys);

      startGame({
        sessionId: created.session_id,
        tokens: created.player_tokens,
        agentAName: playerNames.A ?? "",
        agentBName: playerNames.B ?? "",
        agentAId: agentIds.A ?? "",
        agentBId: agentIds.B ?? "",
        numRounds: (extra.rounds as number) ?? 10,
        numFields,
        totalResources,
        gameSlug,
        remoteKeys: hasRemoteKeys ? keys : null,
        playerNames,
        agentIds,
        interactive: isInteractive,
        ...overrides,
      });
      setStatus("Game started.");
    } catch (err) {
      setStatus(`error=${err instanceof Error ? err.message : String(err)}`);
    } finally {
      setRunning(false);
    }
  };

  return {
    players,
    setPlayers,
    agents,
    remoteKeys,
    status,
    running,
    isReplay,
    formDisabled,
    handleStartGame,
    minPlayers,
    maxPlayers,
    wandbLogging,
  };
}
