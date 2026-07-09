import type {
  CreateExperimentResponse,
  ExperimentConfig,
  GameResult,
  GameState,
  ProvidersResponse,
  SiteConfig,
  DashboardResponse,
  SessionsResponse,
  SessionSummary,
  ApiKeyRow,
  ApiKeyCreatedResponse,
  GameEntry,
  GameMetadata,
  GameAgent,
  MetricDescriptor,
  ScenarioInfo,
  MailboxMessage,
  BenchmarkReport,
  BenchmarkGamesResponse,
  LeaderboardResponse,
  AgentDetailResponse,
  RatingHistoryResponse,
  UserInfo,
  AdminUsersResponse,
  AdminSessionsResponse,
  AdminStatsResponse,
  AdminSettings,
  LobbyMatchSummary,
  LobbyMatchDetail,
  CreateOpenMatchResponse,
  JoinMatchResponse,
} from "./types";

export class ApiError extends Error {
  status: number;
  constructor(message: string, status: number) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

export async function request<T>(
  path: string,
  options: RequestInit = {},
): Promise<T> {
  const token = localStorage.getItem("arena-token");
  const headers: Record<string, string> = {
    Accept: "application/json",
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
    ...(options.body ? { "Content-Type": "application/json" } : {}),
    ...(options.headers as Record<string, string> | undefined),
  };

  const res = await fetch(path, { ...options, headers });

  const text = await res.text();
  let data: Record<string, unknown>;
  try {
    data = JSON.parse(text || "{}");
  } catch {
    throw new ApiError("Invalid JSON response", res.status);
  }

  if (!res.ok) {
    const detail = data.detail || data.error || `HTTP ${res.status}`;
    throw new ApiError(String(detail), res.status);
  }

  return data as T;
}

export function createExperiment(
  config: ExperimentConfig,
): Promise<CreateExperimentResponse> {
  return request<CreateExperimentResponse>("/api/experiment", {
    method: "POST",
    body: JSON.stringify(config),
  });
}

export function getState(sessionId: string): Promise<GameState> {
  return request<GameState>(`/api/session/${sessionId}/state`);
}

export function submitAction(
  sessionId: string,
  action: unknown,
  token: string,
): Promise<GameState> {
  return request<GameState>(`/api/session/${sessionId}/action`, {
    method: "POST",
    body: JSON.stringify({ allocation: action }),
    headers: { Authorization: `Bearer ${token}` },
  });
}

export function getResults(sessionId: string): Promise<GameResult> {
  return request<GameResult>(`/api/session/${sessionId}/results`);
}

export function getProviders(): Promise<ProvidersResponse> {
  return request<ProvidersResponse>("/api/auth/providers");
}

export function getSiteConfig(): Promise<SiteConfig> {
  return request<SiteConfig>("/api/site-config");
}

export function getDashboard(): Promise<DashboardResponse> {
  return request<DashboardResponse>("/api/dashboard");
}

export function listSessions(params?: {
  game?: string;
  agent?: string;
  date_from?: string;
  date_to?: string;
  limit?: number;
  offset?: number;
}): Promise<SessionsResponse> {
  const searchParams = new URLSearchParams();
  if (params?.game) searchParams.set("game", params.game);
  if (params?.agent) searchParams.set("agent", params.agent);
  if (params?.date_from) searchParams.set("date_from", params.date_from);
  if (params?.date_to) searchParams.set("date_to", params.date_to);
  if (params?.limit) searchParams.set("limit", String(params.limit));
  if (params?.offset) searchParams.set("offset", String(params.offset));
  const qs = searchParams.toString();
  return request<SessionsResponse>(`/api/sessions${qs ? `?${qs}` : ""}`);
}

export function getSessionSummary(sessionId: string): Promise<SessionSummary> {
  return request<SessionSummary>(`/api/session/${sessionId}/summary`);
}

export function failSession(sessionId: string, error: string): Promise<{ session_id: string; status: string; error_message: string | null }> {
  return request<{ session_id: string; status: string; error_message: string | null }>(`/api/session/${sessionId}/fail`, {
    method: "POST",
    body: JSON.stringify({ error }),
  });
}

export function deleteSession(sessionId: string): Promise<{ deleted: string }> {
  return request<{ deleted: string }>(`/api/sessions/${sessionId}`, {
    method: "DELETE",
  });
}

export function listKeys(): Promise<ApiKeyRow[]> {
  return request<ApiKeyRow[]>("/api/keys");
}

export function createKey(name?: string): Promise<ApiKeyCreatedResponse> {
  return request<ApiKeyCreatedResponse>("/api/keys", {
    method: "POST",
    body: JSON.stringify({ name: name || null }),
  });
}

export function deleteKey(keyId: string): Promise<{ deleted: string }> {
  return request<{ deleted: string }>(`/api/keys/${keyId}`, {
    method: "DELETE",
  });
}

export function disableKey(keyId: string): Promise<{ disabled: string }> {
  return request<{ disabled: string }>(`/api/keys/${keyId}/disable`, {
    method: "POST",
  });
}

export function enableKey(keyId: string): Promise<{ enabled: string }> {
  return request<{ enabled: string }>(`/api/keys/${keyId}/enable`, {
    method: "POST",
  });
}

export function listGames(): Promise<GameEntry[]> {
  return request<GameEntry[]>("/api/games");
}

export function getGameMetadata(name: string): Promise<GameMetadata> {
  return request<GameMetadata>(`/api/games/${name}`);
}

export function getGameAgents(name: string): Promise<{ agents: GameAgent[] }> {
  return request<{ agents: GameAgent[] }>(`/api/games/${name}/agents`);
}

export function getGameMetrics(name: string): Promise<{ metrics: MetricDescriptor[] }> {
  return request<{ metrics: MetricDescriptor[] }>(`/api/games/${name}/metrics`);
}

export function getGameScenarios(name: string): Promise<{ scenarios: ScenarioInfo[] }> {
  return request<{ scenarios: ScenarioInfo[] }>(`/api/games/${name}/scenarios`);
}

export function getGameSkill(name: string): Promise<{ game: string; title: string; sections: Record<string, string> }> {
  return request(`/api/games/${name}/skill`);
}

// ── W&B Settings ──────────────────────────────────────────────────────

export function getWandbKeyStatus(): Promise<{ configured: boolean; updated_at: string | null; key_fingerprint: string | null }> {
  return request("/api/settings/wandb-key");
}

export function saveWandbKey(apiKey: string): Promise<{ configured: boolean }> {
  return request("/api/settings/wandb-key", {
    method: "PUT",
    body: JSON.stringify({ api_key: apiKey }),
  });
}

export function deleteWandbKey(): Promise<{ configured: boolean }> {
  return request("/api/settings/wandb-key", { method: "DELETE" });
}

export function getWandbEntities(): Promise<{ personal_entity: string; entities: string[] }> {
  return request("/api/settings/wandb-key/entities");
}

export function connectSessionStream(
  sessionId: string,
  onStateChange: (state: GameState) => void,
  onError?: (err: Event) => void,
): EventSource {
  const source = new EventSource(`/api/session/${sessionId}/stream`);
  source.addEventListener("state_change", (e: MessageEvent) => {
    const state = JSON.parse(e.data) as GameState;
    onStateChange(state);
  });
  if (onError) {
    source.onerror = onError;
  }
  return source;
}

export function getInteractiveSchema(
  sessionId: string,
  player: string,
): Promise<{
  schema: Record<string, unknown>;
  ui_metadata: Record<string, unknown>;
  state: GameState;
}> {
  return request<{
    schema: Record<string, unknown>;
    ui_metadata: Record<string, unknown>;
    state: GameState;
  }>(`/api/session/${sessionId}/interactive/schema?player=${player}`);
}

export function submitHumanAction(
  sessionId: string,
  player: string,
  action: unknown,
  token: string,
  forfeit: boolean = false,
): Promise<GameState> {
  return request<GameState>(`/api/session/${sessionId}/interactive/action?player=${player}`, {
    method: "POST",
    body: JSON.stringify({ action, forfeit }),
    headers: { Authorization: `Bearer ${token}` },
  });
}

export function getInteractiveState(
  sessionId: string,
  player: string,
): Promise<GameState> {
  return request<GameState>(`/api/session/${sessionId}/interactive/state?player=${player}`);
}

export function getInteractiveAgents(
  gameName: string,
): Promise<{ agents: GameAgent[] }> {
  return request<{ agents: GameAgent[] }>(`/api/games/${gameName}/interactive/agents`);
}

export function sendMailboxMessage(
  sessionId: string,
  content: string,
  recipient: string,
  token: string,
): Promise<MailboxMessage> {
  return request<MailboxMessage>(`/api/session/${sessionId}/mailbox/send`, {
    method: "POST",
    body: JSON.stringify({ content, recipient }),
    headers: { Authorization: `Bearer ${token}` },
  });
}

export function getMailboxMessages(
  sessionId: string,
  player?: string,
): Promise<{ messages: MailboxMessage[] }> {
  const params = player ? `?player=${player}` : "";
  return request<{ messages: MailboxMessage[] }>(`/api/session/${sessionId}/mailbox/messages${params}`);
}

export function getBenchmarkReport(
  game?: string,
  params?: { date_from?: string; date_to?: string },
): Promise<BenchmarkReport> {
  const searchParams = new URLSearchParams();
  if (game) searchParams.set("game", game);
  if (params?.date_from) searchParams.set("date_from", params.date_from);
  if (params?.date_to) searchParams.set("date_to", params.date_to);
  const qs = searchParams.toString();
  return request<BenchmarkReport>(`/api/benchmark/report${qs ? `?${qs}` : ""}`);
}

export function getBenchmarkGames(): Promise<BenchmarkGamesResponse> {
  return request<BenchmarkGamesResponse>("/api/benchmark/games");
}

export function getLeaderboard(params?: {
  game?: string;
  sort_by?: string;
  sort_dir?: string;
  page?: number;
  page_size?: number;
  agent_ids?: string;
  date_from?: string;
  date_to?: string;
  scope?: "personal" | "public" | "all";
}): Promise<LeaderboardResponse> {
  const searchParams = new URLSearchParams();
  if (params?.game) searchParams.set("game", params.game);
  if (params?.sort_by) searchParams.set("sort_by", params.sort_by);
  if (params?.sort_dir) searchParams.set("sort_dir", params.sort_dir);
  if (params?.page) searchParams.set("page", String(params.page));
  if (params?.page_size) searchParams.set("page_size", String(params.page_size));
  if (params?.agent_ids) searchParams.set("agent_ids", params.agent_ids);
  if (params?.date_from) searchParams.set("date_from", params.date_from);
  if (params?.date_to) searchParams.set("date_to", params.date_to);
  if (params?.scope) searchParams.set("scope", params.scope);
  const qs = searchParams.toString();
  return request<LeaderboardResponse>(`/api/leaderboard${qs ? `?${qs}` : ""}`);
}

export function setSessionVisibility(
  sessionId: string,
  isPublic: boolean,
): Promise<{ session_id: string; is_public: boolean }> {
  return request(`/api/sessions/${sessionId}/visibility`, {
    method: "PATCH",
    body: JSON.stringify({ is_public: isPublic }),
  });
}

export function getAgentDetail(agentId: string): Promise<AgentDetailResponse> {
  return request<AgentDetailResponse>(`/api/leaderboard/agents/${agentId}`);
}

export function getAgentHistory(agentId: string, game?: string): Promise<RatingHistoryResponse> {
  const qs = game ? `?game=${game}` : "";
  return request<RatingHistoryResponse>(`/api/leaderboard/agents/${agentId}/history${qs}`);
}

// ── GDPR ──────────────────────────────────────────────────────────────

/**
 * Fetch the authenticated user's full data export as a JSON blob and
 * trigger a browser file download.  The raw key/token values are never
 * included — the backend redacts them before responding.
 */
export async function downloadUserData(): Promise<void> {
  const resp = await fetch("/api/settings/data-export", {
    credentials: "include",
  });
  if (!resp.ok) {
    const text = await resp.text().catch(() => resp.statusText);
    throw new ApiError(text, resp.status);
  }
  const blob = await resp.blob();
  const disposition = resp.headers.get("Content-Disposition") ?? "";
  const match = disposition.match(/filename="([^"]+)"/);
  const filename = match?.[1] ?? "outplayarena-export.json";
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}

