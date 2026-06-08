import { describe, it, expect, vi } from "vitest";
import { balancedAllocation, randomAllocation, normalizeAllocation, chooseAction } from "../agents";
import type { GameState } from "../types";

describe("agents — expanded", () => {
  describe("normalizeAllocation edge cases", () => {
    it("handles all zeros with target total", () => {
      const result = normalizeAllocation([0, 0, 0], 10);
      expect(result.reduce((a, b) => a + b, 0)).toBe(10);
    });

    it("handles single element", () => {
      const result = normalizeAllocation([100], 50);
      expect(result.reduce((a, b) => a + b, 0)).toBe(50);
    });
  });

  describe("chooseAction — PD expanded", () => {
    function pdState(history: Array<{ actions: Record<string, string>; outcome?: string }> = []): GameState {
      return {
        phase: "awaiting_action",
        round: history.length + 1,
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

    it("forgiving_tft cooperates after defection with probability", () => {
      const state = pdState([{ actions: { A: "cooperate", B: "defect" } }]);
      const action = chooseAction("forgiving_tft", "A", state, "prisonersdilemma") as string;
      expect(["cooperate", "defect"]).toContain(action);
    });

    it("forgiving_tft cooperates on first move", () => {
      const state = pdState([]);
      const action = chooseAction("forgiving_tft", "A", state, "prisonersdilemma") as string;
      expect(action).toBe("cooperate");
    });

    it("pavlov for player B with outcome CC returns cooperate", () => {
      const state = pdState([{ actions: { A: "cooperate", B: "cooperate" }, outcome: "CC" }]);
      const action = chooseAction("pavlov", "B", state, "prisonersdilemma") as string;
      expect(action).toBe("cooperate");
    });

    it("pavlov for player B with outcome CD returns cooperate", () => {
      const state = pdState([{ actions: { A: "cooperate", B: "defect" }, outcome: "CD" }]);
      const action = chooseAction("pavlov", "B", state, "prisonersdilemma") as string;
      expect(action).toBe("cooperate");
    });

    it("pavlov for player A with outcome CD returns defect", () => {
      const state = pdState([{ actions: { A: "cooperate", B: "defect" }, outcome: "CD" }]);
      const action = chooseAction("pavlov", "A", state, "prisonersdilemma") as string;
      expect(action).toBe("defect");
    });

    it("unknown PD agent returns cooperate", () => {
      const state = pdState([]);
      const action = chooseAction("unknown_agent", "A", state, "prisonersdilemma") as string;
      expect(action).toBe("cooperate");
    });
  });

  describe("chooseAction — RPS expanded", () => {
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

    it("biased returns one of the three moves", () => {
      const action = chooseAction("biased", "A", rpsState(), "rock_paper_scissors") as string;
      expect(["rock", "paper", "scissors"]).toContain(action);
    });

    it("counter returns random when opponent played unknown move", () => {
      const state = rpsState([{ actions: { A: "paper", B: "unknown_move" } }]);
      const action = chooseAction("counter", "A", state, "rock_paper_scissors") as string;
      expect(["rock", "paper", "scissors"]).toContain(action);
    });

    it("counter returns random when no history", () => {
      const state = rpsState([]);
      const action = chooseAction("counter", "A", state, "rock_paper_scissors") as string;
      expect(["rock", "paper", "scissors"]).toContain(action);
    });

    it("unknown RPS agent returns random", () => {
      const state = rpsState([]);
      const action = chooseAction("unknown_rps", "A", state, "rock_paper_scissors") as string;
      expect(["rock", "paper", "scissors"]).toContain(action);
    });
  });

  describe("chooseAction — Blotto expanded", () => {
    function blottoState(): GameState {
      return {
        phase: "awaiting_action",
        round: 1,
        round_total: 10,
        awaiting: ["A", "B"],
        history: [],
        config_hash: "h",
        battlefields: [],
        budgets: { A: 0, B: 0 },
      };
    }

    it("unknown Blotto agent falls back to balanced", () => {
      const state = blottoState();
      const action = chooseAction("unknown_blotto", "A", state) as number[];
      expect(action).toEqual([]);
    });

    it("default path selects uniform (balanced)", () => {
      const state = {
        ...blottoState(),
        battlefields: [{ id: "b1", value: 1.0 }, { id: "b2", value: 1.0 }],
        budgets: { A: 10, B: 10 },
      };
      const action = chooseAction("uniform", "A", state) as number[];
      expect(action).toEqual([5, 5]);
    });
  });
});
