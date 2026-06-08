import { describe, it, expect } from "vitest";
import { screen } from "@testing-library/react";
import { GameHeader } from "../GameHeader";
import { renderWithProviders, createMockAuth } from "../../test-utils";
import { createMockGameMetadata } from "../../test-fixtures";

describe("GameHeader", () => {
  it("renders game name", () => {
    const game = createMockGameMetadata({ name: "Colonel Blotto" });
    renderWithProviders(
      <GameHeader game={game} locked={false} status="ready" />,
      { auth: createMockAuth() },
    );
    expect(screen.getByText("Colonel Blotto")).toBeInTheDocument();
  });

  it("shows version when present", () => {
    const game = createMockGameMetadata({ name: "Test Game", version: "2.0.1" });
    renderWithProviders(
      <GameHeader game={game} locked={false} status="ready" />,
      { auth: createMockAuth() },
    );
    expect(screen.getByText("v2.0.1")).toBeInTheDocument();
  });

  it("shows locked indicator when locked", () => {
    const game = createMockGameMetadata();
    renderWithProviders(
      <GameHeader game={game} locked={true} status="completed" />,
      { auth: createMockAuth() },
    );
    expect(screen.getByText("Locked — created via API")).toBeInTheDocument();
  });

  it("does not show locked indicator when not locked", () => {
    const game = createMockGameMetadata();
    renderWithProviders(
      <GameHeader game={game} locked={false} status="ready" />,
      { auth: createMockAuth() },
    );
    expect(screen.queryByText("Locked — created via API")).not.toBeInTheDocument();
  });

  it("shows status badge", () => {
    const game = createMockGameMetadata();
    renderWithProviders(
      <GameHeader game={game} locked={false} status="running" />,
      { auth: createMockAuth() },
    );
    expect(screen.getByText("running")).toBeInTheDocument();
  });

  it("shows createdAt date when provided", () => {
    const game = createMockGameMetadata();
    renderWithProviders(
      <GameHeader game={game} locked={false} status="completed" createdAt="2025-01-15T12:00:00Z" />,
      { auth: createMockAuth() },
    );
    expect(screen.getByText(/2025/)).toBeInTheDocument();
  });
});