export function deleteAccount(): Promise<{ deleted: boolean }> {
  return request<{ deleted: boolean }>("/api/settings/account", { method: "DELETE" });
}

export function acceptPrivacy(): Promise<{ privacy_accepted: boolean }> {
  return request<{ privacy_accepted: boolean }>("/api/settings/accept-privacy", { method: "POST" });
}

export function updatePreferences(prefs: { show_own_leaderboard_badge: boolean }): Promise<UserInfo> {
  return request<UserInfo>("/api/settings/preferences", {
    method: "PATCH",
    body: JSON.stringify(prefs),
  });
}

// ── Admin dashboard (#116) ─────────────────────────────────────────────────

export function getAdminUsers(limit = 100, offset = 0): Promise<AdminUsersResponse> {
  const q = new URLSearchParams({ limit: String(limit), offset: String(offset) });
  return request<AdminUsersResponse>(`/api/admin/users?${q.toString()}`);
}

export function getAdminSessions(limit = 100, offset = 0): Promise<AdminSessionsResponse> {
  const q = new URLSearchParams({ limit: String(limit), offset: String(offset) });
  return request<AdminSessionsResponse>(`/api/admin/sessions?${q.toString()}`);
}

export function getAdminStats(): Promise<AdminStatsResponse> {
  return request<AdminStatsResponse>("/api/admin/stats");
}

