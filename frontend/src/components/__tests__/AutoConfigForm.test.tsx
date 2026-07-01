import { describe, it, expect, beforeEach } from "vitest";
import { screen, waitFor } from "@testing-library/react";
import { userEvent } from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { AutoConfigForm } from "../AutoConfigForm";
import { renderWithProviders } from "../../test-utils";
import { createMockSchema, createMockSchemaComplex } from "../../test-fixtures";
import { server } from "../../mocks/server";
import type { CreateExperimentResponse } from "../../types";

describe("AutoConfigForm — basic rendering", () => {
  it("renders Run Experiment button", async () => {
    renderWithProviders(
      <AutoConfigForm gameSlug="colonelblotto" schema={createMockSchema()} locked={false} />,
    );
    await waitFor(() => {
      expect(screen.getByText("Run Experiment")).toBeInTheDocument();
    });
  });

  it("renders player A and player B selectors", async () => {
    renderWithProviders(
      <AutoConfigForm gameSlug="colonelblotto" schema={createMockSchema()} locked={false} />,
    );
    await waitFor(() => {
      expect(screen.getByText("Player A")).toBeInTheDocument();
      expect(screen.getByText("Player B")).toBeInTheDocument();
    });
  });

  it("renders schema-driven form fields", async () => {
    renderWithProviders(
      <AutoConfigForm gameSlug="colonelblotto" schema={createMockSchema()} locked={false} />,
    );
    await waitFor(() => {
      expect(screen.getByText("rounds")).toBeInTheDocument();
      expect(screen.getByText("num_battlefields")).toBeInTheDocument();
      expect(screen.getByText("total_resources")).toBeInTheDocument();
      expect(screen.getByText("seed")).toBeInTheDocument();
    });
  });

  it("renders select for enum fields", async () => {
    renderWithProviders(
      <AutoConfigForm gameSlug="colonelblotto" schema={createMockSchema()} locked={false} />,
    );
    await waitFor(() => {
      expect(screen.getByText("mode")).toBeInTheDocument();
    });
  });

  it("renders checkbox for boolean fields", async () => {
    renderWithProviders(
      <AutoConfigForm gameSlug="colonelblotto" schema={createMockSchema()} locked={false} />,
    );
    await waitFor(() => {
      expect(screen.getByText("enable_golden_snitch")).toBeInTheDocument();
    });
  });
});

