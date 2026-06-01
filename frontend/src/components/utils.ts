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
    history: result.history.map((round) => ({
      round: round.round,
      agent_a: config.agent_a,
      agent_b: config.agent_b,
      action_a: round.allocations.A,
      action_b: round.allocations.B,
      score_a: round.scores.A,
      score_b: round.scores.B,
      total_score_a: round.total_scores.A,
      total_score_b: round.total_scores.B,
      winner: round.winner,
    })),
  };
}
