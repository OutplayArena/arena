import { describe, it, expect, vi } from "vitest";
import { screen } from "@testing-library/react";
import { GameHeader } from "../GameHeader";
import { renderWithProviders, createMockAuth } from "../../test-utils";
import { createMockGameMetadata, createMockMatch } from "../../test-fixtures";
import { useApp } from "../../hooks/useApp";

vi.mock("../../hooks/useApp", () => ({
  useApp: vi.fn(),
}));

describe("GameHeader — with activeMatch", () => {
  it("shows download button when activeMatch exists", () => {
    (useApp as ReturnType<typeof vi.fn>).mockReturnValue({
      state: { activeMatch: createMockMatch() },
    });

    const game = createMockGameMetadata();
    const { container } = renderWithProviders(
      <GameHeader game={game} locked={false} status="completed" />,
      { auth: createMockAuth() },
    );

    const downloadBtn = container.querySelector('button[title="Download match data as JSON"]');
    expect(downloadBtn).toBeInTheDocument();
  });

  it("does not show download button when no activeMatch", () => {
    (useApp as ReturnType<typeof vi.fn>).mockReturnValue({
      state: { activeMatch: null },
    });

    const game = createMockGameMetadata();
    const { container } = renderWithProviders(
      <GameHeader game={game} locked={false} status="completed" />,
      { auth: createMockAuth() },
    );

    const downloadBtn = container.querySelector('button[title="Download match data as JSON"]');
    expect(downloadBtn).not.toBeInTheDocument();
  });

  it("shows createdAt date with full format", () => {
    (useApp as ReturnType<typeof vi.fn>).mockReturnValue({
      state: { activeMatch: null },
    });

    const game = createMockGameMetadata({ name: "Test" });
    renderWithProviders(
      <GameHeader game={game} locked={false} status="ready" createdAt="2026-06-15T14:30:00Z" />,
      { auth: createMockAuth() },
    );
    expect(screen.getByText(/2026/)).toBeInTheDocument();
  });
});
