import { useEffect, useState } from "react";
import { useApp } from "../hooks/useApp";
import { downloadJSON } from "./badges";
import { getGameMetrics } from "../api";
import type { RichMetrics, MetricDescriptor } from "../types";

interface AutoHistoryViewProps {
  hasMatch: boolean;
  canvasCollapsed: boolean;
  onExpandCanvas: () => void;
  gameSlug?: string;
}

function MetricLabel({ name, catalog }: { name: string; catalog: Record<string, MetricDescriptor> }) {
  const def = catalog[name];
  const [open, setOpen] = useState(false);

  if (!def?.description) {
    return <span className="text-[10px] font-extrabold text-muted uppercase">{name}</span>;
  }

  return (
    <span className="relative inline-flex items-center gap-1">
      <span className="text-[10px] font-extrabold text-muted uppercase">{name}</span>
      <button
        type="button"
        className="text-muted/60 hover:text-muted cursor-help transition-colors leading-none"
        onClick={(e) => { e.stopPropagation(); setOpen(!open); }}
        onBlur={() => setTimeout(() => setOpen(false), 150)}
        title={def.description}
      >
        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <circle cx="12" cy="12" r="10" />
          <line x1="12" y1="16" x2="12" y2="12" />
          <line x1="12" y1="8" x2="12.01" y2="8" />
        </svg>
      </button>
      {open && (
        <span className="absolute bottom-full left-0 mb-1.5 w-48 rounded-lg bg-ink dark:bg-surface-container border border-line/50 p-2 z-50 shadow-lg">
          <span className="text-[10px] text-white dark:text-ink leading-snug">{def.description}</span>
        </span>
      )}
    </span>
  );
}

function formatValue(value: unknown): string {
  if (typeof value === "number") {
    return Number.isInteger(value) ? String(value) : value.toFixed(4);
  }
  if (typeof value === "string") return value;
  return String(value ?? "");
}

function isPlainObj(v: unknown): v is Record<string, unknown> {
  return typeof v === "object" && v !== null && !Array.isArray(v);
}

