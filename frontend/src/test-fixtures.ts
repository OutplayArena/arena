import type { Match, MatchRound, GameState, GameMetadata } from "./types";

export function createMockMatch(overrides: Partial<Match> = {}): Match {
  const rounds: MatchRound[] = overrides.history ?? [
    {
      round: 1,
      agent_a: "bold-bear",
      agent_b: "swift-fox",
      action_a: [10, 20, 30, 40, 0],
      action_b: [5, 15, 25, 35, 20],
      score_a: 2,
      score_b: 1,
      total_score_a: 2,
      total_score_b: 1,
      winner: "A",
    },
    {
      round: 2,
      agent_a: "bold-bear",
      agent_b: "swift-fox",
      action_a: [15, 15, 25, 25, 20],
      action_b: [10, 20, 30, 20, 20],
      score_a: 1,
      score_b: 2,
      total_score_a: 3,
      total_score_b: 3,
      winner: "B",
    },
    {
      round: 3,
      agent_a: "bold-bear",
      agent_b: "swift-fox",
      action_a: [20, 10, 30, 20, 20],
      action_b: [15, 25, 20, 25, 15],
      score_a: 2,
      score_b: 1,
      total_score_a: 5,
      total_score_b: 4,
      winner: "A",
    },
  ];

  return {
    agent_a: "bold-bear",
    agent_b: "swift-fox",
    session_id: "mock-session-1",
    config_hash: "mock-hash",
    num_rounds: 3,
    num_battlefields: 5,
    total_resources: 100,
    total_score_a: 5,
    total_score_b: 4,
    match_winner: "A",
    metrics: {},
    history: rounds,
    ...overrides,
  };
}

export function createMockGameState(overrides: Partial<GameState> = {}): GameState {
  return {
    phase: "awaiting_action",
    round: 1,
    round_total: 5,
    awaiting: ["A", "B"],
    history: [],
    config_hash: "mock-hash",
    battlefields: [
      { id: "battlefield_1", value: 1.0 },
      { id: "battlefield_2", value: 1.0 },
      { id: "battlefield_3", value: 1.0 },
      { id: "battlefield_4", value: 1.0 },
      { id: "battlefield_5", value: 1.0 },
    ],
    budgets: { A: 100, B: 100 },
    ...overrides,
  };
}

export function createMockSchema(): Record<string, unknown> {
  return {
    rounds: { type: "integer", minimum: 1, maximum: 100, default: 10, description: "Number of rounds" },
    num_battlefields: { type: "integer", minimum: 1, maximum: 20, default: 5, description: "Number of battlefields" },
    total_resources: { type: "integer", minimum: 1, maximum: 1000, default: 100, description: "Total resources per round" },
    seed: { type: ["integer", "null"], default: null, description: "Random seed" },
    mode: { type: "string", enum: ["classic", "asymmetric", "continuous"], enum_labels: { classic: "Classic Mode", asymmetric: "Asymmetric Mode", continuous: "Continuous Mode" }, description: "Game mode" },
    enable_golden_snitch: { type: "boolean", default: false, description: "Enable golden snitch" },
    scenario: { type: "string", enum: ["prison", "business"], description: "Scenario" },
  };
}

export function createMockSchemaComplex(): Record<string, unknown> {
  return {
    rounds: { type: "integer", minimum: 1, maximum: 100, default: 10 },
    num_battlefields: { type: "integer", minimum: 1, maximum: 20, default: 5 },
    total_resources: { type: "integer", minimum: 1, maximum: 1000, default: 100 },
    battlefields: {
      type: "array",
      minItems: 2,
      maxItems: 10,
      items: {
        type: "object",
        properties: {
          id: { type: "string" },
          value: { type: "number", minimum: 0.5, maximum: 3.0, default: 1.0 },
        },
      },
      description: "Custom battlefield values",
    },
    weights: {
      type: "array",
      minItems: 3,
      items: { type: "number", minimum: 1, default: 1 },
      description: "Resource weights",
    },
    mode: {
      type: "string",
      enum: ["classic", "asymmetric"],
      default: "classic",
    },
    extended_rules: {
      type: "boolean",
      default: false,
      visible_when: { mode: "asymmetric" },
      description: "Only shows in asymmetric mode",
    },
  };
}

export function createMockGameMetadata(overrides: Partial<GameMetadata> = {}): GameMetadata {
  return {
    name: "Colonel Blotto",
    slug: "colonelblotto",
    version: "1.0.0",
    description: "Classic resource allocation game",
    config_schema: createMockSchema(),
    ui: {
      live_view: true,
      custom_config: false,
      custom_history: false,
    },
    ...overrides,
  };
}

export function createMockRPSGameMetadata(overrides: Partial<GameMetadata> = {}): GameMetadata {
  return {
    name: "Rock Paper Scissors",
    slug: "rock_paper_scissors",
    version: "1.0.0",
    description: "Classic hand game",
    config_schema: {
      rounds: { type: "integer", minimum: 1, maximum: 100, default: 10 },
    },
    ui: {
      live_view: true,
      custom_config: true,
      custom_history: false,
    },
    ...overrides,
  };
}
