import { useEffect, useRef, useState } from "react";
import { createExperiment, getGameAgents } from "@frontend/api";
import { randomAgentName } from "@frontend/components/names";
import { useApp } from "@frontend/hooks/useApp";
import type { GameAgent } from "@frontend/types";

const inputClass =
  "w-full min-h-[40px] text-ink bg-surface-container border rounded-input px-[14px] shadow-none transition-[border-color,background,box-shadow] duration-150 outline-none hover:border-accent/40 focus:border-accent focus:bg-surface focus:shadow-[0_0_0_3px_var(--color-accent-soft)] border-line/40";

interface CournotConfigFormProps {
  gameSlug: string;
  locked: boolean;
  sessionStatus?: string;
  initialValues?: Record<string, unknown>;
}

export default function CournotConfigForm({ gameSlug, locked, sessionStatus, initialValues }: CournotConfigFormProps) {
  const { state, startGame } = useApp();
  const initRanRef = useRef(false);
  const [playerAName, setPlayerAName] = useState(() => randomAgentName());
  const [playerBName, setPlayerBName] = useState(() => randomAgentName());
  const [playerAId, setPlayerAId] = useState("collusive");
  const [playerBId, setPlayerBId] = useState("nash");
  const [agents, setAgents] = useState<GameAgent[]>([]);
  const roundsRef = useRef<HTMLInputElement>(null);
  const demandARef = useRef<HTMLInputElement>(null);
  const demandBRef = useRef<HTMLInputElement>(null);
  const costRef = useRef<HTMLInputElement>(null);
  const maxQRef = useRef<HTMLInputElement>(null);
  const seedRef = useRef<HTMLInputElement>(null);
  const [sessionKeys, setSessionKeys] = useState<Record<string, string> | null>(null);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [status, setStatus] = useState("");
  const [running, setRunning] = useState(false);

  useEffect(() => {
    getGameAgents(gameSlug).then((data) => setAgents(data.agents)).catch(() => {});
  }, [gameSlug]);

  const effectiveLocked = locked || state.sessionLocked;
  const effectiveStatus = sessionStatus || state.sessionStatus;
  const isReplay = effectiveLocked || effectiveStatus === "completed" || effectiveStatus === "running" || effectiveStatus === "failed";
  const formDisabled = effectiveLocked || running || state.pendingGame !== null || effectiveStatus === "completed" || effectiveStatus === "running" || effectiveStatus === "failed";
  const showRunButton = !isReplay && !state.pendingGame;

  useEffect(() => {
    if (initRanRef.current) return;
    if (isReplay && initialValues) {
      initRanRef.current = true;
      if (initialValues.agent_a) setPlayerAName(String(initialValues.agent_a));
      if (initialValues.agent_b) setPlayerBName(String(initialValues.agent_b));
      if (initialValues.agent_a_id) setPlayerAId(String(initialValues.agent_a_id));
      if (initialValues.agent_b_id) setPlayerBId(String(initialValues.agent_b_id));
      if (roundsRef.current && initialValues.rounds !== undefined) roundsRef.current.value = String(initialValues.rounds);
      if (seedRef.current && initialValues.seed !== undefined && initialValues.seed !== null) seedRef.current.value = String(initialValues.seed);
    }
  }, [isReplay, initialValues]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (running || !roundsRef.current) return;

    const numRounds = Number(roundsRef.current.value);
    const seedVal = seedRef.current?.value ? Number(seedRef.current.value) : null;

    setRunning(true);
    setSessionKeys(null);
    setSessionId(null);
    setStatus("Creating experiment...");

    const config = {
      game: gameSlug,
      variant: "classic",
      players: 2,
      rounds: numRounds,
      seed: seedVal,
      agents: { A: playerAName.trim(), B: playerBName.trim() },
      interactive: playerAId === "interactive" || playerBId === "interactive",
      demand_a: demandARef.current ? Number(demandARef.current.value) : 120.0,
      demand_b: demandBRef.current ? Number(demandBRef.current.value) : 1.0,
      cost_per_unit: costRef.current ? Number(costRef.current.value) : 0.0,
      max_quantity: maxQRef.current ? Number(maxQRef.current.value) : 120.0,
    };

    try {
      const created = await createExperiment(config);
      setSessionId(created.session_id);

      const hasRemote = playerAId === "remote" || playerBId === "remote";
      const remoteKeys: Record<string, string> | null = hasRemote
        ? (() => {
            const keys: Record<string, string> = {};
            if (playerAId === "remote") keys.A = created.player_tokens.A;
            if (playerBId === "remote") keys.B = created.player_tokens.B;
            return keys;
          })()
        : null;

      if (remoteKeys) setSessionKeys(remoteKeys);

      const isInteractive = playerAId === "interactive" || playerBId === "interactive";

      startGame({
        sessionId: created.session_id,
        tokens: created.player_tokens,
        agentAName: playerAName.trim(),
        agentBName: playerBName.trim(),
        agentAId: playerAId,
        agentBId: playerBId,
        numRounds,
        numFields: 0,
        totalResources: 0,
        gameSlug,
        remoteKeys,
        interactive: isInteractive,
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
          <span>Player A</span>
          <select
            value={playerAId}
            onChange={(e) => {
              setPlayerAId(e.target.value);
              if (e.target.value === "interactive") {
                setPlayerAName("You");
              }
            }}
            className={inputClass}
            disabled={formDisabled}
          >
            <option value="interactive">Interactive (Human Player)</option>
            {agents.map((ag) => <option key={ag.id} value={ag.id}>{ag.label}</option>)}
          </select>
          <input type="text" value={playerAName} onChange={(e) => setPlayerAName(e.target.value)} className={inputClass} disabled={formDisabled || playerAId === "interactive"} placeholder="Player display name" />
        </label>

        <label className="grid gap-1 text-muted text-[11px] font-extrabold">
          <span>Player B</span>
          <select
            value={playerBId}
            onChange={(e) => {
              setPlayerBId(e.target.value);
              if (e.target.value === "interactive") {
                setPlayerBName("You");
              }
            }}
            className={inputClass}
            disabled={formDisabled}
          >
            <option value="interactive">Interactive (Human Player)</option>
            {agents.map((ag) => <option key={ag.id} value={ag.id}>{ag.label}</option>)}
          </select>
          <input type="text" value={playerBName} onChange={(e) => setPlayerBName(e.target.value)} className={inputClass} disabled={formDisabled || playerBId === "interactive"} placeholder="Player display name" />
        </label>

        <label className="grid gap-1 text-muted text-[11px] font-extrabold">
          <span>num_rounds</span>
          <input ref={roundsRef} type="number" min={1} max={100} defaultValue={10} className={inputClass} disabled={formDisabled} />
        </label>

        <div className="grid gap-1">
          <span className="text-muted text-[11px] font-extrabold">Market parameters</span>
          <p className="text-[10px] text-quiet -mt-0.5">P = max(0, a − b·(q₁+q₂))</p>
          <div className="grid grid-cols-2 gap-2">
            <label className="grid gap-0.5">
              <span className="text-[10px] text-quiet font-semibold">demand_a (intercept)</span>
              <input ref={demandARef} type="number" step="10" defaultValue={120} className={inputClass} disabled={formDisabled} />
            </label>
            <label className="grid gap-0.5">
              <span className="text-[10px] text-quiet font-semibold">demand_b (slope)</span>
              <input ref={demandBRef} type="number" step="0.1" min={0.1} defaultValue={1.0} className={inputClass} disabled={formDisabled} />
            </label>
            <label className="grid gap-0.5">
              <span className="text-[10px] text-quiet font-semibold">cost_per_unit</span>
              <input ref={costRef} type="number" step="1" min={0} defaultValue={0} className={inputClass} disabled={formDisabled} />
            </label>
            <label className="grid gap-0.5">
              <span className="text-[10px] text-quiet font-semibold">max_quantity</span>
              <input ref={maxQRef} type="number" step="10" min={1} defaultValue={120} className={inputClass} disabled={formDisabled} />
            </label>
          </div>
        </div>

        <label className="grid gap-1 text-muted text-[11px] font-extrabold">
          <span>seed</span>
          <input ref={seedRef} type="number" className={inputClass} disabled={formDisabled} placeholder="Random" />
        </label>

        {showRunButton && (
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
                <span className="text-xs text-ink font-medium">{player === "A" ? playerAName : playerBName}</span>
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
