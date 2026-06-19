import { useState, useEffect, useRef } from "react";
import { sendMailboxMessage } from "../api";
import type { MailboxMessage } from "../types";

interface MailboxPanelProps {
  sessionId: string;
  playerToken: string;
  humanPlayer: string;
  allPlayers: string[];
  messages: MailboxMessage[];
  disabled?: boolean;
  collapsed?: boolean;
  onToggleCollapse?: () => void;
}

const PLAYER_COLORS: Record<string, string> = {
  A: "text-agent-a",
  B: "text-agent-b",
  C: "text-violet-500",
  D: "text-amber-500",
  E: "text-rose-500",
  F: "text-sky-500",
  G: "text-teal-500",
  H: "text-orange-500",
  I: "text-pink-500",
  J: "text-lime-500",
};

function playerLabel(player: string, humanPlayer: string): string {
  return player === humanPlayer ? "You" : `Player ${player}`;
}

function MessageBubble({
  msg,
  humanPlayer,
}: {
  msg: MailboxMessage;
  humanPlayer: string;
}) {
  const isMe = msg.sender === humanPlayer;
  const colorClass = PLAYER_COLORS[msg.sender] ?? "text-muted";

  return (
    <div className={`flex flex-col ${isMe ? "items-end" : "items-start"} mb-2`}>
      <div className="flex items-center gap-1.5 mb-0.5">
        <span className={`text-[10px] font-bold ${colorClass}`}>
          {playerLabel(msg.sender, humanPlayer)}
        </span>
        {msg.recipient !== "all" && (
          <span className="text-[9px] text-muted/60 px-1 py-0.5 rounded bg-ink/5">
            to {playerLabel(msg.recipient, humanPlayer)}
          </span>
        )}
        <span className="text-[9px] text-muted/50">R{msg.round}</span>
      </div>
      <div
        className={`max-w-[80%] px-3 py-1.5 rounded-xl text-sm ${
          isMe
            ? "bg-accent/10 text-ink border border-accent/20"
            : "bg-surface-container text-ink border border-line/30"
        }`}
      >
        {msg.content}
      </div>
    </div>
  );
}

