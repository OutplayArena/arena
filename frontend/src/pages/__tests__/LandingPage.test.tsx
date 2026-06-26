import { describe, it, expect, beforeEach } from "vitest";
import { screen, waitFor } from "@testing-library/react";
import { userEvent } from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { server } from "../../mocks/server";
import { renderWithProviders } from "../../test-utils";
import { LandingPage } from "../LandingPage";
import type { BenchmarkReport, BenchmarkGamesResponse } from "../../types";

const SAMPLE_REPORT: BenchmarkReport = {
  agents: {
    "anthropic__claude-opus-4-8": {
      elo: 1500,
      alpha_rank: 0.4,
      matches_played: 50,
      metrics: { nash_gap: 0.05, cooperation_rate: 0.6 },
    },
    "openai__gpt-4o": {
      elo: 1400,
      alpha_rank: 0.3,
      matches_played: 30,
      metrics: { nash_gap: 0.1, cooperation_rate: 0.5 },
    },
  },
  ranking: ["anthropic__claude-opus-4-8", "openai__gpt-4o"],
  population: {},
  total_matches: 80,
};

const GAMES_RESPONSE: BenchmarkGamesResponse = {
  games: ["colonelblotto", "ultimatum"],
};

function mockBenchmark(report: BenchmarkReport | string, status = 200) {
  server.use(
    http.get("/api/benchmark/report", () => {
      if (typeof report === "string") {
        return new HttpResponse(report, { status });
      }
      return HttpResponse.json(report);
    }),
    http.get("/api/benchmark/games", () => HttpResponse.json(GAMES_RESPONSE)),
  );
}

