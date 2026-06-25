import { describe, it, expect } from "vitest";
import { render } from "@testing-library/react";
import { InfoTooltip } from "../InfoTooltip";

describe("InfoTooltip", () => {
  it("renders nothing for unknown metric keys", () => {
    const { container } = render(<InfoTooltip metricKey="unknown_metric" />);
    expect(container.firstChild).toBeNull();
  });

  it("renders an SVG info icon for known metrics", () => {
    const { container } = render(<InfoTooltip metricKey="elo" />);
    const svg = container.querySelector("svg");
    expect(svg).toBeInTheDocument();
  });

  it.each([
    "elo",
    "alpha_rank",
    "avg_payoff",
    "nash_gap",
    "cumulative_regret",
    "strategy_entropy",
    "behavioral_consistency",
    "cooperation_rate",
  ])("renders for metric key: %s", (key) => {
    const { container } = render(<InfoTooltip metricKey={key} />);
    expect(container.querySelector("svg")).toBeInTheDocument();
  });

  it("includes the description in the tooltip", () => {
    const { container } = render(<InfoTooltip metricKey="elo" />);
    // Description text is in a hidden div with opacity-0 — query by text content.
    expect(container.textContent).toContain("Pairwise rating");
  });

  it("uses cursor-help to indicate interactivity", () => {
    const { container } = render(<InfoTooltip metricKey="elo" />);
    const svg = container.querySelector("svg");
    expect(svg?.getAttribute("class") || "").toContain("cursor-help");
  });
});
