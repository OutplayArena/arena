import { describe, it, expect, vi } from "vitest";
import { screen } from "@testing-library/react";
import { renderWithProviders } from "../../test-utils";

// Tests UI components from games/core/colonelblotto/

describe("ColonelBlotto UI Contract", () => {
  it("LiveView renders without match (empty state)", async () => {
    const mod = await import("@games/core/colonelblotto/ui/LiveView.tsx");
    const LiveView = mod.default;
    renderWithProviders(<LiveView onToggleCollapse={vi.fn()} />);
    expect(screen.getByText("No battle data yet")).toBeInTheDocument();
  });

  it("LiveView accepts all standard props", async () => {
    const mod = await import("@games/core/colonelblotto/ui/LiveView.tsx");
    const LiveView = mod.default;
    const onScores = vi.fn();
    const onToggleCollapse = vi.fn();
    renderWithProviders(
      <LiveView onScores={onScores} onToggleCollapse={onToggleCollapse} createdAt="2025-01-01T00:00:00Z" />,
    );
    expect(screen.getByText("No battle data yet")).toBeInTheDocument();
  });

  it("ConfigForm renders with standard props", async () => {
    const mod = await import("@games/core/colonelblotto/ui/ConfigForm.tsx");
    const ConfigForm = mod.default;
    renderWithProviders(
      <ConfigForm gameSlug="colonelblotto" locked={false} />,
    );
    expect(screen.getByText("Run Experiment")).toBeInTheDocument();
  });

  it("ConfigForm renders in locked mode", async () => {
    const mod = await import("@games/core/colonelblotto/ui/ConfigForm.tsx");
    const ConfigForm = mod.default;
    renderWithProviders(
      <ConfigForm gameSlug="colonelblotto" locked={true} />,
    );
    expect(screen.getByText(/Locked/)).toBeInTheDocument();
  });
});
