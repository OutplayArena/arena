import { fireEvent, render, screen, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { ExternalRegretPanel } from "../ExternalRegretPanel";
import { AutoHistoryView } from "../AutoHistoryView";
import { createMockMatch } from "../../test-fixtures";
import { renderWithProviders } from "../../test-utils";
import { useApp } from "../../hooks/useApp";

vi.mock("../../hooks/useApp", () => ({ useApp: vi.fn() }));

const metric = {
  status: "available", cumulative: -3, average: -1, normalized_average: -0.5,
  actual_total_payoff: 3, best_fixed_total_payoff: 0, best_fixed_action: "rock", num_rounds: 3,
  series: [
    { round: 1, cumulative: 0, average: 0 },
    { round: 2, cumulative: -1, average: -0.5 },
    { round: 3, cumulative: -3, average: -1 },
  ],
};

const opponent = {
  ...metric, cumulative: 3, average: 1, normalized_average: 0.5, actual_total_payoff: -3,
  series: [
    { round: 1, cumulative: 2, average: 2 },
    { round: 2, cumulative: 3, average: 1.5 },
    { round: 3, cumulative: 3, average: 1 },
  ],
};

describe("External regret match results", () => {
  it("shows signed values and fixed comparator payoffs for each player", () => {
    render(<ExternalRegretPanel byPlayer={{ A: metric, B: opponent }} />);
    const a = within(screen.getByRole("article", { name: "Player A external regret" }));
    expect(a.getByText("-3")).toBeInTheDocument();
    expect(a.getByText("-0.5")).toBeInTheDocument();
    expect(a.getByText("rock")).toBeInTheDocument();
    expect(a.getByText("Actual payoff")).toBeInTheDocument();
    expect(screen.getByRole("img", { name: "Cumulative external regret by round" })).toBeInTheDocument();
    expect(screen.getByText("Player A: 0")).toBeInTheDocument();
    expect(screen.getByText("Player B: 2")).toBeInTheDocument();
  });

  it("switches curves and allows inspection of each prefix", () => {
    render(<ExternalRegretPanel byPlayer={{ A: metric, B: opponent }} />);
    fireEvent.click(screen.getByRole("button", { name: "Average" }));
    expect(screen.getByRole("button", { name: "Average" })).toHaveAttribute("aria-pressed", "true");
    expect(screen.getByRole("img", { name: "Average external regret by round" })).toBeInTheDocument();
    fireEvent.change(screen.getByRole("slider", { name: "Inspect regret round" }), { target: { value: "2" } });
    expect(screen.getByText("Player A: -0.5")).toBeInTheDocument();
    expect(screen.getByText("Player B: 1.5")).toBeInTheDocument();
    fireEvent.change(screen.getByRole("slider"), { target: { value: "3" } });
    expect(screen.getByText("Player A: -1")).toBeInTheDocument();
  });

  it("shows the reason for unavailable metrics without drawing fabricated curves", () => {
    render(<ExternalRegretPanel byPlayer={{ A: { status: "unavailable", reason: "action noise prevents exact counterfactuals" } }} />);
    expect(screen.getByText(/Unavailable: action noise/)).toBeInTheDocument();
    expect(screen.queryByRole("img")).not.toBeInTheDocument();
    expect(screen.queryByRole("slider")).not.toBeInTheDocument();
  });

  it("handles a single round and undefined normalization", () => {
    const { container } = render(<ExternalRegretPanel byPlayer={{ A: { ...metric, cumulative: 0, average: 0, normalized_average: null, num_rounds: 1, series: [{ round: 1, cumulative: 0, average: 0 }] } }} />);
    expect(screen.getByText("Undefined (constant payoff range)")).toBeInTheDocument();
    expect(screen.getByRole("slider")).toHaveAttribute("max", "1");
    expect(container.innerHTML).not.toMatch(/NaN|Infinity/);
  });

  it.each([undefined, null, {}])("omits absent metrics: %s", byPlayer => {
    const { container } = render(<ExternalRegretPanel byPlayer={byPlayer} />);
    expect(container).toBeEmptyDOMElement();
  });

  it("rejects malformed data and bounds the inspector after changing matches", () => {
    const { rerender } = render(<ExternalRegretPanel byPlayer={{ A: metric }} />);
    fireEvent.change(screen.getByRole("slider"), { target: { value: "3" } });
    rerender(<ExternalRegretPanel byPlayer={{ A: { ...metric, num_rounds: 1, series: [{ round: 1, cumulative: 0, average: 0 }] }, B: { ...metric, cumulative: Number.NaN } }} />);
    expect(screen.getByRole("slider")).toHaveValue("1");
    expect(screen.getByText(/Unavailable: Incomplete or invalid regret data/)).toBeInTheDocument();
  });

  it("integrates the dedicated panel into completed match history", () => {
    const match = createMockMatch({ metrics: { external_regret: { A: metric, B: opponent }, total_payoff: { A: 3, B: -3 } } });
    vi.mocked(useApp).mockReturnValue({ state: { activeMatch: match } } as ReturnType<typeof useApp>);
    renderWithProviders(<AutoHistoryView hasMatch canvasCollapsed={false} onExpandCanvas={vi.fn()} />);
    expect(screen.getByRole("region", { name: "External regret evaluation" })).toBeInTheDocument();
    expect(screen.getByText("Download JSON")).toBeInTheDocument();
    expect(screen.queryByText("external_regret")).not.toBeInTheDocument();
  });
});
