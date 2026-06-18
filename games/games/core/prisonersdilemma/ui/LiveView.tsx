import { useApp } from "@frontend/hooks/useApp";
import type { Match, MatchRound } from "@frontend/types";

function agentInitial(name: string): string {
  return (name.trim().charAt(0) || "?").toUpperCase();
}

function getAction(round: MatchRound | null, side: "A" | "B"): string | undefined {
  return (round?.raw?.actions as Record<string, string> | undefined)?.[side];
}

function getOutcome(round: MatchRound | null): string | undefined {
  return round?.raw?.outcome as string | undefined;
}

const ACTION_LABEL: Record<string, string> = { cooperate: "Cooperate", defect: "Defect" };
const ACTION_EMOJI: Record<string, string> = { cooperate: "\u{1F91D}", defect: "\u{1F5E1}\u{FE0F}" };
const ACTION_SHORT: Record<string, string> = { cooperate: "C", defect: "D" };
const ACTION_COLOR: Record<string, string> = {
  cooperate: "text-emerald-600 dark:text-emerald-400",
  defect: "text-red-600 dark:text-red-400",
};
const ACTION_BG: Record<string, string> = {
  cooperate: "bg-emerald-50 border-emerald-200 dark:bg-emerald-950/30 dark:border-emerald-800/50",
  defect: "bg-red-50 border-red-200 dark:bg-red-950/30 dark:border-red-800/50",
};
const OUTCOME_STYLE: Record<string, string> = {
  CC: "bg-emerald-100 text-emerald-700 border-emerald-200 dark:bg-emerald-950/40 dark:text-emerald-300 dark:border-emerald-700/40",
  DD: "bg-red-100 text-red-700 border-red-200 dark:bg-red-950/40 dark:text-red-300 dark:border-red-700/40",
  CD: "bg-amber-100 text-amber-700 border-amber-200 dark:bg-amber-950/40 dark:text-amber-300 dark:border-amber-700/40",
  DC: "bg-amber-100 text-amber-700 border-amber-200 dark:bg-amber-950/40 dark:text-amber-300 dark:border-amber-700/40",
};

function outcomeCounts(history: MatchRound[]): { cc: number; cd: number; dc: number; dd: number } {
  let cc = 0, cd = 0, dc = 0, dd = 0;
  for (const r of history) {
    const o = getOutcome(r);
    if (o === "CC") cc++;
    else if (o === "CD") cd++;
    else if (o === "DC") dc++;
    else if (o === "DD") dd++;
  }
  return { cc, cd, dc, dd };
}

interface LiveViewProps {
  onScores?: (scores: { displayedScoreA: number; displayedScoreB: number }) => void;
  onToggleCollapse: () => void;
  createdAt?: string | null;
}

