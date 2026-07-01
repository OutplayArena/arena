import { describe, it, expect, vi } from "vitest";
import { screen, waitFor } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { server } from "../../mocks/server";
import type { GameAgent } from "../../types";
import { renderWithProviders } from "../../test-utils";

// Tests UI components from games/core/prisonersdilemma/

const PD_AGENTS: GameAgent[] = [
  { id: "always_cooperate", label: "Always Cooperate" },
  { id: "always_defect", label: "Always Defect" },
  { id: "tit_for_tat", label: "Tit-for-Tat" },
  { id: "grim_trigger", label: "Grim Trigger" },
  { id: "forgiving_tft", label: "Forgiving TFT" },
  { id: "pavlov", label: "Pavlov (Win-Stay/Lose-Shift)" },
  { id: "random", label: "Random" },
  { id: "remote", label: "Remote Agent (LLM/MCP)" },
  { id: "interactive", label: "Interactive (Human)" },
];

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

describe("Prisoner's Dilemma ConfigForm — agent reconstruction on replay", () => {
  it("reconstructs the agent dropdown from saved display names of remote LLM agents", async () => {
    // Use the real PD agent list so the test exercises the same code path
    // a live session at /play/prisonersdilemma/{id} would take.
    server.resetHandlers();
    server.use(
      http.get("/api/games/:name/agents", () =>
        HttpResponse.json<{ agents: GameAgent[] }>({ agents: PD_AGENTS }),
      ),
    );
    const mod = await import("@games/core/prisonersdilemma/ui/ConfigForm.tsx");
    const ConfigForm = mod.default;
    renderWithProviders(
      <ConfigForm
        gameSlug="prisonersdilemma"
        locked={true}
        sessionStatus="completed"
        initialValues={{
          agent_a: "deepseek-v4-pro",
          agent_b: "glm-5.1",
        }}
      />,
    );
    await waitFor(() => {
      const selects = screen.getAllByRole("combobox") as HTMLSelectElement[];
      expect(selects[0]?.value).toBe("remote");
      expect(selects[1]?.value).toBe("remote");
    });
    expect(screen.getByDisplayValue("deepseek-v4-pro")).toBeInTheDocument();
    expect(screen.getByDisplayValue("glm-5.1")).toBeInTheDocument();
  });

  it("reconstructs a built-in bot agent id when the saved display name matches a label", async () => {
    server.resetHandlers();
    server.use(
      http.get("/api/games/:name/agents", () =>
        HttpResponse.json<{ agents: GameAgent[] }>({ agents: PD_AGENTS }),
      ),
    );
    const mod = await import("@games/core/prisonersdilemma/ui/ConfigForm.tsx");
    const ConfigForm = mod.default;
    renderWithProviders(
      <ConfigForm
        gameSlug="prisonersdilemma"
        locked={true}
        sessionStatus="completed"
        initialValues={{
          agent_a: "Tit-for-Tat",
          agent_b: "Grim Trigger",
        }}
      />,
    );
    await waitFor(() => {
      const selects = screen.getAllByRole("combobox") as HTMLSelectElement[];
      expect(selects[0]?.value).toBe("tit_for_tat");
      expect(selects[1]?.value).toBe("grim_trigger");
    });
  });
});
