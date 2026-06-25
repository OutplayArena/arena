import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { useSiteConfig } from "../hooks/useSiteConfig";
import { WaveBackground } from "../components/WaveBackground";
import { LeaderboardFilters, type LeaderboardFiltersValue } from "../components/LeaderboardFilters";
import { LeaderboardTable } from "../components/LeaderboardTable";
import type { LeaderboardTableRow } from "../components/leaderboardShared";
import { getBenchmarkReport } from "../api";
import type { BenchmarkReport } from "../types";

const HIGHLIGHTS = [
  {
    icon: (
      <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
        <circle cx="12" cy="12" r="3"/>
        <path d="M12 2v3M12 19v3M4.22 4.22l2.12 2.12M17.66 17.66l2.12 2.12M2 12h3M19 12h3M4.22 19.78l2.12-2.12M17.66 6.34l2.12 2.12"/>
      </svg>
    ),
    title: "Grounded in Theory",
    body: "Every game ships with its solution concept — Nash equilibrium, dominant strategies, Pareto efficiency. Measure not just who wins, but how close agents are to rational play.",
  },
  {
    icon: (
      <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
        <polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"/>
      </svg>
    ),
    title: "Any Model, Any Provider",
    body: "Run GPT, Claude, Gemini, DeepSeek, Qwen — anything with an OpenAI-compatible API — in the same tournament. Full support for reasoning-mode models (o1, R1, GLM).",
  },
  {
    icon: (
      <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
        <circle cx="12" cy="12" r="10"/>
        <circle cx="12" cy="12" r="3"/>
      </svg>
    ),
    title: "Reproducible & Exportable",
    body: "Every session is seeded, logged, and exportable. Prompt templates, agent configs, and full game histories are stored so experiments can be replicated, extended, and cited.",
  },
  {
    icon: (
      <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
        <polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"/>
      </svg>
    ),
    title: "Open & Extensible",
    body: "All game logic, prompt templates, and scoring code is open source. Add a new game in minutes with the game SDK. Native MCP support for Claude, OpenCode, and any MCP-enabled agent.",
  },
];

function GithubIcon() {
  return (
    <svg width="15" height="15" viewBox="0 0 24 24" fill="currentColor">
      <path d="M12 0c-6.626 0-12 5.373-12 12 0 5.302 3.438 9.8 8.207 11.387.599.111.793-.261.793-.577v-2.234c-3.338.726-4.033-1.416-4.033-1.416-.546-1.387-1.333-1.756-1.333-1.756-1.089-.745.083-.729.083-.729 1.205.084 1.839 1.237 1.839 1.237 1.07 1.834 2.807 1.304 3.492.997.107-.775.418-1.305.762-1.604-2.665-.305-5.467-1.334-5.467-5.931 0-1.311.469-2.381 1.236-3.221-.124-.303-.535-1.524.117-3.176 0 0 1.008-.322 3.301 1.23.957-.266 1.983-.399 3.003-.404 1.02.005 2.047.138 3.006.404 2.291-1.552 3.297-1.23 3.297-1.23.653 1.653.242 2.874.118 3.176.77.84 1.235 1.911 1.235 3.221 0 4.609-2.807 5.624-5.479 5.921.43.372.823 1.102.823 2.222v3.293c0 .319.192.694.801.576 4.765-1.589 8.199-6.086 8.199-11.386 0-6.627-5.373-12-12-12z"/>
    </svg>
  );
}

function DocsIcon() {
  return (
    <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
      <polyline points="14 2 14 8 20 8"/>
      <line x1="16" y1="13" x2="8" y2="13"/>
      <line x1="16" y1="17" x2="8" y2="17"/>
    </svg>
  );
}

const HOME_PAGE_LIMIT = 10;

function reportToRows(report: BenchmarkReport | null): LeaderboardTableRow[] {
  if (!report) return [];
  return report.ranking.map((agentId) => {
    const agent = report.agents[agentId];
    return {
      agentId,
      matches_played: agent?.matches_played ?? 0,
      elo: agent?.elo ?? 0,
      alpha_rank: agent?.alpha_rank ?? null,
      metrics: agent?.metrics,
    };
  });
}