export function MailboxPanel({
  sessionId,
  playerToken,
  humanPlayer,
  allPlayers,
  messages,
  disabled = false,
  collapsed = false,
  onToggleCollapse,
}: MailboxPanelProps) {
  const [inputValue, setInputValue] = useState("");
  const [recipient, setRecipient] = useState("all");
  const [sending, setSending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const scrollRef = useRef<HTMLDivElement>(null);

  const opponentPlayers = allPlayers.filter((p) => p !== humanPlayer);

  useEffect(() => {
    if (scrollRef.current && !collapsed) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages.length, collapsed]);

  const handleSend = async () => {
    const content = inputValue.trim();
    if (!content || sending || disabled) return;
    setSending(true);
    setError(null);
    try {
      await sendMailboxMessage(sessionId, content, recipient, playerToken);
      setInputValue("");
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setSending(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  if (collapsed) {
    const unreadCount = 0;
    return (
      <button
        type="button"
        onClick={onToggleCollapse}
        className="shrink-0 flex items-center gap-2 px-3 py-1.5 rounded-lg bg-surface-container border border-line/30 hover:border-accent/40 transition-colors"
      >
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="text-muted">
          <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/>
        </svg>
        <span className="text-xs font-semibold text-muted">Chat</span>
        {messages.length > 0 && (
          <span className="text-[10px] font-bold text-accent">{messages.length}</span>
        )}
        {unreadCount > 0 && (
          <span className="w-2 h-2 rounded-full bg-accent animate-pulse" />
        )}
      </button>
    );
  }

  return (
    <div className="shrink-0 flex flex-col border-t border-line/30 bg-surface/80 max-h-48">
      <div className="shrink-0 flex items-center justify-between px-3 py-1.5 border-b border-line/20">
        <div className="flex items-center gap-2">
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="text-muted">
            <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/>
          </svg>
          <span className="text-[11px] font-bold text-muted uppercase tracking-wider">Chat</span>
        </div>
        <button
          type="button"
          onClick={onToggleCollapse}
          className="w-5 h-5 flex items-center justify-center rounded hover:bg-surface-container text-muted hover:text-ink transition-colors"
        >
          <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round">
            <polyline points="18 15 12 9 6 15"/>
          </svg>
        </button>
      </div>

      <div ref={scrollRef} className="flex-1 overflow-y-auto px-3 py-2 min-h-0">
        {messages.length === 0 ? (
          <div className="flex items-center justify-center h-full text-[11px] text-muted/60">
            No messages yet
          </div>
        ) : (
          messages.map((msg) => (
            <MessageBubble key={msg.id} msg={msg} humanPlayer={humanPlayer} />
          ))
        )}
      </div>

      {error && (
        <div className="shrink-0 mx-3 mb-1 px-2 py-1 rounded bg-red-50 dark:bg-red-950/30 border border-red-200 dark:border-red-800/40 text-[10px] text-red-600 dark:text-red-400">
          {error}
        </div>
      )}

      <div className="shrink-0 flex items-center gap-2 px-3 py-2 border-t border-line/20">
        {opponentPlayers.length > 1 && (
          <select
            value={recipient}
            onChange={(e) => setRecipient(e.target.value)}
            disabled={disabled || sending}
            className="shrink-0 text-[10px] font-semibold px-1.5 py-1 rounded border border-line/40 bg-surface text-muted focus:outline-none focus:border-accent/60"
          >
            <option value="all">All</option>
            {opponentPlayers.map((p) => (
              <option key={p} value={p}>P{p}</option>
            ))}
          </select>
        )}
        <input
          type="text"
          value={inputValue}
          onChange={(e) => setInputValue(e.target.value)}
          onKeyDown={handleKeyDown}
          disabled={disabled || sending}
          placeholder={disabled ? "Game ended" : "Type a message..."}
          className="flex-1 min-w-0 px-2 py-1 rounded-lg border border-line/40 bg-surface text-ink text-xs focus:outline-none focus:border-accent/60 disabled:opacity-50"
        />
        <button
          type="button"
          onClick={handleSend}
          disabled={disabled || sending || !inputValue.trim()}
          className="shrink-0 px-2.5 py-1 rounded-lg bg-accent text-white text-[11px] font-bold hover:bg-accent/90 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
        >
          {sending ? "..." : "Send"}
        </button>
      </div>
    </div>
  );
}

export function MailboxHistory({
  messages,
  humanPlayer,
}: {
  messages: MailboxMessage[];
  humanPlayer?: string;
}) {
  if (messages.length === 0) return null;

  return (
    <div className="mt-4 border border-line/30 rounded-xl overflow-hidden">
      <div className="flex items-center gap-2 px-4 py-2 bg-surface-container border-b border-line/20">
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="text-muted">
          <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/>
        </svg>
        <span className="text-xs font-bold text-muted uppercase tracking-wider">
          Chat ({messages.length} messages)
        </span>
      </div>
      <div className="px-4 py-3 bg-surface max-h-60 overflow-y-auto">
        {messages.map((msg) => (
          <div key={msg.id} className="flex items-start gap-2 mb-2 last:mb-0">
            <span className={`text-[10px] font-bold ${PLAYER_COLORS[msg.sender] ?? "text-muted"} shrink-0 mt-0.5`}>
              R{msg.round} {playerLabel(msg.sender, humanPlayer ?? "")}
            </span>
            {msg.recipient !== "all" && (
              <span className="text-[9px] text-muted/60 px-1 py-0.5 rounded bg-ink/5 shrink-0 mt-0.5">
                → {playerLabel(msg.recipient, humanPlayer ?? "")}
              </span>
            )}
            <span className="text-xs text-ink">{msg.content}</span>
          </div>
        ))}
      </div>
    </div>
  );
}
