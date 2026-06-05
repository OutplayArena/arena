import { useState } from "react";
import { useApp } from "@frontend/hooks/useApp";
import type { AnimatedScores } from "@frontend/hooks/useCanvasRenderer";
import type { Match, MatchRound } from "@frontend/types";
import { PlaybackPanel } from "@frontend/components/PlaybackPanel";

interface LiveViewProps {
  onScores?: (scores: AnimatedScores) => void;
  onToggleCollapse: () => void;
  createdAt?: string | null;
}

function fieldWinner(
  actionA: number[] | undefined,
  actionB: number[] | undefined,
  index: number,
): "A" | "B" | "Tie" {
  const a = actionA?.[index] ?? 0;
  const b = actionB?.[index] ?? 0;
  if (a > b) return "A";
  if (b > a) return "B";
  return "Tie";
}

function barWidth(a: number, b: number): string {
  const total = a + b;
  if (total === 0) return "50%";
  return `${Math.round((a / total) * 100)}%`;
}

function agentInitial(name: string): string {
  return (name.trim().charAt(0) || "?").toUpperCase();
}

function LeaderLine({ match, round }: { match: Match; round: MatchRound | null }) {
  if (match.match_winner) {
    if (match.match_winner === "Tie") {
      return (
        <span className="text-[11px] font-extrabold text-gold tracking-wide">
          Match drawn
        </span>
      );
    }
    const w = match.match_winner;
    const name = w === "A" ? match.agent_a : match.agent_b;
    const colorClass = w === "A" ? "text-agent-a" : "text-agent-b";
    return (
      <span className="flex items-center gap-1 text-[11px] font-extrabold tracking-wide">
        <span className={`inline-flex w-4 h-4 rounded-full items-center justify-center border ${w === "A" ? "bg-agent-a/12 border-agent-a/40" : "bg-agent-b/12 border-agent-b/40"}`}>
          <span className={`text-[8px] font-black ${colorClass}`}>
            {agentInitial(name)}
          </span>
        </span>
        <span className={colorClass}>{name}</span>
        <span className="text-ink">wins</span>
      </span>
    );
  }

  const scoreA = round ? round.total_score_a : 0;
  const scoreB = round ? round.total_score_b : 0;

  if (scoreA === scoreB && scoreA === 0) {
    return <span className="text-[10px] text-quiet font-medium">Tied</span>;
  }

  const diff = Math.abs(scoreA - scoreB);
  const leader = scoreA > scoreB ? "A" : scoreB > scoreA ? "B" : null;

  if (!leader) {
    return <span className="text-[10px] text-quiet font-medium">Tied</span>;
  }

  const name = leader === "A" ? match.agent_a : match.agent_b;
  const colorClass = leader === "A" ? "text-agent-a" : "text-agent-b";
  const bgClass = leader === "A" ? "bg-agent-a/12 border-agent-a/40" : "bg-agent-b/12 border-agent-b/40";

  return (
    <span className="flex items-center gap-1 text-[10px] font-semibold">
      <span className={`inline-flex w-4 h-4 rounded-full items-center justify-center border ${bgClass}`}>
        <span className={`text-[8px] font-black ${colorClass}`}>
          {agentInitial(name)}
        </span>
      </span>
      <span className={colorClass}>{name}</span>
      <span className="text-quiet"> leads by {diff}</span>
    </span>
  );
}

