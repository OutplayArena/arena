import type { GameState, PlayerSide } from "./types";

export function balancedAllocation(count: number, total: number): number[] {
  const base = Math.floor(total / count);
  const allocation = Array<number>(count).fill(base);
  for (let i = 0; i < total - base * count; i += 1) {
    allocation[i] += 1;
  }
  return allocation;
}

export function randomAllocation(count: number, total: number): number[] {
  const cuts: number[] = [];
  for (let i = 0; i < count - 1; i += 1) {
    cuts.push(Math.floor(Math.random() * (total + 1)));
  }
  cuts.sort((a, b) => a - b);

  const allocation: number[] = [];
  let previous = 0;
  for (const cut of cuts) {
    allocation.push(cut - previous);
    previous = cut;
  }
  allocation.push(total - previous);
  return allocation;
}

export function normalizeAllocation(
  allocation: number[],
  total: number,
): number[] {
  const next = allocation.slice();
  let currentTotal = next.reduce((sum, v) => sum + v, 0);

  while (currentTotal > total) {
    const maxValue = Math.max(...next);
    const maxIndex = next.indexOf(maxValue);
    next[maxIndex] -= 1;
    currentTotal -= 1;
  }

  while (currentTotal < total) {
    const minValue = Math.min(...next);
    const minIndex = next.indexOf(minValue);
    next[minIndex] += 1;
    currentTotal += 1;
  }

  return next;
}

function greedyAllocation(player: PlayerSide, state: GameState): number[] {
  if (!state.history.length || !state.battlefields?.length) {
    return balancedAllocation(
      state.battlefields?.length ?? 0,
      state.budgets?.[player] ?? 0,
    );
  }

  const opponent: PlayerSide = player === "A" ? "B" : "A";
  const lastRound = state.history[state.history.length - 1];
  const opponentAction = lastRound.allocations?.[opponent] ?? [];
  return normalizeAllocation(
    opponentAction.map((v) => v + 1),
    state.budgets?.[player] ?? 0,
  );
}

// ── RPS agents ──────────────────────────────────────────────────────────────

const RPS_MOVES = ["rock", "paper", "scissors"] as const;
type RPSMove = typeof RPS_MOVES[number];
const RPS_BEATEN_BY: Record<RPSMove, RPSMove> = { scissors: "rock", rock: "paper", paper: "scissors" };

function randomRPSMove(): RPSMove {
  return RPS_MOVES[Math.floor(Math.random() * 3)];
}

function chooseRPSAction(agent: string, player: PlayerSide, state: GameState): string {
  const opponent: PlayerSide = player === "A" ? "B" : "A";

  switch (agent) {
    case "random":
      return randomRPSMove();
    case "biased":
      return Math.random() < 0.5 ? "rock" : (Math.random() < 0.5 ? "paper" : "scissors");
    case "copycat": {
      if (!state.history.length) return randomRPSMove();
      const last = state.history[state.history.length - 1];
      const move = (last.actions as Record<PlayerSide, string> | undefined)?.[opponent];
      return move ?? randomRPSMove();
    }
    case "counter": {
      if (!state.history.length) return randomRPSMove();
      const last = state.history[state.history.length - 1];
      const move = (last.actions as Record<PlayerSide, string> | undefined)?.[opponent] as RPSMove | undefined;
      return move && move in RPS_BEATEN_BY ? RPS_BEATEN_BY[move] : randomRPSMove();
    }
    default:
      return randomRPSMove();
  }
}

// ── Prisoner's Dilemma agents ────────────────────────────────────────────────

