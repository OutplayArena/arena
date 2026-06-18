import { useApp } from "@frontend/hooks/useApp";
import type { MatchRound } from "@frontend/types";

function agentInitial(name: string) { return (name.trim().charAt(0) || "?").toUpperCase(); }

function getRoundData(r: MatchRound) {
  const raw = r.raw as Record<string, unknown> | undefined;
  return {
    proposer: raw?.proposer as string | undefined,
    responder: raw?.responder as string | undefined,
    offer: raw?.offer as number | undefined,
    offerFraction: raw?.offer_fraction as number | undefined,
    accepted: raw?.accepted as boolean | undefined,
    response: raw?.response as string | undefined,
  };
}

export default function UltimatumLiveView() {
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
            <span className="text-xs font-extrabold text-muted uppercase tracking-wider">Agent A</span>
          </div>
          <div className="flex items-center gap-2">
            <span className="text-xs font-extrabold text-muted uppercase tracking-wider">Agent B</span>
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
              ) : "⚖️"}
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

  const acceptedRounds = history.filter((r) => getRoundData(r).accepted === true);
  const acceptanceRate = history.length > 0 ? Math.round((acceptedRounds.length / history.length) * 100) : 0;
  const avgOffer = history.length > 0
    ? history.reduce((sum, r) => sum + (getRoundData(r).offerFraction ?? 0), 0) / history.length
    : 0;

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
              <div className="text-[10px] text-quiet font-mono">{totalScoreA.toFixed(1)} pts</div>
            </div>
          </div>

          <div className="flex flex-col items-center gap-0.5">
            <div className="text-[11px] font-bold text-muted">
              {acceptedRounds.length}/{history.length} accepted
            </div>
            <div className="text-[10px] text-quiet">
              Avg offer: {(avgOffer * 100).toFixed(0)}% · Rate: {acceptanceRate}%
            </div>
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
              <div className="text-[10px] text-quiet font-mono">{totalScoreB.toFixed(1)} pts</div>
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
            const { proposer, offer, offerFraction, accepted } = getRoundData(r);
            const isActive = r.round === currentRound;
            const proposerIsA = proposer === "A";
            const offerPct = offerFraction != null ? Math.round(offerFraction * 100) : null;

            return (
              <div
                key={r.round}
                className={`rounded-xl border px-4 py-3 transition-colors ${isActive ? "border-accent/50 bg-accent/5" : "border-line/30 bg-surface"}`}
              >
                <div className="flex items-center gap-3">
                  <span className="text-[11px] font-extrabold text-muted w-10 shrink-0">R{r.round}</span>

                  <div className="flex items-center gap-1.5 shrink-0">
                    <span className={`text-[9px] font-extrabold px-1.5 py-0.5 rounded uppercase ${proposerIsA ? "bg-agent-a/10 text-agent-a border border-agent-a/30" : "bg-agent-b/10 text-agent-b border border-agent-b/30"}`}>
                      {proposer ?? "?"} proposes
                    </span>
                  </div>

                  {offer != null ? (
                    <div className="flex-1 flex items-center gap-2">
                      <div className="flex-1 h-2 rounded-full bg-line/20 overflow-hidden">
                        <div
                          className={`h-full rounded-full transition-all duration-300 ${proposerIsA ? "bg-agent-a/50" : "bg-agent-b/50"}`}
                          style={{ width: `${offerPct ?? 0}%` }}
                        />
                      </div>
                      <span className="text-[11px] font-bold text-ink shrink-0 tabular-nums">
                        {offer.toFixed(0)} ({offerPct}%)
                      </span>
                    </div>
                  ) : (
                    <div className="flex-1" />
                  )}

                  <span className={`text-[11px] font-black px-2 py-0.5 rounded border shrink-0 ${
                    accepted === true
                      ? "bg-emerald-100 text-emerald-700 border-emerald-200 dark:bg-emerald-950/40 dark:text-emerald-300 dark:border-emerald-700/40"
                      : accepted === false
                        ? "bg-red-100 text-red-700 border-red-200 dark:bg-red-950/40 dark:text-red-300 dark:border-red-700/40"
                        : "bg-surface-container border-line/40 text-quiet"
                  }`}>
                    {accepted === true ? "✓ Accept" : accepted === false ? "✗ Reject" : "—"}
                  </span>

                  <span className="text-[10px] text-quiet font-mono w-16 text-right shrink-0">
                    {r.score_a.toFixed(1)}/{r.score_b.toFixed(1)}
                  </span>
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}
