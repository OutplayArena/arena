import { useApp } from "../hooks/useApp";

interface AutoHistoryViewProps {
  hasMatch: boolean;
  canvasCollapsed: boolean;
  onExpandCanvas: () => void;
}

function downloadJSON(data: unknown, filename: string) {
  const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}

export function AutoHistoryView({ hasMatch, canvasCollapsed, onExpandCanvas }: AutoHistoryViewProps) {
  const { state } = useApp();
  const { activeMatch } = state;

  const history = activeMatch?.history ?? [];
  const total = history.length;

  return (
    <div className="overflow-y-auto overscroll-contain">
      <div className="p-4">
        <div className="flex items-center justify-between mb-3">
          <h2 className="text-xs font-extrabold text-muted uppercase tracking-wider">History</h2>
          <div className="flex items-center gap-2">
            {canvasCollapsed && (
              <button
                type="button"
                onClick={onExpandCanvas}
                className="text-[10px] font-semibold text-accent hover:underline"
              >
                Show Live View
              </button>
            )}
            <span className="text-[11px] text-muted">
              {hasMatch ? `Complete — ${total} round${total !== 1 ? "s" : ""}` : "No data yet."}
            </span>
          </div>
        </div>

        {hasMatch && activeMatch && total > 0 && (
          <>
            <div className="rounded-card border border-line/40 overflow-hidden">
              <table className="w-full text-left text-sm">
                <thead>
                  <tr className="border-b border-line/40 bg-surface-container/50">
                    <th className="px-3 py-2 text-[10px] font-extrabold text-muted">R</th>
                    <th className="px-3 py-2 text-[10px] font-extrabold text-muted">{activeMatch.agent_a}</th>
                    <th className="px-3 py-2 text-[10px] font-extrabold text-muted">{activeMatch.agent_b}</th>
                    <th className="px-3 py-2 text-[10px] font-extrabold text-muted">Scores</th>
                    <th className="px-3 py-2 text-[10px] font-extrabold text-muted">W</th>
                  </tr>
                </thead>
                <tbody>
                  {history.map((round) => (
                    <tr
                      key={round.round}
                      className={`border-b border-line/20 last:border-b-0 ${
                        round.winner === "A" ? "bg-agent-a/[0.04]" : round.winner === "B" ? "bg-agent-b/[0.04]" : ""
                      }`}
                    >
                      <td className="px-3 py-2 text-xs text-muted font-mono">{round.round}</td>
                      <td className="px-3 py-2 text-xs text-ink font-mono">
                        [{round.action_a.join(", ")}]
                      </td>
                      <td className="px-3 py-2 text-xs text-ink font-mono">
                        [{round.action_b.join(", ")}]
                      </td>
                      <td className="px-3 py-2 text-xs text-ink">
                        A:{round.score_a} B:{round.score_b}
                      </td>
                      <td className="px-3 py-2 text-xs font-bold">
                        <span className={round.winner === "A" ? "text-agent-a" : round.winner === "B" ? "text-agent-b" : "text-muted"}>
                          {round.winner === "Tie" ? "T" : round.winner}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            <div className="mt-3 flex items-center justify-between">
              <div className="text-[11px] text-muted">
                Final: <span className="text-agent-a font-bold">{activeMatch.total_score_a}</span> — <span className="text-agent-b font-bold">{activeMatch.total_score_b}</span>
                {activeMatch.match_winner !== "Tie" && (
                  <span className={`ml-1 font-bold ${activeMatch.match_winner === "A" ? "text-agent-a" : "text-agent-b"}`}>
                    ({activeMatch.match_winner === "A" ? activeMatch.agent_a : activeMatch.agent_b} wins)
                  </span>
                )}
              </div>
              <button
                type="button"
                onClick={() => downloadJSON(activeMatch, `${activeMatch.session_id || "match"}.json`)}
                className="text-[10px] font-semibold text-accent hover:underline"
              >
                Download JSON
              </button>
            </div>

            {activeMatch.metrics && Object.keys(activeMatch.metrics).length > 0 && (
              <div className="mt-4">
                <h3 className="text-[11px] font-extrabold text-muted uppercase mb-2">Metrics</h3>
                <div className="grid grid-cols-2 gap-2">
                  {Object.entries(activeMatch.metrics).map(([key, value]) => (
                    <div key={key} className="rounded-card bg-surface-container/30 border border-line/30 p-2">
                      <span className="text-[10px] font-extrabold text-muted uppercase">{key}</span>
                      <p className="text-xs text-ink font-mono mt-0.5">
                        {typeof value === "object" ? JSON.stringify(value) : String(value)}
                      </p>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </>
        )}

        {!hasMatch && (
          <div className="text-xs text-muted text-center py-8">
            No match data. Complete a game to see history.
          </div>
        )}
      </div>
    </div>
  );
}
