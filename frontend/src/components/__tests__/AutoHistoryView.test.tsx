import { describe, it, expect, vi } from "vitest";
import { screen } from "@testing-library/react";
import { AutoHistoryView } from "../AutoHistoryView";
import { renderWithProviders } from "../../test-utils";
import { useApp } from "../../hooks/useApp";
import { createMockMatch } from "../../test-fixtures";

vi.mock("../../hooks/useApp", () => ({
  useApp: vi.fn(),
}));

describe("AutoHistoryView", () => {
  it("shows empty state when no match", () => {
    (useApp as ReturnType<typeof vi.fn>).mockReturnValue({
      state: { activeMatch: null },
    });
    renderWithProviders(
      <AutoHistoryView hasMatch={false} canvasCollapsed={false} onExpandCanvas={vi.fn()} />,
    );
    expect(screen.getByText("No data yet.")).toBeInTheDocument();
  });

  it("shows empty message when hasMatch is false", () => {
    (useApp as ReturnType<typeof vi.fn>).mockReturnValue({
      state: { activeMatch: null },
    });
    renderWithProviders(
      <AutoHistoryView hasMatch={false} canvasCollapsed={false} onExpandCanvas={vi.fn()} />,
    );
    expect(screen.getByText("No match data. Complete a game to see history.")).toBeInTheDocument();
  });

  it("renders round history table when match exists", () => {
    const match = createMockMatch();
    (useApp as ReturnType<typeof vi.fn>).mockReturnValue({
      state: { activeMatch: match },
    });
    renderWithProviders(
      <AutoHistoryView hasMatch={true} canvasCollapsed={false} onExpandCanvas={vi.fn()} />,
    );
    expect(screen.getByText("History")).toBeInTheDocument();
    expect(screen.getByText("Complete — 3 rounds")).toBeInTheDocument();
    expect(screen.getByText(/Final:/)).toBeInTheDocument();
  });

  it("shows final score display", () => {
    const match = createMockMatch({ total_score_a: 5, total_score_b: 4, match_winner: "A" });
    (useApp as ReturnType<typeof vi.fn>).mockReturnValue({
      state: { activeMatch: match },
    });
    renderWithProviders(
      <AutoHistoryView hasMatch={true} canvasCollapsed={false} onExpandCanvas={vi.fn()} />,
    );
    expect(screen.getByText("5")).toBeInTheDocument();
    expect(screen.getByText("4")).toBeInTheDocument();
  });

  it("shows Show Live View button when canvasCollapsed", () => {
    const match = createMockMatch();
    (useApp as ReturnType<typeof vi.fn>).mockReturnValue({
      state: { activeMatch: match },
    });
    renderWithProviders(
      <AutoHistoryView hasMatch={true} canvasCollapsed={true} onExpandCanvas={vi.fn()} />,
    );
    expect(screen.getByText("Show Live View")).toBeInTheDocument();
  });

  it("does not show Show Live View when canvas is not collapsed", () => {
    const match = createMockMatch();
    (useApp as ReturnType<typeof vi.fn>).mockReturnValue({
      state: { activeMatch: match },
    });
    renderWithProviders(
      <AutoHistoryView hasMatch={true} canvasCollapsed={false} onExpandCanvas={vi.fn()} />,
    );
    expect(screen.queryByText("Show Live View")).not.toBeInTheDocument();
  });

  it("renders Download JSON button", () => {
    const match = createMockMatch();
    (useApp as ReturnType<typeof vi.fn>).mockReturnValue({
      state: { activeMatch: match },
    });
    renderWithProviders(
      <AutoHistoryView hasMatch={true} canvasCollapsed={false} onExpandCanvas={vi.fn()} />,
    );
    expect(screen.getByText("Download JSON")).toBeInTheDocument();
  });
});
