import { describe, it, expect } from "vitest";
import { appReducer, initialState, type AppState } from "../state";
import { createMockMatch } from "../test-fixtures";
import type { MatchRound } from "../types";

describe("appReducer — expanded", () => {
  it("SET_MATCH transitions isPlaying to true on new match", () => {
    const match = createMockMatch();
    const before = { ...initialState(), isPlaying: false };
    const after = appReducer(before, { type: "SET_MATCH", match });
    expect(after.isPlaying).toBe(true);
  });

  it("SET_MATCH with same session preserves session meta", () => {
    const match = createMockMatch({ session_id: "s1" });
    const before: AppState = {
      ...initialState(),
      activeMatch: createMockMatch({ session_id: "s1" }),
      sessionLocked: true,
      sessionStatus: "running",
      isPlaying: true,
    };
    const after = appReducer(before, { type: "SET_MATCH", match });
    expect(after.sessionLocked).toBe(true);
    expect(after.sessionStatus).toBe("running");
  });

  it("SET_MATCH with empty history keeps existing isPlaying state", () => {
    const match = createMockMatch({ history: [] });
    const after = appReducer(initialState(), { type: "SET_MATCH", match });
    expect(after.activeRoundIndex).toBe(0);
    expect(after.isPlaying).toBe(false);
  });

  it("TOGGLE_PLAY restarts from round 0 when at end", () => {
    const match = createMockMatch({ num_rounds: 3 });
    const state: AppState = {
      ...initialState(),
      activeMatch: match,
      activeRoundIndex: 2,
      isPlaying: false,
    };
    const after = appReducer(state, { type: "TOGGLE_PLAY" });
    expect(after.activeRoundIndex).toBe(0);
    expect(after.isPlaying).toBe(true);
  });

  it("TOGGLE_PLAY no-ops without activeMatch", () => {
    const before = initialState();
    const after = appReducer(before, { type: "TOGGLE_PLAY" });
    expect(after).toEqual(before);
  });

  it("NEXT_ROUND no-ops without activeMatch", () => {
    const before = initialState();
    const after = appReducer(before, { type: "NEXT_ROUND" });
    expect(after).toEqual(before);
  });

  it("PREV_ROUND no-ops without activeMatch", () => {
    const before = initialState();
    const after = appReducer(before, { type: "PREV_ROUND" });
    expect(after).toEqual(before);
  });

  it("SHOW_ROUND no-ops without activeMatch", () => {
    const before = initialState();
    const after = appReducer(before, { type: "SHOW_ROUND", index: 0 });
    expect(after).toEqual(before);
  });

  it("SET_STATUS updates status text", () => {
    const after = appReducer(initialState(), { type: "SET_STATUS", status: "Hello" });
    expect(after.status).toBe("Hello");
  });

  it("default action returns unchanged state", () => {
    const before = initialState();
    const after = appReducer(before, { type: "UNKNOWN" as never });
    expect(after).toEqual(before);
  });
});

describe("initialState", () => {
  it("initialState produces fresh state each call", () => {
    const a = initialState();
    const b = initialState();
    expect(a).toEqual(b);
    expect(a).not.toBe(b);
  });
});
