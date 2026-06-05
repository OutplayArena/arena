import { useState } from "react";
import { useApp } from "@frontend/hooks/useApp";
import { PlaybackPanel } from "@frontend/components/PlaybackPanel";
import type { Match, MatchRound } from "@frontend/types";

const MOVE_LABEL: Record<string, string> = { rock: "Rock", paper: "Paper", scissors: "Scissors" };
const MOVE_COLOR: Record<string, string> = {
  rock: "text-amber-600 dark:text-amber-400",
  paper: "text-sky-600 dark:text-sky-400",
  scissors: "text-rose-600 dark:text-rose-400",
};
const MOVE_BG: Record<string, string> = {
  rock: "bg-amber-50 border-amber-200 dark:bg-amber-950/30 dark:border-amber-800/50",
  paper: "bg-sky-50 border-sky-200 dark:bg-sky-950/30 dark:border-sky-800/50",
  scissors: "bg-rose-50 border-rose-200 dark:bg-rose-950/30 dark:border-rose-800/50",
};

function agentInitial(name: string): string {
  return (name.trim().charAt(0) || "?").toUpperCase();
}

function getMove(round: MatchRound | null, side: "A" | "B"): string | undefined {
  return (round?.raw?.actions as Record<string, string> | undefined)?.[side];
}

function LeaderLine({ match, round }: { match: Match; round: MatchRound | null }) {
  if (match.match_winner) {
    if (match.match_winner === "Tie") {
      return <span className="text-[11px] font-extrabold text-gold tracking-wide">Match drawn</span>;
    }
    const w = match.match_winner;
    const name = w === "A" ? match.agent_a : match.agent_b;
    const colorClass = w === "A" ? "text-agent-a" : "text-agent-b";
    return (
      <span className="flex items-center gap-1 text-[11px] font-extrabold tracking-wide">
        <span className={colorClass}>{name}</span>
        <span className="text-ink">wins</span>
      </span>
    );
  }

  const scoreA = round ? round.total_score_a : 0;
  const scoreB = round ? round.total_score_b : 0;

  if (scoreA === scoreB) return <span className="text-[10px] text-quiet font-medium">Tied</span>;

  const leader = scoreA > scoreB ? "A" : "B";
  const name = leader === "A" ? match.agent_a : match.agent_b;
  const diff = Math.abs(scoreA - scoreB);
  const colorClass = leader === "A" ? "text-agent-a" : "text-agent-b";

  return (
    <span className="flex items-center gap-1 text-[10px] font-semibold">
      <span className={colorClass}>{name}</span>
      <span className="text-quiet">leads by {diff}</span>
    </span>
  );
}

interface LiveViewProps {
  onScores?: (scores: { displayedScoreA: number; displayedScoreB: number }) => void;
  onToggleCollapse: () => void;
  createdAt?: string | null;
}

