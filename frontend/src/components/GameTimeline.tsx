import type { MailboxMessage, MatchRound } from "../types";

interface GameTimelineProps {
  history: MatchRound[];
  messages: MailboxMessage[];
  agentA?: string;
  agentB?: string;
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

function formatAction(action: unknown): string {
  if (Array.isArray(action)) return `[${action.join(", ")}]`;
  if (typeof action === "string") return action;
  if (typeof action === "number") return String(action);
  return String(action ?? "");
}

function formatTime(createdAt?: string): string | null {
  if (!createdAt) return null;
  const d = new Date(createdAt);
  if (Number.isNaN(d.getTime())) return null;
  return d.toLocaleTimeString(undefined, { hour: "2-digit", minute: "2-digit", second: "2-digit" });
}

function TimelineMessage({ msg }: { msg: MailboxMessage }) {
  const colorClass = PLAYER_COLORS[msg.sender] ?? "text-muted";
  const time = formatTime(msg.created_at);

  return (
    <div className="flex items-start gap-2 px-3 py-1.5 border-b border-line/20 last:border-b-0 bg-surface-container/20">
      <span className={`text-[10px] font-bold ${colorClass} shrink-0 mt-0.5`}>
        Player {msg.sender}
      </span>
      {msg.recipient !== "all" && (
        <span className="text-[9px] text-muted/60 px-1 py-0.5 rounded bg-ink/5 shrink-0 mt-0.5">
          → Player {msg.recipient}
        </span>
      )}
      <span className="text-xs text-ink flex-1">{msg.content}</span>
      {msg.turn_phase && (
        <span className="text-[9px] font-semibold text-muted/70 px-1.5 py-0.5 rounded bg-ink/5 shrink-0">
          {msg.turn_phase === "before" ? `before ${msg.sender}'s move` : `after ${msg.sender}'s move`}
        </span>
      )}
      {time && (
        <span className="text-[10px] text-muted/50 font-mono shrink-0 mt-0.5">{time}</span>
      )}
    </div>
  );
}

function RoundResultRow({ round }: { round: MatchRound }) {
  return (
    <div
      className={`grid grid-cols-[auto_1fr_1fr_auto_auto] gap-3 items-center px-3 py-2 border-b border-line/20 last:border-b-0 ${
        round.winner === "A" ? "bg-agent-a/[0.04]" : round.winner === "B" ? "bg-agent-b/[0.04]" : ""
      }`}
    >
      <span className="text-xs text-muted font-mono">R{round.round}</span>
      <span className="text-xs text-ink font-mono">{formatAction(round.action_a)}</span>
      <span className="text-xs text-ink font-mono">{formatAction(round.action_b)}</span>
      <span className="text-xs text-ink">
        A:{round.score_a} B:{round.score_b}
      </span>
      <span className={`text-xs font-bold ${round.winner === "A" ? "text-agent-a" : round.winner === "B" ? "text-agent-b" : "text-muted"}`}>
        {round.winner === "Tie" ? "D" : round.winner}
      </span>
    </div>
  );
}

export function GameTimeline({ history, messages, agentA, agentB }: GameTimelineProps) {
  if (history.length === 0 && messages.length === 0) return null;

  const messagesByRound = new Map<number, MailboxMessage[]>();
  for (const msg of messages) {
    const round = typeof msg.round === "number" ? msg.round : 0;
    const list = messagesByRound.get(round) ?? [];
    list.push(msg);
    messagesByRound.set(round, list);
  }

  const roundNumbers = new Set<number>(history.map((r) => r.round));
  for (const round of messagesByRound.keys()) {
    roundNumbers.add(round);
  }
  const orderedRounds = Array.from(roundNumbers).sort((a, b) => a - b);
  const historyByRound = new Map<number, MatchRound>(history.map((r) => [r.round, r]));

  return (
    <div className="rounded-card border border-line/40 overflow-hidden">
      <div className="grid grid-cols-[auto_1fr_1fr_auto_auto] gap-3 items-center px-3 py-2 border-b border-line/40 bg-surface-container/50">
        <span className="text-[10px] font-extrabold text-muted">R</span>
        <span className="text-[10px] font-extrabold text-muted">{agentA ?? "A"}</span>
        <span className="text-[10px] font-extrabold text-muted">{agentB ?? "B"}</span>
        <span className="text-[10px] font-extrabold text-muted">Scores</span>
        <span className="text-[10px] font-extrabold text-muted">W</span>
      </div>
      {orderedRounds.map((round) => {
        const roundMessages = messagesByRound.get(round) ?? [];
        const roundResult = historyByRound.get(round);
        return (
          <div key={round}>
            {roundMessages.map((msg) => (
              <TimelineMessage key={msg.id} msg={msg} />
            ))}
            {roundResult && <RoundResultRow round={roundResult} />}
          </div>
        );
      })}
    </div>
  );
}
