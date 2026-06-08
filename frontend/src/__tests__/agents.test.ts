import { describe, it, expect } from "vitest";
import {
  balancedAllocation,
  randomAllocation,
  normalizeAllocation,
  chooseAction,
} from "../agents";
import type { GameState } from "../types";

function createBlottoState(overrides: Partial<GameState> = {}): GameState {
  return {
    phase: "awaiting_action",
    round: 2,
    round_total: 10,
    awaiting: ["A", "B"],
    history: [],
    config_hash: "h",
    battlefields: [
      { id: "b1", value: 1.0 },
      { id: "b2", value: 1.0 },
      { id: "b3", value: 1.0 },
      { id: "b4", value: 1.0 },
      { id: "b5", value: 1.0 },
    ],
    budgets: { A: 100, B: 100 },
    ...overrides,
  };
}

describe("balancedAllocation", () => {
  it("distributes resources evenly", () => {
    const result = balancedAllocation(5, 100);
    expect(result).toEqual([20, 20, 20, 20, 20]);
  });

  it("handles remainder by distributing to first fields", () => {
    const result = balancedAllocation(3, 10);
    expect(result).toEqual([4, 3, 3]);
  });

  it("returns zeros when total is 0", () => {
    const result = balancedAllocation(3, 0);
    expect(result).toEqual([0, 0, 0]);
  });
});

describe("randomAllocation", () => {
  it("returns array of correct length", () => {
    const result = randomAllocation(5, 100);
    expect(result).toHaveLength(5);
  });

  it("sums to total", () => {
    for (let i = 0; i < 10; i++) {
      const result = randomAllocation(5, 100);
      const sum = result.reduce((a, b) => a + b, 0);
      expect(sum).toBe(100);
    }
  });

  it("handles zero total", () => {
    const result = randomAllocation(3, 0);
    expect(result).toEqual([0, 0, 0]);
  });
});

describe("normalizeAllocation", () => {
  it("increases allocation to meet total", () => {
    const result = normalizeAllocation([5, 5, 5], 20);
    expect(result.reduce((a, b) => a + b, 0)).toBe(20);
  });

  it("decreases allocation to meet total", () => {
    const result = normalizeAllocation([50, 50, 50], 20);
    expect(result.reduce((a, b) => a + b, 0)).toBe(20);
  });

  it("returns unchanged if already correct", () => {
    const result = normalizeAllocation([10, 10, 10], 30);
    expect(result).toEqual([10, 10, 10]);
  });
});

describe("chooseAction — Blotto", () => {
  it("uniform returns balanced allocation", () => {
    const state = createBlottoState();
    const action = chooseAction("uniform", "A", state);
    expect(action).toEqual([20, 20, 20, 20, 20]);
  });

  it("random returns allocation summing to budget", () => {
    const state = createBlottoState();
    const action = chooseAction("random", "A", state) as number[];
    expect(action).toHaveLength(5);
    expect(action.reduce((a, b) => a + b, 0)).toBe(100);
  });

  it("greedy uses balanced when no history", () => {
    const state = createBlottoState({ history: [] });
    const action = chooseAction("greedy", "A", state) as number[];
    expect(action).toEqual([20, 20, 20, 20, 20]);
  });

  it("greedy beats last opponent move", () => {
    const state = createBlottoState({
      history: [{
        round: 1,
        allocations: { A: [20, 20, 20, 20, 20], B: [10, 10, 20, 30, 30] },
        scores: { A: 0, B: 0 },
        total_scores: { A: 0, B: 0 },
        winner: "Tie",
      } as never],
    });
    const action = chooseAction("greedy", "A", state) as number[];
    expect(action.reduce((a, b) => a + b, 0)).toBe(100);
  });
});

describe("chooseAction — RPS", () => {
  function rpsState(history: Array<{ actions: Record<string, string> }> = []): GameState {
    return {
      phase: "awaiting_action",
      round: 1,
      round_total: 10,
      awaiting: ["A", "B"],
      history: history.map((h, i) => ({
        round: i + 1,
        actions: h.actions,
      })) as never,
      config_hash: "h",
    };
  }

  it("random returns a valid RPS move", () => {
    const action = chooseAction("random", "A", rpsState(), "rock_paper_scissors") as string;
    expect(["rock", "paper", "scissors"]).toContain(action);
  });

  it("copycat copies opponent's last move", () => {
    const state = rpsState([{ actions: { A: "rock", B: "paper" } }]);
    const action = chooseAction("copycat", "A", state, "rock_paper_scissors") as string;
    expect(action).toBe("paper");
  });

  it("copycat returns random when no history", () => {
    const state = rpsState([]);
    const action = chooseAction("copycat", "A", state, "rock_paper_scissors") as string;
    expect(["rock", "paper", "scissors"]).toContain(action);
  });

  it("counter beats opponent's last move", () => {
    const state = rpsState([{ actions: { A: "paper", B: "rock" } }]);
    const action = chooseAction("counter", "A", state, "rock_paper_scissors") as string;
    expect(action).toBe("paper");
  });
});

describe("chooseAction — Prisoner's Dilemma", () => {
  function pdState(history: Array<{ actions: Record<string, string>; outcome?: string }> = []): GameState {
    return {
      phase: "awaiting_action",
      round: 1,
      round_total: 10,
      awaiting: ["A", "B"],
      history: history.map((h, i) => ({
        round: i + 1,
        actions: h.actions,
        outcome: h.outcome,
      })) as never,
      config_hash: "h",
    };
  }

  it("always_cooperate returns cooperate", () => {
    const action = chooseAction("always_cooperate", "A", pdState(), "prisonersdilemma") as string;
    expect(action).toBe("cooperate");
  });

  it("always_defect returns defect", () => {
    const action = chooseAction("always_defect", "A", pdState(), "prisonersdilemma") as string;
    expect(action).toBe("defect");
  });

  it("tit_for_tat returns cooperate on first move", () => {
    const action = chooseAction("tit_for_tat", "A", pdState([]), "prisonersdilemma") as string;
    expect(action).toBe("cooperate");
  });

  it("tit_for_tat copies opponent's last move", () => {
    const state = pdState([{ actions: { A: "cooperate", B: "defect" } }]);
    const action = chooseAction("tit_for_tat", "A", state, "prisonersdilemma") as string;
    expect(action).toBe("defect");
  });

  it("grim_trigger defects after any defection", () => {
    const state = pdState([
      { actions: { A: "cooperate", B: "cooperate" } },
      { actions: { A: "cooperate", B: "defect" } },
    ]);
    const action = chooseAction("grim_trigger", "A", state, "prisonersdilemma") as string;
    expect(action).toBe("defect");
  });

  it("grim_trigger cooperates if no defections", () => {
    const state = pdState([
      { actions: { A: "cooperate", B: "cooperate" } },
    ]);
    const action = chooseAction("grim_trigger", "A", state, "prisonersdilemma") as string;
    expect(action).toBe("cooperate");
  });
});

describe("chooseAction — defaults to Blotto for unknown game", () => {
  it("returns balanced allocation for unknown slug", () => {
    const state = createBlottoState();
    const action = chooseAction("uniform", "A", state, "unknown_game") as number[];
    expect(action).toEqual([20, 20, 20, 20, 20]);
  });
});
