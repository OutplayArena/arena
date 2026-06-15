import { useEffect, useRef, useState } from "react";
import { createExperiment, getGameAgents } from "@frontend/api";
import { randomAgentName } from "@frontend/components/names";
import { useApp } from "@frontend/hooks/useApp";
import type { GameAgent } from "@frontend/types";

const inputClass =
  "w-full min-h-[40px] text-ink bg-surface-container border rounded-input px-[14px] shadow-none transition-[border-color,background,box-shadow] duration-150 outline-none hover:border-accent/40 focus:border-accent focus:bg-surface focus:shadow-[0_0_0_3px_var(--color-accent-soft)] border-line/40";

const PLAYER_IDS = ["A", "B", "C", "D", "E", "F"];

interface PGGConfigFormProps {
  gameSlug: string;
  locked: boolean;
  sessionStatus?: string;
  initialValues?: Record<string, unknown>;
}

export default function PGGConfigForm({ gameSlug, locked, sessionStatus, initialValues }: PGGConfigFormProps) {
  const { state, startGame } = useApp();
  const initRanRef = useRef(false);
  const [numPlayers, setNumPlayers] = useState(4);
  const [variant, setVariant] = useState("classic");
  const [agents, setAgents] = useState<GameAgent[]>([]);
  const [playerNames, setPlayerNames] = useState<Record<string, string>>(() =>
    Object.fromEntries(PLAYER_IDS.map((id) => [id, randomAgentName()]))
  );
  const [playerAgentIds, setPlayerAgentIds] = useState<Record<string, string>>(() =>
    Object.fromEntries(PLAYER_IDS.map((id, i) => [id, i === 0 ? "always_max" : i === 1 ? "always_zero" : "conditional_cooperator"]))
  );
  const roundsRef = useRef<HTMLInputElement>(null);
  const endowmentRef = useRef<HTMLInputElement>(null);
  const multiplierRef = useRef<HTMLInputElement>(null);
  const seedRef = useRef<HTMLInputElement>(null);
  const [sessionKeys, setSessionKeys] = useState<Record<string, string> | null>(null);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [status, setStatus] = useState("");
  const [running, setRunning] = useState(false);

  useEffect(() => {
    getGameAgents(gameSlug).then((data) => setAgents(data.agents)).catch(() => {});
  }, [gameSlug]);

  const isReplay = locked || sessionStatus === "completed";
  const formDisabled = locked || running || state.pendingGame !== null || sessionStatus === "completed" || sessionStatus === "running";

  useEffect(() => {
    if (initRanRef.current) return;
    if (isReplay && initialValues) {
      initRanRef.current = true;
      if (roundsRef.current && initialValues.rounds !== undefined) roundsRef.current.value = String(initialValues.rounds);
      if (seedRef.current && initialValues.seed !== undefined && initialValues.seed !== null) seedRef.current.value = String(initialValues.seed);
    }
  }, [isReplay, initialValues]);

  const activePlayers = PLAYER_IDS.slice(0, numPlayers);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (running || !roundsRef.current) return;

    const numRounds = Number(roundsRef.current.value);
    const seedVal = seedRef.current?.value ? Number(seedRef.current.value) : null;

    setRunning(true);
    setSessionKeys(null);
    setSessionId(null);
    setStatus("Creating experiment...");

    const agentsMap = Object.fromEntries(activePlayers.map((id) => [id, (playerNames[id] || id).trim()]));
    const agentIdsMap = Object.fromEntries(activePlayers.map((id) => [id, playerAgentIds[id] || "random"]));

    const config = {
      game: gameSlug,
      variant,
      players: numPlayers,
      rounds: numRounds,
      seed: seedVal,
      agents: agentsMap,
      interactive: true,
      endowment: endowmentRef.current ? Number(endowmentRef.current.value) : 10.0,
      multiplier: multiplierRef.current ? Number(multiplierRef.current.value) : 2.0,
    };

    try {
      const created = await createExperiment(config);
      setSessionId(created.session_id);

      const hasRemote = Object.values(agentIdsMap).includes("remote");
      const remoteKeys: Record<string, string> | null = hasRemote
        ? Object.fromEntries(
            activePlayers
              .filter((id) => agentIdsMap[id] === "remote")
              .map((id) => [id, created.player_tokens[id]])
          )
        : null;

      if (remoteKeys) setSessionKeys(remoteKeys);

      startGame({
        sessionId: created.session_id,
        tokens: created.player_tokens,
        agentAName: agentsMap.A,
        agentBName: agentsMap.B,
        agentAId: agentIdsMap.A,
        agentBId: agentIdsMap.B,
        numRounds,
        numFields: 0,
        totalResources: 0,
        gameSlug,
        remoteKeys,
        playerNames: agentsMap,
        agentIds: agentIdsMap,
      });
      setStatus("Game started — switch to Live View to watch.");
    } catch (err) {
      setStatus(`error=${err instanceof Error ? err.message : String(err)}`);
    } finally {
      setRunning(false);
    }
  };

  return (
    <div>
      <form className="grid gap-3 p-4" onSubmit={handleSubmit}>
        {isReplay && (
          <div className="flex items-center gap-2 px-3 py-2 rounded bg-amber-50 dark:bg-amber-950/30 border border-amber-200 dark:border-amber-800/50">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="text-amber-600 dark:text-amber-400 shrink-0">
              <rect x="3" y="11" width="18" height="11" rx="2" ry="2" />
              <path d="M7 11V7a5 5 0 0 1 10 0v4" />
            </svg>
            <span className="text-xs text-amber-700 dark:text-amber-300 font-semibold">{locked ? "Locked. Game was created via programmatic API" : "Completed. Replay in Live View only"}</span>
          </div>
        )}

        <label className="grid gap-1 text-muted text-[11px] font-extrabold">
          <span>variant</span>
          <select value={variant} onChange={(e) => setVariant(e.target.value)} className={inputClass} disabled={formDisabled}>
            <option value="classic">Classic</option>
            <option value="punishment">With Punishment</option>
          </select>
        </label>

        <label className="grid gap-1 text-muted text-[11px] font-extrabold">
          <span>num_players (3–6)</span>
          <select value={numPlayers} onChange={(e) => setNumPlayers(Number(e.target.value))} className={inputClass} disabled={formDisabled}>
            {[3, 4, 5, 6].map((n) => <option key={n} value={n}>{n} players</option>)}
          </select>
        </label>

        <div className="grid gap-1">
          <span className="text-muted text-[11px] font-extrabold">Players</span>
          <div className="grid gap-2">
            {activePlayers.map((id) => (
              <div key={id} className="grid gap-1 pl-2 border-l-2 border-line/40">
                <span className="text-[10px] font-extrabold text-muted uppercase">Player {id}</span>
                <select
                  value={playerAgentIds[id] || "random"}
                  onChange={(e) => setPlayerAgentIds((prev) => ({ ...prev, [id]: e.target.value }))}
                  className={inputClass}
                  disabled={formDisabled}
                >
                  {agents.map((ag) => <option key={ag.id} value={ag.id}>{ag.label}</option>)}
                </select>
                <input
                  type="text"
                  value={playerNames[id] || ""}
                  onChange={(e) => setPlayerNames((prev) => ({ ...prev, [id]: e.target.value }))}
                  className={inputClass}
                  disabled={formDisabled}
                  placeholder={`Player ${id} display name`}
                />
              </div>
            ))}
          </div>
        </div>

        <label className="grid gap-1 text-muted text-[11px] font-extrabold">
          <span>num_rounds</span>
          <input ref={roundsRef} type="number" min={1} max={100} defaultValue={10} className={inputClass} disabled={formDisabled} />
        </label>

        <div className="grid grid-cols-2 gap-2">
          <label className="grid gap-1 text-muted text-[11px] font-extrabold">
            <span>endowment</span>
            <input ref={endowmentRef} type="number" step="1" min={1} defaultValue={10} className={inputClass} disabled={formDisabled} />
          </label>
          <label className="grid gap-1 text-muted text-[11px] font-extrabold">
            <span>multiplier r</span>
            <input ref={multiplierRef} type="number" step="0.1" min={1.0} defaultValue={2.0} className={inputClass} disabled={formDisabled} />
          </label>
        </div>

        <label className="grid gap-1 text-muted text-[11px] font-extrabold">
          <span>seed</span>
          <input ref={seedRef} type="number" className={inputClass} disabled={formDisabled} placeholder="Random" />
        </label>

        {!isReplay && !state.pendingGame && (
          <button
            type="submit"
            disabled={running}
            className="min-h-[42px] bg-accent border-accent text-white rounded-input px-6 font-extrabold cursor-pointer shadow-elevation-3 transition-[transform,background,border-color,box-shadow] duration-150 hover:not-disabled:-translate-y-px hover:not-disabled:shadow-elevation-4 active:not-disabled:translate-y-0.5 disabled:cursor-not-allowed disabled:bg-line/50 disabled:border-line/50 disabled:text-quiet disabled:shadow-none mt-1"
          >
            {running ? "Running..." : "Run Experiment"}
          </button>
        )}

        {status && !status.startsWith("error=") && (
          <div className="text-xs text-muted text-center">{status}</div>
        )}
        {status && status.startsWith("error=") && (
          <div className="text-xs text-red-500 text-center">{status.replace("error=", "")}</div>
        )}
      </form>

      {sessionKeys && Object.keys(sessionKeys).length > 0 && (
        <div className="mx-4 mb-4 p-4 rounded-card border border-line/40 bg-surface-container/30">
          <h3 className="text-sm font-extrabold text-ink mb-2">Remote Agent Keys</h3>
          <p className="text-xs text-muted mb-3">Pass these to your LLM agents as <code className="bg-ink/8 px-1 rounded text-[11px]">NASH_ARENA_KEY</code>.</p>
          {Object.entries(sessionKeys).map(([player, key]) => (
            <div key={player} className="mb-2 last:mb-0">
              <div className="flex items-center gap-2">
                <span className="text-[11px] font-extrabold text-muted uppercase">Player {player}</span>
                <span className="text-xs text-ink font-medium">{playerNames[player]}</span>
              </div>
              <code className="text-[11px] bg-ink/6 px-2 py-1.5 rounded text-ink break-all font-mono block mt-1">{key}</code>
            </div>
          ))}
        </div>
      )}

      {sessionId && !sessionKeys && (
        <div className="mx-4 mb-4 text-xs text-muted">
          Session: <code className="bg-ink/6 px-1 rounded font-mono">{sessionId}</code>
        </div>
      )}
    </div>
  );
}
