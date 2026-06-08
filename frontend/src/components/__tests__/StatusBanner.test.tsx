import { describe, it, expect, vi } from "vitest";
import { screen } from "@testing-library/react";
import { userEvent } from "@testing-library/user-event";
import { StatusBanner } from "../StatusBanner";
import { renderWithProviders } from "../../test-utils";
import { useApp } from "../../hooks/useApp";

vi.mock("../../hooks/useApp", () => ({
  useApp: vi.fn(),
}));

describe("StatusBanner", () => {
  it("renders nothing when status is empty", () => {
    (useApp as ReturnType<typeof vi.fn>).mockReturnValue({
      state: { status: "", activeMatch: null, pendingGame: null },
      setStatus: vi.fn(),
    });
    const { container } = renderWithProviders(<StatusBanner />);
    expect(container.firstChild).toBeNull();
  });

  it("renders status text", () => {
    (useApp as ReturnType<typeof vi.fn>).mockReturnValue({
      state: { status: "Round 3 / 10", activeMatch: null, pendingGame: null },
      setStatus: vi.fn(),
    });
    renderWithProviders(<StatusBanner />);
    expect(screen.getByText("Round 3 / 10")).toBeInTheDocument();
  });

  it("shows progress when activeMatch exists", () => {
    (useApp as ReturnType<typeof vi.fn>).mockReturnValue({
      state: {
        status: "Running...",
        activeMatch: {
          history: [{}, {}, {}],
          num_rounds: 10,
        },
        pendingGame: null,
      },
      setStatus: vi.fn(),
    });
    renderWithProviders(<StatusBanner />);
    expect(screen.getByText("Round 4 / 10")).toBeInTheDocument();
  });

  it("shows progress from pendingGame when no activeMatch", () => {
    (useApp as ReturnType<typeof vi.fn>).mockReturnValue({
      state: {
        status: "Starting...",
        activeMatch: null,
        pendingGame: {
          numRounds: 5,
          sessionId: "s1",
          tokens: {},
          agentAName: "a",
          agentBName: "b",
          agentAId: "u",
          agentBId: "g",
          numFields: 5,
          totalResources: 100,
          gameSlug: "blotto",
          remoteKeys: null,
        },
      },
      setStatus: vi.fn(),
    });
    renderWithProviders(<StatusBanner />);
    expect(screen.getByText("Round 1 / 5")).toBeInTheDocument();
  });

  it("dismisses on button click", async () => {
    const user = userEvent.setup();
    const setStatus = vi.fn();
    (useApp as ReturnType<typeof vi.fn>).mockReturnValue({
      state: { status: "Some status", activeMatch: null, pendingGame: null },
      setStatus,
    });
    renderWithProviders(<StatusBanner />);
    await user.click(screen.getByLabelText("Dismiss"));
    expect(setStatus).toHaveBeenCalledWith("");
  });
});