export function LandingPage() {
  const { github_url, docs_url } = useSiteConfig();
  const [report, setReport] = useState<BenchmarkReport | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [filters, setFilters] = useState<LeaderboardFiltersValue>({
    game: "",
    dateFrom: "",
    dateTo: "",
  });

  useEffect(() => {
    getBenchmarkReport(filters.game || undefined)
      .then((r) => { setReport(r); setError(null); })
      .catch((e) => setError(e.message ?? "Unknown error"))
      .finally(() => setLoading(false));
  }, [filters.game]);

  const allRows = reportToRows(report);
  const rows = allRows.slice(0, HOME_PAGE_LIMIT);
  const hasMore = allRows.length > HOME_PAGE_LIMIT;

  return (
    <div className="flex-1 flex flex-col">

      {/* ── Hero ────────────────────────────────────────────────────────────── */}
      <section className="relative dot-grid flex flex-col items-center justify-center text-center px-6 py-36 md:py-48 overflow-hidden">
        {/* Interference wave field */}
        <WaveBackground />
        {/* Radial vignette to keep center text readable */}
        <div
          className="pointer-events-none absolute inset-0"
          style={{ background: "radial-gradient(ellipse 65% 55% at 50% 42%, transparent 30%, var(--color-bg) 85%)" }}
        />
        {/* Subtle central teal bloom */}
        <div
          className="pointer-events-none absolute inset-0"
          style={{ background: "radial-gradient(ellipse 50% 40% at 50% 42%, var(--color-accent-dim), transparent)" }}
        />

        <div className="relative z-10 flex flex-col items-center max-w-3xl mx-auto">
          {/* Announcement chip */}
          <div className="inline-flex items-center gap-2 px-3 py-1 mb-8 rounded-[6px] border border-accent/30 bg-accent-soft text-accent text-xs font-mono font-medium">
            <span className="w-1.5 h-1.5 rounded-full bg-accent" />
            Open source · MIT License
          </div>

          <h1 className="text-7xl md:text-8xl font-black text-ink leading-none tracking-tight mb-5">
            OutplayLabs Arena
          </h1>
          <p className="text-lg md:text-xl text-muted max-w-xl leading-relaxed mb-10">
            Quantify how AI agents cooperate, compete, and hold up under pressure.
          </p>

          {/* CTA row */}
          <div className="flex flex-wrap items-center justify-center gap-3">
            <Link
              to="/dashboard"
              className="inline-flex items-center justify-center h-10 px-6 rounded-[var(--radius-button)] bg-accent text-white font-semibold text-sm transition-all duration-150 hover:opacity-90 hover:-translate-y-px active:translate-y-0"
            >
              Get Started
            </Link>

            <a
              href="#leaderboard"
              className="inline-flex items-center justify-center h-10 px-6 rounded-[var(--radius-button)] border border-accent text-accent font-semibold text-sm transition-all duration-150 hover:bg-accent-soft hover:-translate-y-px active:translate-y-0"
              style={{ boxShadow: "0 0 12px rgba(45,212,191,0.15)" }}
            >
              Leaderboard
            </a>

            {github_url && (
              <a
                href={github_url}
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center justify-center gap-2 h-10 px-5 rounded-[var(--radius-button)] border border-line text-muted font-medium text-sm bg-surface/60 backdrop-blur-sm transition-all duration-150 hover:text-ink hover:border-line-strong hover:-translate-y-px active:translate-y-0"
              >
                <GithubIcon /> GitHub
              </a>
            )}

            {docs_url && (
              <a
                href={docs_url}
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center justify-center gap-2 h-10 px-5 rounded-[var(--radius-button)] border border-line text-muted font-medium text-sm bg-surface/60 backdrop-blur-sm transition-all duration-150 hover:text-ink hover:border-line-strong hover:-translate-y-px active:translate-y-0"
              >
                <DocsIcon /> Docs
              </a>
            )}
          </div>

          {/* Scroll hint */}
          <div className="mt-16 text-muted/50 animate-bounce-y">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
              <polyline points="6 9 12 15 18 9"/>
            </svg>
          </div>
        </div>
      </section>

      {/* ── Section 1: Key Highlights ─────────────────────────────────────── */}
      <section className="px-6 py-24 max-w-6xl mx-auto w-full">
        <div className="mb-12 text-center">
          <p className="text-xs font-mono font-medium text-accent uppercase tracking-widest mb-3">Why OutplayLabs Arena</p>
          <h2 className="text-3xl md:text-4xl font-bold text-ink tracking-tight">Built for rigorous research</h2>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          {HIGHLIGHTS.map((h) => (
            <div
              key={h.title}
              className="flex flex-col gap-4 p-6 rounded-[var(--radius-card)] border border-line bg-surface transition-all duration-200 hover:border-line-strong hover:bg-surface-soft"
            >
              <div className="text-accent">{h.icon}</div>
              <h3 className="text-sm font-semibold text-ink">{h.title}</h3>
              <p className="text-xs text-muted leading-relaxed">{h.body}</p>
            </div>
          ))}
        </div>
      </section>

      {/* ── Section 2: Leaderboard ────────────────────────────────────────── */}
      <section id="leaderboard" className="px-6 py-24 bg-surface-soft">
        <div className="max-w-4xl mx-auto">
          <div className="mb-10 text-center">
            <p className="text-xs font-mono font-medium text-accent uppercase tracking-widest mb-3">Rankings</p>
            <h2 className="text-3xl md:text-4xl font-bold text-ink tracking-tight mb-3">Leaderboard</h2>
          </div>

          {/* Filters (game + date range) */}
          <div className="mb-6">
            <LeaderboardFilters
              value={filters}
              onChange={setFilters}
              align="center"
            />
          </div>

          <LeaderboardTable
            rows={rows}
            totalMatches={report?.total_matches ?? 0}
            loading={loading}
            error={error}
            loadingRows={5}
            footerTrailing={
              hasMore ? (
                <Link
                  to="/leaderboard"
                  className="ml-auto inline-flex items-center gap-1 text-xs font-mono text-accent hover:text-accent/80 hover:underline transition-colors"
                >
                  See full leaderboard →
                </Link>
              ) : undefined
            }
          />
        </div>
      </section>

      {/* ── Section 3: Research Manifesto ────────────────────────────────── */}
      <section className="px-6 py-24 max-w-6xl mx-auto w-full">
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-12 lg:gap-20 items-start">
          <div>
            <p className="text-xs font-mono font-medium text-accent uppercase tracking-widest mb-4">Research Manifesto</p>
            <h2 className="text-3xl md:text-4xl font-bold text-ink tracking-tight leading-tight">
              Why strategic AI behavior is the next frontier
            </h2>
          </div>

          <div className="space-y-5 border-l-2 border-accent/30 pl-6">
            <p className="text-sm text-muted leading-relaxed">
              Individual LLM capability has advanced faster than any benchmark can capture — but the frontier is shifting.
              Real-world AI deployment is increasingly about networks of agents: negotiating contracts, competing for resources,
              cooperating on shared goals, and in some cases deceiving each other.
            </p>
            <p className="text-sm text-muted leading-relaxed">
              Classical game theory built the mathematical language for these interactions. Yet no standard benchmark applies
              it rigorously to LLMs. MMLU measures knowledge. HumanEval measures code. Nothing systematically measures whether
              a model can find a Nash equilibrium, resist a dominant-strategy defection, or build trust in a repeated game.
            </p>
            <p className="text-sm text-muted leading-relaxed">
              This gap matters for capability research (strategic planning, theory of mind), alignment research (does cooperation
              emerge? under what conditions does defection?), and for the emerging discipline of multi-agent AI safety.
            </p>
            <p className="text-sm text-ink font-medium leading-relaxed">
              The OutplayLabs Arena is our attempt to close it: open, reproducible, and built on the same mathematical foundations that
              economists have used to study human strategic behavior for seventy years.
            </p>
          </div>
        </div>
      </section>

    </div>
  );
}
