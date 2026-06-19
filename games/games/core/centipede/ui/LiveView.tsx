import { useApp } from "@frontend/hooks/useApp";
import type { MatchRound } from "@frontend/types";

function agentInitial(name: string) { return (name.trim().charAt(0) || "?").toUpperCase(); }

function getStepData(r: MatchRound) {
  const raw = r.raw as Record<string, unknown> | undefined;
  return {
    step: raw?.step as number | undefined,
    player: raw?.player as string | undefined,
    action: raw?.action as string | undefined,
    potABefore: raw?.pot_a_before as number | undefined,
    potBBefore: raw?.pot_b_before as number | undefined,
    potAAfter: raw?.pot_a_after as number | undefined,
    potBAfter: raw?.pot_b_after as number | undefined,
    payoffs: raw?.payoffs as Record<string, number> | undefined,
  };
}

export default function CentipedeLiveView() {
  const { state } = useApp();
  const match = state.activeMatch;
  const hasMatch = Boolean(match);
  const isGameRunning = Boolean(state.pendingGame);
  const round = match?.history[state.activeRoundIndex] ?? null;
  const totalRounds = match?.num_rounds ?? 0;
  const currentStep = round ? (getStepData(round).step ?? round.round) : 0;
  const totalScoreA = round ? round.total_score_a : 0;
  const totalScoreB = round ? round.total_score_b : 0;
  const roundProgress = totalRounds > 0 ? Math.round(((match?.history.length ?? 0) / totalRounds) * 100) : 0;

  if (!hasMatch) {
    return (
      <div className="flex flex-col h-full bg-surface-soft">
        <div className="shrink-0 flex items-center justify-between gap-4 px-5 py-3 border-b border-line bg-surface/80 backdrop-blur-sm">
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
            <div className="w-16 h-16 mx-auto mb-4 rounded-[var(--radius-card)] bg-surface-container flex items-center justify-center text-3xl">
              {isGameRunning ? (
                <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" className="text-accent/70 animate-spin">
                  <path d="M21 12a9 9 0 1 1-6.219-8.56" />
                </svg>
              ) : "🐛"}
            </div>
            {isGameRunning ? (
              <p className="text-sm font-semibold text-muted">Waiting for first move...</p>
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

  const passCount = history.filter((r) => getStepData(r).action === "pass").length;
  const totalSteps = history.length;
  const lastStep = history.length > 0 ? getStepData(history[history.length - 1]) : null;
  const gameEndedByTake = lastStep?.action === "take";

  const maxPot = Math.max(
    ...history.flatMap((r) => {
      const d = getStepData(r);
      return [d.potABefore ?? 0, d.potBBefore ?? 0, d.potAAfter ?? 0, d.potBAfter ?? 0];
    }),
    1,
  );

  return (
    <div className="flex flex-col h-full bg-surface-soft">
      <div className="shrink-0 sticky top-0 z-10 border-b border-line bg-surface/80 backdrop-blur-sm">
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
              Step {currentStep} · {passCount}/{totalSteps} passed
            </div>
            <div className="text-[10px] text-quiet">
              {gameEndedByTake ? `Ended by TAKE at step ${lastStep?.step ?? totalSteps}` : matchComplete ? "Forced payout" : "In progress"}
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
          <span className="text-[10px] font-extrabold text-muted uppercase whitespace-nowrap">{totalSteps}/{totalRounds} steps</span>
        </div>
      </div>

      <div className="flex-1 overflow-y-auto p-4">
        {/* Pot progression chart */}
        {history.length > 0 && (
          <div className="mb-4 rounded-[var(--radius-card)] border border-line bg-surface p-4">
            <div className="text-[10px] font-extrabold text-muted uppercase tracking-wider mb-3">Pot Progression</div>
            <div className="flex items-end gap-1 h-12">
              {history.map((r, i) => {
                const d = getStepData(r);
                const pot = (d.potAAfter ?? d.potABefore ?? 0) + (d.potBAfter ?? d.potBBefore ?? 0);
                const h = maxPot > 0 ? Math.round((pot / (maxPot * 2)) * 100) : 0;
                const isActive = r.round === round?.round;
                return (
                  <div
                    key={i}
                    className={`flex-1 rounded-sm transition-all ${isActive ? "bg-accent" : d.action === "take" ? "bg-red-400 dark:bg-red-600" : "bg-emerald-400 dark:bg-emerald-600"}`}
                    style={{ height: `${Math.max(h, 8)}%` }}
                    title={`Step ${d.step}: ${d.action} by ${d.player}`}
                  />
                );
              })}
            </div>
            <div className="flex items-center gap-3 mt-2 text-[9px] text-quiet">
              <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-sm bg-emerald-400 dark:bg-emerald-600 inline-block" />Pass</span>
              <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-sm bg-red-400 dark:bg-red-600 inline-block" />Take</span>
            </div>
          </div>
        )}

        <div className="text-[10px] font-extrabold text-muted uppercase tracking-wider mb-3">Step History</div>
        <div className="grid gap-2">
          {[...history].reverse().map((r, i) => {
            const { step, player, action, potABefore, potBBefore, potAAfter, potBAfter, payoffs } = getStepData(r);
            const isActive = r.round === round?.round;
            const isTake = action === "take";
            const isPlayerA = player === "A";
            const potBefore = (potABefore ?? 0) + (potBBefore ?? 0);
            const potAfter = potAAfter != null && potBAfter != null ? potAAfter + potBAfter : null;

            return (
              <div
                key={history.length - 1 - i}
                className={`flex items-center gap-3 rounded-[var(--radius-card)] px-4 py-3 border transition-colors ${isActive ? "border-accent/50 bg-accent/5" : "border-line bg-surface"}`}
              >
                <span className="text-[11px] font-extrabold text-muted w-10 shrink-0">S{step ?? (history.length - i)}</span>

                <span className={`text-[9px] font-extrabold px-1.5 py-0.5 rounded uppercase shrink-0 ${isPlayerA ? "bg-agent-a/10 text-agent-a border border-agent-a/30" : "bg-agent-b/10 text-agent-b border border-agent-b/30"}`}>
                  {player ?? "?"}
                </span>

                <span className={`text-[11px] font-black px-2 py-0.5 rounded border shrink-0 ${
                  isTake
                    ? "bg-red-100 text-red-700 border-red-200 dark:bg-red-950/40 dark:text-red-300 dark:border-red-700/40"
                    : "bg-emerald-100 text-emerald-700 border-emerald-200 dark:bg-emerald-950/40 dark:text-emerald-300 dark:border-emerald-700/40"
                }`}>
                  {isTake ? "TAKE" : "PASS"}
                </span>

                <div className="flex-1 text-[10px] text-quiet font-mono text-center">
                  {isTake ? (
                    <span>
                      Pot {potBefore.toFixed(1)} → <span className="text-ink font-semibold">A:{payoffs?.A?.toFixed(1) ?? "?"} B:{payoffs?.B?.toFixed(1) ?? "?"}</span>
                    </span>
                  ) : potAfter != null ? (
                    <span>{potBefore.toFixed(1)} → {potAfter.toFixed(1)}</span>
                  ) : (
                    <span>Pot {potBefore.toFixed(1)}</span>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}