function choosePDAction(agent: string, player: PlayerSide, state: GameState): string {
  const opponent: PlayerSide = player === "A" ? "B" : "A";

  switch (agent) {
    case "always_cooperate":
      return "cooperate";
    case "always_defect":
      return "defect";
    case "random":
      return Math.random() < 0.5 ? "cooperate" : "defect";
    case "tit_for_tat": {
      if (!state.history.length) return "cooperate";
      const last = state.history[state.history.length - 1];
      const move = (last.actions as Record<PlayerSide, string> | undefined)?.[opponent];
      return move ?? "cooperate";
    }
    case "grim_trigger": {
      for (const round of state.history) {
        const move = (round.actions as Record<PlayerSide, string> | undefined)?.[opponent];
        if (move === "defect") return "defect";
      }
      return "cooperate";
    }
    case "forgiving_tft": {
      if (!state.history.length) return "cooperate";
      const last = state.history[state.history.length - 1];
      const move = (last.actions as Record<PlayerSide, string> | undefined)?.[opponent];
      if (move === "defect" && Math.random() < 0.1) return "cooperate";
      return move ?? "cooperate";
    }
    case "pavlov": {
      if (!state.history.length) return "cooperate";
      const last = state.history[state.history.length - 1];
      const outcome = last.outcome as string | undefined;
      if (!outcome) return "cooperate";
      if (player === "A") return (outcome === "CC" || outcome === "DC") ? "cooperate" : "defect";
      return (outcome === "CC" || outcome === "CD") ? "cooperate" : "defect";
    }
    default:
      return "cooperate";
  }
}

function pick<T>(arr: T[]): T {
  return arr[Math.floor(Math.random() * arr.length)];
}

function chooseTexasHoldEmAction(agent: string, player: PlayerSide, state: GameState): string {
  const gs = state as Record<string, unknown>;
  const chips = gs.chips as Record<string, number> | undefined;
  const handStartChips = gs.hand_start_chips as Record<string, number> | undefined;
  const streetActions = gs.street_actions as Array<{ player: string; action: string }> | undefined;

  const opponent: PlayerSide = player === "A" ? "B" : "A";
  const hsc = handStartChips ?? chips ?? {};
  const playerCommitted = (hsc[player] ?? 0) - (chips?.[player] ?? 0);
  const oppCommitted = (hsc[opponent] ?? 0) - (chips?.[opponent] ?? 0);
  const toCall = Math.max(0, oppCommitted - playerCommitted);
  const hasBet = toCall > 0;
  const alreadyRaised = (streetActions ?? []).some(sa => sa.player === player && sa.action === "raise");
  const canRaise = !alreadyRaised && (chips?.[player] ?? 0) >= 2;

  const validActions: string[] = [];
  if (!hasBet) validActions.push("check");
  if (hasBet) validActions.push("call");
  if (canRaise) validActions.push("raise");
  if (validActions.length === 0) validActions.push("fold");

  switch (agent) {
    case "random": {
      const all = [...validActions];
      if (!all.includes("fold")) all.push("fold");
      return pick(all);
    }
    case "conservative": {
      if (!hasBet) {
        return Math.random() < 0.15 ? (canRaise ? "raise" : "fold") : "check";
      }
      const r = Math.random();
      if (r < 0.5) return "fold";
      if (r < 0.85) return "call";
      return canRaise ? "raise" : "fold";
    }
    case "aggressive": {
      if (canRaise && Math.random() < 0.6) return "raise";
      if (hasBet) return Math.random() < 0.8 ? "call" : "fold";
      return "check";
    }
    case "call_station": {
      if (!hasBet) return "check";
      return Math.random() < 0.9 ? "call" : (canRaise ? "raise" : "call");
    }
    default:
      return pick(validActions);
  }
}

// ── Public dispatcher ─────────────────────────────────────────────────────────

export function chooseAction(
  agent: string,
  player: PlayerSide,
  state: GameState,
  gameSlug?: string,
): unknown {
  if (gameSlug === "rock_paper_scissors") return chooseRPSAction(agent, player, state);
  if (gameSlug === "prisonersdilemma") return choosePDAction(agent, player, state);
  if (gameSlug === "texas_hold_em") return chooseTexasHoldEmAction(agent, player, state);

  // Default: Blotto allocation
  const count = state.battlefields?.length ?? 0;
  const total = state.budgets?.[player] ?? 0;
  switch (agent) {
    case "uniform":
      return balancedAllocation(count, total);
    case "random":
      return randomAllocation(count, total);
    case "greedy":
      return greedyAllocation(player, state);
    default:
      return balancedAllocation(count, total);
  }
}
