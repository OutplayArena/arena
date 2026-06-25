import { useEffect, useState } from "react";
import { getBenchmarkGames } from "../api";
import { useGameNames, gameName } from "../hooks/useGameNames";

export interface LeaderboardFiltersValue {
  game: string;
  dateFrom: string;
  dateTo: string;
}

export interface LeaderboardFiltersProps {
  value: LeaderboardFiltersValue;
  onChange: (next: LeaderboardFiltersValue) => void;
  onClear?: () => void;
  align?: "left" | "center";
  /** When true, only the game dropdown is rendered (used by the home preview). */
  gameOnly?: boolean;
}

const FILTER_INPUT_CLS =
  "h-9 text-ink bg-surface border border-line rounded-[var(--radius-input)] px-3 text-sm outline-none transition-colors " +
  "hover:border-line-strong focus:border-accent focus:shadow-[0_0_0_3px_var(--color-accent-soft)]";

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex items-center gap-1.5">
      <label className="text-xs font-mono text-muted">{label}:</label>
      {children}
    </div>
  );
}

export function LeaderboardFilters({
  value,
  onChange,
  onClear,
  align = "left",
  gameOnly = false,
}: LeaderboardFiltersProps) {
  const [games, setGames] = useState<string[]>([]);
  const gameNames = useGameNames();

  useEffect(() => {
    let cancelled = false;
    getBenchmarkGames()
      .then((res) => { if (!cancelled) setGames(res.games); })
      .catch(() => { if (!cancelled) setGames([]); });
    return () => { cancelled = true; };
  }, []);

  const hasActiveFilter = Boolean(value.game || value.dateFrom || value.dateTo);

  const update = (patch: Partial<LeaderboardFiltersValue>) => {
    onChange({ ...value, ...patch });
  };

  return (
    <div
      className={`flex flex-wrap items-center gap-3 ${align === "center" ? "justify-center" : ""}`}
      data-testid="leaderboard-filters"
    >
      <Field label="Game">
        <div className="relative inline-flex items-center">
          <span className="sr-only">Filter leaderboard by game</span>
          <select
            value={value.game}
            onChange={(e) => update({ game: e.target.value })}
            className={FILTER_INPUT_CLS + " min-w-[200px] appearance-none cursor-pointer pr-9"}
          >
            <option value="">All games (overall)</option>
            {games.map((g) => (
              <option key={g} value={g}>{gameName(g, gameNames)}</option>
            ))}
          </select>
          <svg
            className="pointer-events-none absolute right-3 top-1/2 -translate-y-1/2 text-muted"
            width="12"
            height="12"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
            aria-hidden="true"
          >
            <polyline points="6 9 12 15 18 9" />
          </svg>
        </div>
      </Field>

      {!gameOnly && (
        <>
          <Field label="From">
            <input
              type="date"
              value={value.dateFrom}
              onChange={(e) => update({ dateFrom: e.target.value })}
              className={FILTER_INPUT_CLS}
              data-testid="leaderboard-filter-from"
            />
          </Field>
          <Field label="To">
            <input
              type="date"
              value={value.dateTo}
              onChange={(e) => update({ dateTo: e.target.value })}
              className={FILTER_INPUT_CLS}
              data-testid="leaderboard-filter-to"
            />
          </Field>
        </>
      )}

      {!gameOnly && hasActiveFilter && onClear && (
        <button
          type="button"
          onClick={onClear}
          className="px-3 py-1.5 text-xs font-mono rounded-[var(--radius-chip)] border border-line text-muted hover:text-ink hover:border-line-strong transition-colors"
        >
          Clear filters
        </button>
      )}
    </div>
  );
}
