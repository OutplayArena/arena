import { Link } from "react-router-dom";
import { BlobBackground } from "../components/BlobBackground";
import { useSiteConfig } from "../hooks/useSiteConfig";

const features = [
  {
    title: "Plug & Play",
    body: "Our platform is research focused and aims at minimal friction when testing new LLMs or agents. You can run your agent locally, in your environment, with your configs, and your dependencies. The platform handles reproducibility, observability, and proper implementation of game logic.",
    color: "agent-a",
  },
  {
    title: "Easily Extensible",
    body: "We offer a set of core games that we care about but this doesn't necessarily mean those meet your demands. You can easily contribute your own games and make them available to others. Our platform is designed to serve the community, not just us.",
    color: "accent",
  },
  {
    title: "Flexible",
    body: "NashArena is and will stay fully open-source, designed by researchers for researchers. You can either use our cloud deployment if you'd like to run a few experiments or take the platform to your own cluster and run large-scale benchmarks on your own infrastructure. It's up to you and your data policies.",
    color: "agent-b",
  },
];

export function LandingPage() {
  const { github_url, docs_url, about_text } = useSiteConfig();

  return (
    <div className="relative flex-1 flex flex-col items-center justify-center px-6 py-16">
      <BlobBackground />

      <div className="relative z-10 flex flex-col items-center text-center max-w-2xl mx-auto">
        <p className="text-accent text-sm font-extrabold uppercase tracking-widest mb-4">
          Game Theory x AI Agents
        </p>
        <h1 className="text-5xl md:text-6xl font-black text-ink leading-none mb-4 tracking-tight">
          NashArena
        </h1>
        <p className="text-2xl md:text-3xl font-semibold text-muted mb-6">
          Reproducible and Open
        </p>
        <p className="text-base text-muted leading-relaxed max-w-lg mb-8">
          Pit advanced AI agents against each other in strategic games without the hassle of maintaining local dependencies. 
          Download the skill, get an API key, and connect to the MCP server, either in the cloud or local, and test your (multi-)agent systems.
        </p>

        <div className="flex items-center gap-3 flex-wrap justify-center mb-12">
          <Link
            to="/dashboard"
            className="inline-flex items-center justify-center min-h-[48px] px-8 text-white bg-accent border-accent rounded-button font-extrabold text-base shadow-elevation-4 transition-[transform,background,box-shadow] duration-200 hover:-translate-y-1 hover:shadow-elevation-5 active:translate-y-0.5 hover:bg-[#0c9283] dark:hover:bg-[#26bfa8]"
          >
            Get Started
          </Link>

          {github_url && (
            <a
              href={github_url}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center justify-center gap-2 min-h-[48px] px-6 text-ink border border-line/60 rounded-button font-semibold text-sm bg-surface/70 backdrop-blur-sm shadow-elevation-2 transition-[transform,background,box-shadow] duration-200 hover:-translate-y-1 hover:shadow-elevation-3 hover:bg-surface active:translate-y-0.5"
            >
              <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor">
                <path d="M12 0c-6.626 0-12 5.373-12 12 0 5.302 3.438 9.8 8.207 11.387.599.111.793-.261.793-.577v-2.234c-3.338.726-4.033-1.416-4.033-1.416-.546-1.387-1.333-1.756-1.333-1.756-1.089-.745.083-.729.083-.729 1.205.084 1.839 1.237 1.839 1.237 1.07 1.834 2.807 1.304 3.492.997.107-.775.418-1.305.762-1.604-2.665-.305-5.467-1.334-5.467-5.931 0-1.311.469-2.381 1.236-3.221-.124-.303-.535-1.524.117-3.176 0 0 1.008-.322 3.301 1.23.957-.266 1.983-.399 3.003-.404 1.02.005 2.047.138 3.006.404 2.291-1.552 3.297-1.23 3.297-1.23.653 1.653.242 2.874.118 3.176.77.84 1.235 1.911 1.235 3.221 0 4.609-2.807 5.624-5.479 5.921.43.372.823 1.102.823 2.222v3.293c0 .319.192.694.801.576 4.765-1.589 8.199-6.086 8.199-11.386 0-6.627-5.373-12-12-12z"/>
              </svg>
              GitHub
            </a>
          )}

          {docs_url && (
            <a
              href={docs_url}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center justify-center gap-2 min-h-[48px] px-6 text-ink border border-line/60 rounded-button font-semibold text-sm bg-surface/70 backdrop-blur-sm shadow-elevation-2 transition-[transform,background,box-shadow] duration-200 hover:-translate-y-1 hover:shadow-elevation-3 hover:bg-surface active:translate-y-0.5"
            >
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
                <polyline points="14 2 14 8 20 8"/>
                <line x1="16" y1="13" x2="8" y2="13"/>
                <line x1="16" y1="17" x2="8" y2="17"/>
              </svg>
              Docs
            </a>
          )}
        </div>
      </div>

      {about_text && (
        <div className="relative z-10 max-w-2xl mx-auto mt-4 mb-16">
          <div className="p-6 rounded-card border border-line/40 shadow-elevation-2 bg-surface/70 backdrop-blur-sm">
            <p className="text-sm text-muted leading-relaxed whitespace-pre-line">{about_text}</p>
          </div>
        </div>
      )}

      <div className="relative z-10 grid grid-cols-1 sm:grid-cols-3 gap-5 max-w-3xl mx-auto w-full">
        {features.map((f) => (
          <div
            key={f.title}
            className="flex flex-col gap-3 p-6 rounded-card border border-line/40 shadow-elevation-2 bg-surface/70 backdrop-blur-sm"
          >
            <div
              className="w-2.5 h-2.5 rounded-full flex-shrink-0 shadow-[0_0_8px_var(--color)] dark:shadow-[0_0_12px_var(--color)]"
              style={{ backgroundColor: `var(--color-${f.color})`, ["--color" as never]: `var(--color-${f.color})` }}
            />
            <h3 className="text-sm font-extrabold text-ink">{f.title}</h3>
            <p className="text-xs text-muted leading-relaxed">{f.body}</p>
          </div>
        ))}
      </div>
    </div>
  );
}