describe("AutoConfigForm — locked/replay mode", () => {
  it("shows locked message when locked", async () => {
    renderWithProviders(
      <AutoConfigForm gameSlug="colonelblotto" schema={createMockSchema()} locked={true} />,
    );
    await waitFor(() => {
      expect(screen.getByText("Locked. Game was created via programmatic API")).toBeInTheDocument();
    });
  });

  it("shows completed message when session completed", async () => {
    renderWithProviders(
      <AutoConfigForm gameSlug="colonelblotto" schema={createMockSchema()} locked={false} sessionStatus="completed" />,
    );
    await waitFor(() => {
      expect(screen.getByText("Completed. Replay in Live View only")).toBeInTheDocument();
    });
  });

  it("does not show Run Experiment in replay mode", async () => {
    renderWithProviders(
      <AutoConfigForm gameSlug="colonelblotto" schema={createMockSchema()} locked={true} />,
    );
    await waitFor(() => {
      expect(screen.queryByText("Run Experiment")).not.toBeInTheDocument();
    });
  });

  it("pre-populates fields from initialValues when locked", async () => {
    renderWithProviders(
      <AutoConfigForm
        gameSlug="colonelblotto"
        schema={createMockSchema()}
        locked={true}
        initialValues={{
          rounds: 7,
          num_battlefields: 3,
          total_resources: 50,
          seed: 123,
        }}
      />,
    );

    await waitFor(() => {
      expect(screen.getByDisplayValue("7")).toBeInTheDocument();
      expect(screen.getByDisplayValue("3")).toBeInTheDocument();
      expect(screen.getByDisplayValue("50")).toBeInTheDocument();
      expect(screen.getByDisplayValue("123")).toBeInTheDocument();
    });
  });

  it("pre-populates fields when session is completed", async () => {
    renderWithProviders(
      <AutoConfigForm
        gameSlug="colonelblotto"
        schema={createMockSchema()}
        locked={false}
        sessionStatus="completed"
        initialValues={{
          rounds: 4,
          num_battlefields: 8,
          total_resources: 25,
          seed: 999,
        }}
      />,
    );

    await waitFor(() => {
      expect(screen.getByDisplayValue("4")).toBeInTheDocument();
      expect(screen.getByDisplayValue("8")).toBeInTheDocument();
      expect(screen.getByDisplayValue("25")).toBeInTheDocument();
      expect(screen.getByDisplayValue("999")).toBeInTheDocument();
    });
  });

  it("reconstructs the agent dropdown from saved display names of remote LLM agents", async () => {
    // Reproduces the bug where the player dropdowns reset to the
    // default ("🙋 You" for A, "Remote" for B) instead of reflecting the
    // actually-played agents when those agents were external LLM model
    // names (e.g. "deepseek-v4-pro") that don't appear in the game's
    // built-in agent list.  The fix falls back to the "remote" dropdown
    // option (the slot reserved for arbitrary LLM/MCP agents).
    renderWithProviders(
      <AutoConfigForm
        gameSlug="colonelblotto"
        schema={createMockSchema()}
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
    await waitFor(() => {
      // First two comboboxes are the Player A and Player B agent dropdowns;
      // the others are the wandb select / scenario / mode / system_prompt
      // controls that depend on the test schema.  Wait for the agent
      // dropdowns specifically to land on "remote".
      const selects = screen.getAllByRole("combobox") as HTMLSelectElement[];
      expect(selects[0]?.value).toBe("remote");
      expect(selects[1]?.value).toBe("remote");
    });
    expect(screen.getByDisplayValue("deepseek-v4-pro")).toBeInTheDocument();
    expect(screen.getByDisplayValue("glm-5.1")).toBeInTheDocument();
  });

  it("reconstructs a built-in bot agent id when the saved display name matches the label", async () => {
    renderWithProviders(
      <AutoConfigForm
        gameSlug="colonelblotto"
        schema={createMockSchema()}
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

  it("reconstructs the human-player agent id when the saved name is 'You'", async () => {
    renderWithProviders(
      <AutoConfigForm
        gameSlug="colonelblotto"
        schema={createMockSchema()}
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

describe("AutoConfigForm — submission", () => {
  beforeEach(() => {
    server.resetHandlers();
    server.use(
      http.post("/api/experiment", () => {
        return HttpResponse.json<CreateExperimentResponse>({
          session_id: "submit-test-session",
          player_tokens: { A: "tok-a", B: "tok-b" },
          config_hash: "submit-hash",
        });
      }),
    );
  });

  it("shows keys when remote agent selected", async () => {
    const user = userEvent.setup();
    renderWithProviders(
      <AutoConfigForm gameSlug="colonelblotto" schema={createMockSchema()} locked={false} />,
    );

    await waitFor(() => {
      expect(screen.getByText("Run Experiment")).toBeInTheDocument();
    });

    const agentASelect = screen.getAllByRole("combobox")[0];
    await user.selectOptions(agentASelect, "remote");

    await user.click(screen.getByText("Run Experiment"));

    await waitFor(() => {
      expect(screen.getByText("tok-a")).toBeInTheDocument();
    });
  });

  it("shows session ID when no remote agents", async () => {
    server.resetHandlers();
    server.use(
      http.post("/api/experiment", () => {
        return HttpResponse.json<CreateExperimentResponse>({
          session_id: "no-remote-session",
          player_tokens: {},
          config_hash: "h",
        });
      }),
      http.get("/api/games/:name/agents", () => {
        return HttpResponse.json({
          agents: [
            { id: "uniform", label: "Uniform" },
            { id: "random", label: "Random" },
          ],
        });
      }),
    );

    const user = userEvent.setup();
    renderWithProviders(
      <AutoConfigForm gameSlug="colonelblotto" schema={createMockSchema()} locked={false} />,
    );

    await waitFor(() => {
      expect(screen.getByText("Run Experiment")).toBeInTheDocument();
    });

    const agentBSelect = screen.getAllByRole("combobox")[1];
    await user.selectOptions(agentBSelect, "uniform");

    await user.click(screen.getByText("Run Experiment"));

    await waitFor(() => {
      expect(screen.getByText("no-remote-session")).toBeInTheDocument();
    });
  });

  it("shows error message on submission failure", async () => {
    server.resetHandlers();
    server.use(
      http.post("/api/experiment", () => {
        return HttpResponse.json({ detail: "Server error" }, { status: 500 });
      }),
    );

    const user = userEvent.setup();
    renderWithProviders(
      <AutoConfigForm gameSlug="colonelblotto" schema={createMockSchema()} locked={false} />,
    );

    await waitFor(() => {
      expect(screen.getByText("Run Experiment")).toBeInTheDocument();
    });

    await user.click(screen.getByText("Run Experiment"));

    await waitFor(() => {
      expect(screen.getByText("Server error")).toBeInTheDocument();
    });
  });
});

describe("AutoConfigForm — complex schema", () => {
  it("renders array fields with add button", async () => {
    renderWithProviders(
      <AutoConfigForm gameSlug="colonelblotto" schema={createMockSchemaComplex()} locked={false} />,
    );

    await waitFor(() => {
      expect(screen.getByText("battlefields")).toBeInTheDocument();
      expect(screen.getByText("weights")).toBeInTheDocument();
    });
  });

  it("renders object array fields", async () => {
    renderWithProviders(
      <AutoConfigForm gameSlug="colonelblotto" schema={createMockSchemaComplex()} locked={false} />,
    );

    await waitFor(() => {
      expect(screen.getByText("battlefields")).toBeInTheDocument();
    });
  });

  it("shows conditionally visible fields", async () => {
    renderWithProviders(
      <AutoConfigForm gameSlug="colonelblotto" schema={createMockSchemaComplex()} locked={false} />,
    );

    await waitFor(() => {
      expect(screen.getByText("mode")).toBeInTheDocument();
    });

    expect(screen.queryByText("extended_rules")).not.toBeInTheDocument();
  });
});
