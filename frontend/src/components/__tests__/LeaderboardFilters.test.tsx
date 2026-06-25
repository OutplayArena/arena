import { describe, it, expect, beforeEach, vi } from "vitest";
import { useState } from "react";
import { screen, waitFor } from "@testing-library/react";
import { userEvent } from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { server } from "../../mocks/server";
import { renderWithProviders } from "../../test-utils";
import { LeaderboardFilters, type LeaderboardFiltersValue } from "../LeaderboardFilters";

const GAMES_RESPONSE = { games: ["colonelblotto", "ultimatum", "battle_of_the_sexes"] };

function TestHarness({
  initial,
  align,
  gameOnly,
  onChangeSpy,
}: {
  initial?: Partial<LeaderboardFiltersValue>;
  align?: "left" | "center";
  gameOnly?: boolean;
  onChangeSpy: (next: LeaderboardFiltersValue) => void;
}) {
  const [value, setValue] = useState<LeaderboardFiltersValue>({
    game: initial?.game ?? "",
    dateFrom: initial?.dateFrom ?? "",
    dateTo: initial?.dateTo ?? "",
  });
  return (
    <LeaderboardFilters
      value={value}
      onChange={(next) => {
        setValue(next);
        onChangeSpy(next);
      }}
      onClear={() => {
        const cleared = { game: "", dateFrom: "", dateTo: "" };
        setValue(cleared);
        onChangeSpy(cleared);
      }}
      align={align}
      gameOnly={gameOnly}
    />
  );
}

describe("LeaderboardFilters", () => {
  beforeEach(() => {
    server.resetHandlers();
  });

  it("renders the game filter, date range, and clear button (when a filter is active)", async () => {
    server.use(
      http.get("/api/games", () =>
        HttpResponse.json([
          { slug: "colonelblotto", name: "Colonel Blotto" },
          { slug: "ultimatum", name: "Ultimatum Game" },
        ]),
      ),
      http.get("/api/benchmark/games", () => HttpResponse.json(GAMES_RESPONSE)),
    );
    const onChange = vi.fn();
    renderWithProviders(
      <TestHarness initial={{ game: "ultimatum" }} onChangeSpy={onChange} />,
    );
    await waitFor(() => {
      expect(screen.getByText("Colonel Blotto")).toBeInTheDocument();
    });
    expect(screen.getByRole("combobox")).toBeInTheDocument();
    expect(screen.getByTestId("leaderboard-filter-from")).toBeInTheDocument();
    expect(screen.getByTestId("leaderboard-filter-to")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /clear filters/i })).toBeInTheDocument();
  });

  it("hides the clear button when no filter is set", async () => {
    server.use(
      http.get("/api/games", () => HttpResponse.json([{ slug: "ultimatum", name: "Ultimatum Game" }])),
      http.get("/api/benchmark/games", () => HttpResponse.json(GAMES_RESPONSE)),
    );
    renderWithProviders(<TestHarness onChangeSpy={vi.fn()} />);
    await waitFor(() => {
      expect(screen.getByRole("combobox")).toBeInTheDocument();
    });
    expect(screen.queryByRole("button", { name: /clear filters/i })).not.toBeInTheDocument();
  });

  it("hides the date range when gameOnly is set", async () => {
    server.use(
      http.get("/api/games", () => HttpResponse.json([{ slug: "ultimatum", name: "Ultimatum Game" }])),
      http.get("/api/benchmark/games", () => HttpResponse.json(GAMES_RESPONSE)),
    );
    renderWithProviders(<TestHarness gameOnly onChangeSpy={vi.fn()} />);
    await waitFor(() => {
      expect(screen.getByRole("combobox")).toBeInTheDocument();
    });
    expect(screen.queryByTestId("leaderboard-filter-from")).not.toBeInTheDocument();
    expect(screen.queryByTestId("leaderboard-filter-to")).not.toBeInTheDocument();
  });

  it("emits the slug (not the label) when a game is selected", async () => {
    server.use(
      http.get("/api/games", () =>
        HttpResponse.json([
          { slug: "colonelblotto", name: "Colonel Blotto" },
          { slug: "ultimatum", name: "Ultimatum Game" },
        ]),
      ),
      http.get("/api/benchmark/games", () => HttpResponse.json(GAMES_RESPONSE)),
    );
    const onChange = vi.fn();
    const user = userEvent.setup();
    renderWithProviders(<TestHarness onChangeSpy={onChange} />);
    await waitFor(() => {
      expect(screen.getByText("Colonel Blotto")).toBeInTheDocument();
    });
    const select = screen.getByRole("combobox");
    await user.selectOptions(select, "ultimatum");
    await waitFor(() => {
      const last = onChange.mock.calls[onChange.mock.calls.length - 1]?.[0];
      expect(last?.game).toBe("ultimatum");
    });
  });

  it("prettifies slugs from /api/benchmark/games when /api/games fails", async () => {
    server.use(
      http.get("/api/games", () => new HttpResponse("boom", { status: 500 })),
      http.get("/api/benchmark/games", () => HttpResponse.json(GAMES_RESPONSE)),
    );
    renderWithProviders(<TestHarness onChangeSpy={vi.fn()} />);
    await waitFor(() => {
      const options = Array.from(document.querySelectorAll("option")).map((o) => o.textContent);
      // "colonelblotto" → "Colonelblotto"
      expect(options).toContain("Colonelblotto");
      // "battle_of_the_sexes" → "Battle Of The Sexes"
      expect(options).toContain("Battle Of The Sexes");
    });
  });

  it("applies the center alignment when align='center'", async () => {
    server.use(
      http.get("/api/games", () => HttpResponse.json([{ slug: "ultimatum", name: "Ultimatum Game" }])),
      http.get("/api/benchmark/games", () => HttpResponse.json(GAMES_RESPONSE)),
    );
    renderWithProviders(<TestHarness align="center" onChangeSpy={vi.fn()} />);
    await waitFor(() => {
      expect(screen.getByRole("combobox")).toBeInTheDocument();
    });
    const wrapper = screen.getByTestId("leaderboard-filters");
    expect(wrapper.className).toContain("justify-center");
  });
});
