import { describe, it, expect, vi } from "vitest";
import { screen } from "@testing-library/react";
import { PlaybackPanel } from "../PlaybackPanel";
import { renderWithProviders } from "../../test-utils";
import { AppContext, type AppContextValue, type AppState } from "../../state";
import { createMockMatch } from "../../test-fixtures";

function createCtx(overrides: Partial<AppState> = {}): AppContextValue {
  const match = createMockMatch();
  const state: AppState = {
    activeMatch: match,
    activeRoundIndex: 0,
    isPlaying: false,
    status: "",
    roundDuration: 100,
    sessionLocked: false,
    sessionStatus: "",
    sessionConfig: null,
    pendingGame: null,
    ...overrides,
  };
  return {
    state,
    dispatch: vi.fn(),
    setMatch: vi.fn(),
    showRound: vi.fn(),
    nextRound: vi.fn(),
    prevRound: vi.fn(),
    togglePlay: vi.fn(),
    stopPlay: vi.fn(),
    clearMatch: vi.fn(),
    setStatus: vi.fn(),
    startGame: vi.fn(),
    endGame: vi.fn(),
    setSessionMeta: vi.fn(),
    currentRound: vi.fn(() => match.history[state.activeRoundIndex] ?? null),
  };
}

describe("PlaybackPanel — expanded", () => {
  it("all controls disabled when no match", () => {
    const ctx = createCtx({ activeMatch: null });
    renderWithProviders(
      <AppContext.Provider value={ctx}>
        <PlaybackPanel />
      </AppContext.Provider>,
    );
    expect(screen.getByLabelText("Previous round")).toBeDisabled();
    expect(screen.getByLabelText("Next round")).toBeDisabled();
  });

  it("shows Play when not playing and has match", () => {
    const ctx = createCtx({ activeMatch: createMockMatch(), isPlaying: false });
    renderWithProviders(
      <AppContext.Provider value={ctx}>
        <PlaybackPanel />
      </AppContext.Provider>,
    );
    expect(screen.getByText("Play")).toBeInTheDocument();
  });

  it("shows Pause when playing", () => {
    const ctx = createCtx({ isPlaying: true });
    renderWithProviders(
      <AppContext.Provider value={ctx}>
        <PlaybackPanel />
      </AppContext.Provider>,
    );
    expect(screen.getByText("Pause")).toBeInTheDocument();
  });

  it("displays correct round fraction", () => {
    const ctx = createCtx({ activeRoundIndex: 1 });
    renderWithProviders(
      <AppContext.Provider value={ctx}>
        <PlaybackPanel />
      </AppContext.Provider>,
    );
    expect(screen.getByText("2/3")).toBeInTheDocument();
  });

  it("next button disabled at last round", () => {
    const ctx = createCtx({ activeRoundIndex: 2 });
    renderWithProviders(
      <AppContext.Provider value={ctx}>
        <PlaybackPanel />
      </AppContext.Provider>,
    );
    expect(screen.getByLabelText("Next round")).toBeDisabled();
  });
});
