import { useApp } from "@frontend/hooks/useApp";
import type { MatchRound } from "@frontend/types";

const PLAYER_COLORS: Record<string, string> = {
  A: "bg-agent-a text-white",
  B: "bg-agent-b text-white",
  C: "bg-violet-500 text-white",
  D: "bg-amber-500 text-white",
  E: "bg-rose-500 text-white",
  F: "bg-sky-500 text-white",
  G: "bg-teal-500 text-white",
  H: "bg-orange-500 text-white",
  I: "bg-pink-500 text-white",
  J: "bg-lime-500 text-white",
};
const PLAYER_BAR_COLORS: Record<string, string> = {
  A: "bg-agent-a",
  B: "bg-agent-b",
  C: "bg-violet-500",
  D: "bg-amber-500",
  E: "bg-rose-500",
  F: "bg-sky-500",
  G: "bg-teal-500",
  H: "bg-orange-500",
  I: "bg-pink-500",
  J: "bg-lime-500",
};

function getRoundData(r: MatchRound) {
  const raw = r.raw as Record<string, unknown> | undefined;
  return {
    contributions: raw?.contributions as Record<string, number> | undefined,
    pool: raw?.pool as number | undefined,
    share: raw?.share as number | undefined,
    roundPayoffs: raw?.round_payoffs as Record<string, number> | undefined,
  };
}

