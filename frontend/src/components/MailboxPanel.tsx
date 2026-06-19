import { useState, useEffect, useRef } from "react";
import { sendMessage, getMessages } from "../api";
import type { MailMessage } from "../types";

interface MailboxPanelProps {
  sessionId: string;
  playerToken?: string;
}

export function MailboxPanel({ sessionId, playerToken }: MailboxPanelProps) {
  const [messages, setMessages] = useState<MailMessage[]>([]);
  const [input, setInput] = useState("");
  const [expanded, setExpanded] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);

  const fetchMessages = async () => {
    try {
      const data = await getMessages(sessionId, playerToken);
      setMessages(data.messages);
    } catch {
      // silent
    }
  };

  useEffect(() => {
    fetchMessages();
    const id = setInterval(fetchMessages, 3000);
    return () => clearInterval(id);
  }, [sessionId]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const handleSend = async () => {
    const text = input.trim();
    if (!text) return;
    try {
      await sendMessage(sessionId, text, undefined, playerToken);
      setInput("");
      await fetchMessages();
    } catch {
      // silent
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  return (
    <div className="border-t border-line/40">
      <button
        type="button"
        onClick={() => setExpanded(!expanded)}
        className="w-full flex items-center justify-between px-4 py-2 text-xs font-bold text-muted hover:text-ink transition-colors cursor-pointer"
      >
        <span>Mailbox ({messages.length})</span>
        <svg
          width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor"
          strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"
          className={`transition-transform ${expanded ? "rotate-180" : ""}`}
        >
          <polyline points="6 9 12 15 18 9" />
        </svg>
      </button>
      {expanded && (
        <div className="px-4 pb-3">
          <div className="max-h-48 overflow-y-auto space-y-1.5 mb-2 bg-surface-container/20 rounded-card p-2 border border-line/20">
            {messages.length === 0 && (
              <p className="text-[10px] text-muted text-center py-2">No messages yet.</p>
            )}
            {messages.map((m, i) => (
              <div key={i} className="text-[11px] leading-snug">
                <span className="font-bold text-ink">{m.from_player}</span>
                {m.to_player && (
                  <span className="text-muted"> → {m.to_player}</span>
                )}
                <span className="text-muted">: </span>
                <span className="text-ink">{m.content}</span>
              </div>
            ))}
            <div ref={bottomRef} />
          </div>
          <div className="flex gap-2">
            <input
              type="text"
              value={input}
              onChange={(e) => setInput(e.target.value.slice(0, 200))}
              onKeyDown={handleKeyDown}
              placeholder="Type a message..."
              maxLength={200}
              className="flex-1 min-w-0 rounded-md border border-line/40 bg-surface px-2 py-1 text-xs text-ink placeholder:text-muted/50 outline-none focus:border-accent transition-colors"
            />
            <button
              type="button"
              onClick={handleSend}
              disabled={!input.trim()}
              className="shrink-0 rounded-md bg-accent text-white px-3 py-1 text-xs font-semibold hover:bg-accent/90 disabled:opacity-40 disabled:cursor-not-allowed cursor-pointer transition-colors"
            >
              Send
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
