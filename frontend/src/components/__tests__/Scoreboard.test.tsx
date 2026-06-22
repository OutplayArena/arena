import { describe, it, expect, vi } from "vitest";
import { screen } from "@testing-library/react";
import { Scoreboard } from "../Scoreboard";
import { renderWithProviders } from "../../test-utils";
import { useApp } from "../../hooks/useApp";

vi.mock("../../hooks/useApp", () => ({
  useApp: vi.fn(),
}));

const mockScores = { displayedScoreA: 10.5, displayedScoreB: 5.2 };

describe("Scoreboard", () => {
  it("shows total_score_a and total_score_b", () => {
    (useApp as ReturnType<typeof vi.fn>).mockReturnValue({
      state: {
        activeMatch: {
          history: [],
          num_rounds: 10,
          agent_a: "A",
          agent_b: "B",
          session_id: "s",
          config_hash: "h",
          num_battlefields: 5,
          total_resources: 100,
          total_score_a: 0,
          total_score_b: 0,
          metrics: {},
        },
        activeRoundIndex: 0,
      },
    });
    renderWithProviders(<Scoreboard scores={mockScores} />);
    expect(screen.getByText("Agent A")).toBeInTheDocument();
    expect(screen.getByText("Agent B")).toBeInTheDocument();
    expect(screen.getByText("Round")).toBeInTheDocument();
  });

  it("shows round progress", () => {
    (useApp as ReturnType<typeof vi.fn>).mockReturnValue({
      state: {
        activeMatch: {
          history: [{}, {}, {}],
          num_rounds: 10,
          agent_a: "A",
          agent_b: "B",
          session_id: "s",
          config_hash: "h",
          num_battlefields: 5,
          total_resources: 100,
          total_score_a: 0,
          total_score_b: 0,
          metrics: {},
        },
        activeRoundIndex: 2,
      },
    });
    renderWithProviders(<Scoreboard scores={mockScores} />);
    expect(screen.getByText("3 / 10")).toBeInTheDocument();
  });

  it("shows 0 / 0 when no activeMatch", () => {
    (useApp as ReturnType<typeof vi.fn>).mockReturnValue({
      state: { activeMatch: null, activeRoundIndex: -1 },
    });
    renderWithProviders(<Scoreboard scores={mockScores} />);
    expect(screen.getByText("—")).toBeInTheDocument();
  });
});
