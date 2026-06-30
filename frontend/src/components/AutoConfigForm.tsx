import { useEffect, useRef, useState } from "react";
import { createExperiment, getGameAgents, getGameScenarios } from "../api";
import { copyToClipboard } from "./utils";
import { randomAgentName } from "./names";
import { useApp } from "../hooks/useApp";
import { useWandbLoggingConfig } from "../hooks/useWandbLoggingConfig";
import { WandbLoggingSection } from "./WandbLoggingSection";
import type { GameAgent, ScenarioInfo } from "../types";

const inputClass =
  "w-full h-9 text-ink bg-surface border border-line rounded-[var(--radius-input)] px-3 outline-none " +
  "transition-colors duration-150 hover:border-line-strong " +
  "focus:border-accent focus:shadow-[0_0_0_3px_var(--color-accent-soft)]";

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
  enumLabels?: Record<string, string>;
  items?: SchemaProp;
  properties?: Record<string, SchemaProp>;
  minItems?: number;
  maxItems?: number;
  description?: string;
  visibleWhen?: Record<string, unknown>;
}

interface PlayerConfig {
  id: string;
  name: string;
  agentId: string;
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
        enumLabels: prop.enum_labels as Record<string, string> | undefined,
        items: prop.items as SchemaProp | undefined,
        properties: (prop.properties as Record<string, SchemaProp>) ?? undefined,
        minItems: prop.minItems as number | undefined,
        maxItems: prop.maxItems as number | undefined,
        description: prop.description as string | undefined,
        visibleWhen: prop.visible_when as Record<string, unknown> | undefined,
      };
    }
  }
  return result;
}

