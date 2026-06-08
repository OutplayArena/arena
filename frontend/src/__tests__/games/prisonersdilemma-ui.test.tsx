import { describe, it, expect, vi } from "vitest";
import { screen } from "@testing-library/react";
import { renderWithProviders } from "../../test-utils";

// Tests UI components from games/core/prisonersdilemma/

describe("Prisoner's Dilemma UI Contract", () => {
  it("LiveView renders without match (empty state)", async () => {
    const mod = await import("@games/core/prisonersdilemma/ui/LiveView.tsx");
    const LiveView = mod.default;
    renderWithProviders(<LiveView onToggleCollapse={vi.fn()} />);
    expect(screen.getByText("No match data yet")).toBeInTheDocument();
  });

  it("LiveView accepts all standard props", async () => {
    const mod = await import("@games/core/prisonersdilemma/ui/LiveView.tsx");
    const LiveView = mod.default;
    const onScores = vi.fn();
    const onToggleCollapse = vi.fn();
    renderWithProviders(
      <LiveView onScores={onScores} onToggleCollapse={onToggleCollapse} createdAt={null} />,
    );
    expect(screen.getByText("No match data yet")).toBeInTheDocument();
  });

  it("LiveView shows agent placeholders in empty state", async () => {
    const mod = await import("@games/core/prisonersdilemma/ui/LiveView.tsx");
    const LiveView = mod.default;
    renderWithProviders(<LiveView onToggleCollapse={vi.fn()} />);
    expect(screen.getByText("Agent A")).toBeInTheDocument();
    expect(screen.getByText("Agent B")).toBeInTheDocument();
  });
});
