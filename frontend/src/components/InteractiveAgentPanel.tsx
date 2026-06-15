import { useState, useEffect, useRef } from "react";
import { useApp } from "../hooks/useApp";
import { submitAction } from "../api";

type PlayerSide = "A" | "B";

interface ChatMessage {
  player: PlayerSide;
  text: string;
  round: number;
}

const PLAYER_COLORS: Record<PlayerSide, string> = {
  A: "border-agent-a/30 bg-agent-a/8 text-agent-a",
  B: "border-agent-b/30 bg-agent-b/8 text-agent-b",
};

const PLAYER_LABELS: Record<PlayerSide, string> = {
  A: "Agent A",
  B: "Agent B",
};

export function InteractiveAgentPanel() {
  const { state } = useApp();
  const pg = state.pendingGame;
  const match = state.activeMatch;
  const listRef = useRef<HTMLDivElement>(null);

  const [inputValue, setInputValue] = useState("");
  const [submitting, setSubmitting] = useState(false);

  const interactivePlayers: PlayerSide[] = [];
  if (pg?.agentAId === "interactive") interactivePlayers.push("A");
  if (pg?.agentBId === "interactive") interactivePlayers.push("B");

  const currentState = match?.currentState;
  const awaiting = (currentState?.awaiting as PlayerSide[]) ?? [];
  const phase = currentState?.phase as string | undefined;

  const messages: ChatMessage[] = (match?.history ?? []).flatMap((r) => {
    const msgs: ChatMessage[] = [];
    if (r.action_a !== undefined)
      msgs.push({ player: "A", text: formatAction(r.action_a), round: r.round });
    if (r.action_b !== undefined)
      msgs.push({ player: "B", text: formatAction(r.action_b), round: r.round });
    return msgs;
  });

  const awaitingInteractive = awaiting.filter((p) => interactivePlayers.includes(p));

  useEffect(() => {
    if (listRef.current) {
      listRef.current.scrollTop = listRef.current.scrollHeight;
    }
  }, [messages, awaitingInteractive]);

  if (interactivePlayers.length === 0) return null;

  const handleSubmit = async () => {
    const trimmed = inputValue.trim();
    if (!trimmed || submitting) return;
    setSubmitting(true);
    try {
      let action: unknown = trimmed;
      try { action = JSON.parse(trimmed); } catch { /* keep as string */ }
      const playerSide = awaitingInteractive[0];
      const token = pg!.tokens[playerSide];
      await submitAction(pg!.sessionId, action, token);
      setInputValue("");
    } catch (e) {
      console.error("Failed to submit action:", e);
      alert(`Failed to submit action: ${e instanceof Error ? e.message : String(e)}`);
    } finally {
      setSubmitting(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter") handleSubmit();
  };

  const gameComplete = phase === "complete";

  return (
    <div className="border-t border-line/40">
      <div className="flex items-center gap-2 px-4 py-2 bg-surface/80 border-b border-line/30">
        <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
        <span className="text-[11px] font-extrabold text-muted uppercase tracking-wider">
          Interactive Agent
        </span>
      </div>

      <div ref={listRef} className="max-h-64 overflow-y-auto p-3 space-y-2">
        {messages.length === 0 && awaitingInteractive.length === 0 && (
          <p className="text-[11px] text-muted text-center py-4">
            Waiting for the game to start...
          </p>
        )}
        {messages.map((msg, i) => (
          <div key={i} className={`flex items-start gap-2 text-xs`}>
            <span
              className={`shrink-0 px-1.5 py-0.5 rounded text-[10px] font-extrabold border ${PLAYER_COLORS[msg.player]}`}
            >
              {PLAYER_LABELS[msg.player]}
            </span>
            <span className="text-ink/80 break-all min-w-0">{msg.text}</span>
          </div>
        ))}
        {awaitingInteractive.map((p) => (
          <div key={`await-${p}`} className="flex items-center gap-2 text-xs text-muted italic">
            <span
              className={`shrink-0 px-1.5 py-0.5 rounded text-[10px] font-extrabold border ${PLAYER_COLORS[p]}`}
            >
              {PLAYER_LABELS[p]}
            </span>
            <span>awaiting your action...</span>
          </div>
        ))}
        {gameComplete && (
          <p className="text-[11px] text-muted text-center pt-2 border-t border-line/20">
            Game complete.
          </p>
        )}
      </div>

      {awaitingInteractive.length > 0 && (
        <div className="flex items-center gap-2 p-3 border-t border-line/30 bg-surface">
          <input
            type="text"
            value={inputValue}
            onChange={(e) => setInputValue(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder={`Enter action for ${PLAYER_LABELS[awaitingInteractive[0]]}...`}
            disabled={submitting}
            className="flex-1 px-3 py-1.5 text-xs rounded-md border border-line/40 bg-surface-soft text-ink placeholder:text-muted/60 focus:outline-none focus:border-accent/50"
          />
          <button
            type="button"
            onClick={handleSubmit}
            disabled={submitting || !inputValue.trim()}
            className="px-3 py-1.5 text-xs font-bold rounded-md bg-accent text-white hover:bg-accent/90 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
          >
            {submitting ? "Sending..." : "Submit"}
          </button>
        </div>
      )}
    </div>
  );
}

function formatAction(action: unknown): string {
  if (typeof action === "string") return action;
  if (Array.isArray(action)) return `[${action.join(", ")}]`;
  if (typeof action === "number") return String(action);
  if (action && typeof action === "object") {
    try {
      return JSON.stringify(action);
    } catch {
      return String(action);
    }
  }
  return String(action);
}
