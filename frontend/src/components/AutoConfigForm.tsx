import { useCallback, useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { createExperiment, getState, submitAction, getResults, getGameAgents } from "../api";
import { chooseAction } from "../agents";
import { resultToMatch, copyToClipboard } from "./utils";
import { randomAgentName } from "./names";
import { useApp } from "../hooks/useApp";
import type { RunConfig, GameAgent, Match } from "../types";

const inputClass =
  "w-full min-h-[40px] text-ink bg-surface-container border rounded-input px-[14px] shadow-none transition-[border-color,background,box-shadow] duration-150 outline-none hover:border-accent/40 focus:border-accent focus:bg-surface focus:shadow-[0_0_0_3px_var(--color-accent-soft)] border-line/40";

interface AutoConfigFormProps {
  gameSlug: string;
  schema: Record<string, unknown>;
  locked: boolean;
  sessionStatus?: string;
  initialValues?: Record<string, unknown>;
}

interface SchemaProp {
  type: string;
  const?: unknown;
  minimum?: number;
  maximum?: number;
  default?: unknown;
  enum?: string[];
  items?: SchemaProp;
  properties?: Record<string, SchemaProp>;
  minItems?: number;
  maxItems?: number;
}

function isConst(prop: SchemaProp): boolean {
  return prop.const !== undefined;
}

function resolveType(prop: Record<string, unknown>): string {
  const t = prop.type;
  if (Array.isArray(t)) {
    const types = t as string[];
    if (types.includes("integer") || types.includes("number")) return "number";
    return types[0] ?? "string";
  }
  return (t as string) ?? "string";
}

function resolveProps(schema: Record<string, unknown>): Record<string, SchemaProp> {
  const result: Record<string, SchemaProp> = {};
  for (const [key, value] of Object.entries(schema)) {
    if (typeof value === "object" && value !== null && !Array.isArray(value)) {
      const prop = value as Record<string, unknown>;
      result[key] = {
        type: resolveType(prop),
        const: prop.const,
        minimum: prop.minimum as number | undefined,
        maximum: prop.maximum as number | undefined,
        default: prop.default,
        enum: prop.enum as string[] | undefined,
        items: prop.items as SchemaProp | undefined,
        properties: (prop.properties as Record<string, SchemaProp>) ?? undefined,
        minItems: prop.minItems as number | undefined,
        maxItems: prop.maxItems as number | undefined,
      };
    }
  }
  return result;
}

function getDefault(prop: SchemaProp): unknown {
  if (prop.default !== undefined) return prop.default;
  if (prop.type === "integer" || prop.type === "number") return prop.minimum ?? 0;
  if (prop.type === "boolean") return false;
  if (prop.type === "array") return [];
  if (prop.type === "string") return "";
  return "";
}

function getInputType(prop: SchemaProp): string {
  if (prop.type === "integer" || prop.type === "number") return "number";
  if (prop.enum) return "select";
  if (prop.type === "boolean") return "checkbox";
  if (prop.type === "array") return "array";
  return "text";
}

export function AutoConfigForm({ gameSlug, schema, locked, sessionStatus, initialValues }: AutoConfigFormProps) {
  const navigate = useNavigate();
  const { setMatch } = useApp();
  const [agents, setAgents] = useState<GameAgent[]>([]);
  const initRanRef = useRef(false);
  const [agentAName, setAgentAName] = useState(() => randomAgentName());
  const [agentBName, setAgentBName] = useState(() => randomAgentName());
  const [agentAId, setAgentAId] = useState("uniform");
  const [agentBId, setAgentBId] = useState("greedy");
  const [formValues, setFormValues] = useState<Record<string, unknown>>({});
  const [status, setStatus] = useState("");
  const [running, setRunning] = useState(false);
  const [sessionKeys, setSessionKeys] = useState<Record<string, string> | null>(null);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const btnRef = useRef<HTMLButtonElement>(null);

  const props = resolveProps(schema);
  const editableProps = Object.entries(props).filter(([, p]) => !isConst(p));

  const isReplay = locked || sessionStatus === "completed";
  const formDisabled = locked || running || sessionStatus === "completed" || sessionStatus === "running";

  useEffect(() => {
    getGameAgents(gameSlug).then((data) => setAgents(data.agents)).catch(() => {});
  }, [gameSlug]);

  useEffect(() => {
    if (isReplay && initialValues) {
      const vals: Record<string, unknown> = {};
      for (const [key, prop] of Object.entries(props)) {
        if (!isConst(prop)) {
          vals[key] = key in initialValues ? initialValues[key] : getDefault(prop);
        }
      }
      setFormValues(vals);
      if (initialValues.agent_a) setAgentAName(String(initialValues.agent_a));
      if (initialValues.agent_b) setAgentBName(String(initialValues.agent_b));
    } else if (!isReplay) {
      const vals: Record<string, unknown> = {};
      for (const [key, prop] of Object.entries(props)) {
        if (!isConst(prop)) vals[key] = getDefault(prop);
      }
      setFormValues(vals);
    }
  }, [schema, initialValues, isReplay]);

  useEffect(() => {
    if (initRanRef.current) return;
    if (isReplay && initialValues) {
      initRanRef.current = true;
      if (initialValues.agent_a) setAgentAName(String(initialValues.agent_a));
      if (initialValues.agent_b) setAgentBName(String(initialValues.agent_b));
    }
  }, [isReplay, initialValues]);

  const handleValueChange = (key: string, value: unknown, fieldType?: string) => {
    let v = value;
    if (fieldType === "number" && typeof value === "string") {
      v = value === "" ? null : Number(value);
    }
    setFormValues((prev) => ({ ...prev, [key]: v }));
  };

  const buildConfig = () => {
    const config: Record<string, unknown> = {};
    for (const [key, prop] of Object.entries(props)) {
      if (isConst(prop)) {
        config[key] = prop.const;
      } else {
        config[key] = key in formValues ? formValues[key] : getDefault(prop);
      }
    }
    config.agents = { A: agentAName.trim(), B: agentBName.trim() };
    config.interactive = true;
    return config;
  };

  const buildLiveMatch = useCallback((state: { history?: { round: number; allocations?: Record<string, number[]>; scores?: Record<string, number>; total_scores?: Record<string, number>; winner?: string }[]; battlefields?: { id: string }[]; budgets?: Record<string, number>; config_hash?: string; total_scores?: Record<string, number>; winner?: string } | null, sessionId: string, agentA: string, agentB: string): Match => {
    if (!state) {
      return {
        agent_a: agentA,
        agent_b: agentB,
        session_id: sessionId,
        config_hash: "",
        num_rounds: 1,
        num_battlefields: 1,
        total_resources: 100,
        total_score_a: 0,
        total_score_b: 0,
        history: [],
        metrics: {},
      };
    }
    const history = (state.history || []).map((r) => ({
      round: r.round,
      agent_a: agentA,
      agent_b: agentB,
      action_a: r.allocations?.A || [],
      action_b: r.allocations?.B || [],
      score_a: r.scores?.A || 0,
      score_b: r.scores?.B || 0,
      total_score_a: r.total_scores?.A || 0,
      total_score_b: r.total_scores?.B || 0,
      winner: (r.winner || "Tie") as "A" | "B" | "Tie",
    }));
    return {
      agent_a: agentA,
      agent_b: agentB,
      session_id: sessionId,
      config_hash: state.config_hash || "",
      num_rounds: state.history?.length || 0,
      num_battlefields: (state.battlefields || []).length || 1,
      total_resources: state.budgets?.A || 100,
      total_score_a: state.total_scores?.A || 0,
      total_score_b: state.total_scores?.B || 0,
      match_winner: (state.winner || undefined) as "A" | "B" | "Tie" | undefined,
      history,
      metrics: {},
    };
  }, []);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (running) return;
    setRunning(true);
    setSessionKeys(null);
    setSessionId(null);
    setStatus("Running experiment...");

    const config = buildConfig();
    const numRounds = (config.rounds as number) || 10;

    try {
      const created = await createExperiment(config as never);
      setSessionId(created.session_id);

      const hasRemote = agentAId === "remote" || agentBId === "remote";
      if (hasRemote) {
        const keys: Record<string, string> = {};
        if (agentAId === "remote") keys.A = created.player_tokens.A;
        if (agentBId === "remote") keys.B = created.player_tokens.B;
        setSessionKeys(keys);
      }

      let gameState = await getState(created.session_id);
      setMatch(buildLiveMatch(gameState as never, created.session_id, agentAName, agentBName));

      while (gameState.phase !== "complete") {
        let acted = false;
        for (const player of ["A", "B"] as const) {
          if (!gameState.awaiting.includes(player)) continue;
          const isRemote = player === "A" ? agentAId === "remote" : agentBId === "remote";
          if (isRemote) continue;

          const agent = player === "A" ? agentAId : agentBId;
          const action = chooseAction(agent, player, gameState);
          gameState = await submitAction(created.session_id, action, created.player_tokens[player]);
          acted = true;
        }
        if (!acted) {
          setStatus(`Waiting for remote agents (round ${gameState.round}/${gameState.round_total})`);
          setMatch(buildLiveMatch(gameState as never, created.session_id, agentAName, agentBName));
          break;
        }
        setMatch(buildLiveMatch(gameState as never, created.session_id, agentAName, agentBName));
        setStatus(`Round ${gameState.round}/${gameState.round_total}`);
      }

      if (gameState.phase === "complete") {
        const result = await getResults(created.session_id);
        const match = resultToMatch(result as never, {
          agent_a: agentAName,
          agent_b: agentBName,
          num_rounds: numRounds,
          num_battlefields: 5,
          total_resources: 100,
          session_id: created.session_id,
        } as RunConfig);
        navigate(`/play/${gameSlug}/${created.session_id}`, { state: { match } });
      }
    } catch (err) {
      setStatus(`error=${err instanceof Error ? err.message : String(err)}`);
    } finally {
      setRunning(false);
    }
  };

  const renderField = (key: string, prop: SchemaProp) => {
    const inputType = getInputType(prop);
    const value = formValues[key];
    const disabled = formDisabled;

    if (inputType === "select" && prop.enum) {
      return (
        <select
          value={String(value ?? getDefault(prop))}
          onChange={(e) => handleValueChange(key, e.target.value)}
          className={inputClass}
          disabled={disabled}
        >
          {prop.enum.map((opt) => (
            <option key={opt} value={opt}>{opt}</option>
          ))}
        </select>
      );
    }

    if (inputType === "checkbox") {
      return (
        <input
          type="checkbox"
          checked={Boolean(value ?? getDefault(prop))}
          onChange={(e) => handleValueChange(key, e.target.checked)}
          className="w-4 h-4"
          disabled={disabled}
        />
      );
    }

    if (inputType === "array" && prop.items?.type === "object" && prop.items.properties) {
      return (
        <div className="text-xs text-muted">
          Array of objects — use custom ConfigForm for this game type.
        </div>
      );
    }

    if (inputType === "array") {
      const arr = Array.isArray(value) ? value : (getDefault(prop) as unknown[]);
      return (
        <div className="grid gap-1">
          {arr.map((item, i) => (
            <input
              key={i}
              type="number"
              value={item as number}
              onChange={(e) => {
                const next = [...arr];
                next[i] = Number(e.target.value);
                handleValueChange(key, next);
              }}
              className={inputClass}
              disabled={disabled}
            />
          ))}
        </div>
      );
    }

    return (
      <input
        type={inputType}
        value={value as string ?? String(getDefault(prop))}
        onChange={(e) => handleValueChange(key, inputType === "number" ? Number(e.target.value) : e.target.value)}
        min={prop.minimum}
        max={prop.maximum}
        className={inputClass}
        disabled={disabled}
        placeholder={prop.default !== undefined ? String(prop.default) : undefined}
      />
    );
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
          {agents.length > 0 && (
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
          )}
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
          {agents.length > 0 && (
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
          )}
          <input
            type="text"
            value={agentBName}
            onChange={(e) => setAgentBName(e.target.value)}
            className={inputClass}
            disabled={formDisabled}
            placeholder="Agent display name"
          />
        </label>

        {editableProps.map(([key, prop]) => (
          <label key={key} className="grid gap-1 text-muted text-[11px] font-extrabold">
            <span>{key}</span>
            {renderField(key, prop)}
          </label>
        ))}

        {!isReplay && (
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
