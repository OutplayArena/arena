import { useEffect, useState } from "react";
import { useParams, useLocation } from "react-router-dom";
import { GamePlayView } from "../components/GamePlayView";
import { LoadingSpinner } from "../components/LoadingSpinner";
import { getGameMetadata, getSessionSummary, getState, getResults } from "../api";
import { resultToMatch } from "../components/utils";
import type { GameMetadata, Match, RunConfig, GameState } from "../types";

export function GamePlayPage() {
  const { gameSlug, sessionId } = useParams<{ gameSlug: string; sessionId?: string }>();
  const location = useLocation();
  const [game, setGame] = useState<GameMetadata | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [replayMatch, setReplayMatch] = useState<Match | null>(null);
  const [sessionMeta, setSessionMeta] = useState<{
    locked: boolean;
    status: string;
    agent_a: string;
    agent_b: string;
    rounds: number;
    num_battlefields: number;
    resources: number;
    seed?: number | null;
    created_at: string | null;
  } | null>(null);

  useEffect(() => {
    if (!gameSlug) return;
    let cancelled = false;

    const load = async () => {
      setLoading(true);
      setError(null);
      try {
        const gameMeta = await getGameMetadata(gameSlug);
        if (cancelled) return;
        setGame(gameMeta);

        if (sessionId) {
          const summary = await getSessionSummary(sessionId);
          if (cancelled) return;

          setSessionMeta({
            locked: summary.locked,
            status: summary.status,
            agent_a: summary.agent_a || "",
            agent_b: summary.agent_b || "",
            rounds: summary.rounds || 10,
            num_battlefields: summary.num_battlefields || 5,
            resources: summary.resources || 100,
            seed: summary.seed ?? null,
            created_at: summary.created_at,
          });

          const state: GameState = await getState(sessionId);
          if (cancelled) return;

          if (state.phase === "complete") {
            const result = await getResults(sessionId);
            if (cancelled) return;
            const payload: RunConfig = {
              agent_a: summary.agent_a || "unknown",
              agent_b: summary.agent_b || "unknown",
              num_rounds: state.round_total,
              num_battlefields: (state.battlefields ?? []).length,
              total_resources: (state.budgets as Record<string, number> | undefined)?.A ?? 0,
              session_id: sessionId,
            };
            const match = resultToMatch(result as never, payload);
            if (!cancelled) setReplayMatch(match);
          } else {
            const match = location.state?.match as Match | undefined;
            if (!cancelled) setReplayMatch(match ?? null);
          }
        }
      } catch (err) {
        if (!cancelled) setError(err instanceof Error ? err.message : String(err));
      } finally {
        if (!cancelled) setLoading(false);
      }
    };

    load();
    return () => { cancelled = true; };
  }, [gameSlug, sessionId, location.state]);

  if (loading) {
    return (
      <div className="flex items-center justify-center flex-1">
        <LoadingSpinner />
      </div>
    );
  }

  if (error || !game) {
    return (
      <div className="flex items-center justify-center flex-1 text-muted text-sm">
        {error || "Game not found"}
      </div>
    );
  }

  return (
    <div className="flex-1 min-h-0 flex flex-col">
      <GamePlayView
        game={game}
        sessionId={sessionId ?? null}
        locked={sessionMeta?.locked ?? false}
        sessionStatus={sessionMeta?.status ?? ""}
        replayMatch={replayMatch}
        sessionConfig={sessionMeta}
        createdAt={sessionMeta?.created_at ?? null}
      />
    </div>
  );
}
