import { http, HttpResponse } from "msw";
import type { CreateExperimentResponse, GameState, GameResult, GameAgent, GameEntry, ScenarioInfo, MetricDescriptor, LeaderboardResponse, BenchmarkGamesResponse } from "../types";

const API = "/api";

const MOCK_GAMES: GameEntry[] = [
  { slug: "battle_of_the_sexes", name: "Battle of the Sexes" },
  { slug: "centipede", name: "Centipede Game" },
  { slug: "colonelblotto", name: "Colonel Blotto" },
  { slug: "cournot_duopoly", name: "Cournot Duopoly" },
  { slug: "prisonersdilemma", name: "Prisoner's Dilemma" },
  { slug: "public_goods", name: "Public Goods Game" },
  { slug: "rock_paper_scissors", name: "Rock-Paper-Scissors" },
  { slug: "stag_hunt", name: "Stag Hunt" },
  { slug: "texas_hold_em", name: "Texas Hold'em" },
  { slug: "ultimatum", name: "Ultimatum Game" },
];

export const handlers = [
  http.get(`${API}/games`, () => HttpResponse.json<GameEntry[]>(MOCK_GAMES)),

  http.post(`${API}/experiment`, () => {
    return HttpResponse.json<CreateExperimentResponse>({
      session_id: "test-session-123",
      player_tokens: { A: "token-a", B: "token-b" },
      config_hash: "abc123",
    });
  }),

  http.get(`${API}/session/:sessionId/state`, () => {
    return HttpResponse.json<GameState>({
      phase: "complete",
      round: 5,
      round_total: 5,
      awaiting: [],
      history: [
        {
          round: 1,
          allocations: { A: [10, 20, 30, 40, 0], B: [5, 15, 25, 35, 20] },
          scores: { A: 2, B: 1 },
          total_scores: { A: 2, B: 1 },
          winner: "A",
        },
        {
          round: 2,
          allocations: { A: [15, 15, 25, 25, 20], B: [10, 20, 30, 20, 20] },
          scores: { A: 1, B: 2 },
          total_scores: { A: 3, B: 3 },
          winner: "B",
        },
        {
          round: 3,
          allocations: { A: [20, 10, 30, 20, 20], B: [15, 25, 20, 25, 15] },
          scores: { A: 2, B: 1 },
          total_scores: { A: 5, B: 4 },
          winner: "A",
        },
        {
          round: 4,
          allocations: { A: [25, 15, 20, 20, 20], B: [10, 20, 30, 20, 20] },
          scores: { A: 1, B: 2 },
          total_scores: { A: 6, B: 6 },
          winner: "B",
        },
        {
          round: 5,
          allocations: { A: [30, 10, 20, 20, 20], B: [25, 15, 20, 20, 20] },
          scores: { A: 2, B: 1 },
          total_scores: { A: 8, B: 7 },
          winner: "A",
        },
      ],
      config_hash: "abc123",
    });
  }),

  http.post(`${API}/session/:sessionId/action`, () => {
    return HttpResponse.json<GameState>({
      phase: "awaiting_action",
      round: 3,
      round_total: 5,
      awaiting: [],
      history: [],
      config_hash: "abc123",
    });
  }),

  http.get(`${API}/session/:sessionId/results`, () => {
    return HttpResponse.json<GameResult>({
      config_hash: "abc123",
      total_scores: { A: 8, B: 7 },
      winner: "A",
      metrics: {
        nash_gap: { A: 0.05, B: 0.03 },
        strategy_entropy: { A: 1.5, B: 1.2 },
      },
      history: [
        {
          round: 1,
          allocations: { A: [10, 20, 30, 40, 0], B: [5, 15, 25, 35, 20] },
          scores: { A: 2, B: 1 },
          total_scores: { A: 2, B: 1 },
          winner: "A",
        },
      ],
      rich_metrics: {
        match_id: "test-session-123",
        game_type: "colonelblotto",
        num_agents: 2,
        agents: {
          A: {
            total_payoff: 8,
            avg_payoff: 1.6,
            strategy_entropy: 1.5,
            behavioral_consistency: 0.8,
            cumulative_regret: 0.3,
            adaptive_regret_series: [0.1, 0.2, 0.3],
            nash_gap: 0.05,
          },
          B: {
            total_payoff: 7,
            avg_payoff: 1.4,
            strategy_entropy: 1.2,
            behavioral_consistency: 0.7,
            cumulative_regret: 0.4,
            adaptive_regret_series: [0.15, 0.25, 0.35],
            nash_gap: 0.03,
          },
        },
        joint: { cooperation_rate: 0.6, nash_gap: 0.04 },
        pairwise: {},
      },
    });
  }),

  http.get(`${API}/games/:name/agents`, () => {
    return HttpResponse.json<{ agents: GameAgent[] }>({
      agents: [
        { id: "uniform", label: "Uniform Distribution", description: "Balanced across fields" },
        { id: "random", label: "Random", description: "Random allocation" },
        { id: "greedy", label: "Greedy", description: "Beats last move" },
        { id: "remote", label: "Remote Agent", description: "Controlled via API" },
      ],
    });
  }),

  http.get(`${API}/games/:name/scenarios`, () => {
    return HttpResponse.json<{ scenarios: ScenarioInfo[] }>({
      scenarios: [
        {
          id: "prison",
          name: "Prisoner's Dilemma",
          description: "Classic scenario",
          cooperate_label: "Stay Silent",
          defect_label: "Betray",
          system_prompt: "You are a prisoner.",
        },
        {
          id: "business",
          name: "Business Deal",
          description: "Business scenario",
          cooperate_label: "Honor Deal",
          defect_label: "Break Deal",
          system_prompt: "You are a businessperson.",
        },
      ],
    });
  }),

  http.get(`${API}/games/:name/metrics`, () => {
    return HttpResponse.json<{ metrics: MetricDescriptor[] }>({
      metrics: [
        { name: "nash_gap", when: "post_match", type: "number", description: "Distance from Nash equilibrium" },
        { name: "strategy_entropy", when: "post_match", type: "number", description: "Measure of strategy diversity" },
      ],
    });
  }),

  http.get(`${API}/games/:name`, () => {
    return HttpResponse.json({
      name: "Colonel Blotto",
      slug: "colonelblotto",
      config_schema: {
        rounds: { type: "integer", minimum: 1, maximum: 100, default: 10, description: "Number of rounds" },
        num_battlefields: { type: "integer", minimum: 1, maximum: 20, default: 5, description: "Number of battlefields" },
        total_resources: { type: "integer", minimum: 1, maximum: 1000, default: 100, description: "Total resources per round" },
        seed: { type: ["integer", "null"], default: null, description: "Random seed" },
      },
    });
  }),

  // Fallback leaderboard handlers — test-specific handlers added via server.use()
  // take priority. These exist so that in-flight requests triggered by
  // LeaderboardPage's date auto-populate effect still resolve after a test's
  // own handlers are removed by server.resetHandlers(), preventing open handles
  // from keeping the worker process alive.
  http.get(`${API}/leaderboard`, () =>
    HttpResponse.json<LeaderboardResponse>({
      agents: [],
      total: 0,
      page: 1,
      page_size: 50,
      total_matches: 0,
      date_range: { min_date: null, max_date: null },
    }),
  ),

  http.get(`${API}/benchmark/games`, () =>
    HttpResponse.json<BenchmarkGamesResponse>({ games: [] }),
  ),
];
