import { describe, it, expect, vi } from "vitest";
import { screen } from "@testing-library/react";
import { renderWithProviders } from "../../test-utils";

describe("Vickrey Auction UI Contract", () => {
  it("LiveView renders without match (empty state)", async () => {
    const mod = await import("@games/community/vickrey_auction/ui/LiveView.tsx");
    const LiveView = mod.default;
    renderWithProviders(<LiveView onToggleCollapse={vi.fn()} />);
    expect(screen.getByText("No match data yet")).toBeInTheDocument();
  });

  it("LiveView accepts all standard props", async () => {
    const mod = await import("@games/community/vickrey_auction/ui/LiveView.tsx");
    const LiveView = mod.default;
    renderWithProviders(
      <LiveView onScores={vi.fn()} onToggleCollapse={vi.fn()} createdAt={null} />,
    );
    expect(screen.getByText("No match data yet")).toBeInTheDocument();
  });

  it("ConfigForm renders with standard props", async () => {
    const mod = await import("@games/community/vickrey_auction/ui/ConfigForm.tsx");
    const ConfigForm = mod.default;
    renderWithProviders(<ConfigForm gameSlug="vickrey_auction" locked={false} />);
    expect(screen.getByText("Rounds")).toBeInTheDocument();
  });
});