describe("LandingPage leaderboard", () => {
  beforeEach(() => {
    server.resetHandlers();
  });

  it("renders the hero and leaderboard sections", async () => {
    mockBenchmark(SAMPLE_REPORT);
    renderWithProviders(<LandingPage />, { initialRoute: "/" });
    expect(screen.getByRole("heading", { name: /OutplayArena/i })).toBeInTheDocument();
    await waitFor(() => {
      expect(screen.getByText("claude-opus-4-8")).toBeInTheDocument();
    });
  });

  it("renders leaderboard rows from the report", async () => {
    mockBenchmark(SAMPLE_REPORT);
    renderWithProviders(<LandingPage />, { initialRoute: "/" });
    await waitFor(() => {
      expect(screen.getByText("claude-opus-4-8")).toBeInTheDocument();
    });
    expect(screen.getByText("gpt-4o")).toBeInTheDocument();
  });

  it("limits home page leaderboard to top 10 and shows link to full page", async () => {
    const manyAgents: BenchmarkReport = {
      agents: Object.fromEntries(
        Array.from({ length: 15 }, (_, i) => [
          `provider__agent-${i}`,
          {
            elo: 1500 - i * 5,
            alpha_rank: 0.4 - i * 0.01,
            matches_played: 100 - i,
            metrics: {},
          },
        ]),
      ),
      ranking: Array.from({ length: 15 }, (_, i) => `provider__agent-${i}`),
      population: {},
      total_matches: 1000,
    };
    mockBenchmark(manyAgents);
    renderWithProviders(<LandingPage />, { initialRoute: "/" });
    await waitFor(() => {
      expect(screen.getByText("agent-0")).toBeInTheDocument();
    });
    // agent-10 should NOT be on the home page (only top 10).
    expect(screen.queryByText("agent-10")).not.toBeInTheDocument();
    // "See full leaderboard" link should be visible.
    expect(screen.getByText(/See full leaderboard/i)).toBeInTheDocument();
  });

  it("does not show 'See full leaderboard' link when fewer than 10 agents", async () => {
    mockBenchmark(SAMPLE_REPORT);
    renderWithProviders(<LandingPage />, { initialRoute: "/" });
    await waitFor(() => {
      expect(screen.getByText("claude-opus-4-8")).toBeInTheDocument();
    });
    expect(screen.queryByText(/See full leaderboard/i)).not.toBeInTheDocument();
  });

  it("shows loading skeleton while fetching", async () => {
    server.use(
      http.get("/api/benchmark/report", async () => {
        await new Promise((r) => setTimeout(r, 100));
        return HttpResponse.json(SAMPLE_REPORT);
      }),
      http.get("/api/benchmark/games", () => HttpResponse.json(GAMES_RESPONSE)),
    );
    renderWithProviders(<LandingPage />, { initialRoute: "/" });
    // While loading, the shimmer animation is present.
    expect(document.querySelectorAll(".animate-shimmer").length).toBeGreaterThan(0);
  });

  it("shows error state when the report fetch fails", async () => {
    server.use(
      http.get("/api/benchmark/report", () =>
        new HttpResponse("Internal Server Error", { status: 500 }),
      ),
      http.get("/api/benchmark/games", () => HttpResponse.json(GAMES_RESPONSE)),
    );
    renderWithProviders(<LandingPage />, { initialRoute: "/" });
    await waitFor(() => {
      expect(screen.getByText(/Failed to load leaderboard/)).toBeInTheDocument();
    });
  });

  it("shows empty state when there are no agents", async () => {
    mockBenchmark({
      agents: {},
      ranking: [],
      population: {},
      total_matches: 0,
    });
    renderWithProviders(<LandingPage />, { initialRoute: "/" });
    await waitFor(() => {
      expect(screen.getByText(/No data yet/)).toBeInTheDocument();
    });
  });

  it("renders game filter dropdown when games are available", async () => {
    mockBenchmark(SAMPLE_REPORT);
    renderWithProviders(<LandingPage />, { initialRoute: "/" });
    await waitFor(() => {
      expect(screen.getByText("claude-opus-4-8")).toBeInTheDocument();
    });
    const select = document.querySelector("select");
    expect(select).toBeInTheDocument();
    // "All games (overall)" is the default option.
    const options = Array.from(select!.querySelectorAll("option"));
    expect(options[0]?.textContent).toBe("All games (overall)");
    // Every game from the API appears in the dropdown with its human-readable
    // name (from /api/games) once that endpoint has resolved.
    const optionTexts = options.map((o) => o.textContent);
    expect(optionTexts).toContain("Colonel Blotto");
    expect(optionTexts).toContain("Ultimatum Game");
  });

  it("switches the report when a different game is selected", async () => {
    let requestedGame: string | undefined;
    server.use(
      http.get("/api/benchmark/report", ({ request }) => {
        const url = new URL(request.url);
        requestedGame = url.searchParams.get("game") || undefined;
        return HttpResponse.json(SAMPLE_REPORT);
      }),
      http.get("/api/benchmark/games", () => HttpResponse.json(GAMES_RESPONSE)),
    );
    const user = userEvent.setup();
    renderWithProviders(<LandingPage />, { initialRoute: "/" });
    await waitFor(() => {
      expect(screen.getByText("claude-opus-4-8")).toBeInTheDocument();
    });
    // Pick a specific game in the dropdown by its (human-readable) label.
    const select = document.querySelector("select") as HTMLSelectElement;
    await user.selectOptions(select, "ultimatum");
    await waitFor(() => {
      expect(requestedGame).toBe("ultimatum");
    });
  });

  it("displays total matches count from the report", async () => {
    mockBenchmark(SAMPLE_REPORT);
    renderWithProviders(<LandingPage />, { initialRoute: "/" });
    await waitFor(() => {
      expect(screen.getByText(/80 matches recorded/)).toBeInTheDocument();
    });
  });

  it("formats cooperation rate as percentage", async () => {
    mockBenchmark(SAMPLE_REPORT);
    renderWithProviders(<LandingPage />, { initialRoute: "/" });
    await waitFor(() => {
      expect(screen.getByText("claude-opus-4-8")).toBeInTheDocument();
    });
    // cooperation_rate for anthropic__claude-opus-4-8 is 0.6 → "60%".
    expect(screen.getByText("60%")).toBeInTheDocument();
  });

  it("uses a combined Agent column (model + provider) — same as the full leaderboard", async () => {
    mockBenchmark(SAMPLE_REPORT);
    renderWithProviders(<LandingPage />, { initialRoute: "/" });
    await waitFor(() => {
      expect(screen.getByText("claude-opus-4-8")).toBeInTheDocument();
    });
    // The "Agent" column header is present (not separate "Model" / "Provider").
    expect(screen.getByRole("columnheader", { name: "Agent" })).toBeInTheDocument();
    expect(screen.queryByRole("columnheader", { name: "Model" })).not.toBeInTheDocument();
    expect(screen.queryByRole("columnheader", { name: "Provider" })).not.toBeInTheDocument();
  });

  it("renders agent names as clickable buttons that navigate to the detail page", async () => {
    mockBenchmark(SAMPLE_REPORT);
    renderWithProviders(<LandingPage />, { initialRoute: "/" });
    await waitFor(() => {
      expect(screen.getByText("claude-opus-4-8")).toBeInTheDocument();
    });
    const link = screen.getByRole("button", { name: /claude-opus-4-8/i });
    expect(link.tagName).toBe("BUTTON");
  });

  it("exposes a From/To date range filter (same as the full leaderboard)", async () => {
    mockBenchmark(SAMPLE_REPORT);
    renderWithProviders(<LandingPage />, { initialRoute: "/" });
    await waitFor(() => {
      expect(screen.getByText("claude-opus-4-8")).toBeInTheDocument();
    });
    expect(screen.getByTestId("leaderboard-filter-from")).toBeInTheDocument();
    expect(screen.getByTestId("leaderboard-filter-to")).toBeInTheDocument();
  });
});
