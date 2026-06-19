import { useState, useMemo } from "react";
import { Link } from "react-router-dom";

interface GameEntry {
  slug: string;
  name: string;
  description: string;
  measures: string;
  tags: string[];
  solutionConcept: string;
}

const GAMES: GameEntry[] = [
  {
    slug: "colonelblotto",
    name: "Colonel Blotto",
    description:
      "Two players distribute a fixed pool of resources across N battlefields simultaneously. Each battlefield is won by the player who commits more — ties split evenly.",
    measures: "Mixed-strategy equilibria in resource allocation; measures whether agents discover the maximin strategy and avoid exploitable patterns.",
    solutionConcept: "Mixed Nash Equilibrium",
    tags: ["zero-sum", "simultaneous", "resource allocation"],
  },
  {
    slug: "rock_paper_scissors",
    name: "Rock Paper Scissors",
    description:
      "The canonical symmetric zero-sum game. Each round both players simultaneously choose rock, paper, or scissors — rock beats scissors, scissors beats paper, paper beats rock.",
    measures: "Adherence to the unique mixed Nash equilibrium (1/3–1/3–1/3); detects exploitable patterns and tests randomization quality over repeated play.",
    solutionConcept: "Mixed Nash Equilibrium",
    tags: ["zero-sum", "simultaneous", "non-transitive"],
  },
  {
    slug: "prisonersdilemma",
    name: "Prisoner's Dilemma",
    description:
      "Two players independently choose to cooperate or defect. Mutual cooperation is Pareto-optimal, but defection is the dominant strategy — creating a tension between individual and collective rationality.",
    measures: "Cooperation rates vs defection; tests whether agents recognise dominant strategies and whether trust emerges in repeated play.",
    solutionConcept: "Dominant Strategy (Defect); Pareto-optimal outcome (Cooperate)",
    tags: ["coordination", "simultaneous", "social dilemma"],
  },
  {
    slug: "stag_hunt",
    name: "Stag Hunt",
    description:
      "Two hunters can collaborate to catch a stag (high reward, risky) or independently hunt a hare (low reward, safe). Success requires mutual commitment.",
    measures: "Coordination under uncertainty; risk dominance vs payoff dominance trade-off; whether agents resolve the equilibrium selection problem.",
    solutionConcept: "Two Nash Equilibria (Stag/Stag and Hare/Hare)",
    tags: ["coordination", "simultaneous", "trust"],
  },
  {
    slug: "battle_of_the_sexes",
    name: "Battle of the Sexes",
    description:
      "Two players must coordinate on one of two outcomes (e.g., Opera or Football) — each player prefers a different option but both prefer coordination over misalignment.",
    measures: "Conflict resolution under misaligned preferences; tests signalling, compromise, and mixed-strategy play between the two pure equilibria.",
    solutionConcept: "Two Pure Nash Equilibria + one Mixed Nash Equilibrium",
    tags: ["coordination", "simultaneous", "conflicting preferences"],
  },
  {
    slug: "ultimatum",
    name: "Ultimatum Game",
    description:
      "One player proposes a split of a fixed sum; the other accepts or rejects. Rejection means both receive nothing. Classical game theory predicts acceptance of any positive offer.",
    measures: "Fairness norms, rejection of individually rational but 'unfair' offers, proposer strategy; a canonical test for social preference modelling.",
    solutionConcept: "Subgame-Perfect Nash Equilibrium vs fairness-adjusted play",
    tags: ["bargaining", "sequential", "fairness"],
  },
  {
    slug: "public_goods",
    name: "Public Goods",
    description:
      "Each player contributes to a shared pool; contributions are multiplied and split equally. Contributing benefits everyone, but free-riding is individually rational.",
    measures: "Contribution rates relative to the social optimum; emergence of cooperation; tests whether agents internalise group welfare vs pure self-interest.",
    solutionConcept: "Nash Equilibrium at zero contribution; Social optimum at full contribution",
    tags: ["social dilemma", "simultaneous", "free-rider problem"],
  },
  {
    slug: "centipede",
    name: "Centipede Game",
    description:
      "A sequential game where two players alternate deciding to 'take' (ending the game) or 'pass' (continuing for a larger shared pot). Backward induction predicts immediate defection.",
    measures: "Backward induction depth; altruistic vs strategic play; tests theory-of-mind and whether agents anticipate opponent rationality over long horizons.",
    solutionConcept: "Subgame-Perfect Nash Equilibrium (immediate take)",
    tags: ["sequential", "backward induction", "trust"],
  },
  {
    slug: "cournot_duopoly",
    name: "Cournot Duopoly",
    description:
      "Two firms simultaneously choose production quantities. Market price is determined by total output. Each firm maximises profit given the other's output choice.",
    measures: "Convergence to the Cournot-Nash output equilibrium; tests whether agents perform continuous optimisation and best-response reasoning.",
    solutionConcept: "Cournot-Nash Equilibrium (⅓ monopoly output each)",
    tags: ["continuous action", "simultaneous", "oligopoly"],
  },
  {
    slug: "texas_hold_em",
    name: "Texas Hold'em",
    description:
      "The classic incomplete-information poker variant. Private hole cards, shared community cards, and multi-round betting with bluffing, pot-odds reasoning, and hand reading.",
    measures: "Bluffing frequency, pot-odds adherence, hand range estimation, and bet-sizing; tests performance under hidden information and stochastic outcomes.",
    solutionConcept: "GTO (Game-Tree Optimal) mixed strategies",
    tags: ["incomplete information", "stochastic", "sequential"],
  },
];

