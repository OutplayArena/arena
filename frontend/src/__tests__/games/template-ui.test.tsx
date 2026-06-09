import { describe, it, expect } from "vitest";
import { screen } from "@testing-library/react";
import { renderWithProviders } from "../../test-utils";

// Tests UI components from games/_template/

describe("Template UI Contract — new game requirements", () => {
  it("LiveView renders without match", async () => {
    const mod = await import("@games/_template/ui/LiveView.tsx");
    const LiveView = mod.default;
    renderWithProviders(<LiveView />);
    expect(screen.getByText("No match data yet")).toBeInTheDocument();
  });

  it("LiveView shows agent placeholders", async () => {
    const mod = await import("@games/_template/ui/LiveView.tsx");
    const LiveView = mod.default;
    renderWithProviders(<LiveView />);
    expect(screen.getByText("Agent A")).toBeInTheDocument();
    expect(screen.getByText("Agent B")).toBeInTheDocument();
  });

  it("ConfigForm renders with standard props", async () => {
    const mod = await import("@games/_template/ui/ConfigForm.tsx");
    const ConfigForm = mod.default;
    renderWithProviders(
      <ConfigForm gameSlug="example" locked={false} />,
    );
    expect(screen.getByText("Run Experiment")).toBeInTheDocument();
  });
});
