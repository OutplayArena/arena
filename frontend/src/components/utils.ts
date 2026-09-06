import type { Battlefield, GameResult, Match, MatchRound, RunConfig } from "../types";

export async function copyToClipboard(text: string): Promise<boolean> {
  try {
    await navigator.clipboard.writeText(text);
    return true;
  } catch {
    const textarea = document.createElement("textarea");
    textarea.value = text;
    textarea.style.position = "fixed";
    textarea.style.opacity = "0";
    document.body.appendChild(textarea);
    textarea.select();
    const ok = document.execCommand("copy");
    document.body.removeChild(textarea);
    return ok;
  }
}

export function buildBattlefields(count: number): Battlefield[] {
  return Array.from({ length: count }, (_, i) => ({
    id: `battlefield_${i + 1}`,
    value: 1.0,
  }));
}

/** Last action per player from a Texas Hold'em-style `street_actions` list
 * (issue #24) -- games that record a per-street action log instead of a
 * single actions dict per round. */
export function lastActionsByPlayer(streetActions: unknown): Record<string, unknown> {
  const moves: Record<string, unknown> = {};
  if (!Array.isArray(streetActions)) return moves;
  for (const act of streetActions) {
    if (act && typeof act === "object" && "player" in act) {
      const p = (act as Record<string, unknown>).player;
      if (typeof p === "string") moves[p] = (act as Record<string, unknown>).action;
    }
  }
  return moves;
}

export function resultToMatch(result: GameResult, config: RunConfig): Match {
  // Cumulative total_scores from the previous round, for games (Texas
  // Hold'em) whose history entries carry a running total rather than a
  // per-round delta (#24).
  let prevTotalA = 0;
  let prevTotalB = 0;

  return {
    agent_a: config.agent_a,
    agent_b: config.agent_b,
    session_id: config.session_id ?? "",
    config_hash: result.config_hash,
    num_rounds: config.num_rounds,
    num_battlefields: config.num_battlefields,
    total_resources: config.total_resources,
    total_score_a: result.total_scores.A,
    total_score_b: result.total_scores.B,
    match_winner: result.winner,
    metrics: result.metrics,
    rich_metrics: result.rich_metrics,
    history: result.history.map((round) => {
      const r = round as unknown as Record<string, unknown>;
      const hasStreetActions = Array.isArray(r.street_actions);
      const moves = hasStreetActions
        ? lastActionsByPlayer(r.street_actions)
        : ((round.allocations || round.actions || {}) as Record<string, unknown>);
      const totals = (round.total_scores || {}) as Record<string, number>;
      const totalA = totals.A ?? prevTotalA;
      const totalB = totals.B ?? prevTotalB;
      // A dedicated per-round scores dict (Blotto, RPS, ...) is a per-round
      // delta already; a cumulative total_scores (Hold'em) needs diffing
      // against the previous round to get this round's own delta.
      const scores = (round.payoffs || round.scores) as Record<string, number> | undefined;
      const scoreA = scores ? (scores.A ?? 0) : totalA - prevTotalA;
      const scoreB = scores ? (scores.B ?? 0) : totalB - prevTotalB;
      prevTotalA = totalA;
      prevTotalB = totalB;
      const resultObj = r.result as Record<string, unknown> | undefined;
      const winner = (round.winner ?? resultObj?.winner ?? "Tie") as MatchRound["winner"];
      return {
        round: round.round ?? (r.hand as number | undefined) ?? 0,
        agent_a: config.agent_a,
        agent_b: config.agent_b,
        action_a: moves.A,
        action_b: moves.B,
        score_a: scoreA,
        score_b: scoreB,
        total_score_a: totalA,
        total_score_b: totalB,
        winner,
        raw: round as unknown as Record<string, unknown>,
      };
    }),
  };
}
