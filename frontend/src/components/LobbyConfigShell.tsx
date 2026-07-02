import type { ReactNode } from "react";
import type { GameAgent } from "@frontend/types";
import { PlayerSetupCard, type PlayerSetupValue } from "./PlayerSetupCard";
import { WandbLoggingSection } from "./WandbLoggingSection";
import { useApp } from "@frontend/hooks/useApp";
import type { WandbLoggingState, WandbLoggingSetters } from "@frontend/hooks/useWandbLoggingConfig";

interface LobbyConfigShellProps {
  players: PlayerSetupValue[];
  onPlayersChange: (players: PlayerSetupValue[]) => void;
  agents: GameAgent[];
  remoteKeys?: Record<string, string> | null;
  onStartGame: (e: React.FormEvent) => Promise<void> | void;
  disabled: boolean;
  running: boolean;
  isReplay: boolean;
  locked: boolean;
  status?: string;
  minPlayers?: number;
  maxPlayers?: number;
  children?: ReactNode;
  wandbLogging?: WandbLoggingState & WandbLoggingSetters;
}

const PLAYER_IDS = ["A", "B", "C", "D", "E", "F", "G", "H", "I", "J"];

export function LobbyConfigShell({
  players,
  onPlayersChange,
  agents,
  remoteKeys,
  onStartGame,
  disabled,
  running,
  isReplay,
  locked,
  status,
  minPlayers = 2,
  maxPlayers = 2,
  children,
  wandbLogging,
}: LobbyConfigShellProps) {
  const { state } = useApp();
  const effectiveStatus = state.sessionStatus;
  const showStartButton = !isReplay;
  // Session is running on the server but the token is gone — user can't resume, must start fresh
  const tokenLost = !state.pendingGame && effectiveStatus === "running";
  const errorMsg = status?.startsWith("error=") ? status.replace("error=", "") : null;
  const infoMsg = status && !status.startsWith("error=") ? status : null;

  const bannerMessage = locked
    ? "Locked — created via API"
    : effectiveStatus === "running"
      ? "Game in progress — switch to the Play tab to continue"
      : effectiveStatus === "failed"
        ? "Session failed — start a new game below"
        : "Completed — replay in Live View";

  const handlePlayerChange = (index: number, value: PlayerSetupValue) => {
    const updated = [...players];
    updated[index] = value;
    onPlayersChange(updated);
  };

  const handleAddPlayer = () => {
    if (players.length >= maxPlayers) return;
    const nextId = PLAYER_IDS[players.length];
    onPlayersChange([
      ...players,
      { agentId: "remote", name: `Remote ${nextId}` },
    ]);
  };

  const handleRemovePlayer = (index: number) => {
    if (players.length <= minPlayers) return;
    onPlayersChange(players.filter((_, i) => i !== index));
  };

  return (
    <form onSubmit={onStartGame} className="flex flex-col gap-0 h-full">
      <div className="flex-1 overflow-y-auto p-4 space-y-5">
        {isReplay && (
          <div className="flex items-center gap-2 px-3 py-2 rounded-lg bg-amber-50 dark:bg-amber-950/30 border border-amber-200 dark:border-amber-800/40">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="text-amber-600 dark:text-amber-400 shrink-0">
              <rect x="3" y="11" width="18" height="11" rx="2" ry="2" />
              <path d="M7 11V7a5 5 0 0 1 10 0v4" />
            </svg>
            <span className="text-xs text-amber-700 dark:text-amber-300 font-semibold">
              {bannerMessage}
            </span>
          </div>
        )}
        {tokenLost && (
          <div className="flex items-center gap-2 px-3 py-2 rounded-lg bg-sky-50 dark:bg-sky-950/30 border border-sky-200 dark:border-sky-800/40">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="text-sky-600 dark:text-sky-400 shrink-0">
              <circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/>
            </svg>
            <span className="text-xs text-sky-700 dark:text-sky-300">
              A session is running but your connection was lost — start a new game below.
            </span>
          </div>
        )}

        {/* Players section */}
        <section>
          <h2 className="text-[10px] font-extrabold text-muted uppercase tracking-widest mb-3 flex items-center gap-2">
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
              <path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2" />
              <circle cx="9" cy="7" r="4" />
              <path d="M23 21v-2a4 4 0 0 0-3-3.87" />
              <path d="M16 3.13a4 4 0 0 1 0 7.75" />
            </svg>
            Players ({players.length})
          </h2>
          <div className="grid gap-3">
            {players.map((player, index) => (
              <PlayerSetupCard
                key={PLAYER_IDS[index]}
                side={PLAYER_IDS[index]}
                value={player}
                agents={agents}
                onChange={(v) => handlePlayerChange(index, v)}
                onRemove={() => handleRemovePlayer(index)}
                canRemove={players.length > minPlayers}
                disabled={disabled}
                remoteKey={remoteKeys?.[PLAYER_IDS[index]]}
              />
            ))}
          </div>
          {players.length < maxPlayers && (
            <button
              type="button"
              onClick={handleAddPlayer}
              disabled={disabled}
              className="mt-3 w-full py-2.5 rounded-xl border-2 border-dashed border-line/50 text-muted text-xs font-bold hover:border-accent/50 hover:text-accent hover:bg-accent/5 transition-all disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-1.5"
            >
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                <line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/>
              </svg>
              Add player
            </button>
          )}
        </section>

        {/* Game Settings section */}
        {children && (
          <section>
            <h2 className="text-[10px] font-extrabold text-muted uppercase tracking-widest mb-3 flex items-center gap-2">
              <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                <circle cx="12" cy="12" r="3" />
                <path d="M19.07 4.93a10 10 0 1 1-14.14 14.14" />
                <path d="M12 2v4" />
                <path d="M12 18v4" />
                <path d="M4.93 4.93l2.83 2.83" />
                <path d="M16.24 16.24l2.83 2.83" />
              </svg>
              Game Settings
            </h2>
            <div className="space-y-3">{children}</div>
          </section>
        )}

        {/* Logging — always rendered for every game */}
        {wandbLogging && (
          <WandbLoggingSection {...wandbLogging} disabled={disabled} />
        )}
      </div>

      {/* Footer: start button + status */}
      <div className="shrink-0 border-t border-line/30 p-4 space-y-2 bg-surface/80">
        {errorMsg && (
          <p className="text-xs text-red-500 text-center">{errorMsg}</p>
        )}
        {infoMsg && !showStartButton && (
          <p className="text-xs text-muted text-center">{infoMsg}</p>
        )}
        {showStartButton && (
          <button
            type="submit"
            disabled={disabled || running}
            className="w-full min-h-[44px] bg-accent text-white rounded-xl font-extrabold text-sm cursor-pointer shadow-lg transition-all duration-150 hover:not-disabled:bg-accent/90 hover:not-disabled:-translate-y-px hover:not-disabled:shadow-xl active:not-disabled:translate-y-0 disabled:cursor-not-allowed disabled:bg-line/50 disabled:text-quiet disabled:shadow-none flex items-center justify-center gap-2"
          >
            {running ? (
              <>
                <svg className="animate-spin w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round">
                  <path d="M21 12a9 9 0 1 1-6.219-8.56" />
                </svg>
                Starting...
              </>
            ) : (
              <>
                <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor">
                  <polygon points="5,3 19,12 5,21" />
                </svg>
                Start Game
              </>
            )}
          </button>
        )}
      </div>
    </form>
  );
}

export type { PlayerSetupValue };
