import { useApp } from "@frontend/hooks/useApp";
import type { Match, MatchRound } from "@frontend/types";

function agentInitial(name: string): string {
  return (name.trim().charAt(0) || "?").toUpperCase();
}

export default function ExampleLiveView() {
  const { state } = useApp();
  const hasMatch = Boolean(state.activeMatch);
  const isGameRunning = Boolean(state.pendingGame);

  const match = state.activeMatch;
  const round = match?.history[state.activeRoundIndex] ?? null;

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
  const matchComplete = match!.match_winner !== undefined;

  return (
    <div className="flex flex-col h-full bg-surface-soft">
      <div className="shrink-0 sticky top-0 z-10 border-b border-line/40 bg-surface/80 backdrop-blur-sm">
        <div className="flex items-center justify-between px-4 py-2.5">
          <div className="flex items-center gap-2 min-w-0">
            <div className="w-7 h-7 rounded-full bg-agent-a/12 border border-agent-a/40 flex items-center justify-center shrink-0">
              <span className="text-[10px] font-black text-agent-a">{agentInitial(match!.agent_a)}</span>
            </div>
            <span className="text-xs font-semibold text-ink truncate">{match!.agent_a}</span>
          </div>

          <div className="flex flex-col items-center gap-0.5">
            <div className="flex items-center gap-1.5">
              <span className="tabular-nums text-sm font-black text-agent-a">{match!.score_a}</span>
              <span className="text-[10px] font-bold text-muted">-</span>
              <span className="tabular-nums text-sm font-black text-agent-b">{match!.score_b}</span>
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

          <div className="flex items-center gap-2 min-w-0">
            <span className="text-xs font-semibold text-ink truncate">{match!.agent_b}</span>
            <div className="w-7 h-7 rounded-full bg-agent-b/12 border border-agent-b/40 flex items-center justify-center shrink-0">
              <span className="text-[10px] font-black text-agent-b">{agentInitial(match!.agent_b)}</span>
            </div>
          </div>
        </div>
      </div>

      <div className="flex-1 overflow-y-auto p-4">
        <div className="grid gap-3">
          {history.map((r) => {
            const isActive = r.round === round?.round;
            return (
              <div
                key={r.round}
                className={`flex items-center gap-3 rounded-xl px-4 py-3 border transition-colors ${isActive ? "border-accent/50 bg-accent/5" : "border-line/30 bg-surface"}`}
              >
                <span className="text-[11px] font-extrabold text-muted w-10 shrink-0">R{r.round}</span>
                <span className="text-xs text-quiet flex-1 text-center">Round {r.round}</span>
                <span className="text-[10px] text-quiet font-mono w-14 text-right shrink-0">
                  {r.score_a > 0 ? "+" : ""}{r.score_a}/{r.score_b > 0 ? "+" : ""}{r.score_b}
                </span>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}
