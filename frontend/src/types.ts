export interface UserInfo {
  id: string;
  email: string;
  name: string;
  avatar_url: string | null;
  privacy_accepted: boolean;
  /** Public display handle: GitHub @login or Google first name. Never email. */
  username: string | null;
}

export interface ProvidersResponse {
  github: boolean;
  google: boolean;
}

export type AgentName = "uniform" | "random" | "greedy";
export type PlayerSide = "A" | "B";
export type PlayerId = string;

export interface Battlefield {
  id: string;
  value: number;
}

export interface ExperimentConfig {
  game: string;
  variant: string;
  players: number;
  budget?: number[];
  battlefields?: Battlefield[];
  rounds: number;
  seed?: number | null;
  agents?: Record<string, string>;
  interactive?: boolean;
  [key: string]: unknown;
}

export interface CreateExperimentResponse {
  session_id: string;
  player_tokens: Record<string, string>;
  config_hash: string;
}

export interface GameState {
  phase: "awaiting_action" | "complete";
  round: number;
  round_total: number;
  awaiting: PlayerSide[];
  budgets?: Record<PlayerSide, number>;
  battlefields?: Battlefield[];
  total_scores?: Record<PlayerSide, number>;
  history: GameStateRound[];
  [key: string]: unknown;
}

export interface GameStateRound {
  round: number;
  allocations?: Record<PlayerSide, number[]>;
  actions?: Record<PlayerSide, unknown>;
  scores?: Record<PlayerSide, number>;
  payoffs?: Record<PlayerSide, number>;
  total_scores?: Record<PlayerSide, number>;
  winner?: PlayerSide | "Tie";
  outcome?: string;
}

export interface GameResult {
  config_hash: string;
  total_scores: Record<PlayerSide, number>;
  winner: PlayerSide | "Tie";
  metrics: Record<string, unknown>;
  history: GameStateRound[];
  rich_metrics?: RichMetrics;
}

export interface RichMetrics {
  match_id: string;
  game_type: string;
  num_agents: number;
  agents: Record<string, RichAgentMetrics>;
  joint: Record<string, unknown>;
  pairwise: Record<string, unknown>;
}

export interface RichAgentMetrics {
  total_payoff: number;
  avg_payoff: number;
  strategy_entropy: number;
  behavioral_consistency: number;
  cumulative_regret: number;
  adaptive_regret_series: number[];
  nash_gap: number;
  cooperation_rate?: number;
  tit_for_tat_adherence?: Record<string, number>;
  forgiveness_index?: Record<string, number>;
  conditional_cooperation?: Record<string, number>;
  mean_tft_adherence?: number;
  mean_forgiveness?: number;
  [key: string]: unknown;
}

export interface Match {
  agent_a: string;
  agent_b: string;
  session_id: string;
  config_hash: string;
  num_rounds: number;
  num_battlefields: number;
  total_resources: number;
  total_score_a: number;
  total_score_b: number;
  match_winner?: PlayerSide | "Tie";
  metrics: Record<string, unknown>;
  history: MatchRound[];
  currentState?: Record<string, unknown>;
  rich_metrics?: RichMetrics;
  agents?: Record<string, string>;
  total_scores?: Record<string, number>;
  player_ids?: string[];
}

export interface MatchRound {
  round: number;
  agent_a: string;
  agent_b: string;
  action_a: unknown;
  action_b: unknown;
  score_a: number;
  score_b: number;
  total_score_a: number;
  total_score_b: number;
  winner: PlayerSide | "Tie";
  raw?: Record<string, unknown>;
}

export interface RunConfig {
  agent_a: string;
  agent_b: string;
  num_rounds: number;
  num_battlefields: number;
  total_resources: number;
  session_id?: string;
}

export interface SiteConfig {
  github_url: string;
  docs_url: string;
  privacy_notice_url: string;
  about_text: string;
  footer: {
    copyright: string;
    tagline: string;
  };
}

export interface HealthResponse {
  status: string;
}

export interface StaticVersionResponse {
  version: number;
}

