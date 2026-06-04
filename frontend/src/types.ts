export interface UserInfo {
  id: string;
  email: string;
  name: string;
  avatar_url: string | null;
}

export interface ProvidersResponse {
  github: boolean;
  google: boolean;
}

export type AgentName = "uniform" | "random" | "greedy";
export type PlayerSide = "A" | "B";

export interface Battlefield {
  id: string;
  value: number;
}

export interface ExperimentConfig {
  game: string;
  variant: string;
  players: number;
  budget: number[];
  battlefields: Battlefield[];
  rounds: number;
  seed: null;
  agents?: Record<string, string>;
  interactive?: boolean;
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
  budgets: Record<PlayerSide, number>;
  battlefields: Battlefield[];
  history: GameStateRound[];
}

export interface GameStateRound {
  round: number;
  allocations: Record<PlayerSide, number[]>;
  scores: Record<PlayerSide, number>;
  total_scores: Record<PlayerSide, number>;
  winner: PlayerSide | "Tie";
}

export interface GameResult {
  config_hash: string;
  total_scores: Record<PlayerSide, number>;
  winner: PlayerSide | "Tie";
  metrics: Record<string, number>;
  history: GameStateRound[];
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
  metrics: Record<string, number>;
  history: MatchRound[];
}

export interface MatchRound {
  round: number;
  agent_a: string;
  agent_b: string;
  action_a: number[];
  action_b: number[];
  score_a: number;
  score_b: number;
  total_score_a: number;
  total_score_b: number;
  winner: PlayerSide | "Tie";
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
    privacy_notice: string;
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
  status: string;
  locked: boolean;
}

export interface SessionsResponse {
  sessions: SessionSummary[];
  total: number;
}

export interface DashboardResponse {
  total_games: number;
  games: Record<string, SessionSummary[]>;
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

export const CLIENT_AGENTS: AgentName[] = ["uniform", "random", "greedy"];
