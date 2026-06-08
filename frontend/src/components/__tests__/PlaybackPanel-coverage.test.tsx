import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { act } from "@testing-library/react";
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

describe("PlaybackPanel — timer coverage", () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("advances round on timer tick when playing", () => {
    const ctx = createCtx({ isPlaying: true, activeRoundIndex: 0 });
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

  it("stops at last round and sets final status", () => {
    const ctx = createCtx({
      isPlaying: true,
      activeRoundIndex: 2,
      activeMatch: createMockMatch({
        match_winner: "B",
        total_score_a: 2,
        total_score_b: 5,
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
      expect.stringContaining("match_winner=B"),
    );
  });

  it("cleanup stops timer on unmount", () => {
    const ctx = createCtx({ isPlaying: true });
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

  it("status banner updates with round info", () => {
    const round: MatchRound = {
      round: 1, agent_a: "a", agent_b: "b",
      action_a: [5, 5], action_b: [3, 7],
      score_a: 1, score_b: 2,
      total_score_a: 1, total_score_b: 2,
      winner: "B",
    };

    const ctx = createCtx({ activeRoundIndex: 0 });
    ctx.currentRound = vi.fn(() => round);

    renderWithProviders(
      <AppContext.Provider value={ctx}>
        <PlaybackPanel />
      </AppContext.Provider>,
    );

    expect(ctx.setStatus).toHaveBeenCalledWith(
      expect.stringContaining("round=1"),
    );
    expect(ctx.setStatus).toHaveBeenCalledWith(
      expect.stringContaining("winner=B"),
    );
  });
});
