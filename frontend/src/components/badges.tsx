export function outcomeBadge(winner: string | null) {
  if (!winner) return null;
  const color = winner === "A" ? "text-agent-a bg-agent-a/10" : winner === "B" ? "text-agent-b bg-agent-b/10" : "text-muted bg-ink/6";
  return <span className={`text-[11px] font-extrabold px-2 py-0.5 rounded-chip ${color}`}>{winner === "Tie" ? "Draw" : `Agent ${winner}`}</span>;
}

export function statusBadge(status: string) {
  const map: Record<string, string> = {
    ready: "bg-[#d4edda] text-[#155724]",
    running: "bg-[#cce5ff] text-[#004085] animate-pulse",
    completed: "bg-[#1e7e34] text-white",
    failed: "bg-[#f8d7da] text-[#721c24]",
  };
  const cls = map[status] || "bg-ink/8 text-muted";
  return <span className={`text-[11px] font-extrabold px-2 py-0.5 rounded-chip ${cls}`}>{status}</span>;
}

export function downloadJSON(data: unknown, filename: string) {
  const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}