export interface SessionSummary {
  id: string;
  game_slug: string;
  agents: Record<string, string>;
  agent_a: string | null;
  agent_b: string | null;
  winner: string | null;
  total_score_a: number | null;
  total_score_b: number | null;
  created_at: string | null;
  rounds?: number;
  num_battlefields?: number;
  resources?: number;
  seed?: number | null;
  /**
   * Full config exactly as it was submitted when the session was created.
   * The Config tab on the play page uses this to show the parameters that
   * were used to run a current/completed/failed game (read-only).  The
   * flattened fields above are kept for convenience in list/history views.
   */
  config?: Record<string, unknown>;
  status: string;
  locked: boolean;
  /** Whether this session contributes to the public leaderboard. */
  is_public: boolean;
}

export interface SessionsResponse {
  sessions: SessionSummary[];
  total: number;
}

export interface DashboardGameEntry {
  count: number;
  sessions: SessionSummary[];
}

export interface DashboardResponse {
  total_games: number;
  games: Record<string, DashboardGameEntry>;
}

export interface GameEntry {
  name: string;
  slug: string;
  version?: string;
  status?: string;
  description?: string;
  tags?: string[];
  players?: Record<string, unknown>;
  ontology?: Record<string, unknown>;
}

export interface GameMetadata extends GameEntry {
  config_schema?: Record<string, unknown>;
  ui?: GameUIFlags;
}

export interface GameUIFlags {
  live_view: boolean;
  custom_config: boolean;
  custom_history: boolean;
  interactive_play: boolean;
}

export interface GameAgent {
  id: string;
  label: string;
  description?: string;
}

export interface ApiKeyRow {
  id: string;
  key_prefix: string;
  name: string | null;
  is_active: boolean;
  last_used_at: string | null;
  created_at: string | null;
}

export interface ApiKeyCreatedResponse extends ApiKeyRow {
  full_key: string;
}

export interface MetricDescriptor {
  name: string;
  when: string;
  type: string;
  description: string;
}

export interface ScenarioInfo {
  id: string;
  name: string;
  description: string;
  cooperate_label: string;
  defect_label: string;
  system_prompt: string;
}

export interface MailboxMessage {
  id: string;
  sender: string;
  recipient: string;
  content: string;
  round: number;
  created_at?: string;
  turn_phase?: "before" | "after";
}

export interface BenchmarkAgent {
  elo: number;
  alpha_rank?: number;
  matches_played: number;
  metrics?: Record<string, number>;
}

export interface BenchmarkReport {
  agents: Record<string, BenchmarkAgent>;
  ranking: string[];
  population: Record<string, unknown>;
  total_matches: number;
  /** Inclusive [min_date, max_date] of recorded match activity, in YYYY-MM-DD. */
  date_range?: { min_date: string | null; max_date: string | null };
  note?: string;
}

export interface BenchmarkGamesResponse {
  games: string[];
}

export interface LeaderboardEntry {
  agent_id: string;
  /** The model/agent name without the @username suffix. */
  display_name: string;
  /** Public handle of the owner (GitHub @login or Google first name). Null for personal scope. */
  owner_username: string | null;
  /** True when this entry belongs to the currently logged-in user. */
  is_own: boolean;
  elo: number;
  alpha_rank: number | null;
  matches_played: number;
  metrics: Record<string, number>;
}

export interface LeaderboardResponse {
  agents: LeaderboardEntry[];
  total: number;
  page: number;
  page_size: number;
  total_matches?: number;
  /** Inclusive [min_date, max_date] of recorded match activity, in YYYY-MM-DD. */
  date_range?: { min_date: string | null; max_date: string | null };
  note?: string;
  scope?: "personal" | "public" | "all";
}

export interface AgentGameEntry {
  elo: number;
  matches_played: number;
  alpha_rank: number | null;
  metrics: Record<string, number>;
  total_agents: number;
}

export interface AgentDetailResponse {
  agent_id: string;
  overall: AgentGameEntry | null;
  per_game: Record<string, AgentGameEntry>;
}

export interface RatingHistoryPoint {
  timestamp: string;
  elo: number;
}

export interface RatingHistoryResponse {
  agent_id: string;
  game: string;
  history: RatingHistoryPoint[];
}


