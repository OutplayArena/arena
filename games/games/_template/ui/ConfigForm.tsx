import { useEffect, useRef, useState } from "react";
import { createExperiment, getGameAgents } from "@frontend/api";
import { randomAgentName } from "@frontend/components/names";
import { useApp } from "@frontend/hooks/useApp";
import type { GameAgent } from "@frontend/types";

const inputClass =
  "w-full min-h-[40px] text-ink bg-surface-container border rounded-input px-[14px] shadow-none transition-[border-color,background,box-shadow] duration-150 outline-none hover:border-accent/40 focus:border-accent focus:bg-surface focus:shadow-[0_0_0_3px_var(--color-accent-soft)] border-line/40";

interface ExampleConfigFormProps {
  gameSlug: string;
  locked: boolean;
  sessionStatus?: string;
  initialValues?: Record<string, unknown>;
}

export default function ExampleConfigForm({ gameSlug, locked, sessionStatus, initialValues }: ExampleConfigFormProps) {
  const { state, startGame } = useApp();
  const initRanRef = useRef(false);
  const [agentAName, setAgentAName] = useState(() => randomAgentName());
  const [agentBName, setAgentBName] = useState(() => randomAgentName());
  const [agentAId, setAgentAId] = useState("random");
  const [agentBId, setAgentBId] = useState("counter");
  const [agents, setAgents] = useState<GameAgent[]>([]);
  const [sessionKeys, setSessionKeys] = useState<Record<string, string> | null>(null);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [status, setStatus] = useState("");
  const [running, setRunning] = useState(false);

  useEffect(() => {
    getGameAgents(gameSlug).then((data) => setAgents(data.agents)).catch(() => {});
  }, []);

  const effectiveLocked = locked || state.sessionLocked;
  const effectiveStatus = sessionStatus || state.sessionStatus;
  const isReplay = effectiveLocked || effectiveStatus === "completed" || effectiveStatus === "running" || effectiveStatus === "failed";
  const formDisabled = effectiveLocked || running || state.pendingGame !== null || effectiveStatus === "completed" || effectiveStatus === "running" || effectiveStatus === "failed";
  const showRunButton = !isReplay && !state.pendingGame;

  useEffect(() => {
    if (initRanRef.current) return;
    if (isReplay && initialValues) {
      initRanRef.current = true;
      if (initialValues.agent_a) setAgentAName(String(initialValues.agent_a));
      if (initialValues.agent_b) setAgentBName(String(initialValues.agent_b));
      if (initialValues.agent_a_id) setAgentAId(String(initialValues.agent_a_id));
      if (initialValues.agent_b_id) setAgentBId(String(initialValues.agent_b_id));
    }
  }, [isReplay, initialValues]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (running) return;

    setRunning(true);
    setSessionKeys(null);
    setSessionId(null);
    setStatus("Creating experiment...");

    const config = {
      game: gameSlug,
      variant: "classic",
      players: 2,
      agents: { A: agentAName.trim(), B: agentBName.trim() },
      interactive: true,
    };

    try {
      const created = await createExperiment(config);
      setSessionId(created.session_id);

      const hasRemote = agentAId === "remote" || agentBId === "remote";
      const remoteKeys: Record<string, string> | null = hasRemote
        ? (() => {
            const keys: Record<string, string> = {};
            if (agentAId === "remote") keys.A = created.player_tokens.A;
            if (agentBId === "remote") keys.B = created.player_tokens.B;
            return keys;
          })()
        : null;

      if (remoteKeys) setSessionKeys(remoteKeys);

      startGame({
        sessionId: created.session_id,
        tokens: created.player_tokens,
        agentAName: agentAName.trim(),
        agentBName: agentBName.trim(),
        agentAId,
        agentBId,
        numRounds: 0,
        numFields: 0,
        totalResources: 0,
        gameSlug,
        remoteKeys,
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
          <span>Agent A</span>
          <select value={agentAId} onChange={(e) => setAgentAId(e.target.value)} className={inputClass} disabled={formDisabled}>
            {agents.map((ag) => <option key={ag.id} value={ag.id}>{ag.label}</option>)}
          </select>
          <input type="text" value={agentAName} onChange={(e) => setAgentAName(e.target.value)} className={inputClass} disabled={formDisabled} placeholder="Agent display name" />
        </label>

        <label className="grid gap-1 text-muted text-[11px] font-extrabold">
          <span>Agent B</span>
          <select value={agentBId} onChange={(e) => setAgentBId(e.target.value)} className={inputClass} disabled={formDisabled}>
            {agents.map((ag) => <option key={ag.id} value={ag.id}>{ag.label}</option>)}
          </select>
          <input type="text" value={agentBName} onChange={(e) => setAgentBName(e.target.value)} className={inputClass} disabled={formDisabled} placeholder="Agent display name" />
        </label>

        <label className="grid gap-1 text-muted text-[11px] font-extrabold">
          <span>num_rounds</span>
          <input type="number" min={1} max={100} defaultValue={10} className={inputClass} disabled={formDisabled} />
        </label>

        <label className="grid gap-1 text-muted text-[11px] font-extrabold">
          <span>seed</span>
          <input type="number" className={inputClass} disabled={formDisabled} placeholder="Random" />
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
          <p className="text-xs text-muted mb-3">
            Pass these to your LLM agents as <code className="bg-ink/8 px-1 rounded text-[11px]">OUTPLAYARENA_KEY</code>.
          </p>
          {Object.entries(sessionKeys).map(([player, key]) => (
            <div key={player} className="mb-2 last:mb-0">
              <div className="flex items-center gap-2">
                <span className="text-[11px] font-extrabold text-muted uppercase">Player {player}</span>
                <span className="text-xs text-ink font-medium">{player === "A" ? agentAName : agentBName}</span>
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
