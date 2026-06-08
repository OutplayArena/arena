import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { screen, act } from "@testing-library/react";
import { userEvent } from "@testing-library/user-event";
import { PlaybackPanel } from "../PlaybackPanel";
import { renderWithProviders } from "../../test-utils";
import { AppContext, type AppContextValue, type AppState } from "../../state";
import { createMockMatch } from "../../test-fixtures";
import type { MatchRound } from "../../types";

function createCtx(overrides: Partial<AppState> = {}): AppContextValue {
  const match = createMockMatch();
  const state: AppState = {
    activeMatch: match,
    activeRoundIndex: 0,
    isPlaying: false,
    status: "",
    roundDuration: 50,
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

describe("PlaybackPanel — deep coverage", () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("auto-advances round with fake timers", async () => {
    const ctx = createCtx({ isPlaying: true, activeRoundIndex: 0, roundDuration: 100 });
    renderWithProviders(
      <AppContext.Provider value={ctx}>
        <PlaybackPanel />
      </AppContext.Provider>,
    );

    act(() => {
      vi.advanceTimersByTime(100);
    });

    expect(ctx.nextRound).toHaveBeenCalled();
  });

  it("stops playback and sets status at last round", () => {
    const ctx = createCtx({
      isPlaying: true,
      activeRoundIndex: 2,
      roundDuration: 100,
      activeMatch: createMockMatch({
        match_winner: "A",
        total_score_a: 5,
        total_score_b: 4,
      }),
    });

    renderWithProviders(
      <AppContext.Provider value={ctx}>
        <PlaybackPanel />
      </AppContext.Provider>,
    );

    act(() => {
      vi.advanceTimersByTime(100);
    });

    expect(ctx.stopPlay).toHaveBeenCalled();
    expect(ctx.setStatus).toHaveBeenCalledWith(
      expect.stringContaining("match_winner=A"),
    );
  });

  it("cleans up timer on unmount", () => {
    const ctx = createCtx({ isPlaying: true, roundDuration: 100 });
    const { unmount } = renderWithProviders(
      <AppContext.Provider value={ctx}>
        <PlaybackPanel />
      </AppContext.Provider>,
    );

    unmount();

    act(() => {
      vi.advanceTimersByTime(100);
    });

    expect(ctx.nextRound).not.toHaveBeenCalled();
  });

  it("sets status from currentRound", () => {
    const round: MatchRound = {
      round: 1, agent_a: "a", agent_b: "b",
      action_a: [1, 2, 3], action_b: [3, 2, 1],
      score_a: 10, score_b: 5,
      total_score_a: 10, total_score_b: 5,
      winner: "A",
    };

    const ctx = createCtx({
      isPlaying: false,
      activeRoundIndex: 0,
      activeMatch: createMockMatch({ history: [round] }),
    });
    ctx.currentRound = vi.fn(() => round);

    renderWithProviders(
      <AppContext.Provider value={ctx}>
        <PlaybackPanel />
      </AppContext.Provider>,
    );

    expect(ctx.setStatus).toHaveBeenCalledWith(
      expect.stringContaining("round=1"),
    );
  });
});
