import type { Battlefield, GameResult, Match, RunConfig } from "../types";

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

export function resultToMatch(result: GameResult, config: RunConfig): Match {
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
      const moves = (round.allocations || round.actions || {}) as Record<string, unknown>;
      const scores = (round.payoffs || round.scores || {}) as Record<string, number>;
      const totals = (round.total_scores || {}) as Record<string, number>;
      return {
        round: round.round,
        agent_a: config.agent_a,
        agent_b: config.agent_b,
        action_a: moves.A,
        action_b: moves.B,
        score_a: scores.A ?? 0,
        score_b: scores.B ?? 0,
        total_score_a: totals.A ?? 0,
        total_score_b: totals.B ?? 0,
        winner: round.winner ?? "Tie",
      };
    }),
  };
}
