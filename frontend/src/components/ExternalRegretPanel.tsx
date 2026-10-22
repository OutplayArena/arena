import { useState } from "react";

interface Point {
  round: number;
  cumulative: number;
  average: number;
}

interface Regret {
  status: "available";
  cumulative: number;
  average: number;
  normalized_average: number | null;
  actual_total_payoff: number;
  best_fixed_total_payoff: number;
  best_fixed_action: string;
  num_rounds: number;
  series: Point[];
}

function object(value: unknown): value is Record<string, unknown> {
  return value !== null && typeof value === "object" && !Array.isArray(value);
}

function finite(value: unknown): value is number {
  return typeof value === "number" && Number.isFinite(value);
}

function available(value: unknown): value is Regret {
  if (!object(value) || value.status !== "available") return false;
  return finite(value.cumulative) && finite(value.average)
    && (value.normalized_average === null || finite(value.normalized_average))
    && finite(value.actual_total_payoff) && finite(value.best_fixed_total_payoff)
    && typeof value.best_fixed_action === "string"
    && finite(value.num_rounds) && value.num_rounds > 0
    && Array.isArray(value.series) && value.series.length === value.num_rounds
    && value.series.every((p: unknown, i: number) => object(p)
      && p.round === i + 1 && finite(p.cumulative) && finite(p.average));
}

function number(value: number | null): string {
  return value === null ? "Undefined (constant payoff range)" : value.toLocaleString(undefined, { maximumFractionDigits: 4 });
}

export function ExternalRegretPanel({ byPlayer }: { byPlayer: unknown }) {
  const [metric, setMetric] = useState<"cumulative" | "average">("cumulative");
  const [selectedRound, setSelectedRound] = useState(1);
  if (!object(byPlayer)) return null;
  const entries = Object.entries(byPlayer);
  if (!entries.length) return null;
  const curves = entries.flatMap(([player, value], i) => available(value)
    ? [{ player, value, color: i % 2 === 0 ? "var(--color-agent-a)" : "var(--color-agent-b)" }] : []);
  const rounds = Math.max(1, ...curves.map(c => c.value.num_rounds));
  const round = Math.min(selectedRound, rounds);
  const values = curves.flatMap(c => c.value.series.map(p => p[metric]));
  const low = Math.min(0, ...values);
  const high = Math.max(0, ...values);
  const span = high - low || 1;
  const x = (r: number) => 48 + ((r - 1) / Math.max(1, rounds - 1)) * 500;
  const y = (v: number) => 170 - ((v - low) / span) * 135;

  return (
    <section className="mt-4 rounded-card border border-line/50 bg-surface-container/20 p-3" aria-label="External regret evaluation">
      <h3 className="text-sm font-bold text-ink">External regret</h3>
      <p className="mt-1 text-xs text-muted">Best fixed move payoff minus actual payoff. Negative means the player beat every fixed move.</p>
      <div className="mt-3 grid gap-3 sm:grid-cols-2">
        {entries.map(([player, value]) => (
          <article key={player} aria-label={`Player ${player} external regret`} className="rounded-card border border-line/40 p-3">
            <h4 className="text-xs font-bold text-ink">Player {player}</h4>
            {available(value) ? (
              <dl className="mt-2 grid grid-cols-2 gap-x-3 gap-y-1 text-xs">
                <dt className="text-muted">Cumulative regret</dt><dd className="text-ink font-mono">{number(value.cumulative)}</dd>
                <dt className="text-muted">Average regret</dt><dd className="text-ink font-mono">{number(value.average)}</dd>
                <dt className="text-muted">Normalized average</dt><dd className="text-ink font-mono">{number(value.normalized_average)}</dd>
                <dt className="text-muted">Best fixed move</dt><dd className="text-ink">{value.best_fixed_action}</dd>
                <dt className="text-muted">Best fixed payoff</dt><dd className="text-ink font-mono">{number(value.best_fixed_total_payoff)}</dd>
                <dt className="text-muted">Actual payoff</dt><dd className="text-ink font-mono">{number(value.actual_total_payoff)}</dd>
                <dt className="text-muted">Completed rounds</dt><dd className="text-ink font-mono">{value.num_rounds}</dd>
              </dl>
            ) : <p className="mt-2 text-xs text-muted">Unavailable: {object(value) && typeof value.reason === "string" ? value.reason : "Incomplete or invalid regret data."}</p>}
          </article>
        ))}
      </div>
      {curves.length > 0 && (
        <div className="mt-3">
          <div className="flex gap-2" aria-label="Regret chart metric">
            {(["cumulative", "average"] as const).map(key => <button key={key} type="button" aria-pressed={metric === key} onClick={() => setMetric(key)} className={`rounded px-3 py-1 text-xs font-semibold ${metric === key ? "bg-accent text-white" : "bg-surface-container text-muted"}`}>{key === "cumulative" ? "Cumulative" : "Average"}</button>)}
          </div>
          <svg className="mt-2 w-full" viewBox="0 0 580 205" role="img" aria-label={`${metric === "cumulative" ? "Cumulative" : "Average"} external regret by round`}>
            <title>Signed external regret against each player’s observed opponent sequence</title>
            <path d="M48 30 V170 H548" fill="none" stroke="currentColor" className="text-muted" />
            <path d={`M48 ${y(0)} H548`} stroke="currentColor" className="text-muted opacity-40" />
            <text x="3" y="38" className="fill-muted text-[10px]">{number(high)}</text>
            <text x="3" y="170" className="fill-muted text-[10px]">{number(low)}</text>
            <text x="48" y="190" className="fill-muted text-[10px]">1</text>
            <text x="535" y="190" className="fill-muted text-[10px]">{rounds}</text>
            <text x="270" y="202" className="fill-muted text-[10px]">Round</text>
            <path d={`M${x(round)} 30 V170`} stroke="currentColor" strokeDasharray="3 3" className="text-muted opacity-50" />
            {curves.map(c => <g key={c.player}>
              <polyline points={c.value.series.map(p => `${x(p.round)},${y(p[metric])}`).join(" ")} fill="none" stroke={c.color} strokeWidth="2" />
              {c.value.series.filter(p => p.round === round).map(p => <circle key={p.round} cx={x(p.round)} cy={y(p[metric])} r="3.5" fill={c.color} />)}
            </g>)}
          </svg>
          <label className="block text-xs text-muted">Inspect round {round}
            <input className="mt-1 w-full accent-accent" type="range" min={1} max={rounds} value={round} onChange={e => setSelectedRound(Number(e.target.value))} aria-label="Inspect regret round" />
          </label>
          <div className="mt-2 flex flex-wrap gap-3 text-xs" aria-live="polite">
            {curves.map(c => {
              const point = c.value.series.find(p => p.round === round);
              return <span key={c.player} style={{ color: c.color }}>Player {c.player}: {point ? number(point[metric]) : "No observation"}</span>;
            })}
          </div>
          <p className="mt-2 text-[11px] text-muted">Each round uses its own best fixed move in hindsight. These curves describe this match; they do not establish an asymptotic no-regret guarantee.</p>
        </div>
      )}
    </section>
  );
}
