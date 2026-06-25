import { describe, it, expect, beforeEach } from "vitest";
import { screen, waitFor } from "@testing-library/react";
import { Routes, Route } from "react-router-dom";
import { http, HttpResponse } from "msw";
import { server } from "../../mocks/server";
import { renderWithProviders } from "../../test-utils";
import { AgentDetailPage } from "../AgentDetailPage";
import type { AgentDetailResponse, RatingHistoryResponse } from "../../types";

function renderAgentDetail(initialRoute: string) {
  return renderWithProviders(
    <Routes>
      <Route path="/leaderboard/:agentId" element={<AgentDetailPage />} />
      <Route path="/leaderboard" element={<AgentDetailPage />} />
    </Routes>,
    { initialRoute },
  );
}

const SAMPLE_DETAIL: AgentDetailResponse = {
  agent_id: "anthropic__claude-opus-4-8",
  overall: {
    elo: 1500,
    matches_played: 50,
    alpha_rank: 0.4,
    metrics: { nash_gap: 0.05, cooperation_rate: 0.6, avg_payoff: 0.5 },
    total_agents: 10,
  },
  per_game: {
    colonelblotto: {
      elo: 1480,
      matches_played: 20,
      alpha_rank: 0.35,
      metrics: { nash_gap: 0.04 },
      total_agents: 8,
    },
    ultimatum: {
      elo: 1520,
      matches_played: 30,
      alpha_rank: 0.45,
      metrics: { cooperation_rate: 0.7 },
      total_agents: 6,
    },
  },
};

const SAMPLE_HISTORY: RatingHistoryResponse = {
  agent_id: "anthropic__claude-opus-4-8",
  game: "overall",
  history: [
    { timestamp: "2025-01-01T00:00:00+00:00", elo: 1200 },
    { timestamp: "2025-02-01T00:00:00+00:00", elo: 1250 },
    { timestamp: "2025-03-01T00:00:00+00:00", elo: 1300 },
  ],
};

const EMPTY_HISTORY: RatingHistoryResponse = {
  agent_id: "anthropic__claude-opus-4-8",
  game: "overall",
  history: [],
};

function mockAgentEndpoints(detail: AgentDetailResponse, history: RatingHistoryResponse) {
  server.use(
    http.get("/api/leaderboard/agents/:agentId", () => HttpResponse.json(detail)),
    http.get("/api/leaderboard/agents/:agentId/history", () => HttpResponse.json(history)),
  );
}