function MetricValue({ value }: { value: unknown }) {
  if (value === null || value === undefined) {
    return <span className="text-xs text-quiet font-mono mt-0.5 block">—</span>;
  }
  if (isPlainObj(value)) {
    const entries = Object.entries(value);
    if (entries.length === 0) return <span className="text-xs text-ink font-mono mt-0.5 block">{}</span>;
    return (
      <table className="w-full mt-0.5 text-[10px] border-separate border-spacing-0">
        <tbody>
          {entries.map(([k, v]) => (
            <tr key={k}>
              <td className="pr-2 py-0.5 text-muted font-semibold whitespace-nowrap align-top">{k}</td>
              <td className="py-0.5 text-ink font-mono text-right">
                {isPlainObj(v) ? <MetricValue value={v} />
                 : Array.isArray(v) ? JSON.stringify(v)
                 : formatValue(v)}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    );
  }
  if (Array.isArray(value)) {
    return <span className="text-xs text-ink font-mono mt-0.5 block">{JSON.stringify(value)}</span>;
  }
  return <span className="text-xs text-ink font-mono mt-0.5 block">{formatValue(value)}</span>;
}

function RichMetricsPanel({ rich, catalog }: { rich: RichMetrics; catalog: Record<string, MetricDescriptor> }) {
  const agents = rich.agents ? Object.keys(rich.agents) : [];

  return (
    <div className="mt-4 space-y-3">
      <h3 className="text-[11px] font-extrabold text-muted uppercase">Rich Metrics</h3>

      <div className="rounded-card bg-surface-container/30 border border-line/30 p-3">
        <h4 className="text-[10px] font-extrabold text-muted uppercase mb-2">Joint</h4>
        <div className="grid grid-cols-2 gap-2">
          {Object.entries(rich.joint).map(([key, value]) => (
            <div key={key} className="rounded-card bg-surface-container/30 border border-line/30 p-2">
              <MetricLabel name={key} catalog={catalog} />
              <MetricValue value={value} />
            </div>
          ))}
        </div>
      </div>

      {agents.map((agentId) => {
        const agent = rich.agents[agentId];
        if (!agent) return null;
        return (
          <div key={agentId} className="rounded-card bg-surface-container/30 border border-line/30 p-3">
            <h4 className="text-[10px] font-extrabold text-muted uppercase mb-2">
              Agent {agentId}
            </h4>
            <div className="grid grid-cols-2 gap-2">
              {Object.entries(agent).map(([key, value]) => {
                if (key === "adaptive_regret_series") return null;
                return (
                  <div key={key} className="rounded-card bg-surface-container/30 border border-line/30 p-2">
                    <MetricLabel name={key} catalog={catalog} />
                    <MetricValue value={value} />
                  </div>
                );
              })}
            </div>
          </div>
        );
      })}
    </div>
  );
}

function formatAction(action: unknown): string {
  if (Array.isArray(action)) return `[${action.join(", ")}]`;
  if (typeof action === "string") return action;
  if (typeof action === "number") return String(action);
  return String(action ?? "");
}

export function AutoHistoryView({ hasMatch, canvasCollapsed, onExpandCanvas, gameSlug }: AutoHistoryViewProps) {
  const { state } = useApp();
  const { activeMatch } = state;
  const [catalog, setCatalog] = useState<Record<string, MetricDescriptor>>({});

  useEffect(() => {
    if (!gameSlug) return;
    let cancelled = false;
    getGameMetrics(gameSlug).then((data) => {
      if (cancelled) return;
      const map: Record<string, MetricDescriptor> = {};
      for (const m of data.metrics) {
        map[m.name] = m;
      }
      setCatalog(map);
    }).catch(() => {});
    return () => { cancelled = true; };
  }, [gameSlug]);

  const history = activeMatch?.history ?? [];
  const total = history.length;

  return (
    <div>
      <div className="p-4">
        <div className="flex items-center justify-between mb-3">
          <h2 className="text-xs font-extrabold text-muted uppercase tracking-wider">History</h2>
          <div className="flex items-center gap-2">
            {canvasCollapsed && (
              <button
                type="button"
                onClick={onExpandCanvas}
                className="text-[10px] font-semibold text-accent hover:underline"
              >
                Show Live View
              </button>
            )}
            <span className="text-[11px] text-muted">
              {hasMatch ? `Complete — ${total} round${total !== 1 ? "s" : ""}` : "No data yet."}
            </span>
          </div>
        </div>

        {hasMatch && activeMatch && total > 0 && (
          <>
            <div className="rounded-card border border-line/40 overflow-hidden">
              <table className="w-full text-left text-sm">
                <thead>
                  <tr className="border-b border-line/40 bg-surface-container/50">
                    <th className="px-3 py-2 text-[10px] font-extrabold text-muted">R</th>
                    <th className="px-3 py-2 text-[10px] font-extrabold text-muted">{activeMatch.agent_a}</th>
                    <th className="px-3 py-2 text-[10px] font-extrabold text-muted">{activeMatch.agent_b}</th>
                    <th className="px-3 py-2 text-[10px] font-extrabold text-muted">Scores</th>
                    <th className="px-3 py-2 text-[10px] font-extrabold text-muted">W</th>
                  </tr>
                </thead>
                <tbody>
                  {history.map((round) => (
                    <tr
                      key={round.round}
                      className={`border-b border-line/20 last:border-b-0 ${
                        round.winner === "A" ? "bg-agent-a/[0.04]" : round.winner === "B" ? "bg-agent-b/[0.04]" : ""
                      }`}
                    >
                      <td className="px-3 py-2 text-xs text-muted font-mono">{round.round}</td>
                      <td className="px-3 py-2 text-xs text-ink font-mono">
                        {formatAction(round.action_a)}
                      </td>
                      <td className="px-3 py-2 text-xs text-ink font-mono">
                        {formatAction(round.action_b)}
                      </td>
                      <td className="px-3 py-2 text-xs text-ink">
                        A:{round.score_a} B:{round.score_b}
                      </td>
                      <td className="px-3 py-2 text-xs font-bold">
                        <span className={round.winner === "A" ? "text-agent-a" : round.winner === "B" ? "text-agent-b" : "text-muted"}>
                          {round.winner === "Tie" ? "D" : round.winner}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            <div className="mt-3 flex items-center justify-between">
              <div className="text-[11px] text-muted">
                Final: <span className="text-agent-a font-bold">{activeMatch.total_score_a}</span> — <span className="text-agent-b font-bold">{activeMatch.total_score_b}</span>
                {activeMatch.match_winner !== "Tie" && (
                  <span className={`ml-1 font-bold ${activeMatch.match_winner === "A" ? "text-agent-a" : "text-agent-b"}`}>
                    ({activeMatch.match_winner === "A" ? activeMatch.agent_a : activeMatch.agent_b} wins)
                  </span>
                )}
              </div>
              <button
                type="button"
                onClick={() => downloadJSON(activeMatch, `${activeMatch.session_id || "match"}.json`)}
                className="text-[10px] font-semibold text-accent hover:underline"
              >
                Download JSON
              </button>
            </div>

            {activeMatch.metrics && Object.keys(activeMatch.metrics).length > 0 && (
              <div className="mt-4">
                <h3 className="text-[11px] font-extrabold text-muted uppercase mb-2">Metrics</h3>
                <div className="grid grid-cols-2 gap-2">
                  {Object.entries(activeMatch.metrics).map(([key, value]) => (
                    <div key={key} className="rounded-card bg-surface-container/30 border border-line/30 p-2">
                      <MetricLabel name={key} catalog={catalog} />
                      <MetricValue value={value} />
                    </div>
                  ))}
                </div>
              </div>
            )}

            {activeMatch.rich_metrics && (
              <RichMetricsPanel rich={activeMatch.rich_metrics} catalog={catalog} />
            )}
          </>
        )}

        {!hasMatch && (
          <div className="text-xs text-muted text-center py-8">
            No match data. Complete a game to see history.
          </div>
        )}
      </div>
    </div>
  );
}
