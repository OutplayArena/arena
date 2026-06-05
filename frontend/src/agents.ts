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
  if (!state.history.length) {
    return balancedAllocation(
      state.battlefields.length,
      state.budgets[player],
    );
  }

  const opponent: PlayerSide = player === "A" ? "B" : "A";
  const lastRound = state.history[state.history.length - 1];
  const opponentAction = lastRound.allocations[opponent];
  return normalizeAllocation(
    opponentAction.map((v) => v + 1),
    state.budgets[player],
  );
}

export function chooseAction(
  agent: string,
  player: PlayerSide,
  state: GameState,
): number[] {
  const count = state.battlefields.length;
  const total = state.budgets[player];

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
