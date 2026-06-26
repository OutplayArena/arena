import { useState } from "react";
import type { GameAgent } from "@frontend/types";
import { copyToClipboard } from "./utils";

const SPECIAL_AGENT_IDS = ["interactive", "remote"];

export interface PlayerSetupValue {
  agentId: string;
  name: string;
}

interface PlayerSetupCardProps {
  side: string;
  value: PlayerSetupValue;
  agents: GameAgent[];
  onChange: (v: PlayerSetupValue) => void;
  disabled: boolean;
  remoteKey?: string | null;
  onRemove?: () => void;
  canRemove?: boolean;
}

const SIDE_COLORS: Record<string, { ring: string; bg: string; text: string }> = {
  A: { ring: "border-agent-a/50", bg: "bg-agent-a/10", text: "text-agent-a" },
  B: { ring: "border-agent-b/50", bg: "bg-agent-b/10", text: "text-agent-b" },
  C: { ring: "border-violet-500/50", bg: "bg-violet-500/10", text: "text-violet-500" },
  D: { ring: "border-amber-500/50", bg: "bg-amber-500/10", text: "text-amber-500" },
  E: { ring: "border-rose-500/50", bg: "bg-rose-500/10", text: "text-rose-500" },
  F: { ring: "border-sky-500/50", bg: "bg-sky-500/10", text: "text-sky-500" },
  G: { ring: "border-teal-500/50", bg: "bg-teal-500/10", text: "text-teal-500" },
  H: { ring: "border-orange-500/50", bg: "bg-orange-500/10", text: "text-orange-500" },
  I: { ring: "border-pink-500/50", bg: "bg-pink-500/10", text: "text-pink-500" },
  J: { ring: "border-lime-500/50", bg: "bg-lime-500/10", text: "text-lime-500" },
};

function CopyButton({ value }: { value: string }) {
  const [copied, setCopied] = useState(false);
  const copy = async () => {
    const ok = await copyToClipboard(value);
    if (ok) {
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  };
  return (
    <button
      type="button"
      onClick={copy}
      title="Copy"
      className="shrink-0 w-6 h-6 flex items-center justify-center rounded text-muted hover:text-accent hover:bg-accent/10 transition-colors"
    >
      {copied ? (
        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
          <polyline points="20 6 9 17 4 12" />
        </svg>
      ) : (
        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <rect x="9" y="9" width="13" height="13" rx="2" ry="2" />
          <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1" />
        </svg>
      )}
    </button>
  );
}

export function PlayerSetupCard({ side, value, agents, onChange, disabled, remoteKey, onRemove, canRemove }: PlayerSetupCardProps) {
  const colors = SIDE_COLORS[side] ?? SIDE_COLORS.A;
  const isHuman = value.agentId === "interactive";
  const isRemote = value.agentId === "remote";

  const handleAgentChange = (agentId: string) => {
    let name = value.name;
    if (agentId === "interactive") name = "You";
    else if (agentId === "remote") name = `Remote ${side}`;
    else {
      const agent = agents.find((a) => a.id === agentId);
      if (agent) name = agent.label;
    }
    onChange({ agentId, name });
  };

  const handleNameChange = (name: string) => {
    onChange({ ...value, name });
  };

  return (
    <div className={`rounded-xl border ${colors.ring} bg-surface p-4 flex flex-col gap-3`}>
      {/* Header */}
      <div className="flex items-center gap-2.5">
        <div className={`w-8 h-8 rounded-full ${colors.bg} border ${colors.ring} flex items-center justify-center shrink-0`}>
          {isHuman ? (
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className={colors.text}>
              <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2" />
              <circle cx="12" cy="7" r="4" />
            </svg>
          ) : (
            <span className={`text-[11px] font-black ${colors.text}`}>{side}</span>
          )}
        </div>
        <div className="flex-1 min-w-0">
          <div className={`text-[11px] font-extrabold uppercase tracking-wider ${colors.text}`}>
            Player {side}
          </div>
          <div className="text-[10px] text-muted">
            {isHuman ? "Human player" : isRemote ? "External LLM agent" : "Built-in AI"}
          </div>
        </div>
        {canRemove && onRemove && (
          <button
            type="button"
            onClick={onRemove}
            disabled={disabled}
            title="Remove player"
            className="shrink-0 w-7 h-7 flex items-center justify-center rounded-lg text-muted hover:text-red-500 hover:bg-red-500/10 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
          >
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/>
            </svg>
          </button>
        )}
      </div>

      {/* Agent selector */}
      <div className="grid gap-1.5">
        <label className="text-[10px] font-extrabold text-muted uppercase tracking-wider">Agent</label>
        <select
          value={value.agentId}
          onChange={(e) => handleAgentChange(e.target.value)}
          disabled={disabled}
          className="w-full min-h-[36px] text-sm text-ink bg-surface-container border border-line/40 rounded-lg px-3 outline-none focus:border-accent/60 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
        >
          <option value="interactive">🙋 You (Human Player)</option>
          <option value="remote">🌐 Remote Agent (API)</option>
          {agents.filter((a) => !SPECIAL_AGENT_IDS.includes(a.id)).map((ag) => (
            <option key={ag.id} value={ag.id}>{ag.label}</option>
          ))}
        </select>
      </div>

      {/* Name field — hidden for human player (always "You") */}
      {!isHuman && (
        <div className="grid gap-1.5">
          <label className="text-[10px] font-extrabold text-muted uppercase tracking-wider">Display Name</label>
          <input
            type="text"
            value={value.name}
            onChange={(e) => handleNameChange(e.target.value)}
            disabled={disabled}
            placeholder="Agent display name"
            className="w-full min-h-[36px] text-sm text-ink bg-surface-container border border-line/40 rounded-lg px-3 outline-none focus:border-accent/60 disabled:opacity-50 transition-colors"
          />
        </div>
      )}

      {/* Remote key display — shown after game starts */}
      {isRemote && remoteKey && (
        <div className="rounded-lg border border-accent/30 bg-accent/5 p-3">
          <div className="text-[10px] font-extrabold text-accent/80 uppercase tracking-wider mb-1.5">
            OUTPLAYARENA_KEY
          </div>
          <div className="flex items-center gap-1.5">
            <code className="flex-1 text-[10px] font-mono text-ink bg-ink/5 px-2 py-1 rounded break-all leading-relaxed">
              {remoteKey}
            </code>
            <CopyButton value={remoteKey} />
          </div>
          <p className="text-[9px] text-muted mt-1.5">Pass this as OUTPLAYARENA_KEY to your agent</p>
        </div>
      )}
    </div>
  );
}
