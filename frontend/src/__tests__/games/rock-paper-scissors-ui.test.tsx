import { describe, it, expect } from "vitest";
import { screen } from "@testing-library/react";
import { renderWithProviders } from "../../test-utils";

// Tests UI components from games/core/rock_paper_scissors/

describe("Rock Paper Scissors UI Contract", () => {
  it("LiveView renders without match (empty state)", async () => {
    const mod = await import("@games/core/rock_paper_scissors/ui/LiveView.tsx");
    const LiveView = mod.default;
    renderWithProviders(<LiveView />);
    expect(screen.getByText("No match data yet")).toBeInTheDocument();
  });

  it("LiveView shows agent placeholders in empty state", async () => {
    const mod = await import("@games/core/rock_paper_scissors/ui/LiveView.tsx");
    const LiveView = mod.default;
    renderWithProviders(<LiveView />);
    expect(screen.getByText("Agent A")).toBeInTheDocument();
    expect(screen.getByText("Agent B")).toBeInTheDocument();
  });

  it("ConfigForm renders with standard props", async () => {
    const mod = await import("@games/core/rock_paper_scissors/ui/ConfigForm.tsx");
    const ConfigForm = mod.default;
    renderWithProviders(
      <ConfigForm gameSlug="rock_paper_scissors" locked={false} />,
    );
    expect(screen.getByText("Run Experiment")).toBeInTheDocument();
  });

  it("ConfigForm renders in replay mode", async () => {
    const mod = await import("@games/core/rock_paper_scissors/ui/ConfigForm.tsx");
    const ConfigForm = mod.default;
    renderWithProviders(
      <ConfigForm gameSlug="rock_paper_scissors" locked={false} sessionStatus="completed" />,
    );
    expect(screen.getByText(/Completed/)).toBeInTheDocument();
  });
});
