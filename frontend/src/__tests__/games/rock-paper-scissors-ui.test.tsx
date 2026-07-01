import { describe, it, expect } from "vitest";
import { screen, waitFor } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { server } from "../../mocks/server";
import type { GameAgent } from "../../types";
import { renderWithProviders } from "../../test-utils";

// Tests UI components from games/core/rock_paper_scissors/

const RPS_AGENTS: GameAgent[] = [
  { id: "random", label: "Random" },
  { id: "biased", label: "Biased (rock-heavy)" },
  { id: "copycat", label: "Copycat" },
  { id: "counter", label: "Counter" },
  { id: "remote", label: "Remote Agent (LLM/MCP)" },
  { id: "interactive", label: "Interactive (Human)" },
];

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
    expect(screen.getByText("Start Game")).toBeInTheDocument();
  });

  it("ConfigForm renders in replay mode", async () => {
    const mod = await import("@games/core/rock_paper_scissors/ui/ConfigForm.tsx");
    const ConfigForm = mod.default;
    renderWithProviders(
      <ConfigForm gameSlug="rock_paper_scissors" locked={false} sessionStatus="completed" />,
    );
    expect(screen.getByText(/Completed/)).toBeInTheDocument();
  });

  it("ConfigForm reconstructs agent dropdown on replay (remote LLM and built-in bot)", async () => {
    // Use the real RPS agent list to exercise the live replay path.
    server.resetHandlers();
    server.use(
      http.get("/api/games/:name/agents", () =>
        HttpResponse.json<{ agents: GameAgent[] }>({ agents: RPS_AGENTS }),
      ),
    );
    const mod = await import("@games/core/rock_paper_scissors/ui/ConfigForm.tsx");
    const ConfigForm = mod.default;
    renderWithProviders(
      <ConfigForm
        gameSlug="rock_paper_scissors"
        locked={true}
        sessionStatus="completed"
        initialValues={{
          agent_a: "deepseek-v4-pro",
          agent_b: "Copycat",
        }}
      />,
    );
    await waitFor(() => {
      const selects = screen.getAllByRole("combobox") as HTMLSelectElement[];
      expect(selects[0]?.value).toBe("remote");
      expect(selects[1]?.value).toBe("copycat");
    });
    expect(screen.getByDisplayValue("deepseek-v4-pro")).toBeInTheDocument();
  });
});
