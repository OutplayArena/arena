import { describe, it, expect, vi } from "vitest";
import { screen, act } from "@testing-library/react";
import { userEvent } from "@testing-library/user-event";
import { PlaybackPanel } from "../PlaybackPanel";
import { renderWithProviders } from "../../test-utils";
import { AppContext, type AppContextValue, type AppState } from "../../state";
import { createMockMatch } from "../../test-fixtures";

function createAppContext(overrides: Partial<AppState> = {}): AppContextValue {
  const match = createMockMatch({ history: [
    { round: 1, agent_a: "a", agent_b: "b", action_a: [10, 20], action_b: [5, 25], score_a: 1, score_b: 2, total_score_a: 1, total_score_b: 2, winner: "B" as const },
    { round: 2, agent_a: "a", agent_b: "b", action_a: [20, 10], action_b: [15, 15], score_a: 2, score_b: 1, total_score_a: 3, total_score_b: 3, winner: "A" as const },
    { round: 3, agent_a: "a", agent_b: "b", action_a: [30, 0], action_b: [10, 20], score_a: 1, score_b: 1, total_score_a: 4, total_score_b: 4, winner: "Tie" as const },
  ]});
  const state: AppState = {
    activeMatch: match,
    activeRoundIndex: 0,
    isPlaying: false,
    status: "",
    roundDuration: 3200,
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

function renderPlaybackPanel(ctx: AppContextValue) {
  return renderWithProviders(
    <AppContext.Provider value={ctx}>
      <PlaybackPanel />
    </AppContext.Provider>,
  );
}

describe("PlaybackPanel", () => {
  it("renders round counter", () => {
    const ctx = createAppContext();
    renderPlaybackPanel(ctx);
    expect(screen.getByText("Round")).toBeInTheDocument();
    expect(screen.getByText("1/3")).toBeInTheDocument();
  });

  it("has previous button disabled at round 0", () => {
    const ctx = createAppContext({ activeRoundIndex: 0 });
    renderPlaybackPanel(ctx);
    expect(screen.getByLabelText("Previous round")).toBeDisabled();
  });

  it("has next button disabled at last round", () => {
    const ctx = createAppContext({ activeRoundIndex: 2 });
    renderPlaybackPanel(ctx);
    expect(screen.getByLabelText("Next round")).toBeDisabled();
  });

  it("shows Play button when not playing", () => {
    const ctx = createAppContext({ isPlaying: false });
    renderPlaybackPanel(ctx);
    expect(screen.getByText("Play")).toBeInTheDocument();
  });

  it("shows Pause button when playing", () => {
    const ctx = createAppContext({ isPlaying: true });
    renderPlaybackPanel(ctx);
    expect(screen.getByText("Pause")).toBeInTheDocument();
  });

  it("calls togglePlay on Play/Pause click", async () => {
    const user = userEvent.setup();
    const ctx = createAppContext({ isPlaying: false });
    renderPlaybackPanel(ctx);
    await user.click(screen.getByText("Play"));
    expect(ctx.togglePlay).toHaveBeenCalled();
  });

  it("calls prevRound on previous button click", async () => {
    const user = userEvent.setup();
    const ctx = createAppContext({ activeRoundIndex: 1 });
    renderPlaybackPanel(ctx);
    await user.click(screen.getByLabelText("Previous round"));
    expect(ctx.prevRound).toHaveBeenCalled();
  });

  it("calls nextRound on next button click", async () => {
    const user = userEvent.setup();
    const ctx = createAppContext({ activeRoundIndex: 0 });
    renderPlaybackPanel(ctx);
    await user.click(screen.getByLabelText("Next round"));
    expect(ctx.nextRound).toHaveBeenCalled();
  });
});