export default function RPSLiveView(_props: LiveViewProps) {
  const { state } = useApp();
  const hasMatch = Boolean(state.activeMatch);
  const isGameRunning = Boolean(state.pendingGame);
  const [showPlayback, setShowPlayback] = useState(false);

  const match = state.activeMatch;
  const round = match?.history[state.activeRoundIndex] ?? null;
  const totalRounds = match?.num_rounds ?? 0;
  const currentRound = round?.round ?? 0;
  const totalScoreA = round ? round.total_score_a : 0;
  const totalScoreB = round ? round.total_score_b : 0;
  const roundProgress = totalRounds > 0 ? Math.round((currentRound / totalRounds) * 100) : 0;

  if (!hasMatch) {
    return (
      <div className="flex flex-col h-full bg-surface-soft">
        <div className="shrink-0 flex items-center justify-between gap-4 px-5 py-3 border-b border-line/40 bg-surface/80 backdrop-blur-sm">
          <div className="flex items-center gap-2">
            <span className="w-8 h-8 rounded-full bg-agent-a/15 border border-agent-a/40 flex items-center justify-center text-[11px] font-black text-agent-a">A</span>
            <span className="text-xs font-extrabold text-muted uppercase tracking-wider">Agent A</span>
          </div>
          <div className="flex items-center gap-2">
            <span className="text-xs font-extrabold text-muted uppercase tracking-wider">Agent B</span>
            <span className="w-8 h-8 rounded-full bg-agent-b/15 border border-agent-b/40 flex items-center justify-center text-[11px] font-black text-agent-b">B</span>
          </div>
        </div>
        <div className="flex-1 flex items-center justify-center">
          <div className="text-center px-6">
            <div className="w-16 h-16 mx-auto mb-4 rounded-2xl bg-surface-container flex items-center justify-center">
              {isGameRunning ? (
                <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" className="text-accent/70 animate-spin">
                  <path d="M21 12a9 9 0 1 1-6.219-8.56" />
                </svg>
              ) : (
                <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" className="text-muted/60">
                  <circle cx="12" cy="12" r="10" />
                  <path d="M12 8v4l3 3" />
                </svg>
              )}
            </div>
            {isGameRunning ? (
              <p className="text-sm font-semibold text-muted">Waiting for first round...</p>
            ) : (
              <>
                <p className="text-sm font-semibold text-muted">No match data yet</p>
                <p className="text-xs text-quiet mt-1.5">Start a game from the Config tab.</p>
              </>
            )}
          </div>
        </div>
      </div>
    );
  }

  const history = match!.history;

  return (
    <div className="flex flex-col h-full bg-surface-soft">
      {/* Score bar */}
      <div className="shrink-0 sticky top-0 z-10 flex items-center gap-3 px-4 py-2.5 border-b border-line/40 bg-surface/80 backdrop-blur-sm">
        <div className="flex items-center gap-2.5 min-w-0">
          <div className="w-9 h-9 rounded-full bg-agent-a/12 border border-agent-a/40 flex items-center justify-center shrink-0">
            <span className="text-xs font-black text-agent-a">{agentInitial(match!.agent_a)}</span>
          </div>
          <div className="min-w-0">
            <div className="text-[10px] font-extrabold text-muted uppercase tracking-wider leading-tight">Agent A</div>
            <div className="text-xs font-semibold text-ink truncate max-w-[100px] leading-tight">{match!.agent_a}</div>
          </div>
          <span className="tabular-nums text-2xl font-black text-agent-a ml-1">{totalScoreA}</span>
        </div>

        <div className="flex flex-col items-center gap-1 mx-auto min-w-[150px]">
          <div className="flex items-center gap-2">
            <span className="text-[10px] font-extrabold text-muted uppercase tracking-wider pt-px">Round</span>
            <span className="tabular-nums text-sm font-black text-accent tracking-tight">{currentRound}</span>
            <span className="text-[11px] text-quiet font-medium">/ {totalRounds}</span>
          </div>
          <div className="w-full h-1 rounded-full bg-line/30 overflow-hidden">
            <div className="h-full rounded-full bg-accent transition-all duration-500" style={{ width: `${roundProgress}%` }} />
          </div>
          <LeaderLine match={match!} round={round} />
        </div>

        <div className="flex items-center gap-2.5 min-w-0">
          <span className="tabular-nums text-2xl font-black text-agent-b mr-1">{totalScoreB}</span>
          <div className="min-w-0 text-right">
            <div className="text-[10px] font-extrabold text-muted uppercase tracking-wider leading-tight">Agent B</div>
            <div className="text-xs font-semibold text-ink truncate max-w-[100px] leading-tight">{match!.agent_b}</div>
          </div>
          <div className="w-9 h-9 rounded-full bg-agent-b/12 border border-agent-b/40 flex items-center justify-center shrink-0">
            <span className="text-xs font-black text-agent-b">{agentInitial(match!.agent_b)}</span>
          </div>
        </div>

        <button
          type="button"
          onClick={() => setShowPlayback(p => !p)}
          title={showPlayback ? "Hide round controls" : "Show round controls"}
          className="w-7 h-7 flex items-center justify-center rounded-lg text-muted hover:text-ink hover:bg-surface-container/80 cursor-pointer transition-all duration-200 shrink-0 ml-1"
        >
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"
            className={`transition-transform duration-200 ${showPlayback ? "" : "rotate-180"}`}>
            <polyline points="6 9 12 15 18 9" />
          </svg>
        </button>
      </div>

      {showPlayback && (
        <div className="shrink-0 border-b border-line/40 bg-surface/80 backdrop-blur-sm">
          <PlaybackPanel />
        </div>
      )}

      {/* Round detail — current round */}
      {round && (
        <div className="shrink-0 p-4 border-b border-line/40">
          <div className="flex items-center justify-center gap-4">
            {/* Agent A move */}
            {(() => {
              const move = getMove(round, "A");
              return (
                <div className={`flex-1 max-w-[140px] rounded-xl border p-4 text-center ${move ? MOVE_BG[move] : "bg-surface-container border-line/40"}`}>
                  <div className="text-[10px] font-extrabold text-muted uppercase tracking-wider mb-1">Agent A</div>
                  <div className={`text-lg font-black ${move ? MOVE_COLOR[move] : "text-quiet"}`}>{move ? MOVE_LABEL[move] : "—"}</div>
                </div>
              );
            })()}

            {/* Result */}
            <div className="flex flex-col items-center gap-1 shrink-0">
              <div className={`w-10 h-10 rounded-full flex items-center justify-center border-2 text-sm font-black ${
                round.winner === "A" ? "bg-agent-a/12 border-agent-a/40 text-agent-a" :
                round.winner === "B" ? "bg-agent-b/12 border-agent-b/40 text-agent-b" :
                "bg-gold/15 border-gold/30 text-gold"
              }`}>
                {round.winner === "Tie" ? "T" : round.winner}
              </div>
              <div className="text-[10px] text-quiet font-medium">
                {round.score_a > 0 ? `+${round.score_a}` : round.score_a} / {round.score_b > 0 ? `+${round.score_b}` : round.score_b}
              </div>
            </div>

            {/* Agent B move */}
            {(() => {
              const move = getMove(round, "B");
              return (
                <div className={`flex-1 max-w-[140px] rounded-xl border p-4 text-center ${move ? MOVE_BG[move] : "bg-surface-container border-line/40"}`}>
                  <div className="text-[10px] font-extrabold text-muted uppercase tracking-wider mb-1">Agent B</div>
                  <div className={`text-lg font-black ${move ? MOVE_COLOR[move] : "text-quiet"}`}>{move ? MOVE_LABEL[move] : "—"}</div>
                </div>
              );
            })()}
          </div>
        </div>
      )}

      {/* History list */}
      <div className="flex-1 overflow-y-auto p-4">
        <div className="text-[10px] font-extrabold text-muted uppercase tracking-wider mb-3">Round History</div>
        <div className="grid gap-2">
          {[...history].reverse().map((r) => {
            const moveA = getMove(r, "A");
            const moveB = getMove(r, "B");
            const isActive = r.round === currentRound;
            return (
              <div
                key={r.round}
                className={`flex items-center gap-3 rounded-lg px-3 py-2 border transition-colors ${isActive ? "border-accent/50 bg-accent/5" : "border-line/30 bg-surface"}`}
              >
                <span className="text-[11px] font-extrabold text-muted w-10 shrink-0">R{r.round}</span>
                <span className={`text-xs font-bold flex-1 ${moveA ? MOVE_COLOR[moveA] : "text-quiet"}`}>
                  {moveA ? MOVE_LABEL[moveA] : "—"}
                </span>
                <div className={`w-6 h-6 rounded-full flex items-center justify-center text-[10px] font-black border shrink-0 ${
                  r.winner === "A" ? "bg-agent-a/12 border-agent-a/40 text-agent-a" :
                  r.winner === "B" ? "bg-agent-b/12 border-agent-b/40 text-agent-b" :
                  "bg-gold/15 border-gold/30 text-gold"
                }`}>
                  {r.winner === "Tie" ? "T" : r.winner}
                </div>
                <span className={`text-xs font-bold flex-1 text-right ${moveB ? MOVE_COLOR[moveB] : "text-quiet"}`}>
                  {moveB ? MOVE_LABEL[moveB] : "—"}
                </span>
                <span className="text-[11px] text-quiet font-mono w-16 text-right shrink-0">
                  {r.total_score_a > 0 ? "+" : ""}{r.total_score_a} / {r.total_score_b > 0 ? "+" : ""}{r.total_score_b}
                </span>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}
