import { describe, it, expect, vi, beforeEach } from "vitest";
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

  it("renders agent A and agent B selectors", async () => {
    renderWithProviders(
      <AutoConfigForm gameSlug="colonelblotto" schema={createMockSchema()} locked={false} />,
    );
    await waitFor(() => {
      expect(screen.getByText("Agent A")).toBeInTheDocument();
      expect(screen.getByText("Agent B")).toBeInTheDocument();
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