export default function LiveView(_props: LiveViewProps) {
  const { state } = useApp();
  const hasMatch = Boolean(state.activeMatch);
  const isGameRunning = Boolean(state.pendingGame);
  const [showPlayback, setShowPlayback] = useState(false);

  const match = state.activeMatch;
  const round = match?.history[state.activeRoundIndex] ?? null;
  const totalRounds = match?.num_rounds ?? 0;
  const currentRound = round?.round ?? 0;
  const numFields = match?.num_battlefields ?? 0;

  const totalScoreA = round ? round.total_score_a : 0;
  const totalScoreB = round ? round.total_score_b : 0;
  const roundProgress = totalRounds > 0 ? Math.round((currentRound / totalRounds) * 100) : 0;

  if (!hasMatch) {
    return (
      <div className="flex flex-col h-full bg-surface-soft">
        {/* Minimal bar */}
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
                  <rect x="3" y="3" width="7" height="7" rx="1" />
                  <rect x="14" y="3" width="7" height="7" rx="1" />
                  <rect x="3" y="14" width="7" height="7" rx="1" />
                  <rect x="14" y="14" width="7" height="7" rx="1" />
                </svg>
              )}
            </div>
            {isGameRunning ? (
              <>
                <p className="text-sm font-semibold text-muted">Waiting for first round...</p>
                <p className="text-xs text-quiet mt-1.5">Agents are computing their moves.</p>
              </>
            ) : (
              <>
                <p className="text-sm font-semibold text-muted">No battle data yet</p>
                <p className="text-xs text-quiet mt-1.5">Start a game from the Config tab.</p>
              </>
            )}
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="flex flex-col h-full bg-surface-soft">
      {/* Score bar — modern dashboard */}
      <div className="shrink-0 sticky top-0 z-10 flex items-center gap-3 px-4 py-2.5 border-b border-line/40 bg-surface/80 backdrop-blur-sm">
        {/* Agent A */}
        <div className="flex items-center gap-2.5 min-w-0">
          <div className="w-9 h-9 rounded-full bg-agent-a/12 border border-agent-a/40 flex items-center justify-center shrink-0">
            <span className="text-xs font-black text-agent-a tabular-nums">
              {agentInitial(match.agent_a)}
            </span>
          </div>
          <div className="min-w-0">
            <div className="text-[10px] font-extrabold text-muted uppercase tracking-wider leading-tight">Agent A</div>
            <div className="text-xs font-semibold text-ink truncate max-w-[100px] leading-tight">{match.agent_a}</div>
          </div>
          <span className="tabular-nums text-2xl font-black text-agent-a ml-1">
            {totalScoreA}
          </span>
        </div>

        {/* Center — round counter + leader */}
        <div className="flex flex-col items-center gap-1 mx-auto min-w-[150px]">
          <div className="flex items-center gap-2">
            <span className="text-[10px] font-extrabold text-muted uppercase tracking-wider pt-px">Round</span>
            <span className="tabular-nums text-sm font-black text-accent tracking-tight">{currentRound}</span>
            <span className="text-[11px] text-quiet font-medium">/ {totalRounds}</span>
          </div>
          <div className="w-full h-1 rounded-full bg-line/30 overflow-hidden">
            <div
              className="h-full rounded-full bg-accent transition-all duration-500"
              style={{ width: `${roundProgress}%` }}
            />
          </div>
          <LeaderLine match={match} round={round} />
        </div>

        {/* Agent B */}
        <div className="flex items-center gap-2.5 min-w-0">
          <span className="tabular-nums text-2xl font-black text-agent-b mr-1">
            {totalScoreB}
          </span>
          <div className="min-w-0 text-right">
            <div className="text-[10px] font-extrabold text-muted uppercase tracking-wider leading-tight">Agent B</div>
            <div className="text-xs font-semibold text-ink truncate max-w-[100px] leading-tight">{match.agent_b}</div>
          </div>
          <div className="w-9 h-9 rounded-full bg-agent-b/12 border border-agent-b/40 flex items-center justify-center shrink-0">
            <span className="text-xs font-black text-agent-b tabular-nums">
              {agentInitial(match.agent_b)}
            </span>
          </div>
        </div>

        {/* Toggle */}
        <div className="flex items-center shrink-0">
          <button
            type="button"
            onClick={() => setShowPlayback(p => !p)}
            title={showPlayback ? "Hide round controls" : "Show round controls"}
            className="w-7 h-7 flex items-center justify-center rounded-lg text-muted hover:text-ink hover:bg-surface-container/80 cursor-pointer transition-all duration-200 shrink-0 ml-1"
          >
            <svg
              width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor"
              strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"
              className={`transition-transform duration-200 ${showPlayback ? "" : "rotate-180"}`}
            >
              <polyline points="6 9 12 15 18 9" />
            </svg>
          </button>
        </div>
      </div>

      {/* Playback controls — toggleable */}
      {showPlayback && (
        <div className="shrink-0 border-b border-line/40 bg-surface/80 backdrop-blur-sm">
          <PlaybackPanel />
        </div>
      )}

      {/* Battlefield grid */}
      <div className="flex-1 overflow-y-auto p-4">
        <div className="grid gap-4" style={{ gridTemplateColumns: `repeat(auto-fill, minmax(200px, 1fr))` }}>
          {Array.from({ length: numFields }, (_, i) => {
            const aVal = round?.action_a?.[i] ?? 0;
            const bVal = round?.action_b?.[i] ?? 0;
            const winner = fieldWinner(round?.action_a, round?.action_b, i);
            const aPct = barWidth(aVal, bVal);
            const totalAllocation = aVal + bVal;

            return (
              <div
                key={i}
                className="rounded-xl border bg-surface p-4 shadow-sm transition-shadow hover:shadow-md"
                style={{ borderColor: winner === "A" ? "var(--color-agent-a)" : winner === "B" ? "var(--color-agent-b)" : winner === "Tie" ? "var(--color-gold)" : "var(--color-line)" }}
              >
                <div className="flex items-center justify-between mb-3">
                  <span className="text-xs font-extrabold text-muted uppercase tracking-wider">
                    Battlefield {i + 1}
                  </span>
                  {winner !== "Tie" && (
                    <div
                      className={`w-6 h-6 rounded-full border flex items-center justify-center shrink-0 ${
                        winner === "A"
                          ? "bg-agent-a/12 border-agent-a/40"
                          : "bg-agent-b/12 border-agent-b/40"
                      }`}
                    >
                      <span
                        className={`text-[10px] font-black ${
                          winner === "A" ? "text-agent-a" : "text-agent-b"
                        }`}
                      >
                        {agentInitial(winner === "A" ? match.agent_a : match.agent_b)}
                      </span>
                    </div>
                  )}
                  {winner === "Tie" && (
                    <div className="w-6 h-6 rounded-full bg-gold/15 border border-gold/30 flex items-center justify-center shrink-0">
                      <span className="text-[10px] font-black text-gold">T</span>
                    </div>
                  )}
                </div>

                <div className="mb-2">
                  <div className="flex items-center justify-between text-[11px] mb-1">
                    <span className="font-bold text-agent-a">A: {aVal}</span>
                    <span className="font-bold text-agent-b">B: {bVal}</span>
                  </div>
                  <div className="h-3 rounded-full bg-line/30 overflow-hidden flex">
                    <div
                      className="h-full bg-agent-a transition-all duration-300"
                      style={{ width: aPct }}
                    />
                    <div
                      className="h-full bg-agent-b transition-all duration-300"
                      style={{ width: `${100 - parseFloat(aPct)}%` }}
                    />
                  </div>
                </div>

                <div className="flex items-center justify-between text-[11px] text-quiet">
                  <span>Total: {totalAllocation} troops</span>
                  <span>Worth 1 pt</span>
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}
