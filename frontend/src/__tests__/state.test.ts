import { describe, it, expect } from "vitest";
import { appReducer, initialState } from "../state";
import type { AppState, Action } from "../state";

function freshState(): AppState {
  return initialState();
}

function createMockAppState(overrides: Partial<AppState> = {}): AppState {
  return { ...freshState(), ...overrides };
}

describe("appReducer", () => {
  describe("initial state", () => {
    it("returns default state for unknown action", () => {
      const state = freshState();
      expect(state.activeMatch).toBeNull();
      expect(state.activeRoundIndex).toBe(-1);
      expect(state.isPlaying).toBe(false);
      expect(state.pendingGame).toBeNull();
      expect(state.sessionLocked).toBe(false);
      expect(state.sessionStatus).toBe("");
    });
  });

  describe("SET_MATCH", () => {
    it("sets the match and positions at last round", () => {
      const match = {
        agent_a: "foo", agent_b: "bar", session_id: "s1", config_hash: "h1",
        num_rounds: 3, num_battlefields: 5, total_resources: 100,
        total_score_a: 0, total_score_b: 0, metrics: {},
        history: [
          { round: 1, agent_a: "foo", agent_b: "bar", action_a: [], action_b: [], score_a: 0, score_b: 0, total_score_a: 0, total_score_b: 0, winner: "Tie" as const },
          { round: 2, agent_a: "foo", agent_b: "bar", action_a: [], action_b: [], score_a: 0, score_b: 0, total_score_a: 0, total_score_b: 0, winner: "Tie" as const },
        ],
      };

      const state = appReducer(freshState(), { type: "SET_MATCH", match });
      expect(state.activeMatch).toBe(match);
      expect(state.activeRoundIndex).toBe(1);
      expect(state.isPlaying).toBe(true);
    });

    it("keeps index on same session update", () => {
      const match = {
        agent_a: "foo", agent_b: "bar", session_id: "s1", config_hash: "h1",
        num_rounds: 3, num_battlefields: 5, total_resources: 100,
        total_score_a: 0, total_score_b: 0, metrics: {},
        history: [
          { round: 1, agent_a: "foo", agent_b: "bar", action_a: [], action_b: [], score_a: 0, score_b: 0, total_score_a: 0, total_score_b: 0, winner: "Tie" as const },
        ],
      };
      const prev = appReducer(freshState(), { type: "SET_MATCH", match });
      expect(prev.activeRoundIndex).toBe(0);

      const updated = { ...match, history: [...match.history, { round: 2, agent_a: "foo", agent_b: "bar", action_a: [], action_b: [], score_a: 0, score_b: 0, total_score_a: 0, total_score_b: 0, winner: "Tie" as const }] };
      const next = appReducer(prev, { type: "SET_MATCH", match: updated });
      expect(next.activeRoundIndex).toBe(1);
    });
  });

  describe("SHOW_ROUND", () => {
    it("clamps to valid range", () => {
      const state = createMockAppState({
        activeMatch: {
          agent_a: "a", agent_b: "b", session_id: "s", config_hash: "h",
          num_rounds: 3, num_battlefields: 1, total_resources: 1,
          total_score_a: 0, total_score_b: 0, metrics: {},
          history: [
            { round: 1, agent_a: "a", agent_b: "b", action_a: [], action_b: [], score_a: 0, score_b: 0, total_score_a: 0, total_score_b: 0, winner: "Tie" },
            { round: 2, agent_a: "a", agent_b: "b", action_a: [], action_b: [], score_a: 0, score_b: 0, total_score_a: 0, total_score_b: 0, winner: "Tie" },
          ],
        },
      });

      expect(appReducer(state, { type: "SHOW_ROUND", index: -5 }).activeRoundIndex).toBe(0);
      expect(appReducer(state, { type: "SHOW_ROUND", index: 5 }).activeRoundIndex).toBe(1);
    });
  });

  describe("NEXT_ROUND", () => {
    it("increments round index", () => {
      const state = createMockAppState({
        activeMatch: {
          agent_a: "a", agent_b: "b", session_id: "s", config_hash: "h",
          num_rounds: 3, num_battlefields: 1, total_resources: 1,
          total_score_a: 0, total_score_b: 0, metrics: {},
          history: [
            { round: 1, agent_a: "a", agent_b: "b", action_a: [], action_b: [], score_a: 0, score_b: 0, total_score_a: 0, total_score_b: 0, winner: "Tie" },
            { round: 2, agent_a: "a", agent_b: "b", action_a: [], action_b: [], score_a: 0, score_b: 0, total_score_a: 0, total_score_b: 0, winner: "Tie" },
          ],
        },
        activeRoundIndex: 0,
      });

      const result = appReducer(state, { type: "NEXT_ROUND" });
      expect(result.activeRoundIndex).toBe(1);
    });

    it("stops playing at last round", () => {
      const state = createMockAppState({
        activeMatch: {
          agent_a: "a", agent_b: "b", session_id: "s", config_hash: "h",
          num_rounds: 2, num_battlefields: 1, total_resources: 1,
          total_score_a: 0, total_score_b: 0, metrics: {},
          history: [
            { round: 1, agent_a: "a", agent_b: "b", action_a: [], action_b: [], score_a: 0, score_b: 0, total_score_a: 0, total_score_b: 0, winner: "Tie" },
          ],
        },
        activeRoundIndex: 0,
        isPlaying: true,
      });

      const result = appReducer(state, { type: "NEXT_ROUND" });
      expect(result.isPlaying).toBe(false);
    });
  });

  describe("PREV_ROUND", () => {
    it("decrements and stops playback", () => {
      const state = createMockAppState({
        activeMatch: {
          agent_a: "a", agent_b: "b", session_id: "s", config_hash: "h",
          num_rounds: 3, num_battlefields: 1, total_resources: 1,
          total_score_a: 0, total_score_b: 0, metrics: {},
          history: [
            { round: 1, agent_a: "a", agent_b: "b", action_a: [], action_b: [], score_a: 0, score_b: 0, total_score_a: 0, total_score_b: 0, winner: "Tie" },
            { round: 2, agent_a: "a", agent_b: "b", action_a: [], action_b: [], score_a: 0, score_b: 0, total_score_a: 0, total_score_b: 0, winner: "Tie" },
          ],
        },
        activeRoundIndex: 1,
        isPlaying: true,
      });

      const result = appReducer(state, { type: "PREV_ROUND" });
      expect(result.activeRoundIndex).toBe(0);
      expect(result.isPlaying).toBe(false);
    });
  });

  describe("TOGGLE_PLAY", () => {
    it("starts playing from current position", () => {
      const state = createMockAppState({
        activeMatch: {
          agent_a: "a", agent_b: "b", session_id: "s", config_hash: "h",
          num_rounds: 3, num_battlefields: 1, total_resources: 1,
          total_score_a: 0, total_score_b: 0, metrics: {},
          history: [
            { round: 1, agent_a: "a", agent_b: "b", action_a: [], action_b: [], score_a: 0, score_b: 0, total_score_a: 0, total_score_b: 0, winner: "Tie" },
          ],
        },
        isPlaying: false,
      });
      expect(appReducer(state, { type: "TOGGLE_PLAY" }).isPlaying).toBe(true);
    });

    it("stops when already playing", () => {
      const state = createMockAppState({
        activeMatch: {
          agent_a: "a", agent_b: "b", session_id: "s", config_hash: "h",
          num_rounds: 2, num_battlefields: 1, total_resources: 1,
          total_score_a: 0, total_score_b: 0, metrics: {},
          history: [
            { round: 1, agent_a: "a", agent_b: "b", action_a: [], action_b: [], score_a: 0, score_b: 0, total_score_a: 0, total_score_b: 0, winner: "Tie" },
          ],
        },
        isPlaying: true,
      });
      expect(appReducer(state, { type: "TOGGLE_PLAY" }).isPlaying).toBe(false);
    });

    it("restarts from round 0 when at end", () => {
      const state = createMockAppState({
        activeMatch: {
          agent_a: "a", agent_b: "b", session_id: "s", config_hash: "h",
          num_rounds: 2, num_battlefields: 1, total_resources: 1,
          total_score_a: 0, total_score_b: 0, metrics: {},
          history: [
            { round: 1, agent_a: "a", agent_b: "b", action_a: [], action_b: [], score_a: 0, score_b: 0, total_score_a: 0, total_score_b: 0, winner: "Tie" },
          ],
        },
        activeRoundIndex: 0,
        isPlaying: false,
      });

      const result = appReducer(state, { type: "TOGGLE_PLAY" });
      expect(result.isPlaying).toBe(true);
      expect(result.activeRoundIndex).toBe(0);
    });
  });

  describe("STOP_PLAY", () => {
    it("sets isPlaying to false", () => {
      const state = createMockAppState({ isPlaying: true });
      expect(appReducer(state, { type: "STOP_PLAY" }).isPlaying).toBe(false);
    });
  });

  describe("START_GAME / END_GAME", () => {
    it("sets pendingGame on START_GAME", () => {
      const payload = {
        sessionId: "s1",
        tokens: { A: "tA", B: "tB" },
        agentAName: "AgentA",
        agentBName: "AgentB",
        agentAId: "uniform",
        agentBId: "greedy",
        numRounds: 10,
        numFields: 5,
        totalResources: 100,
        gameSlug: "colonelblotto",
        remoteKeys: null,
      };

      const state = appReducer(freshState(), { type: "START_GAME", payload });
      expect(state.pendingGame).toEqual(payload);
      expect(state.status).toBe("Starting game...");
    });

    it("clears pendingGame on END_GAME", () => {
      const withPending = createMockAppState({
        pendingGame: {
          sessionId: "s1", tokens: {}, agentAName: "a", agentBName: "b",
          agentAId: "u", agentBId: "g", numRounds: 5, numFields: 5,
          totalResources: 100, gameSlug: "blotto", remoteKeys: null,
        },
      });
      const result = appReducer(withPending, { type: "END_GAME" });
      expect(result.pendingGame).toBeNull();
    });
  });

  describe("CLEAR_MATCH", () => {
    it("returns initial state", () => {
      const state = createMockAppState({ status: "Some status", isPlaying: true });
      const cleared = appReducer(state, { type: "CLEAR_MATCH" });
      expect(cleared.activeMatch).toBeNull();
      expect(cleared.isPlaying).toBe(false);
      expect(cleared.pendingGame).toBeNull();
    });
  });

  describe("SET_SESSION_META", () => {
    it("sets lock, status and config", () => {
      const config = { agent_a: "a", agent_b: "b", num_rounds: 3, num_battlefields: 5, total_resources: 100 };
      const result = appReducer(freshState(), { type: "SET_SESSION_META", locked: true, status: "completed", config });
      expect(result.sessionLocked).toBe(true);
      expect(result.sessionStatus).toBe("completed");
      expect(result.sessionConfig).toEqual(config);
    });
  });
});