function getDefault(prop: SchemaProp): unknown {
  if (prop.default !== undefined) {
    if (prop.default === null && (prop.type === "integer" || prop.type === "number")) {
      return undefined;
    }
    return prop.default;
  }
  if (prop.type === "integer" || prop.type === "number") return prop.minimum ?? 0;
  if (prop.type === "boolean") return false;
  if (prop.type === "array") {
    const count = prop.minItems ?? 0;
    if (count > 0 && prop.items) {
      const itemDefault = getDefault(prop.items);
      return Array.from({ length: count }, () => itemDefault);
    }
    return [];
  }
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
  const { state, startGame } = useApp();
  const wandbLogging = useWandbLoggingConfig();
  const [agents, setAgents] = useState<GameAgent[]>([]);
  const [scenarios, setScenarios] = useState<ScenarioInfo[]>([]);
  const initRanRef = useRef(false);
  const [players, setPlayers] = useState<PlayerConfig[]>([
    { id: "A", name: randomAgentName(), agentId: "interactive" },
    { id: "B", name: randomAgentName(), agentId: "remote" },
  ]);
  const [formValues, setFormValues] = useState<Record<string, unknown>>({});
  const [status, setStatus] = useState("");
  const [running, setRunning] = useState(false);
  const [sessionKeys, setSessionKeys] = useState<Record<string, string> | null>(null);
  const [copiedKey, setCopiedKey] = useState<string | null>(null);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const btnRef = useRef<HTMLButtonElement>(null);

  const props = resolveProps(schema);
  const allEditable = Object.entries(props).filter(([, p]) => !isConst(p));
  const editableProps = allEditable.filter(([, prop]) => {
    if (!prop.visibleWhen) return true;
    for (const [depKey, depVal] of Object.entries(prop.visibleWhen)) {
      if (formValues[depKey] !== depVal) return false;
    }
    return true;
  });

  const effectiveLocked = locked || state.sessionLocked;
  const effectiveStatus = sessionStatus || state.sessionStatus;
  const isReplay = effectiveLocked || effectiveStatus === "completed" || effectiveStatus === "running" || effectiveStatus === "failed";
  const formDisabled = effectiveLocked || running || state.pendingGame !== null || effectiveStatus === "completed" || effectiveStatus === "running" || effectiveStatus === "failed";
  const showRunButton = !isReplay && !state.pendingGame;

  useEffect(() => {
    getGameAgents(gameSlug).then((data) => setAgents(data.agents)).catch(() => {});
  }, [gameSlug]);

  useEffect(() => {
    getGameScenarios(gameSlug).then((data) => setScenarios(data.scenarios)).catch(() => {});
  }, [gameSlug]);

  useEffect(() => {
    if (isReplay && initialValues) {
      const vals: Record<string, unknown> = {};
      for (const [key, prop] of Object.entries(props)) {
        if (!isConst(prop)) {
          vals[key] = key in initialValues ? initialValues[key] : getDefault(prop);
        }
      }
      // eslint-disable-next-line react-hooks/set-state-in-effect
      setFormValues(vals);
      setPlayers((prev) =>
        prev.map((p) => ({
          ...p,
          name: (initialValues[`agent_${p.id.toLowerCase()}`] as string) ?? p.name,
          agentId: (initialValues[`agent_${p.id.toLowerCase()}_id`] as string) ?? p.agentId,
        }))
      );
    } else if (!isReplay) {
      const vals: Record<string, unknown> = {};
      for (const [key, prop] of Object.entries(props)) {
        if (!isConst(prop)) vals[key] = getDefault(prop);
      }
      setFormValues(vals);
    }
  },
  // 'props' is intentionally excluded from the deps: it's derived from
  // `schema` in the render body and resolveProps() returns a fresh object
  // on every render, so depending on it would re-run this effect on every
  // render and cause an infinite loop with setFormValues(). The original
  // PR #76 lint fix added 'props' to the deps as a "correctness fix", but
  // that change was itself the bug — it OOM'd the AutoConfigForm test
  // files in CI (the worker sat at 100% memory for 2h53m before the
  // runner killed it with ERR_WORKER_OUT_OF_MEMORY). Reverted.
  // eslint-disable-next-line react-hooks/exhaustive-deps
  [schema, initialValues, isReplay]);

  useEffect(() => {
    if (initRanRef.current) return;
    if (isReplay && initialValues) {
      initRanRef.current = true;
      // eslint-disable-next-line react-hooks/set-state-in-effect
      setPlayers((prev) =>
        prev.map((p) => ({
          ...p,
          name: (initialValues[`agent_${p.id.toLowerCase()}`] as string) ?? p.name,
        }))
      );
    }
  }, [isReplay, initialValues]);

  const scenarioId = formValues["scenario"];
  const systemPrompt = formValues["system_prompt"];
  useEffect(() => {
    if (scenarios.length === 0) return;
    if (scenarioId && !systemPrompt) {
      const matched = scenarios.find((s) => s.id === scenarioId);
      if (matched) {
        // eslint-disable-next-line react-hooks/set-state-in-effect
        setFormValues((prev) => ({ ...prev, system_prompt: matched.system_prompt }));
      }
    }
  }, [scenarios, scenarioId, systemPrompt]);

  const handleValueChange = (key: string, value: unknown, fieldType?: string) => {
    let v = value;
    if (fieldType === "number" && typeof value === "string") {
      v = value === "" ? null : Number(value);
    }
    setFormValues((prev) => {
      const next = { ...prev, [key]: v };
      if (key === "scenario" && scenarios.length > 0) {
        const matched = scenarios.find((s) => s.id === value);
        if (matched) {
          next["system_prompt"] = matched.system_prompt;
        }
      }
      return next;
    });
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
    const agentsDict: Record<string, string> = {};
    players.forEach((p) => { agentsDict[p.id] = p.name.trim(); });
    config.agents = agentsDict;
    config.players = players.length;
    config.interactive = players.some((p) => p.agentId === "interactive");
    Object.assign(config, wandbLogging.toConfigFields());
    return config;
  };


  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (running) return;
    setRunning(true);
    setSessionKeys(null);
    setSessionId(null);
    setStatus("Creating experiment...");

    const config = buildConfig();
    const numRounds = (config.rounds as number) || 10;

    try {
      const created = await createExperiment(config as never);
      setSessionId(created.session_id);

      const remoteKeys: Record<string, string> = {};
      players.forEach((p) => {
        if (p.agentId === "remote") {
          remoteKeys[p.id] = created.player_tokens[p.id];
        }
      });
      const hasRemoteKeys = Object.keys(remoteKeys).length > 0;
      if (hasRemoteKeys) setSessionKeys(remoteKeys);

      const isInteractive = players.some((p) => p.agentId === "interactive");
      const playerNames: Record<string, string> = {};
      const agentIds: Record<string, string> = {};
      players.forEach((p) => {
        playerNames[p.id] = p.name.trim();
        agentIds[p.id] = p.agentId;
      });

      startGame({
        sessionId: created.session_id,
        tokens: created.player_tokens,
        agentAName: playerNames.A ?? "",
        agentBName: playerNames.B ?? "",
        agentAId: agentIds.A ?? "",
        agentBId: agentIds.B ?? "",
        numRounds,
        numFields: (config.num_battlefields as number) ?? 5,
        totalResources: (config.total_resources as number) ?? 100,
        gameSlug,
        remoteKeys: hasRemoteKeys ? remoteKeys : null,
        playerNames,
        agentIds,
        interactive: isInteractive,
      });
      setStatus("Game started — switch to Live View to watch.");
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
            <option key={opt} value={opt}>
              {prop.enumLabels?.[opt] ?? opt}
            </option>
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
      const objProps = prop.items.properties;
      const visibleProps = Object.entries(objProps).filter(([objKey]) => objKey !== "id");
      const arr = (Array.isArray(value) && value.length > 0
        ? value
        : getDefault(prop)) as Record<string, unknown>[];
      const canAdd = !prop.maxItems || arr.length < prop.maxItems;
      const canRemove = !prop.minItems || arr.length > prop.minItems;

      return (
        <div className="grid gap-2">
          {arr.map((item, i) => (
            <div key={i} className="flex items-start gap-2">
              <div className="flex-1 grid gap-1">
                {visibleProps.map(([objKey, objProp]) => (
                  <div key={objKey} className="grid gap-0.5">
                    <label className="text-[10px] font-extrabold text-muted">{objKey}</label>
                    <input
                      type={objProp.type === "number" || objProp.type === "integer" ? "number" : "text"}
                      value={(item as Record<string, unknown>)[objKey] as string ?? getDefault(objProp) as string}
                      onChange={(e) => {
                        const next = arr.map((el, idx) =>
                          idx === i
                            ? { ...el, [objKey]: objProp.type === "number" || objProp.type === "integer" ? Number(e.target.value) : e.target.value }
                            : el,
                        );
                        handleValueChange(key, next);
                      }}
                      className={inputClass}
                      disabled={disabled}
                      min={objProp.minimum}
                      max={objProp.maximum}
                    />
                  </div>
                ))}
              </div>
              {canRemove && (
                <button
                  type="button"
                  onClick={() => {
                    handleValueChange(key, arr.filter((_, idx) => idx !== i));
                  }}
                  className="w-8 h-8 flex items-center justify-center rounded text-muted hover:text-red-500 hover:bg-red-500/10 transition-colors shrink-0"
                  disabled={disabled}
                >
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
                    <line x1="18" y1="6" x2="6" y2="18" /><line x1="6" y1="6" x2="18" y2="18" />
                  </svg>
                </button>
              )}
            </div>
          ))}
          {canAdd && (
            <button
              type="button"
              onClick={() => {
                const itemDefault: Record<string, unknown> = {};
                for (const [objKey, objProp] of Object.entries(objProps)) {
                  if (objKey === "id" && objProp.type === "string") {
                    itemDefault[objKey] = `${objKey}-${arr.length + 1}`;
                  } else {
                    itemDefault[objKey] = getDefault(objProp);
                  }
                }
                handleValueChange(key, [...arr, itemDefault]);
              }}
              className="text-xs font-semibold text-accent hover:underline"
              disabled={disabled}
            >
              + Add
            </button>
          )}
        </div>
      );
    }

    if (inputType === "array") {
      const arr = (Array.isArray(value) && value.length > 0
        ? value
        : getDefault(prop)) as unknown[];
      const canAdd = !prop.maxItems || arr.length < prop.maxItems;
      const canRemove = !prop.minItems || arr.length > prop.minItems;

      return (
        <div className="grid gap-1">
          {arr.map((item, i) => (
            <div key={i} className="flex items-center gap-2">
              <input
                type="number"
                value={item as number}
                onChange={(e) => {
                  const next = [...arr];
                  next[i] = Number(e.target.value);
                  handleValueChange(key, next);
                }}
                className={`${inputClass} flex-1`}
                disabled={disabled}
              />
              {canRemove && (
                <button
                  type="button"
                  onClick={() => handleValueChange(key, arr.filter((_, idx) => idx !== i))}
                  className="w-8 h-8 flex items-center justify-center rounded text-muted hover:text-red-500 hover:bg-red-500/10 transition-colors shrink-0"
                  disabled={disabled}
                >
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
                    <line x1="18" y1="6" x2="6" y2="18" /><line x1="6" y1="6" x2="18" y2="18" />
                  </svg>
                </button>
              )}
            </div>
          ))}
          {canAdd && (
            <button
              type="button"
              onClick={() => handleValueChange(key, [...arr, prop.items ? getDefault(prop.items) : 0])}
              className="text-xs font-semibold text-accent hover:underline"
              disabled={disabled}
            >
              + Add
            </button>
          )}
        </div>
      );
    }

    if (key === "system_prompt") {
      return (
        <textarea
          value={value as string ?? ""}
          onChange={(e) => handleValueChange(key, e.target.value)}
          className={`${inputClass} min-h-[120px]`}
          disabled={disabled}
          placeholder={prop.description ?? undefined}
          rows={5}
        />
      );
    }

    return (
      <input
        type={inputType}
        value={inputType === "number" ? (value != null ? String(value) : "") : (value as string ?? String(getDefault(prop)))}
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

        {players.map((player, index) => (
          <div key={player.id} className="grid gap-1 text-muted text-[11px] font-extrabold">
            <span>Player {player.id}</span>
            {agents.length > 0 && (
              <select
                value={player.agentId}
                onChange={(e) => {
                  const agentId = e.target.value;
                  setPlayers((prev) =>
                    prev.map((p, i) => {
                      if (i !== index) return p;
                      let name = p.name;
                      if (agentId === "interactive") name = "You";
                      else if (agentId === "remote") name = `Remote ${p.id}`;
                      else {
                        const agent = agents.find((a) => a.id === agentId);
                        if (agent) name = agent.label;
                      }
                      return { ...p, agentId, name };
                    })
                  );
                }}
                className={inputClass}
                disabled={formDisabled}
              >
                <option value="interactive">Interactive (Human Player)</option>
                <option value="remote">Remote Agent (API)</option>
                {agents.filter((a) => a.id !== "interactive" && a.id !== "remote").map((ag) => (
                  <option key={ag.id} value={ag.id}>{ag.label}</option>
                ))}
              </select>
            )}
            <input
              type="text"
              value={player.name}
              onChange={(e) => {
                setPlayers((prev) =>
                  prev.map((p, i) => i === index ? { ...p, name: e.target.value } : p)
                );
              }}
              className={inputClass}
              disabled={formDisabled || player.agentId === "interactive" || player.agentId === "remote"}
              placeholder="Player display name"
            />
          </div>
        ))}

        {editableProps.map(([key, prop]) => (
          <label key={key} className="grid gap-1 text-muted text-[11px] font-extrabold">
            <span className="flex items-center gap-1">
              {key}
              {prop.description && (
                <span className="relative group cursor-help">
                  <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="text-muted/50">
                    <circle cx="12" cy="12" r="10" />
                    <path d="M9.09 9a3 3 0 0 1 5.83 1c0 2-3 3-3 3" />
                    <line x1="12" y1="17" x2="12.01" y2="17" />
                  </svg>
                  <span
                    className="absolute left-full top-1/2 -translate-y-1/2 ml-2 px-2.5 py-1.5 bg-ink text-white text-[11px] font-medium rounded whitespace-normal text-left leading-relaxed opacity-0 pointer-events-none group-hover:opacity-100 transition-opacity z-50"
                    style={{ width: "max-content", maxWidth: "520px" }}
                  >
                    {prop.description}
                  </span>
                </span>
              )}
            </span>
            {renderField(key, prop)}
          </label>
        ))}

        <WandbLoggingSection {...wandbLogging} disabled={running || isReplay} />

        {showRunButton && (
          <button
            ref={btnRef}
            type="submit"
            disabled={running}
            className="h-9 px-6 bg-accent text-white rounded-[var(--radius-button)] font-medium text-sm cursor-pointer transition-opacity hover:not-disabled:opacity-90 disabled:cursor-not-allowed disabled:opacity-40 mt-1"
          >
            {running ? "Running..." : state.activeMatch ? "Play Again" : "Run Experiment"}
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
        <div className="mx-4 mb-4 p-4 rounded-[var(--radius-card)] border border-line bg-surface-soft">
          <h3 className="text-sm font-extrabold text-ink mb-2">Remote Agent Keys</h3>
          <p className="text-xs text-muted mb-3">
            Pass these to your LLM agents as <code className="bg-ink/8 px-1 rounded text-[11px]">OUTPLAYARENA_KEY</code>.
          </p>
          {Object.entries(sessionKeys).map(([player, key]) => {
            const playerName = players.find((p) => p.id === player)?.name ?? player;
            return (
              <div key={player} className="mb-2 last:mb-0">
                <div className="flex items-center gap-2">
                  <span className="text-[11px] font-extrabold text-muted uppercase">Player {player}</span>
                  <span className="text-xs text-ink font-medium">{playerName}</span>
                </div>
              <div className="flex items-center gap-2 mt-1">
                <code className="flex-1 text-[11px] bg-ink/6 px-2 py-1.5 rounded text-ink break-all font-mono">{key}</code>
                <button
                  type="button"
                  onClick={async () => {
                    const ok = await copyToClipboard(key);
                    if (ok) {
                      setCopiedKey(player);
                      setTimeout(() => setCopiedKey(null), 1500);
                    }
                  }}
                  title={copiedKey === player ? "Copied!" : "Copy key"}
                  className="w-7 h-7 flex items-center justify-center rounded-md text-muted hover:text-accent hover:bg-accent/[0.12] cursor-pointer transition-colors shrink-0"
                >
                  {copiedKey === player ? (
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                      <polyline points="20 6 9 17 4 12" />
                    </svg>
                  ) : (
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                      <rect x="9" y="9" width="13" height="13" rx="2" ry="2" />
                      <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1" />
                    </svg>
                  )}
                </button>
              </div>
            </div>
            );
          })}
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