export default function PDLiveView(_props: LiveViewProps) {
  const { state } = useApp();
  const hasMatch = Boolean(state.activeMatch);
  const isGameRunning = Boolean(state.pendingGame);

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
                  <path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2" />
                  <circle cx="9" cy="7" r="4" />
                  <path d="M23 21v-2a4 4 0 0 0-3-3.87" />
                  <path d="M16 3.13a4 4 0 0 1 0 7.75" />
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
  const outcomes = outcomeCounts(history);
  const matchComplete = match!.match_winner !== undefined;

  return (
    <div className="flex flex-col h-full bg-surface-soft">
      {/* Header bar */}
      <div className="shrink-0 sticky top-0 z-10 border-b border-line/40 bg-surface/80 backdrop-blur-sm">
        <div className="flex items-center justify-between px-4 py-2.5">
          {/* Agent A */}
          <div className="flex items-center gap-2 min-w-0">
            <div className="w-7 h-7 rounded-full bg-agent-a/12 border border-agent-a/40 flex items-center justify-center shrink-0">
              <span className="text-[10px] font-black text-agent-a">{agentInitial(match!.agent_a)}</span>
            </div>
            <span className="text-xs font-semibold text-ink truncate">{match!.agent_a}</span>
          </div>

          {/* Outcome summary + match result */}
          <div className="flex flex-col items-center gap-0.5">
            <div className="flex items-center gap-2 text-xs font-mono">
              <span className="font-black text-emerald-600 dark:text-emerald-400">CC:{outcomes.cc}</span>
              <span className="text-quiet">-</span>
              <span className="font-black text-amber-600 dark:text-amber-400">CD:{outcomes.cd}</span>
              <span className="text-quiet">-</span>
              <span className="font-black text-amber-600 dark:text-amber-400">DC:{outcomes.dc}</span>
              <span className="text-quiet">-</span>
              <span className="font-black text-red-600 dark:text-red-400">DD:{outcomes.dd}</span>
            </div>
            {matchComplete && (
              <span style={{ fontSize: "12px", color: "var(--color-muted)", lineHeight: 1.2 }}>
                Outcome:{" "}
                <span style={{ fontWeight: 700 }}>
                  {match!.match_winner === "Tie"
                    ? "Draw"
                    : `Player ${match!.match_winner} wins`
                  }
                </span>
              </span>
            )}
          </div>

          {/* Agent B */}
          <div className="flex items-center gap-2 min-w-0">
            <span className="text-xs font-semibold text-ink truncate">{match!.agent_b}</span>
            <div className="w-7 h-7 rounded-full bg-agent-b/12 border border-agent-b/40 flex items-center justify-center shrink-0">
              <span className="text-[10px] font-black text-agent-b">{agentInitial(match!.agent_b)}</span>
            </div>
          </div>
        </div>

        {/* Round progress */}
        <div className="flex items-center gap-3 px-4 pb-2.5">
          <div className="flex-1 h-1 rounded-full bg-line/30 overflow-hidden">
            <div className="h-full rounded-full bg-accent transition-all duration-500" style={{ width: `${roundProgress}%` }} />
          </div>
          <span className="text-[10px] font-extrabold text-muted uppercase whitespace-nowrap">
            R{currentRound}/{totalRounds}
          </span>
        </div>
      </div>

      {/* Round history */}
      <div className="flex-1 overflow-y-auto p-4">
        <div className="text-[10px] font-extrabold text-muted uppercase tracking-wider mb-3">Round History</div>
        <div className="grid gap-2">
          {[...history].reverse().map((r) => {
            const actionA = getAction(r, "A");
            const actionB = getAction(r, "B");
            const outcome = getOutcome(r);
            const isActive = r.round === currentRound;
            return (
              <div
                key={r.round}
                className={`flex items-center gap-3 rounded-xl px-4 py-3 border transition-colors ${isActive ? "border-accent/50 bg-accent/5" : "border-line/30 bg-surface"}`}
              >
                <span className="text-[11px] font-extrabold text-muted w-10 shrink-0">R{r.round}</span>

                <div className={`flex items-center gap-1.5 flex-1 ${actionA ? ACTION_COLOR[actionA] : "text-quiet"}`}>
                  <span className="text-lg">{actionA ? ACTION_EMOJI[actionA] : "\u{1F91D}"}</span>
                  <span className="text-xs font-bold">{actionA ? ACTION_SHORT[actionA] : "—"}</span>
                </div>

                <span className={`text-xs font-black px-2 py-0.5 rounded border shrink-0 ${outcome ? OUTCOME_STYLE[outcome] : "bg-surface-container border-line/40 text-quiet"}`}>
                  {outcome ?? "—"}
                </span>

                <div className={`flex items-center gap-1.5 flex-1 justify-end ${actionB ? ACTION_COLOR[actionB] : "text-quiet"}`}>
                  <span className="text-xs font-bold">{actionB ? ACTION_SHORT[actionB] : "—"}</span>
                  <span className="text-lg">{actionB ? ACTION_EMOJI[actionB] : "\u{1F91D}"}</span>
                </div>

                <span className="text-[10px] text-quiet font-mono w-16 text-right shrink-0">
                  {r.score_a.toFixed(1)}/{r.score_b.toFixed(1)}
                </span>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}
