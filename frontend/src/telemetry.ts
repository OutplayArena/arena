import { ApiError, request } from "./api";

export interface TelemetryEvent {
  id: number;
  session_id: string;
  schema_version: number;
  event_type: string;
  occurred_at: string;
  player_id: string | null;
  round_number: number | null;
  agent_id: string | null;
  payload: Record<string, unknown>;
}

export interface TelemetryEvents {
  schema_version: number;
  session_id: string;
  events: TelemetryEvent[];
  next_after_id: number | null;
}

export interface PlayerTelemetry {
  player_id: string;
  agent_id: string | null;
  accepted_actions: number | null;
  rejected_actions: number | null;
  forfeits: number | null;
  mean_apply_latency_ms: number | null;
  action_distribution: { action: string; count: number }[];
  repeated_action_rate: number | null;
  score: number | null;
}

export interface TelemetryReport {
  schema_version: number;
  session_id: string;
  game: string;
  status: string;
  provenance: {
    arena_version: string | null;
    config_hash: string | null;
    seed: number | null;
    config: Record<string, unknown>;
    agents: Record<string, unknown>;
  };
  coverage: {
    event_count: number;
    recorded_actions: number;
    history_rounds: number;
    history_entries: number;
    legacy: boolean;
    action_source: "events" | "unavailable";
    complete: boolean;
  };
  summary: {
    rounds_completed: number;
    action_count: number | null;
    rejected_actions: number | null;
    forfeits: number | null;
    scores: Record<string, number>;
    winner: string | null;
  };
  players: PlayerTelemetry[];
  patterns: {
    code: string;
    severity: string;
    title: string;
    detail: string;
    player_id?: string | null;
    evidence: Record<string, unknown>;
  }[];
}

export const TELEMETRY_EVENT_TYPES = [
  "session.created",
  "action.accepted",
  "action.rejected",
  "round.completed",
  "session.completed",
  "session.failed",
] as const;

function sessionPath(sessionId: string): string {
  return `/api/session/${encodeURIComponent(sessionId)}/telemetry`;
}

export function getTelemetryReport(sessionId: string, signal?: AbortSignal): Promise<TelemetryReport> {
  return request<TelemetryReport>(sessionPath(sessionId), { signal });
}

export function getTelemetryEvents(
  sessionId: string,
  options: { afterId?: number; limit?: number; eventType?: string; signal?: AbortSignal } = {},
): Promise<TelemetryEvents> {
  const query = new URLSearchParams({ limit: String(options.limit ?? 50) });
  if (options.afterId != null) query.set("after_id", String(options.afterId));
  if (options.eventType) query.set("event_type", options.eventType);
  return request<TelemetryEvents>(`${sessionPath(sessionId)}/events?${query}`, { signal: options.signal });
}

/** Download through an authenticated fetch so browser downloads also support API tokens. */
export async function downloadTelemetry(
  sessionId: string,
  format: "json" | "jsonl",
  signal?: AbortSignal,
): Promise<void> {
  const token = localStorage.getItem("arena-token");
  const response = await fetch(`${sessionPath(sessionId)}/export?format=${format}`, {
    signal,
    headers: {
      Accept: format === "json" ? "application/json" : "application/x-ndjson",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
  });
  if (!response.ok) {
    const data = await response.json().catch(() => ({})) as { detail?: string };
    throw new ApiError(data.detail ?? `Export failed (HTTP ${response.status})`, response.status);
  }
  const blob = await response.blob();
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = `arena-${sessionId.replace(/[^a-zA-Z0-9_-]/g, "_")}-telemetry.${format}`;
  document.body.appendChild(link);
  try {
    link.click();
  } finally {
    link.remove();
    URL.revokeObjectURL(url);
  }
}