describe("AgentDetailPage", () => {
  beforeEach(() => {
    server.resetHandlers();
  });

  it("renders loading state initially", async () => {
    server.use(
      http.get("/api/leaderboard/agents/:agentId", async () => {
        await new Promise((r) => setTimeout(r, 100));
        return HttpResponse.json(SAMPLE_DETAIL);
      }),
      http.get("/api/leaderboard/agents/:agentId/history", async () => {
        await new Promise((r) => setTimeout(r, 100));
        return HttpResponse.json(SAMPLE_HISTORY);
      }),
    );
    renderAgentDetail("/leaderboard/anthropic__claude-opus-4-8");
    expect(screen.getByText(/Loading agent details/i)).toBeInTheDocument();
  });

  it("renders the agent model name from the agent_id", async () => {
    mockAgentEndpoints(SAMPLE_DETAIL, SAMPLE_HISTORY);
    renderAgentDetail("/leaderboard/anthropic__claude-opus-4-8");
    await waitFor(() => {
      expect(screen.getByRole("heading", { name: "claude-opus-4-8" })).toBeInTheDocument();
    });
  });

  it("renders the provider name from the agent_id", async () => {
    mockAgentEndpoints(SAMPLE_DETAIL, SAMPLE_HISTORY);
    renderAgentDetail("/leaderboard/anthropic__claude-opus-4-8");
    await waitFor(() => {
      expect(screen.getByText("anthropic")).toBeInTheDocument();
    });
  });

  it("renders overall stats badges", async () => {
    mockAgentEndpoints(SAMPLE_DETAIL, SAMPLE_HISTORY);
    renderAgentDetail("/leaderboard/anthropic__claude-opus-4-8");
    await waitFor(() => {
      expect(screen.getByText("Overall")).toBeInTheDocument();
    });
    // Elo rounded to integer.
    expect(screen.getByText("1500")).toBeInTheDocument();
  });

  it("renders per-game breakdown cards with human-readable names", async () => {
    mockAgentEndpoints(SAMPLE_DETAIL, SAMPLE_HISTORY);
    renderAgentDetail("/leaderboard/anthropic__claude-opus-4-8");
    await waitFor(() => {
      expect(screen.getByText("Colonel Blotto")).toBeInTheDocument();
    });
    expect(screen.getByText("Ultimatum Game")).toBeInTheDocument();
  });

  it("prettifies the slug when no human-readable name is available (no raw underscores)", async () => {
    // Make /api/games fail so the cache stays empty — the UI must still show
    // a human-readable label, never the raw slug.
    server.use(
      http.get("/api/leaderboard/agents/:agentId", () => HttpResponse.json(SAMPLE_DETAIL)),
      http.get("/api/leaderboard/agents/:agentId/history", () => HttpResponse.json(SAMPLE_HISTORY)),
      http.get("/api/games", () => new HttpResponse("boom", { status: 500 })),
    );
    renderAgentDetail("/leaderboard/anthropic__claude-opus-4-8");
    await waitFor(() => {
      // slug "colonelblotto" → prettified "Colonelblotto"
      expect(screen.getByText("Colonelblotto")).toBeInTheDocument();
    });
    // slug "ultimatum" → prettified "Ultimatum"
    expect(screen.getByText("Ultimatum")).toBeInTheDocument();
  });

  it("renders Elo rating history chart when history is present", async () => {
    mockAgentEndpoints(SAMPLE_DETAIL, SAMPLE_HISTORY);
    renderAgentDetail("/leaderboard/anthropic__claude-opus-4-8");
    await waitFor(() => {
      expect(screen.getByText("Elo Rating History")).toBeInTheDocument();
    });
    expect(screen.getByText("2025-01-01")).toBeInTheDocument();
    expect(screen.getByText("2025-03-01")).toBeInTheDocument();
  });

  it("shows empty state for history when there is none", async () => {
    mockAgentEndpoints(SAMPLE_DETAIL, EMPTY_HISTORY);
    renderAgentDetail("/leaderboard/anthropic__claude-opus-4-8");
    await waitFor(() => {
      expect(screen.getByText(/No rating history available yet/)).toBeInTheDocument();
    });
  });

  it("shows not-found state when the agent doesn't exist", async () => {
    mockAgentEndpoints(
      { agent_id: "ghost", overall: null, per_game: {} },
      EMPTY_HISTORY,
    );
    renderAgentDetail("/leaderboard/ghost");
    await waitFor(() => {
      expect(screen.getByText(/No data found for this agent/)).toBeInTheDocument();
    });
  });

  it("renders back link to leaderboard", async () => {
    mockAgentEndpoints(SAMPLE_DETAIL, SAMPLE_HISTORY);
    renderAgentDetail("/leaderboard/anthropic__claude-opus-4-8");
    await waitFor(() => {
      expect(screen.getAllByText(/Back to Leaderboard/i).length).toBeGreaterThan(0);
    });
  });

  it("shows error state on API failure", async () => {
    server.use(
      http.get("/api/leaderboard/agents/:agentId", () =>
        new HttpResponse("Server error", { status: 500 }),
      ),
      http.get("/api/leaderboard/agents/:agentId/history", () =>
        new HttpResponse("Server error", { status: 500 }),
      ),
    );
    renderAgentDetail("/leaderboard/x");
    // The request() helper throws an "Invalid JSON response" error when the
    // body isn't valid JSON, which the page then displays in its error state.
    await waitFor(() => {
      expect(screen.getByText(/Invalid JSON response/i)).toBeInTheDocument();
    });
  });
});
