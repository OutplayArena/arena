import { describe, it, expect, vi } from "vitest";
import { screen } from "@testing-library/react";
import { userEvent } from "@testing-library/user-event";
import { AutoHistoryView } from "../AutoHistoryView";
import { renderWithProviders } from "../../test-utils";
import { useApp } from "../../hooks/useApp";
import { createMockMatch } from "../../test-fixtures";
import type { Match } from "../../types";

vi.mock("../../hooks/useApp", () => ({
  useApp: vi.fn(),
}));

function renderHistory(match: Match | null, props: Partial<{ hasMatch: boolean; canvasCollapsed: boolean }> = {}) {
  const hasMatch = props.hasMatch ?? (match !== null);
  return renderWithProviders(
    <AutoHistoryView
      hasMatch={hasMatch}
      canvasCollapsed={props.canvasCollapsed ?? false}
      onExpandCanvas={vi.fn()}
    />,
  );
}

describe("AutoHistoryView — with match data", () => {
  it("renders table headers with agent names", () => {
    const match = createMockMatch();
    (useApp as ReturnType<typeof vi.fn>).mockReturnValue({
      state: { activeMatch: match },
    });
    renderHistory(match);
    expect(screen.getByText("bold-bear")).toBeInTheDocument();
    expect(screen.getByText("swift-fox")).toBeInTheDocument();
  });

  it("shows round winner highlights", () => {
    const match = createMockMatch();
    (useApp as ReturnType<typeof vi.fn>).mockReturnValue({
      state: { activeMatch: match },
    });
    renderHistory(match);
    expect(screen.getAllByText("A:2 B:1")).toHaveLength(2);
  });

  it("displays metrics when present", () => {
    const match = createMockMatch({
      metrics: { nash_gap: 0.05, fairness: 0.9 },
    });
    (useApp as ReturnType<typeof vi.fn>).mockReturnValue({
      state: { activeMatch: match },
    });
    renderHistory(match);
    expect(screen.getByText("Metrics")).toBeInTheDocument();
  });

  it("renders rich metrics panel", () => {
    const match = createMockMatch({
      rich_metrics: {
        match_id: "m1",
        game_type: "colonelblotto",
        num_agents: 2,
        agents: {
          A: {
            total_payoff: 10,
            avg_payoff: 2,
            strategy_entropy: 1.5,
            behavioral_consistency: 0.8,
            cumulative_regret: 0.3,
            adaptive_regret_series: [0.1, 0.2],
            nash_gap: 0.05,
          },
          B: {
            total_payoff: 5,
            avg_payoff: 1,
            strategy_entropy: 1.2,
            behavioral_consistency: 0.7,
            cumulative_regret: 0.5,
            adaptive_regret_series: [0.15, 0.25],
            nash_gap: 0.08,
          },
        },
        joint: { cooperation_rate: 0.6 },
        pairwise: {},
      },
    });
    (useApp as ReturnType<typeof vi.fn>).mockReturnValue({
      state: { activeMatch: match },
    });
    renderHistory(match);
    expect(screen.getByText("Rich Metrics")).toBeInTheDocument();
    expect(screen.getByText("Joint")).toBeInTheDocument();
    expect(screen.getByText("Agent A")).toBeInTheDocument();
  });

  it("shows single round text", () => {
    const match = createMockMatch({
      history: [{ round: 1, agent_a: "a", agent_b: "b", action_a: [10], action_b: [5], score_a: 1, score_b: 0, total_score_a: 1, total_score_b: 0, winner: "A" as const }],
      num_rounds: 1,
    });
    (useApp as ReturnType<typeof vi.fn>).mockReturnValue({
      state: { activeMatch: match },
    });
    renderHistory(match);
    expect(screen.getByText("Complete — 1 round")).toBeInTheDocument();
  });

  it("shows win/loss text in final score", () => {
    const match = createMockMatch({ match_winner: "A", total_score_a: 5, total_score_b: 4 });
    (useApp as ReturnType<typeof vi.fn>).mockReturnValue({
      state: { activeMatch: match },
    });
    renderHistory(match);
    expect(screen.getByText(/Player A wins/)).toBeInTheDocument();
  });

  it("shows B wins in final score", () => {
    const match = createMockMatch({ match_winner: "B" });
    (useApp as ReturnType<typeof vi.fn>).mockReturnValue({
      state: { activeMatch: match },
    });
    renderHistory(match);
    expect(screen.getByText(/Player B wins/)).toBeInTheDocument();
  });

  it("calls onExpandCanvas when Show Live View clicked", async () => {
    const user = userEvent.setup();
    const match = createMockMatch();
    const onExpandCanvas = vi.fn();
    (useApp as ReturnType<typeof vi.fn>).mockReturnValue({
      state: { activeMatch: match },
    });
    renderWithProviders(
      <AutoHistoryView hasMatch={true} canvasCollapsed={true} onExpandCanvas={onExpandCanvas} />,
    );
    await user.click(screen.getByText("Show Live View"));
    expect(onExpandCanvas).toHaveBeenCalled();
  });

  it("shows B winner highlights and Tie display", () => {
    const match = createMockMatch({
      history: [
        { round: 1, agent_a: "a", agent_b: "b", action_a: [1], action_b: [2], score_a: 0, score_b: 1, total_score_a: 0, total_score_b: 1, winner: "B" as const },
        { round: 2, agent_a: "a", agent_b: "b", action_a: [2], action_b: [1], score_a: 1, score_b: 0, total_score_a: 1, total_score_b: 1, winner: "A" as const },
        { round: 3, agent_a: "a", agent_b: "b", action_a: [1], action_b: [1], score_a: 0, score_b: 0, total_score_a: 1, total_score_b: 1, winner: "Tie" as const },
      ],
      match_winner: "Tie",
      total_score_a: 1,
      total_score_b: 1,
    });
    (useApp as ReturnType<typeof vi.fn>).mockReturnValue({
      state: { activeMatch: match },
    });
    renderHistory(match);
    expect(screen.getByText("D")).toBeInTheDocument();
  });
});
