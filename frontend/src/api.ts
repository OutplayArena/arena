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
  const token = localStorage.getItem("nasharena_token");
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


