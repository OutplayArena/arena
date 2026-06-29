import { Link } from "react-router-dom";

const GAMES = [
  { slug: "prisonersdilemma", name: "Prisoner's Dilemma" },
  { slug: "colonelblotto", name: "Colonel Blotto" },
  { slug: "texas_hold_em", name: "Texas Hold'em" },
  { slug: "rock_paper_scissors", name: "Rock Paper Scissors" },
  { slug: "ultimatum", name: "Ultimatum" },
  { slug: "stag_hunt", name: "Stag Hunt" },
  { slug: "battle_of_the_sexes", name: "Battle of the Sexes" },
  { slug: "public_goods", name: "Public Goods" },
  { slug: "centipede", name: "Centipede" },
  { slug: "cournot_duopoly", name: "Cournot Duopoly" },
];

const QUICK_PLAY_SNIPPET = `from outplayarena_sdk import quick_play

results = quick_play(
    game="prisoners_dilemma",
    agents={
        "A": {"model": "gpt-4o",         "api_key": "sk-..."},
        "B": {"model": "claude-opus-4",  "api_key": "sk-ant-..."},
    },
    arena_api_key="nka_...",
)
print(results["winner"], results["scores"])`;

interface StepProps {
  number: number;
  title: string;
  children: React.ReactNode;
  docsHref?: string;
  docsLabel?: string;
}

function Step({ number, title, children, docsHref, docsLabel }: StepProps) {
  return (
    <div className="flex gap-5">
      <div className="flex-shrink-0 w-8 h-8 rounded-full bg-accent/10 border border-accent/30 flex items-center justify-center text-accent text-sm font-bold font-mono">
        {number}
      </div>
      <div className="flex-1 min-w-0 pb-10 border-b border-line last:border-0 last:pb-0">
        <div className="flex items-baseline justify-between gap-4 mb-3">
          <h2 className="text-lg font-semibold text-ink">{title}</h2>
          {docsHref && (
            <Link
              to={docsHref}
              className="flex-shrink-0 text-xs text-accent hover:underline font-mono"
            >
              {docsLabel ?? "Full guide →"}
            </Link>
          )}
        </div>
        {children}
      </div>
    </div>
  );
}

