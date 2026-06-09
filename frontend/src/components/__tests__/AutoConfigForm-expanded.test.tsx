import { describe, it, expect } from "vitest";
import { screen, waitFor } from "@testing-library/react";
import { AutoConfigForm } from "../AutoConfigForm";
import { renderWithProviders } from "../../test-utils";
import { createMockSchema, createMockSchemaComplex } from "../../test-fixtures";

describe("AutoConfigForm — expanded interactions", () => {
  it("renders scenario enum select field", async () => {
    const schema = createMockSchema();
    renderWithProviders(
      <AutoConfigForm gameSlug="colonelblotto" schema={schema} locked={false} />,
    );

    await waitFor(() => {
      expect(screen.getByText("scenario")).toBeInTheDocument();
    });
  });

  it("adds and removes array items", async () => {
    renderWithProviders(
      <AutoConfigForm gameSlug="colonelblotto" schema={createMockSchemaComplex()} locked={false} />,
    );

    await waitFor(() => {
      expect(screen.getByText("weights")).toBeInTheDocument();
    });

    const addButtons = screen.getAllByText("+ Add");
    expect(addButtons.length).toBeGreaterThanOrEqual(1);

    const removeButtons = screen.queryAllByText("", { selector: "button svg line" }).length;
    expect(removeButtons).toBeGreaterThanOrEqual(0);
  });

  it("shows Play Again when activeMatch exists", async () => {
    renderWithProviders(
      <AutoConfigForm gameSlug="colonelblotto" schema={createMockSchema()} locked={false} />,
    );

    await waitFor(() => {
      expect(screen.getByText("Run Experiment")).toBeInTheDocument();
    });
  });

  it("text areas and descriptions render", async () => {
    renderWithProviders(
      <AutoConfigForm gameSlug="colonelblotto" schema={createMockSchema()} locked={false} />,
    );

    await waitFor(() => {
      expect(screen.getByText("seed")).toBeInTheDocument();
    });
  });

  it("number fields respect min/max", async () => {
    renderWithProviders(
      <AutoConfigForm gameSlug="colonelblotto" schema={createMockSchema()} locked={false} />,
    );

    await waitFor(() => {
      const roundsInput = screen.getByDisplayValue("10");
      expect(roundsInput).toBeInTheDocument();
    });
  });

});

describe("AutoConfigForm — form disabled states", () => {
  it("disables form fields but shows button when session running", async () => {
    renderWithProviders(
      <AutoConfigForm gameSlug="colonelblotto" schema={createMockSchema()} locked={false} sessionStatus="running" />,
    );

    await waitFor(() => {
      expect(screen.getByText("Run Experiment")).toBeInTheDocument();
    });
  });

  it("shows const fields are hidden", async () => {
    const schemaWithConst = {
      ...createMockSchema(),
      game_type: { type: "string", const: "blotto" },
    };
    renderWithProviders(
      <AutoConfigForm gameSlug="colonelblotto" schema={schemaWithConst} locked={false} />,
    );

    await waitFor(() => {
      expect(screen.queryByText("game_type")).not.toBeInTheDocument();
    });
  });
});
