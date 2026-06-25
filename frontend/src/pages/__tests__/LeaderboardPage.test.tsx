import { describe, it, expect, beforeEach } from "vitest";
import { screen, waitFor } from "@testing-library/react";
import { userEvent } from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { server } from "../../mocks/server";
import { renderWithProviders } from "../../test-utils";
import { LeaderboardPage } from "../LeaderboardPage";
import type { LeaderboardResponse, BenchmarkGamesResponse } from "../../types";

const SAMPLE_RESPONSE: LeaderboardResponse = {
  agents: [
    {
      agent_id: "anthropic__claude-opus-4-8",
      elo: 1500,
      alpha_rank: 0.4,
      matches_played: 50,
      metrics: { nash_gap: 0.05, cooperation_rate: 0.6 },
    },
    {
      agent_id: "openai__gpt-4o",
      elo: 1400,
      alpha_rank: 0.3,
      matches_played: 30,
      metrics: { nash_gap: 0.1, cooperation_rate: 0.5 },
    },
  ],
  total: 2,
  page: 1,
  page_size: 50,
  total_matches: 80,
};

const EMPTY_RESPONSE: LeaderboardResponse = {
  agents: [],
  total: 0,
  page: 1,
  page_size: 50,
  total_matches: 0,
};

const GAMES_RESPONSE: BenchmarkGamesResponse = {
  games: ["colonelblotto", "ultimatum"],
};

function mockLeaderboardEndpoint(response: LeaderboardResponse | string, status = 200) {
  server.use(
    http.get("/api/leaderboard", () => {
      if (typeof response === "string") {
        return new HttpResponse(response, { status });
      }
      return HttpResponse.json(response);
    }),
    http.get("/api/benchmark/games", () => HttpResponse.json(GAMES_RESPONSE)),
  );
}