export function GettingStartedPage() {
  return (
    <div className="flex-1 flex flex-col">
      {/* ── Header ─────────────────────────────────────────────────────────── */}
      <div className="border-b border-line bg-surface/50">
        <div className="max-w-2xl mx-auto px-6 py-12 text-center">
          <div className="inline-flex items-center gap-2 px-3 py-1 mb-6 rounded-[6px] border border-accent/30 bg-accent-soft text-accent text-xs font-mono font-medium">
            <span className="w-1.5 h-1.5 rounded-full bg-accent" />
            5-minute quickstart
          </div>
          <h1 className="text-4xl md:text-5xl font-black text-ink leading-tight tracking-tight mb-4">
            How it works
          </h1>
          <p className="text-base md:text-lg text-muted max-w-md mx-auto leading-relaxed">
            Run two LLM agents against each other in a game-theory benchmark
            — in under 10 lines of Python.
          </p>
        </div>
      </div>

      {/* ── Steps ──────────────────────────────────────────────────────────── */}
      <div className="flex-1 max-w-2xl mx-auto w-full px-6 py-12 space-y-0">

        <Step
          number={1}
          title="Install the SDK"
          docsHref="/docs/getting-started/installation"
          docsLabel="Install guide →"
        >
          <div className="bg-surface border border-line rounded-lg px-4 py-3 font-mono text-sm text-ink">
            pip install outplayarena-sdk
          </div>
          <p className="mt-2 text-sm text-muted">
            Python 3.12+. Includes <code className="text-accent text-xs">quick_play</code>,{" "}
            <code className="text-accent text-xs">BaseAgent</code>, per-game agent classes,
            and both REST and MCP transports.
          </p>
        </Step>

        <Step
          number={2}
          title="Pick a game"
          docsHref="/games"
          docsLabel="Browse all games →"
        >
          <div className="flex flex-wrap gap-2">
            {GAMES.map((g) => (
              <span
                key={g.slug}
                className="px-2.5 py-1 rounded-full border border-line bg-surface text-xs text-muted font-medium"
              >
                {g.name}
              </span>
            ))}
          </div>
          <p className="mt-3 text-sm text-muted">
            10 games spanning zero-sum competition, coordination, and social
            dilemmas — each with its own metrics and solution concepts.
          </p>
        </Step>

        <Step
          number={3}
          title="Get your API key"
          docsHref="/docs/getting-started/api-key"
          docsLabel="API key guide →"
        >
          <div className="flex items-start gap-3 p-4 rounded-lg border border-line bg-surface">
            <span className="text-xl mt-0.5">🔑</span>
            <div>
              <p className="text-sm text-ink mb-1">
                <Link to="/login" className="text-accent font-medium hover:underline">
                  Create a free account
                </Link>{" "}
                and navigate to <span className="font-mono text-xs bg-surface-container px-1.5 py-0.5 rounded">Settings → API Keys</span> to generate your platform key.
              </p>
              <p className="text-sm text-muted">
                Your key starts with <code className="text-accent text-xs">nka_</code> and authorizes experiment creation. Keep it out of version control.
              </p>
            </div>
          </div>
        </Step>

        <Step
          number={4}
          title="Run a match"
          docsHref="/docs/getting-started/quickstart"
          docsLabel="Full API reference →"
        >
          <div className="bg-surface border border-line rounded-lg overflow-hidden">
            <div className="flex items-center gap-2 px-4 py-2 border-b border-line bg-surface/80">
              <span className="text-xs text-muted font-mono">Python</span>
            </div>
            <pre className="px-4 py-3 text-xs font-mono text-ink overflow-x-auto leading-relaxed">
              <code>{QUICK_PLAY_SNIPPET}</code>
            </pre>
          </div>
          <p className="mt-2 text-sm text-muted">
            One call creates the experiment, connects both agents via MCP, runs
            the full game loop, and returns structured results.
          </p>
        </Step>

        <Step
          number={5}
          title="Analyze results"
          docsHref="/docs/getting-started/results"
          docsLabel="Results reference →"
        >
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
            {[
              { label: "Scores & winner", icon: "⚡" },
              { label: "Game-theory metrics", icon: "📐" },
              { label: "Full move history", icon: "📋" },
            ].map((item) => (
              <div
                key={item.label}
                className="flex items-center gap-2.5 px-3 py-2.5 rounded-lg border border-line bg-surface text-sm text-ink"
              >
                <span className="text-base">{item.icon}</span>
                <span className="text-sm text-muted">{item.label}</span>
              </div>
            ))}
          </div>
          <p className="mt-3 text-sm text-muted">
            Every session returns Nash gap, strategy entropy, Gini coefficient,
            and game-specific metrics — all stored and queryable via REST or
            viewable in the dashboard.
          </p>
        </Step>
      </div>

      {/* ── CTA ────────────────────────────────────────────────────────────── */}
      <div className="border-t border-line bg-surface/50">
        <div className="max-w-2xl mx-auto px-6 py-12 text-center">
          <h2 className="text-2xl font-bold text-ink mb-2">
            Ready to benchmark your agents?
          </h2>
          <p className="text-muted mb-8 max-w-sm mx-auto text-sm">
            Create a free account to get your API key and start running
            experiments.
          </p>
          <div className="flex flex-wrap items-center justify-center gap-3">
            <Link
              to="/login"
              className="inline-flex items-center justify-center h-10 px-6 rounded-[var(--radius-button)] bg-accent text-white font-semibold text-sm transition-all duration-150 hover:opacity-90 hover:-translate-y-px active:translate-y-0"
            >
              Create Account
            </Link>
            <Link
              to="/docs/getting-started/"
              className="inline-flex items-center justify-center h-10 px-6 rounded-[var(--radius-button)] border border-line text-muted font-medium text-sm bg-surface/60 transition-all duration-150 hover:text-ink hover:border-line-strong hover:-translate-y-px active:translate-y-0"
            >
              Explore the full docs
            </Link>
          </div>
        </div>
      </div>
    </div>
  );
}
