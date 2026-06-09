import { describe, it, expect } from "vitest";
import { screen } from "@testing-library/react";
import { GameHeader } from "../GameHeader";
import { renderWithProviders, createMockAuth } from "../../test-utils";
import { createMockGameMetadata } from "../../test-fixtures";

describe("GameHeader — expanded", () => {
  it("shows download button when activeMatch exists", () => {
    const game = createMockGameMetadata();
    const { container } = renderWithProviders(
      <GameHeader game={game} locked={false} status="completed" />,
      { auth: createMockAuth() },
    );
    expect(container.querySelector('button[title="Download match data as JSON"]')).not.toBeInTheDocument();
    expect(screen.getByText("completed")).toBeInTheDocument();
  });

  it("renders without createdAt", () => {
    const game = createMockGameMetadata();
    renderWithProviders(
      <GameHeader game={game} locked={false} status="ready" />,
      { auth: createMockAuth() },
    );
    expect(screen.getByText("Colonel Blotto")).toBeInTheDocument();
  });

  it("renders with empty version", () => {
    const game = createMockGameMetadata({ name: "Simple Game", version: undefined });
    renderWithProviders(
      <GameHeader game={game} locked={false} status="ready" />,
      { auth: createMockAuth() },
    );
    expect(screen.getByText("Simple Game")).toBeInTheDocument();
    expect(screen.queryByText(/^v/)).not.toBeInTheDocument();
  });
});
