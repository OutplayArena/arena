import {
  createContext,
  useCallback,
  useEffect,
  useReducer,
  useRef,
} from "react";
import type { ReactNode } from "react";
import type { Match, MatchRound } from "./types";

export interface AppState {
  activeMatch: Match | null;
  activeRoundIndex: number;
  isPlaying: boolean;
  status: string;
  roundDuration: number;
  sessionLocked: boolean;
  sessionStatus: string;
  sessionConfig: {
    agent_a: string;
    agent_b: string;
    num_rounds: number;
    num_battlefields: number;
    total_resources: number;
  } | null;
  pendingGame: {
    sessionId: string;
    tokens: Record<string, string>;
    agentAName: string;
    agentBName: string;
    agentAId: string;
    agentBId: string;
    numRounds: number;
    numFields: number;
    totalResources: number;
    gameSlug: string;
    remoteKeys: Record<string, string> | null;
  } | null;
}

type Action =
  | { type: "SET_MATCH"; match: Match }
  | { type: "SHOW_ROUND"; index: number }
  | { type: "NEXT_ROUND" }
  | { type: "PREV_ROUND" }
  | { type: "TOGGLE_PLAY" }
  | { type: "STOP_PLAY" }
  | { type: "CLEAR_MATCH" }
  | { type: "SET_STATUS"; status: string }
  | { type: "START_GAME"; payload: AppState["pendingGame"] }
  | { type: "END_GAME" }
  | { type: "SET_SESSION_META"; locked: boolean; status: string; config: AppState["sessionConfig"] };

function initialState(): AppState {
  return {
    activeMatch: null,
    activeRoundIndex: -1,
    isPlaying: false,
    status: "Choose agent_a, agent_b, and num_rounds.",
    roundDuration: 3200,
    sessionLocked: false,
    sessionStatus: "",
    sessionConfig: null,
    pendingGame: null,
  };
}

function appReducer(state: AppState, action: Action): AppState {
  switch (action.type) {
    case "SET_MATCH": {
      const sameSession = state.activeMatch?.session_id === action.match.session_id;
      return {
        ...state,
        activeMatch: action.match,
        activeRoundIndex: sameSession
          ? Math.max(0, action.match.history.length - 1)
          : Math.max(0, action.match.history.length - 1),
        isPlaying: !action.match.history.length ? state.isPlaying : true,
        status: sameSession ? state.status : "Running...",
        sessionLocked: sameSession ? state.sessionLocked : false,
        sessionStatus: sameSession ? state.sessionStatus : "",
      };
    }
    case "SHOW_ROUND": {
      if (!state.activeMatch) return state;
      const i = Math.max(
        0,
        Math.min(action.index, state.activeMatch.history.length - 1),
      );
      return { ...state, activeRoundIndex: i };
    }
    case "NEXT_ROUND": {
      if (!state.activeMatch) return state;
      if (
        state.activeRoundIndex >=
        state.activeMatch.history.length - 1
      ) {
        return { ...state, isPlaying: false };
      }
      return { ...state, activeRoundIndex: state.activeRoundIndex + 1 };
    }
    case "PREV_ROUND": {
      if (!state.activeMatch) return state;
      return {
        ...state,
        isPlaying: false,
        activeRoundIndex: Math.max(0, state.activeRoundIndex - 1),
      };
    }
    case "TOGGLE_PLAY":
      if (!state.activeMatch) return state;
      if (state.isPlaying) return { ...state, isPlaying: false };
      if (
        state.activeRoundIndex >=
        state.activeMatch.history.length - 1
      ) {
        return { ...state, activeRoundIndex: 0, isPlaying: true };
      }
      return { ...state, isPlaying: true };
    case "STOP_PLAY":
      return { ...state, isPlaying: false };
    case "START_GAME":
      return { ...state, pendingGame: action.payload, status: "Starting game..." };
    case "END_GAME":
      return { ...state, pendingGame: null };
    case "CLEAR_MATCH":
      return initialState();
    case "SET_STATUS":
      return { ...state, status: action.status };
    case "SET_SESSION_META":
      return {
        ...state,
        sessionLocked: action.locked,
        sessionStatus: action.status,
        sessionConfig: action.config,
      };
    default:
      return state;
  }
}

interface AppContextValue {
  state: AppState;
  dispatch: React.Dispatch<Action>;
  setMatch: (match: Match) => void;
  showRound: (index: number) => void;
  nextRound: () => void;
  prevRound: () => void;
  togglePlay: () => void;
  stopPlay: () => void;
  clearMatch: () => void;
  setStatus: (status: string) => void;
  startGame: (payload: NonNullable<AppState["pendingGame"]>) => void;
  endGame: () => void;
  setSessionMeta: (locked: boolean, status: string, config: AppState["sessionConfig"]) => void;
  currentRound: () => MatchRound | null;
}

const AppContext = createContext<AppContextValue | null>(null);
export { AppContext };
export type { AppContextValue };

export function AppProvider({ children }: { children: ReactNode }) {
  const [state, dispatch] = useReducer(appReducer, null, initialState);
  const stateRef = useRef(state);

  useEffect(() => {
    stateRef.current = state;
  }, [state]);

  const setMatch = useCallback(
    (match: Match) => dispatch({ type: "SET_MATCH", match }),
    [],
  );
  const showRound = useCallback(
    (index: number) => dispatch({ type: "SHOW_ROUND", index }),
    [],
  );
  const nextRound = useCallback(
    () => dispatch({ type: "NEXT_ROUND" }),
    [],
  );
  const prevRound = useCallback(
    () => dispatch({ type: "PREV_ROUND" }),
    [],
  );
  const togglePlay = useCallback(
    () => dispatch({ type: "TOGGLE_PLAY" }),
    [],
  );
  const stopPlay = useCallback(
    () => dispatch({ type: "STOP_PLAY" }),
    [],
  );
  const clearMatch = useCallback(
    () => dispatch({ type: "CLEAR_MATCH" }),
    [],
  );
  const setStatus = useCallback(
    (status: string) => dispatch({ type: "SET_STATUS", status }),
    [],
  );
  const setSessionMeta = useCallback(
    (locked: boolean, status: string, config: AppState["sessionConfig"]) =>
      dispatch({ type: "SET_SESSION_META", locked, status, config }),
    [],
  );
  const currentRound = useCallback((): MatchRound | null => {
    const s = stateRef.current;
    if (!s.activeMatch) return null;
    return s.activeMatch.history[s.activeRoundIndex] ?? null;
  }, []);
  const startGame = useCallback(
    (payload: NonNullable<AppState["pendingGame"]>) =>
      dispatch({ type: "START_GAME", payload }),
    [],
  );
  const endGame = useCallback(
    () => dispatch({ type: "END_GAME" }),
    [],
  );

  return (
    <AppContext.Provider
      value={{
        state,
        dispatch,
        setMatch,
        showRound,
        nextRound,
        prevRound,
        togglePlay,
        stopPlay,
        clearMatch,
        setStatus,
        setSessionMeta,
        currentRound,
        startGame,
        endGame,
      }}
    >
      {children}
    </AppContext.Provider>
  );
}
