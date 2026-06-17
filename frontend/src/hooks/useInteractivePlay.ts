import { useCallback, useEffect, useRef, useState } from "react";
import { submitHumanAction } from "../api";
import { useApp } from "./useApp";
import type { PlayerSide } from "../types";

export interface RoundResult {
  round: number;
  winner: PlayerSide | "Tie" | undefined;
  scoreYou: number;
  scoreOpp: number;
  yourMove: unknown;
  oppMove: unknown;
}

export interface InteractivePlayState {
  humanPlayer: PlayerSide | null;
  opponentPlayers: string[];
  sessionId: string | null;
  token: string | null;
  currentState: Record<string, unknown> | undefined;
  awaiting: string[];
  isMyTurn: boolean;
  isComplete: boolean;
  isSubmitting: boolean;
  hasSubmittedThisRound: boolean;
  submitError: string | null;
  lastRoundResult: RoundResult | null;
  totalScores: Record<string, number>;
  round: number;
  roundTotal: number;
  submitMove: (action: unknown) => Promise<void>;
  forfeit: () => Promise<void>;
}

export function useInteractivePlay(): InteractivePlayState {
  const { state } = useApp();
  const pg = state.pendingGame;
  const match = state.activeMatch;

  const humanPlayer: PlayerSide | null = (() => {
    if (pg?.agentIds) {
      for (const [player, agentId] of Object.entries(pg.agentIds)) {
        if (agentId === "interactive") return player as PlayerSide;
      }
    }
    if (pg?.agentAId === "interactive") return "A";
    if (pg?.agentBId === "interactive") return "B";
    return null;
  })();

  const opponentPlayers: string[] = (() => {
    if (pg?.agentIds) {
      return Object.keys(pg.agentIds).filter((p) => p !== humanPlayer);
    }
    return humanPlayer === "A" ? ["B"] : humanPlayer === "B" ? ["A"] : [];
  })();

  const sessionId = pg?.sessionId ?? null;
  const token = humanPlayer && pg ? pg.tokens[humanPlayer] : null;

  const currentState = match?.currentState as Record<string, unknown> | undefined;
  const awaiting = (currentState?.awaiting as string[]) ?? [];
  const isMyTurn = humanPlayer ? awaiting.includes(humanPlayer) : false;
  const isComplete = currentState?.phase === "complete" || match?.match_winner !== undefined;

  const totalScores: Record<string, number> = (() => {
    const scores = (currentState?.total_scores as Record<string, number>) ?? {};
    if (Object.keys(scores).length > 0) return scores;
    return {
      A: match?.total_score_a ?? 0,
      B: match?.total_score_b ?? 0,
    };
  })();

  const round = (currentState?.round as number) ?? match?.history.length ?? 0;
  const roundTotal = (currentState?.round_total as number) ?? match?.num_rounds ?? 0;

  const [isSubmitting, setIsSubmitting] = useState(false);
  const [hasSubmittedThisRound, setHasSubmittedThisRound] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [lastRoundResult, setLastRoundResult] = useState<RoundResult | null>(null);
  const prevHistoryLen = useRef(0);
  const resultTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const submittedThisRoundRef = useRef(false);
  const prevIsMyTurnRef = useRef(false);

  useEffect(() => {
    const history = match?.history ?? [];
    if (history.length > prevHistoryLen.current) {
      submittedThisRoundRef.current = false;
      setHasSubmittedThisRound(false);
      setSubmitError(null);

      if (humanPlayer && opponentPlayers.length > 0) {
        const latest = history[history.length - 1];
        if (latest) {
          const raw = latest.raw as Record<string, unknown> | undefined;
          const moves = (raw?.actions || raw?.allocations || {}) as Record<string, unknown>;
          const scores = (raw?.payoffs || raw?.round_payoffs || raw?.scores || {}) as Record<string, number>;

          setLastRoundResult({
            round: latest.round,
            winner: latest.winner,
            scoreYou: scores[humanPlayer] ?? latest.score_a ?? 0,
            scoreOpp: scores[opponentPlayers[0]] ?? latest.score_b ?? 0,
            yourMove: moves[humanPlayer] ?? latest.action_a,
            oppMove: moves[opponentPlayers[0]] ?? latest.action_b,
          });

          if (resultTimer.current) clearTimeout(resultTimer.current);
          resultTimer.current = setTimeout(() => setLastRoundResult(null), 3500);
        }
      }
    }
    prevHistoryLen.current = history.length;
  }, [match?.history, humanPlayer, opponentPlayers]);

  // Reset submission flag when turn comes back to human (e.g., new street in poker)
  useEffect(() => {
    if (isMyTurn && !prevIsMyTurnRef.current) {
      submittedThisRoundRef.current = false;
      setHasSubmittedThisRound(false);
    }
    prevIsMyTurnRef.current = isMyTurn;
  }, [isMyTurn]);

  useEffect(() => () => {
    if (resultTimer.current) clearTimeout(resultTimer.current);
  }, []);

  const submitMove = useCallback(async (action: unknown) => {
    if (!sessionId || !humanPlayer || !token || isSubmitting || submittedThisRoundRef.current) return;
    submittedThisRoundRef.current = true;
    setIsSubmitting(true);
    setHasSubmittedThisRound(true);
    setSubmitError(null);
    try {
      await submitHumanAction(sessionId, humanPlayer, action, token);
    } catch (err) {
      submittedThisRoundRef.current = false;
      setHasSubmittedThisRound(false);
      setSubmitError(err instanceof Error ? err.message : String(err));
      throw err;
    } finally {
      setIsSubmitting(false);
    }
  }, [sessionId, humanPlayer, token, isSubmitting]);

  const forfeit = useCallback(async () => {
    if (!sessionId || !humanPlayer || !token || isSubmitting) return;
    setIsSubmitting(true);
    try {
      await submitHumanAction(sessionId, humanPlayer, null, token, true);
    } finally {
      setIsSubmitting(false);
    }
  }, [sessionId, humanPlayer, token, isSubmitting]);

  return {
    humanPlayer,
    opponentPlayers,
    sessionId,
    token,
    currentState,
    awaiting,
    isMyTurn,
    isComplete,
    isSubmitting,
    hasSubmittedThisRound,
    submitError,
    lastRoundResult,
    totalScores,
    round,
    roundTotal,
    submitMove,
    forfeit,
  };
}