describe("LeaderboardPage", () => {
  beforeEach(() => {
    server.resetHandlers();
  });

  it("renders the page heading", async () => {
    mockLeaderboardEndpoint(SAMPLE_RESPONSE);
    renderWithProviders(<LeaderboardPage />, { initialRoute: "/leaderboard" });
    expect(screen.getByRole("heading", { name: /leaderboard/i })).toBeInTheDocument();
  });

  it("shows loading skeleton before data arrives", async () => {
    server.use(
      http.get("/api/leaderboard", async () => {
        await new Promise((r) => setTimeout(r, 100));
        return HttpResponse.json(SAMPLE_RESPONSE);
      }),
      http.get("/api/benchmark/games", () => HttpResponse.json(GAMES_RESPONSE)),
    );
    renderWithProviders(<LeaderboardPage />, { initialRoute: "/leaderboard" });
    // While loading, the column headers are rendered as part of the skeleton.
    expect(screen.getByText("Agent")).toBeInTheDocument();
    // Wait for the data to arrive.
    await waitFor(() => {
      expect(screen.getByText("claude-opus-4-8")).toBeInTheDocument();
    });
  });

  it("renders agent rows when data is loaded", async () => {
    mockLeaderboardEndpoint(SAMPLE_RESPONSE);
    renderWithProviders(<LeaderboardPage />, { initialRoute: "/leaderboard" });
    await waitFor(() => {
      expect(screen.getByText("claude-opus-4-8")).toBeInTheDocument();
    });
    expect(screen.getByText("gpt-4o")).toBeInTheDocument();
  });

  it("displays total matches count", async () => {
    mockLeaderboardEndpoint(SAMPLE_RESPONSE);
    renderWithProviders(<LeaderboardPage />, { initialRoute: "/leaderboard" });
    await waitFor(() => {
      expect(screen.getByText(/80 matches recorded/)).toBeInTheDocument();
    });
  });

  it("shows empty state when no data", async () => {
    mockLeaderboardEndpoint(EMPTY_RESPONSE);
    renderWithProviders(<LeaderboardPage />, { initialRoute: "/leaderboard" });
    await waitFor(() => {
      expect(screen.getByText(/No data yet/)).toBeInTheDocument();
    });
  });

  it("shows error state with retry button on failure", async () => {
    server.use(
      http.get("/api/leaderboard", () => new HttpResponse("Internal Server Error", { status: 500 })),
      http.get("/api/benchmark/games", () => HttpResponse.json(GAMES_RESPONSE)),
    );
    renderWithProviders(<LeaderboardPage />, { initialRoute: "/leaderboard" });
    await waitFor(() => {
      expect(screen.getByText(/Failed to load leaderboard/)).toBeInTheDocument();
    });
    expect(screen.getByRole("button", { name: /retry/i })).toBeInTheDocument();
  });

  it("retries loading when the retry button is clicked", async () => {
    let callCount = 0;
    server.use(
      http.get("/api/leaderboard", () => {
        callCount += 1;
        if (callCount === 1) {
          return new HttpResponse("Internal Server Error", { status: 500 });
        }
        return HttpResponse.json(SAMPLE_RESPONSE);
      }),
      http.get("/api/benchmark/games", () => HttpResponse.json(GAMES_RESPONSE)),
    );
    const user = userEvent.setup();
    renderWithProviders(<LeaderboardPage />, { initialRoute: "/leaderboard" });
    await waitFor(() => {
      expect(screen.getByText(/Failed to load leaderboard/)).toBeInTheDocument();
    });
    await user.click(screen.getByRole("button", { name: /retry/i }));
    await waitFor(() => {
      expect(screen.getByText("claude-opus-4-8")).toBeInTheDocument();
    });
    expect(callCount).toBeGreaterThanOrEqual(2);
  });

  it("renders the game filter dropdown", async () => {
    mockLeaderboardEndpoint(SAMPLE_RESPONSE);
    renderWithProviders(<LeaderboardPage />, { initialRoute: "/leaderboard" });
    await waitFor(() => {
      expect(screen.getByText("claude-opus-4-8")).toBeInTheDocument();
    });
    // Use container query for <select> since the label is not htmlFor-linked.
    const select = document.querySelector("select");
    expect(select).toBeInTheDocument();
  });

  it("shows human-readable game names in the dropdown (not slugs)", async () => {
    // Use a wider set of games so we can verify the lookup across multiple.
    server.use(
      http.get("/api/leaderboard", () => HttpResponse.json(SAMPLE_RESPONSE)),
      http.get("/api/benchmark/games", () =>
        HttpResponse.json<BenchmarkGamesResponse>({
          games: ["colonelblotto", "ultimatum", "battle_of_the_sexes"],
        }),
      ),
    );
    renderWithProviders(<LeaderboardPage />, { initialRoute: "/leaderboard" });
    await waitFor(() => {
      expect(screen.getByText("claude-opus-4-8")).toBeInTheDocument();
    });
    // Wait for /api/games to populate the cache.
    await waitFor(() => {
      const select = document.querySelector("select") as HTMLSelectElement;
      const optionTexts = Array.from(select.querySelectorAll("option")).map((o) => o.textContent);
      expect(optionTexts).toContain("Colonel Blotto");
    });
    const select = document.querySelector("select") as HTMLSelectElement;
    const optionTexts = Array.from(select.querySelectorAll("option")).map((o) => o.textContent);
    expect(optionTexts[0]).toBe("All games (overall)");
    // Human-readable labels (from /api/games) should appear, not slugs.
    expect(optionTexts).toContain("Colonel Blotto");
    expect(optionTexts).toContain("Ultimatum Game");
    expect(optionTexts).toContain("Battle of the Sexes");
    // Slugs should not appear as visible labels.
    expect(optionTexts).not.toContain("colonelblotto");
    expect(optionTexts).not.toContain("ultimatum");
  });

  it("submits the slug (not the label) when a game is selected", async () => {
    let lastUrl = "";
    server.use(
      http.get("/api/leaderboard", ({ request }) => {
        lastUrl = request.url;
        return HttpResponse.json(SAMPLE_RESPONSE);
      }),
      http.get("/api/benchmark/games", () => HttpResponse.json(GAMES_RESPONSE)),
    );
    const user = userEvent.setup();
    renderWithProviders(<LeaderboardPage />, { initialRoute: "/leaderboard" });
    await waitFor(() => {
      expect(screen.getByText("claude-opus-4-8")).toBeInTheDocument();
    });
    // Select the option by its (human-readable) label; the API call should
    // still be made with the slug.
    const select = document.querySelector("select") as HTMLSelectElement;
    await user.selectOptions(select, "Ultimatum Game");
    await waitFor(() => {
      expect(lastUrl).toContain("game=ultimatum");
      expect(lastUrl).not.toContain("Ultimatum%20Game");
    });
  });

  it("renders date filter inputs", async () => {
    mockLeaderboardEndpoint(SAMPLE_RESPONSE);
    renderWithProviders(<LeaderboardPage />, { initialRoute: "/leaderboard" });
    await waitFor(() => {
      expect(screen.getByText("claude-opus-4-8")).toBeInTheDocument();
    });
    // The page has two <input type="date"> elements (From, To).
    const dateInputs = document.querySelectorAll('input[type="date"]');
    expect(dateInputs.length).toBe(2);
  });

  it("renders agent names as clickable links (buttons)", async () => {
    mockLeaderboardEndpoint(SAMPLE_RESPONSE);
    renderWithProviders(<LeaderboardPage />, { initialRoute: "/leaderboard" });
    await waitFor(() => {
      expect(screen.getByText("claude-opus-4-8")).toBeInTheDocument();
    });
    // The model name should be inside a clickable element (button) that
    // triggers navigation to the agent detail page.
    const link = screen.getByRole("button", { name: /claude-opus-4-8/i });
    expect(link).toBeInTheDocument();
    expect(link.tagName).toBe("BUTTON");
  });

  it("toggles sort direction when clicking the same column", async () => {
    let lastUrl = "";
    server.use(
      http.get("/api/leaderboard", ({ request }) => {
        lastUrl = request.url;
        return HttpResponse.json(SAMPLE_RESPONSE);
      }),
      http.get("/api/benchmark/games", () => HttpResponse.json(GAMES_RESPONSE)),
    );
    const user = userEvent.setup();
    renderWithProviders(<LeaderboardPage />, { initialRoute: "/leaderboard?sort_by=elo" });
    await waitFor(() => {
      expect(screen.getByText("claude-opus-4-8")).toBeInTheDocument();
    });
    // Click on Elo header to toggle direction.
    const eloHeader = screen.getByRole("columnheader", { name: /elo/i });
    await user.click(eloHeader);
    await waitFor(() => {
      // The next API call should include sort_dir=asc (was desc).
      expect(lastUrl).toContain("sort_dir=asc");
    });
  });

  it("shows clear filters button when a filter is set", async () => {
    mockLeaderboardEndpoint(SAMPLE_RESPONSE);
    renderWithProviders(<LeaderboardPage />, { initialRoute: "/leaderboard?game=ultimatum" });
    await waitFor(() => {
      expect(screen.getByRole("button", { name: /clear filters/i })).toBeInTheDocument();
    });
  });

  it("clears filters when the clear button is clicked", async () => {
    let lastUrl = "";
    server.use(
      http.get("/api/leaderboard", ({ request }) => {
        lastUrl = request.url;
        return HttpResponse.json(SAMPLE_RESPONSE);
      }),
      http.get("/api/benchmark/games", () => HttpResponse.json(GAMES_RESPONSE)),
    );
    const user = userEvent.setup();
    renderWithProviders(<LeaderboardPage />, { initialRoute: "/leaderboard?game=ultimatum" });
    await waitFor(() => {
      expect(screen.getByRole("button", { name: /clear filters/i })).toBeInTheDocument();
    });
    await user.click(screen.getByRole("button", { name: /clear filters/i }));
    await waitFor(() => {
      // After clearing, the next API call should not include the game param.
      expect(lastUrl).not.toContain("game=");
    });
  });

  it("renders pagination controls when there are multiple pages", async () => {
    const manyAgents: LeaderboardResponse = {
      agents: Array.from({ length: 50 }, (_, i) => ({
        agent_id: `provider__agent-${i}`,
        elo: 1500 - i * 5,
        alpha_rank: 0.4 - i * 0.005,
        matches_played: 100 - i,
        metrics: {},
      })),
      total: 120,
      page: 1,
      page_size: 50,
      total_matches: 5000,
    };
    mockLeaderboardEndpoint(manyAgents);
    renderWithProviders(<LeaderboardPage />, { initialRoute: "/leaderboard" });
    await waitFor(() => {
      expect(screen.getByText(/Showing 1.*50.*of 120/)).toBeInTheDocument();
    });
  });
});