export default function PGGLiveView() {
  const { state } = useApp();
  const match = state.activeMatch;
  const hasMatch = Boolean(match);
  const isGameRunning = Boolean(state.pendingGame);
  const round = match?.history[state.activeRoundIndex] ?? null;
  const totalRounds = match?.num_rounds ?? 0;
  const currentRound = round?.round ?? 0;
  const roundProgress = totalRounds > 0 ? Math.round((currentRound / totalRounds) * 100) : 0;

  if (!hasMatch) {
    return (
      <div className="flex flex-col h-full bg-surface-soft">
        <div className="shrink-0 flex items-center justify-between gap-4 px-5 py-3 border-b border-line/40 bg-surface/80 backdrop-blur-sm">
          {["A", "B", "C", "D", "E", "F"].map((id) => (
            <div key={id} className="flex items-center gap-1.5">
              <span className={`w-7 h-7 rounded-full flex items-center justify-center text-[10px] font-black ${PLAYER_COLORS[id]}`}>{id}</span>
            </div>
          ))}
        </div>
        <div className="flex-1 flex items-center justify-center">
          <div className="text-center px-6">
            <div className="w-16 h-16 mx-auto mb-4 rounded-2xl bg-surface-container flex items-center justify-center text-3xl">
              {isGameRunning ? (
                <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" className="text-accent/70 animate-spin">
                  <path d="M21 12a9 9 0 1 1-6.219-8.56" />
                </svg>
              ) : "🤝"}
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

  const firstRoundData = history.length > 0 ? getRoundData(history[0]) : null;
  const playerIds = firstRoundData?.contributions ? Object.keys(firstRoundData.contributions) : [];

  const endowmentHint = firstRoundData?.contributions && firstRoundData?.pool != null
    ? Math.max(...Object.values(firstRoundData.contributions), (firstRoundData.pool ?? 0) / playerIds.length)
    : 10;

  const avgContributions: Record<string, number> = {};
  for (const pid of playerIds) {
    const total = history.reduce((sum, r) => {
      const d = getRoundData(r);
      return sum + (d.contributions?.[pid] ?? 0);
    }, 0);
    avgContributions[pid] = history.length > 0 ? total / history.length : 0;
  }

  return (
    <div className="flex flex-col h-full bg-surface-soft">
      <div className="shrink-0 sticky top-0 z-10 border-b border-line/40 bg-surface/80 backdrop-blur-sm">
        <div className="flex items-center gap-3 px-4 py-2.5 flex-wrap">
          {playerIds.map((pid) => {
            const totalScore = history.length > 0
              ? (getRoundData(history[history.length - 1]).roundPayoffs?.[pid] ?? 0)
              : 0;
            const cumScore = (history[state.activeRoundIndex]?.raw as Record<string, unknown> | undefined)?.total_scores as Record<string, number> | undefined;
            const cum = cumScore?.[pid];
            return (
              <div key={pid} className="flex items-center gap-1.5">
                <span className={`w-6 h-6 rounded-full flex items-center justify-center text-[9px] font-black shrink-0 ${PLAYER_COLORS[pid] ?? "bg-line text-ink"}`}>{pid}</span>
                <div>
                  <div className="text-[10px] font-semibold text-ink truncate max-w-[60px]">
                    {match!.agents?.[pid] ?? pid}
                  </div>
                  <div className="text-[9px] text-quiet font-mono">{cum != null ? cum.toFixed(1) : totalScore.toFixed(1)}</div>
                </div>
              </div>
            );
          })}
          <div className="ml-auto text-right">
            {matchComplete && (
              <div className="text-[11px] text-muted font-semibold">Complete</div>
            )}
          </div>
        </div>

        <div className="flex items-center gap-3 px-4 pb-2.5">
          <div className="flex-1 h-1 rounded-full bg-line/30 overflow-hidden">
            <div className="h-full rounded-full bg-accent transition-all duration-500" style={{ width: `${roundProgress}%` }} />
          </div>
          <span className="text-[10px] font-extrabold text-muted uppercase whitespace-nowrap">R{currentRound}/{totalRounds}</span>
        </div>
      </div>

      <div className="flex-1 overflow-y-auto p-4">
        <div className="text-[10px] font-extrabold text-muted uppercase tracking-wider mb-3">Round History</div>
        <div className="grid gap-3">
          {[...history].reverse().map((r) => {
            const { contributions, pool, share } = getRoundData(r);
            const isActive = r.round === currentRound;
            return (
              <div
                key={r.round}
                className={`rounded-xl border px-4 py-3 transition-colors ${isActive ? "border-accent/50 bg-accent/5" : "border-line/30 bg-surface"}`}
              >
                <div className="flex items-center justify-between mb-2">
                  <span className="text-[11px] font-extrabold text-muted">R{r.round}</span>
                  <div className="flex items-center gap-3 text-[10px] text-quiet">
                    <span>Pool: <span className="font-bold text-ink">{pool?.toFixed(1) ?? "—"}</span></span>
                    <span>Each: <span className="font-bold text-emerald-600 dark:text-emerald-400">+{share?.toFixed(1) ?? "—"}</span></span>
                  </div>
                </div>
                <div className="grid gap-1.5">
                  {playerIds.map((pid) => {
                    const contrib = contributions?.[pid] ?? 0;
                    const barW = endowmentHint > 0 ? Math.round((contrib / endowmentHint) * 100) : 0;
                    return (
                      <div key={pid} className="flex items-center gap-2">
                        <span className={`w-4 h-4 rounded-full flex items-center justify-center text-[8px] font-black shrink-0 ${PLAYER_COLORS[pid] ?? "bg-line text-ink"}`}>{pid}</span>
                        <div className="flex-1 h-2 rounded-full bg-line/20 overflow-hidden">
                          <div
                            className={`h-full rounded-full transition-all duration-300 ${PLAYER_BAR_COLORS[pid] ?? "bg-line"}`}
                            style={{ width: `${barW}%`, opacity: 0.7 }}
                          />
                        </div>
                        <span className="text-[10px] font-mono text-muted w-10 text-right shrink-0">{contrib.toFixed(1)}</span>
                      </div>
                    );
                  })}
                </div>
              </div>
            );
          })}
        </div>

        {history.length > 0 && (
          <div className="mt-4 rounded-xl border border-line/30 bg-surface p-4">
            <div className="text-[10px] font-extrabold text-muted uppercase tracking-wider mb-3">Avg Contribution</div>
            <div className="grid gap-1.5">
              {playerIds.map((pid) => {
                const avg = avgContributions[pid] ?? 0;
                const barW = endowmentHint > 0 ? Math.round((avg / endowmentHint) * 100) : 0;
                return (
                  <div key={pid} className="flex items-center gap-2">
                    <span className={`w-4 h-4 rounded-full flex items-center justify-center text-[8px] font-black shrink-0 ${PLAYER_COLORS[pid] ?? "bg-line text-ink"}`}>{pid}</span>
                    <div className="flex-1 h-2 rounded-full bg-line/20 overflow-hidden">
                      <div className={`h-full rounded-full transition-all duration-300 ${PLAYER_BAR_COLORS[pid] ?? "bg-line"}`} style={{ width: `${barW}%` }} />
                    </div>
                    <span className="text-[10px] font-mono text-muted w-10 text-right shrink-0">{avg.toFixed(1)}</span>
                  </div>
                );
              })}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
