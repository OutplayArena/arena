import { useEffect, useRef, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { createExperiment, getGameAgents } from "@frontend/api";
import { buildBattlefields, copyToClipboard } from "@frontend/components/utils";
import { randomAgentName } from "@frontend/components/names";
import { useApp } from "@frontend/hooks/useApp";
import type { GameAgent } from "@frontend/types";

const inputClass =
  "w-full min-h-[40px] text-ink bg-surface-container border rounded-input px-[14px] shadow-none transition-[border-color,background,box-shadow] duration-150 outline-none hover:border-accent/40 focus:border-accent focus:bg-surface focus:shadow-[0_0_0_3px_var(--color-accent-soft)] border-line/40";

interface BlottoConfigFormProps {
  gameSlug: string;
  locked: boolean;
  sessionStatus?: string;
  initialValues?: Record<string, unknown>;
}

export default function BlottoConfigForm({ gameSlug, locked, sessionStatus, initialValues }: BlottoConfigFormProps) {
  const { state, setMatch, stopPlay, startGame } = useApp();
  const [searchParams] = useSearchParams();
  const initRanRef = useRef(false);
  const [agentAName, setAgentAName] = useState(() => randomAgentName());
  const [agentBName, setAgentBName] = useState(() => randomAgentName());
  const [agentAId, setAgentAId] = useState("uniform");
  const [agentBId, setAgentBId] = useState("greedy");

  const [agents, setAgents] = useState<GameAgent[]>([]);
  const roundsRef = useRef<HTMLInputElement>(null);
  const fieldsRef = useRef<HTMLInputElement>(null);
  const resourcesRef = useRef<HTMLInputElement>(null);
  const seedRef = useRef<HTMLInputElement>(null);
  const btnRef = useRef<HTMLButtonElement>(null);
  const [sessionKeys, setSessionKeys] = useState<Record<string, string> | null>(null);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [status, setStatus] = useState("");
  const [running, setRunning] = useState(false);

  useEffect(() => {
    const agentA = searchParams.get("agent_a");
    const agentB = searchParams.get("agent_b");
    const rounds = searchParams.get("rounds");
    const fields = searchParams.get("fields");
    const resources = searchParams.get("resources");
    if (agentA) setAgentAName(agentA);
    if (agentB) setAgentBName(agentB);
    if (rounds && roundsRef.current) roundsRef.current.value = rounds;
    if (fields && fieldsRef.current) fieldsRef.current.value = fields;
    if (resources && resourcesRef.current) resourcesRef.current.value = resources;
  }, [searchParams]);

  useEffect(() => {
    getGameAgents(gameSlug).then((data) => setAgents(data.agents)).catch(() => {});
  }, []);

  const isReplay = locked || sessionStatus === "completed";
  const formDisabled = locked || running || state.pendingGame !== null || sessionStatus === "completed" || sessionStatus === "running";

  useEffect(() => {
    if (initRanRef.current) return;
    if (isReplay && initialValues) {
      initRanRef.current = true;
      if (initialValues.agent_a) setAgentAName(String(initialValues.agent_a));
      if (initialValues.agent_b) setAgentBName(String(initialValues.agent_b));
      if (initialValues.agent_a_id) setAgentAId(String(initialValues.agent_a_id));
      if (initialValues.agent_b_id) setAgentBId(String(initialValues.agent_b_id));
      if (roundsRef.current && initialValues.rounds !== undefined) roundsRef.current.value = String(initialValues.rounds);
      if (fieldsRef.current && initialValues.num_battlefields !== undefined) fieldsRef.current.value = String(initialValues.num_battlefields);
      if (resourcesRef.current && initialValues.total_resources !== undefined) resourcesRef.current.value = String(initialValues.total_resources);
      if (seedRef.current && initialValues.seed !== undefined && initialValues.seed !== null) seedRef.current.value = String(initialValues.seed);
    }
  }, [isReplay, initialValues]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (running || !roundsRef.current || !fieldsRef.current || !resourcesRef.current) return;

    const numRounds = Number(roundsRef.current.value);
    const numFields = Number(fieldsRef.current.value);
    const totalResources = Number(resourcesRef.current.value);
    const seedVal = seedRef.current?.value ? Number(seedRef.current.value) : null;

    if (totalResources < numFields) {
      setStatus("error=total_resources must be >= num_battlefields");
      return;
    }

    setRunning(true);
    setSessionKeys(null);
    setSessionId(null);
    setStatus("Creating experiment...");

    const config = {
      game: gameSlug,
      variant: "classic",
      players: 2,
      budget: [totalResources, totalResources] as [number, number],
      battlefields: buildBattlefields(numFields),
      rounds: numRounds,
      seed: seedVal,
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
        numRounds,
        numFields,
        totalResources,
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
    <div className="overflow-y-auto overscroll-contain">
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
          <select
            value={agentAId}
            onChange={(e) => setAgentAId(e.target.value)}
            className={inputClass}
            disabled={formDisabled}
          >
            {agents.map((ag) => (
              <option key={ag.id} value={ag.id}>{ag.label}</option>
            ))}
          </select>
          <input
            type="text"
            value={agentAName}
            onChange={(e) => setAgentAName(e.target.value)}
            className={inputClass}
            disabled={formDisabled}
            placeholder="Agent display name"
          />
        </label>

        <label className="grid gap-1 text-muted text-[11px] font-extrabold">
          <span>Agent B</span>
          <select
            value={agentBId}
            onChange={(e) => setAgentBId(e.target.value)}
            className={inputClass}
            disabled={formDisabled}
          >
            {agents.map((ag) => (
              <option key={ag.id} value={ag.id}>{ag.label}</option>
            ))}
          </select>
          <input
            type="text"
            value={agentBName}
            onChange={(e) => setAgentBName(e.target.value)}
            className={inputClass}
            disabled={formDisabled}
            placeholder="Agent display name"
          />
        </label>

        <label className="grid gap-1 text-muted text-[11px] font-extrabold">
          <span>num_rounds</span>
          <input ref={roundsRef} type="number" min={1} max={50} defaultValue={10} className={inputClass} disabled={formDisabled} />
        </label>

        <label className="grid gap-1 text-muted text-[11px] font-extrabold">
          <span>num_battlefields</span>
          <input ref={fieldsRef} type="number" min={1} max={100} defaultValue={5} className={inputClass} disabled={formDisabled} />
        </label>

        <label className="grid gap-1 text-muted text-[11px] font-extrabold">
          <span>total_resources</span>
          <input ref={resourcesRef} type="number" min={1} max={1000} defaultValue={100} className={inputClass} disabled={formDisabled} />
        </label>

        <label className="grid gap-1 text-muted text-[11px] font-extrabold">
          <span>seed</span>
          <input ref={seedRef} type="number" className={inputClass} disabled={formDisabled} placeholder="Random" />
        </label>

        {!isReplay && !state.pendingGame && (
          <button
            ref={btnRef}
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
            Pass these to your LLM agents as <code className="bg-ink/8 px-1 rounded text-[11px]">NASH_ARENA_KEY</code>.
          </p>
          {Object.entries(sessionKeys).map(([player, key]) => (
            <div key={player} className="mb-2 last:mb-0">
              <div className="flex items-center gap-2">
                <span className="text-[11px] font-extrabold text-muted uppercase">Player {player}</span>
                <span className="text-xs text-ink font-medium">{player === "A" ? agentAName : agentBName}</span>
              </div>
              <div className="flex items-center gap-2 mt-1">
                <code className="flex-1 text-[11px] bg-ink/6 px-2 py-1.5 rounded text-ink break-all font-mono">{key}</code>
                <button
                  type="button"
                  onClick={() => copyToClipboard(key)}
                  title="Copy key"
                  className="w-7 h-7 flex items-center justify-center rounded-md text-muted hover:text-accent hover:bg-accent/[0.12] cursor-pointer transition-colors shrink-0"
                >
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <rect x="9" y="9" width="13" height="13" rx="2" ry="2" />
                    <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1" />
                  </svg>
                </button>
              </div>
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
