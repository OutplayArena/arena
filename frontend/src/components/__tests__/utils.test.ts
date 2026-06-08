import { describe, it, expect, vi, beforeEach } from "vitest";
import { copyToClipboard, buildBattlefields, resultToMatch } from "../utils";
import type { GameResult, RunConfig } from "../types";

describe("buildBattlefields", () => {
  it("returns empty array for count 0", () => {
    expect(buildBattlefields(0)).toEqual([]);
  });

  it("returns correct number of battlefields", () => {
    expect(buildBattlefields(3)).toHaveLength(3);
  });

  it("assigns sequential IDs and value 1.0", () => {
    const result = buildBattlefields(3);
    expect(result).toEqual([
      { id: "battlefield_1", value: 1.0 },
      { id: "battlefield_2", value: 1.0 },
      { id: "battlefield_3", value: 1.0 },
    ]);
  });
});

describe("copyToClipboard", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("returns true on successful clipboard write", async () => {
    const result = await copyToClipboard("hello");
    expect(result).toBe(true);
    expect(navigator.clipboard.writeText).toHaveBeenCalledWith("hello");
  });

  it("falls back to execCommand on clipboard failure", async () => {
    vi.mocked(navigator.clipboard.writeText).mockRejectedValueOnce(new Error("denied"));
    document.execCommand = vi.fn().mockReturnValue(true);

    const result = await copyToClipboard("fallback");
    expect(result).toBe(true);
    expect(document.execCommand).toHaveBeenCalledWith("copy");
  });
});

describe("resultToMatch", () => {
  const config: RunConfig = {
    agent_a: "agent-a",
    agent_b: "agent-b",
    num_rounds: 2,
    num_battlefields: 5,
    total_resources: 100,
    session_id: "sess-1",
  };

  it("converts a GameResult to Match with allocations", () => {
    const result: GameResult = {
      config_hash: "hash1",
      total_scores: { A: 3, B: 2 },
      winner: "A",
      metrics: { fairness: 0.5 },
      history: [
        {
          round: 1,
          allocations: { A: [10, 20, 30, 20, 20], B: [20, 20, 20, 20, 20] },
          scores: { A: 2, B: 1 },
          total_scores: { A: 2, B: 1 },
          winner: "A",
        },
        {
          round: 2,
          allocations: { A: [30, 20, 20, 20, 10], B: [20, 20, 20, 20, 20] },
          scores: { A: 1, B: 1 },
          total_scores: { A: 3, B: 2 },
          winner: "Tie",
        },
      ],
    };

    const match = resultToMatch(result, config);
    expect(match.session_id).toBe("sess-1");
    expect(match.config_hash).toBe("hash1");
    expect(match.history).toHaveLength(2);
    expect(match.history[0].action_a).toEqual([10, 20, 30, 20, 20]);
    expect(match.history[1].winner).toBe("Tie");
    expect(match.total_score_a).toBe(3);
    expect(match.total_score_b).toBe(2);
  });

  it("uses actions field when allocations is absent", () => {
    const result: GameResult = {
      config_hash: "h2",
      total_scores: { A: 1, B: 0 },
      winner: "A",
      metrics: {},
      history: [
        {
          round: 1,
          actions: { A: "cooperate", B: "defect" },
          payoffs: { A: 0, B: 5 },
          total_scores: { A: 0, B: 5 },
          winner: "B",
        },
      ],
    };

    const match = resultToMatch(result, config);
    expect(match.history[0].action_a).toBe("cooperate");
    expect(match.history[0].action_b).toBe("defect");
    expect(match.history[0].score_a).toBe(0);
    expect(match.history[0].score_b).toBe(5);
  });

  it("defaults scores to 0 when missing", () => {
    const result: GameResult = {
      config_hash: "h3",
      total_scores: { A: 0, B: 0 },
      winner: "Tie",
      metrics: {},
      history: [
        { round: 1, winner: "Tie" },
      ],
    };

    const match = resultToMatch(result, config);
    expect(match.history[0].score_a).toBe(0);
    expect(match.history[0].score_b).toBe(0);
  });

  it("fails nicely when session_id is absent from config", () => {
    const cfg: RunConfig = {
      agent_a: "a",
      agent_b: "b",
      num_rounds: 1,
      num_battlefields: 1,
      total_resources: 1,
    };
    const result: GameResult = {
      config_hash: "h",
      total_scores: { A: 0, B: 0 },
      winner: "Tie",
      metrics: {},
      history: [],
    };
    const match = resultToMatch(result, cfg);
    expect(match.session_id).toBe("");
  });
});