export function getAdminSettings(): Promise<AdminSettings> {
  return request<AdminSettings>("/api/admin/settings");
}

export function updateAdminSettings(partial: Partial<AdminSettings>): Promise<Partial<AdminSettings>> {
  return request<Partial<AdminSettings>>("/api/admin/settings", {
    method: "PUT",
    body: JSON.stringify(partial),
  });
}

// ── Matchmaking / lobby (#96) ──────────────────────────────────────────────

export function createOpenMatch(
  config: ExperimentConfig,
  agents?: Record<string, string>,
): Promise<CreateOpenMatchResponse> {
  const payload: Record<string, unknown> = { ...config };
  if (agents) payload.agents = agents;
  return request<CreateOpenMatchResponse>("/api/lobby/matches", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function listOpenMatches(): Promise<LobbyMatchSummary[]> {
  return request<{ matches: LobbyMatchSummary[] }>("/api/lobby/matches").then(
    (r) => r.matches,
  );
}

export function getMatch(matchId: string): Promise<LobbyMatchDetail> {
  return request<LobbyMatchDetail>(`/api/lobby/matches/${matchId}`);
}

export function joinMatch(
  matchId: string,
  slot?: string,
): Promise<JoinMatchResponse> {
  const body = slot ? { slot } : undefined;
  return request<JoinMatchResponse>(`/api/lobby/matches/${matchId}/join`, {
    method: "POST",
    body: body ? JSON.stringify(body) : undefined,
  });
}

export function cancelMatch(matchId: string): Promise<{ cancelled: boolean }> {
  return request<{ cancelled: boolean }>(
    `/api/lobby/matches/${matchId}`,
    { method: "DELETE" },
  );
}


