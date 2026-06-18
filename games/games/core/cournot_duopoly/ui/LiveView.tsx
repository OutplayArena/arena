import { useApp } from "@frontend/hooks/useApp";
import type { MatchRound } from "@frontend/types";

function agentInitial(name: string) { return (name.trim().charAt(0) || "?").toUpperCase(); }

function getRoundData(r: MatchRound) {
  const raw = r.raw as Record<string, unknown> | undefined;
  const quantities = raw?.quantities as Record<string, number> | undefined;
  const price = raw?.price as number | undefined;
  const payoffs = raw?.payoffs as Record<string, number> | undefined;
  return {
    qA: quantities?.A,
    qB: quantities?.B,
    price,
    profitA: payoffs?.A,
    profitB: payoffs?.B,
  };
}

function qBar(q: number, maxQ: number): string {
  if (maxQ <= 0) return "0%";
  return `${Math.round(Math.min((q / maxQ) * 100, 100))}%`;
}

export default function CournotLiveView() {
  const { state } = useApp();
  const match = state.activeMatch;
  const hasMatch = Boolean(match);
  const isGameRunning = Boolean(state.pendingGame);
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
            <span className="text-xs font-extrabold text-muted uppercase tracking-wider">Firm A</span>
          </div>
          <div className="flex items-center gap-2">
            <span className="text-xs font-extrabold text-muted uppercase tracking-wider">Firm B</span>
            <span className="w-8 h-8 rounded-full bg-agent-b/15 border border-agent-b/40 flex items-center justify-center text-[11px] font-black text-agent-b">B</span>
          </div>
        </div>
        <div className="flex-1 flex items-center justify-center">
          <div className="text-center px-6">
            <div className="w-16 h-16 mx-auto mb-4 rounded-2xl bg-surface-container flex items-center justify-center text-3xl">
              {isGameRunning ? (
                <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" className="text-accent/70 animate-spin">
                  <path d="M21 12a9 9 0 1 1-6.219-8.56" />
                </svg>
              ) : "📈"}
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

  const allQuantities = history.flatMap((r) => {
    const d = getRoundData(r);
    return [d.qA ?? 0, d.qB ?? 0];
  });
  const maxQ = Math.max(...allQuantities, 1);

  const avgPriceData = history.map((r) => getRoundData(r).price ?? 0);
  const avgPrice = avgPriceData.length > 0 ? avgPriceData.reduce((a, b) => a + b, 0) / avgPriceData.length : 0;

  return (
    <div className="flex flex-col h-full bg-surface-soft">
      <div className="shrink-0 sticky top-0 z-10 border-b border-line/40 bg-surface/80 backdrop-blur-sm">
        <div className="flex items-center justify-between px-4 py-2.5">
          <div className="flex items-center gap-2 min-w-0">
            <div className="w-7 h-7 rounded-full bg-agent-a/12 border border-agent-a/40 flex items-center justify-center shrink-0">
              <span className="text-[10px] font-black text-agent-a">{agentInitial(match!.agent_a)}</span>
            </div>
            <div className="min-w-0">
              <div className="text-xs font-semibold text-ink truncate max-w-[90px]">{match!.agent_a}</div>
              <div className="text-[10px] text-agent-a font-mono font-bold">{totalScoreA.toFixed(1)} profit</div>
            </div>
          </div>

          <div className="flex flex-col items-center gap-0.5">
            <div className="text-[10px] text-quiet font-medium uppercase tracking-wider">Avg price</div>
            <div className="text-sm font-black text-ink tabular-nums">{avgPrice.toFixed(1)}</div>
            {matchComplete && (
              <span style={{ fontSize: "12px", color: "var(--color-muted)", lineHeight: 1.2 }}>
                Outcome: <span style={{ fontWeight: 700 }}>
                  {match!.match_winner === "Tie" ? "Draw" : `Player ${match!.match_winner} wins`}
                </span>
              </span>
            )}
          </div>

          <div className="flex items-center gap-2 min-w-0">
            <div className="min-w-0 text-right">
              <div className="text-xs font-semibold text-ink truncate max-w-[90px]">{match!.agent_b}</div>
              <div className="text-[10px] text-agent-b font-mono font-bold">{totalScoreB.toFixed(1)} profit</div>
            </div>
            <div className="w-7 h-7 rounded-full bg-agent-b/12 border border-agent-b/40 flex items-center justify-center shrink-0">
              <span className="text-[10px] font-black text-agent-b">{agentInitial(match!.agent_b)}</span>
            </div>
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
        <div className="grid gap-2">
          {[...history].reverse().map((r) => {
            const { qA, qB, price, profitA, profitB } = getRoundData(r);
            const isActive = r.round === currentRound;
            const wA = qBar(qA ?? 0, maxQ);
            const wB = qBar(qB ?? 0, maxQ);

            return (
              <div
                key={r.round}
                className={`rounded-xl border px-4 py-3 transition-colors ${isActive ? "border-accent/50 bg-accent/5" : "border-line/30 bg-surface"}`}
              >
                <div className="flex items-center gap-3 mb-2">
                  <span className="text-[11px] font-extrabold text-muted w-10 shrink-0">R{r.round}</span>
                  <div className="flex-1 flex items-center gap-1 text-[11px]">
                    <span className="text-agent-a font-bold w-14 text-right shrink-0">q={qA?.toFixed(1) ?? "—"}</span>
                    <div className="flex-1 h-2 rounded-full bg-line/20 overflow-hidden mx-1">
                      <div className="h-full rounded-full bg-agent-a/60 transition-all duration-300" style={{ width: wA }} />
                    </div>
                  </div>
                  <span className="text-[10px] font-extrabold text-muted shrink-0 w-16 text-center">
                    P={price?.toFixed(1) ?? "—"}
                  </span>
                  <div className="flex-1 flex items-center gap-1 text-[11px]">
                    <div className="flex-1 h-2 rounded-full bg-line/20 overflow-hidden mx-1 flex justify-end">
                      <div className="h-full rounded-full bg-agent-b/60 transition-all duration-300" style={{ width: wB }} />
                    </div>
                    <span className="text-agent-b font-bold w-14 shrink-0">q={qB?.toFixed(1) ?? "—"}</span>
                  </div>
                </div>
                <div className="flex items-center justify-between px-10 text-[10px] text-quiet font-mono">
                  <span className="text-agent-a">π={profitA?.toFixed(1) ?? "—"}</span>
                  <span className="text-agent-b">π={profitB?.toFixed(1) ?? "—"}</span>
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}
