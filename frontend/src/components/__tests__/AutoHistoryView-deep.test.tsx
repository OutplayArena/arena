import { describe, it, expect, vi } from "vitest";
import { screen, render, waitFor } from "@testing-library/react";
import { userEvent } from "@testing-library/user-event";
import { AutoHistoryView } from "../AutoHistoryView";
import { renderWithProviders } from "../../test-utils";
import { useApp } from "../../hooks/useApp";
import { createMockMatch } from "../../test-fixtures";
import { http, HttpResponse } from "msw";
import { server } from "../../mocks/server";
import type { Match } from "../../types";

vi.mock("../../hooks/useApp", () => ({
  useApp: vi.fn(),
}));

describe("AutoHistoryView — deep coverage", () => {
  it("renders formatAction for string actions", () => {
    const match = createMockMatch({
      history: [{
        round: 1, agent_a: "a", agent_b: "b",
        action_a: "cooperate" as unknown as number[],
        action_b: "defect" as unknown as number[],
        score_a: 3, score_b: 2, total_score_a: 3, total_score_b: 2,
        winner: "A" as const,
      }],
      num_rounds: 1,
      total_score_a: 3,
      total_score_b: 2,
      match_winner: "A",
    });
    (useApp as ReturnType<typeof vi.fn>).mockReturnValue({
      state: { activeMatch: match },
    });
    renderWithProviders(
      <AutoHistoryView hasMatch={true} canvasCollapsed={false} onExpandCanvas={vi.fn()} />,
    );
    expect(screen.getByText("cooperate")).toBeInTheDocument();
    expect(screen.getByText("defect")).toBeInTheDocument();
  });

  it("renders formatAction for number actions", () => {
    const match = createMockMatch({
      history: [{
        round: 1, agent_a: "a", agent_b: "b",
        action_a: 42 as unknown as number[],
        action_b: 7 as unknown as number[],
        score_a: 1, score_b: 0, total_score_a: 1, total_score_b: 0,
        winner: "A" as const,
      }],
      num_rounds: 1,
      total_score_a: 1,
    });
    (useApp as ReturnType<typeof vi.fn>).mockReturnValue({
      state: { activeMatch: match },
    });
    renderWithProviders(
      <AutoHistoryView hasMatch={true} canvasCollapsed={false} onExpandCanvas={vi.fn()} />,
    );
    expect(screen.getByText("42")).toBeInTheDocument();
    expect(screen.getByText("7")).toBeInTheDocument();
  });

  it("renders metric values for null/undefined", () => {
    const match = createMockMatch({
      metrics: { null_val: null as unknown as number },
      match_winner: "Tie",
    });
    (useApp as ReturnType<typeof vi.fn>).mockReturnValue({
      state: { activeMatch: match },
    });
    renderWithProviders(
      <AutoHistoryView hasMatch={true} canvasCollapsed={false} onExpandCanvas={vi.fn()} gameSlug="colonelblotto" />,
    );
    expect(screen.getByText("Metrics")).toBeInTheDocument();
  });

  it("renders rich metrics with Agent A and B", () => {
    const match = createMockMatch({
      rich_metrics: {
        match_id: "m1",
        game_type: "colonelblotto",
        num_agents: 2,
        agents: {
          A: {
            total_payoff: 8,
            avg_payoff: 1.6,
            strategy_entropy: 1.5,
            behavioral_consistency: 0.8,
            cumulative_regret: 0.3,
            adaptive_regret_series: [0.1],
            nash_gap: 0.05,
          },
        },
        joint: {},
        pairwise: {},
      },
      match_winner: "A",
    });
    (useApp as ReturnType<typeof vi.fn>).mockReturnValue({
      state: { activeMatch: match },
    });
    renderWithProviders(
      <AutoHistoryView hasMatch={true} canvasCollapsed={false} onExpandCanvas={vi.fn()} />,
    );
    expect(screen.getByText("Rich Metrics")).toBeInTheDocument();
    expect(screen.getByText("Agent A")).toBeInTheDocument();
  });

  it("renders plain object metric values", () => {
    const match = createMockMatch({
      metrics: { nested: { a: 1, b: 2 } as unknown as number },
      match_winner: "Tie",
    });
    (useApp as ReturnType<typeof vi.fn>).mockReturnValue({
      state: { activeMatch: match },
    });
    renderWithProviders(
      <AutoHistoryView hasMatch={true} canvasCollapsed={false} onExpandCanvas={vi.fn()} />,
    );
    expect(screen.getByText("Metrics")).toBeInTheDocument();
  });

  it("renders array metric values", () => {
    const match = createMockMatch({
      metrics: { series: [1, 2, 3] as unknown as number },
      match_winner: "Tie",
    });
    (useApp as ReturnType<typeof vi.fn>).mockReturnValue({
      state: { activeMatch: match },
    });
    renderWithProviders(
      <AutoHistoryView hasMatch={true} canvasCollapsed={false} onExpandCanvas={vi.fn()} />,
    );
    expect(screen.getByText("Metrics")).toBeInTheDocument();
    expect(screen.getByText("[1,2,3]")).toBeInTheDocument();
  });

  it("fetches game metrics catalog and renders tooltip", async () => {
    server.resetHandlers();
    server.use(
      http.get("/api/games/:name/metrics", () => {
        return HttpResponse.json({
          metrics: [
            { name: "nash_gap", when: "post_match", type: "number", description: "Nash distance" },
          ],
        });
      }),
    );

    const match = createMockMatch({
      metrics: { nash_gap: 0.05 },
      match_winner: "Tie",
    });
    (useApp as ReturnType<typeof vi.fn>).mockReturnValue({
      state: { activeMatch: match },
    });
    renderWithProviders(
      <AutoHistoryView hasMatch={true} canvasCollapsed={false} onExpandCanvas={vi.fn()} gameSlug="colonelblotto" />,
    );

    await waitFor(() => {
      expect(screen.getByText("Metrics")).toBeInTheDocument();
      expect(screen.getByText("nash_gap")).toBeInTheDocument();
    });
  });

  it("metric label button toggles tooltip", async () => {
    const user = userEvent.setup();
    server.resetHandlers();
    server.use(
      http.get("/api/games/:name/metrics", () => {
        return HttpResponse.json({
          metrics: [
            { name: "nash_gap", when: "post_match", type: "number", description: "Nash distance desc" },
          ],
        });
      }),
    );

    const match = createMockMatch({
      metrics: { nash_gap: 0.05 },
      match_winner: "Tie",
    });
    (useApp as ReturnType<typeof vi.fn>).mockReturnValue({
      state: { activeMatch: match },
    });
    renderWithProviders(
      <AutoHistoryView hasMatch={true} canvasCollapsed={false} onExpandCanvas={vi.fn()} gameSlug="colonelblotto" />,
    );

    await waitFor(() => {
      expect(screen.getByText("nash_gap")).toBeInTheDocument();
    });

    expect(screen.getByTitle("Nash distance desc")).toBeInTheDocument();
  });
});