function TagChip({ label }: { label: string }) {
  return (
    <span className="inline-flex items-center px-2 py-0.5 rounded-[var(--radius-chip)] bg-surface-container border border-line text-[10px] font-mono text-muted">
      {label}
    </span>
  );
}

function highlight(text: string, query: string) {
  if (!query) return <>{text}</>;
  const idx = text.toLowerCase().indexOf(query.toLowerCase());
  if (idx === -1) return <>{text}</>;
  return (
    <>
      {text.slice(0, idx)}
      <mark className="bg-accent/20 text-ink rounded-sm">{text.slice(idx, idx + query.length)}</mark>
      {text.slice(idx + query.length)}
    </>
  );
}

export function GamesPage() {
  const [query, setQuery] = useState("");

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return GAMES;
    return GAMES.filter(
      (g) =>
        g.name.toLowerCase().includes(q) ||
        g.description.toLowerCase().includes(q) ||
        g.measures.toLowerCase().includes(q) ||
        g.solutionConcept.toLowerCase().includes(q) ||
        g.tags.some((t) => t.toLowerCase().includes(q)),
    );
  }, [query]);

  return (
    <div className="max-w-5xl mx-auto px-6 py-16">
      {/* Header */}
      <div className="mb-10">
        <p className="text-xs font-mono text-accent mb-3 uppercase tracking-widest">Platform</p>
        <h1 className="text-3xl font-extrabold text-ink mb-3">Games</h1>
        <p className="text-base text-muted max-w-2xl leading-relaxed">
          Each NashArena game is a rigorous implementation of a classical game-theoretic setting.
          Every game ships with its solution concept, equilibrium calculator, and per-round metrics
          so you can measure not just who wins, but how strategically sound an agent's play is.
        </p>
      </div>

      {/* Search */}
      <div className="relative mb-8">
        <svg
          className="absolute left-3 top-1/2 -translate-y-1/2 text-muted pointer-events-none"
          width="15" height="15" viewBox="0 0 24 24" fill="none"
          stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"
        >
          <circle cx="11" cy="11" r="8"/><path d="m21 21-4.35-4.35"/>
        </svg>
        <input
          type="search"
          placeholder="Search games, tags, or solution concepts…"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          className="w-full h-10 pl-9 pr-4 text-sm text-ink bg-surface border border-line rounded-[var(--radius-input)] outline-none transition-colors duration-150 hover:border-line-strong focus:border-accent focus:shadow-[0_0_0_3px_var(--color-accent-soft)] placeholder:text-muted"
        />
        {query && (
          <span className="absolute right-3 top-1/2 -translate-y-1/2 text-xs text-muted font-mono">
            {filtered.length} / {GAMES.length}
          </span>
        )}
      </div>

      {/* Game grid */}
      {filtered.length > 0 ? (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
          {filtered.map((game) => (
            <article
              key={game.slug}
              className="flex flex-col rounded-[var(--radius-card)] border border-line bg-surface p-6 hover:border-accent/40 transition-colors duration-200"
            >
              <div className="flex items-start justify-between gap-4 mb-3">
                <h2 className="text-base font-bold text-ink">
                  {highlight(game.name, query)}
                </h2>
                <span className="shrink-0 text-[10px] font-mono font-semibold text-accent/80 bg-accent/8 px-2 py-0.5 rounded-[var(--radius-chip)] border border-accent/20 whitespace-nowrap">
                  {highlight(game.solutionConcept, query)}
                </span>
              </div>

              <p className="text-sm text-muted leading-relaxed mb-4">
                {highlight(game.description, query)}
              </p>

              <div className="rounded-[var(--radius-input)] bg-surface-soft border border-line px-4 py-3 mb-4">
                <p className="text-[10px] font-mono font-semibold text-accent uppercase tracking-widest mb-1.5">
                  What it measures
                </p>
                <p className="text-xs text-quiet leading-relaxed">
                  {highlight(game.measures, query)}
                </p>
              </div>

              <div className="flex flex-wrap gap-1.5 mt-auto">
                {game.tags.map((t) => (
                  <TagChip key={t} label={t} />
                ))}
              </div>
            </article>
          ))}
        </div>
      ) : (
        <div className="text-center py-20 text-muted">
          <p className="text-sm">No games match <span className="font-mono text-ink">"{query}"</span></p>
          <button
            type="button"
            onClick={() => setQuery("")}
            className="mt-3 text-xs text-accent hover:underline"
          >
            Clear search
          </button>
        </div>
      )}

      {/* CTA */}
      <div className="mt-16 text-center">
        <p className="text-sm text-muted mb-4">Ready to run your first experiment?</p>
        <Link
          to="/dashboard"
          className="inline-flex items-center gap-2 h-9 px-5 rounded-[var(--radius-button)] bg-accent text-white text-sm font-medium transition-opacity hover:opacity-90"
        >
          Open Dashboard
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
            <path d="M5 12h14M12 5l7 7-7 7"/>
          </svg>
        </Link>
      </div>
    </div>
  );
}
