import { describe, it, expect, vi } from "vitest";
import { screen, waitFor } from "@testing-library/react";
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
      <LiveView onScores={onScores} onToggleCollapse={onToggleCollapse} createdAt="2026-01-01T00:00:00Z" />,
    );
    expect(screen.getByText("No battle data yet")).toBeInTheDocument();
  });

  it("ConfigForm renders with standard props", async () => {
    const mod = await import("@games/core/colonelblotto/ui/ConfigForm.tsx");
    const ConfigForm = mod.default;
    renderWithProviders(
      <ConfigForm gameSlug="colonelblotto" locked={false} />,
    );
    expect(screen.getByText("Start Game")).toBeInTheDocument();
  });

  it("ConfigForm renders in locked mode", async () => {
    const mod = await import("@games/core/colonelblotto/ui/ConfigForm.tsx");
    const ConfigForm = mod.default;
    renderWithProviders(
      <ConfigForm gameSlug="colonelblotto" locked={true} />,
    );
    expect(screen.getByText(/Locked/)).toBeInTheDocument();
  });

  it("ConfigForm shows the config that was used to run the game (locked, flat values)", async () => {
    // Reproduces the bug where the Config tab showed a default form instead
    // of the actual parameters of a finished session.
    const mod = await import("@games/core/colonelblotto/ui/ConfigForm.tsx");
    const ConfigForm = mod.default;
    renderWithProviders(
      <ConfigForm
        gameSlug="colonelblotto"
        locked={true}
        sessionStatus="completed"
        initialValues={{
          rounds: 7,
          num_battlefields: 3,
          total_resources: 50,
          seed: 123,
        }}
      />,
    );
    expect(screen.getByDisplayValue("7")).toBeInTheDocument();
    expect(screen.getByDisplayValue("3")).toBeInTheDocument();
    expect(screen.getByDisplayValue("50")).toBeInTheDocument();
    expect(screen.getByDisplayValue("123")).toBeInTheDocument();
  });

  it("ConfigForm derives num_battlefields/total_resources from the raw saved config when flat fields are absent", async () => {
    // Some callers (or older sessions) may surface the raw saved config
    // (with `budget` + `battlefields` lists) rather than the flat
    // `num_battlefields` + `total_resources` shorthand.  The form should
    // still display the correct numbers.
    const mod = await import("@games/core/colonelblotto/ui/ConfigForm.tsx");
    const ConfigForm = mod.default;
    renderWithProviders(
      <ConfigForm
        gameSlug="colonelblotto"
        locked={true}
        sessionStatus="completed"
        initialValues={{
          game: "colonelblotto",
          rounds: 5,
          seed: 42,
          budget: [77, 77],
          battlefields: [
            { id: "battlefield_1", value: 1.0 },
            { id: "battlefield_2", value: 1.0 },
            { id: "battlefield_3", value: 1.0 },
            { id: "battlefield_4", value: 1.0 },
          ],
        }}
      />,
    );
    expect(screen.getByDisplayValue("5")).toBeInTheDocument();
    expect(screen.getByDisplayValue("4")).toBeInTheDocument();
    expect(screen.getByDisplayValue("77")).toBeInTheDocument();
    expect(screen.getByDisplayValue("42")).toBeInTheDocument();
  });

  it("ConfigForm reconstructs the agent dropdown from saved display names of remote LLM agents", async () => {
    // Reproduces the bug where Player A's dropdown reset to "🙋 You" for
    // sessions where the saved display name was an arbitrary LLM model
    // string like "deepseek-v4-pro" (i.e. the user had selected
    // "Remote Agent (LLM/MCP)" and typed a custom display name).
    const mod = await import("@games/core/colonelblotto/ui/ConfigForm.tsx");
    const ConfigForm = mod.default;
    renderWithProviders(
      <ConfigForm
        gameSlug="colonelblotto"
        locked={true}
        sessionStatus="completed"
        initialValues={{
          rounds: 3,
          num_battlefields: 5,
          total_resources: 100,
          seed: 42,
          agent_a: "deepseek-v4-pro",
          agent_b: "glm-5.1",
        }}
      />,
    );
    // Wait for the available-agent list to load + the replay effect to fire.
    await waitFor(() => {
      const selects = screen.getAllByRole("combobox") as HTMLSelectElement[];
      expect(selects[0]?.value).toBe("remote");
      expect(selects[1]?.value).toBe("remote");
    });
    // Display-name inputs reflect the actual saved agents.
    expect(screen.getByDisplayValue("deepseek-v4-pro")).toBeInTheDocument();
    expect(screen.getByDisplayValue("glm-5.1")).toBeInTheDocument();
    // Numeric parameters also come through.
    expect(screen.getByDisplayValue("3")).toBeInTheDocument();
  });

  it("ConfigForm reconstructs a built-in bot agent id when display name matches the label", async () => {
    const mod = await import("@games/core/colonelblotto/ui/ConfigForm.tsx");
    const ConfigForm = mod.default;
    renderWithProviders(
      <ConfigForm
        gameSlug="colonelblotto"
        locked={true}
        sessionStatus="completed"
        initialValues={{
          rounds: 5,
          agent_a: "Uniform Distribution",
          agent_b: "Greedy",
        }}
      />,
    );
    await waitFor(() => {
      const selects = screen.getAllByRole("combobox") as HTMLSelectElement[];
      expect(selects[0]?.value).toBe("uniform");
      expect(selects[1]?.value).toBe("greedy");
    });
  });

  it("ConfigForm reconstructs the human-player agent id when the saved name is 'You'", async () => {
    const mod = await import("@games/core/colonelblotto/ui/ConfigForm.tsx");
    const ConfigForm = mod.default;
    renderWithProviders(
      <ConfigForm
        gameSlug="colonelblotto"
        locked={true}
        sessionStatus="completed"
        initialValues={{
          rounds: 5,
          agent_a: "You",
          agent_b: "Remote B",
        }}
      />,
    );
    await waitFor(() => {
      const selects = screen.getAllByRole("combobox") as HTMLSelectElement[];
      expect(selects[0]?.value).toBe("interactive");
      expect(selects[1]?.value).toBe("remote");
    });
  });
});
