export function PapersPage() {
  return (
    <div className="max-w-3xl mx-auto px-6 py-32 flex flex-col items-center text-center">
      {/* Icon */}
      <div className="w-16 h-16 rounded-[var(--radius-card)] bg-accent/10 border border-accent/20 flex items-center justify-center mb-8">
        <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="var(--color-accent)" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
          <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
          <polyline points="14 2 14 8 20 8"/>
          <line x1="16" y1="13" x2="8" y2="13"/>
          <line x1="16" y1="17" x2="8" y2="17"/>
          <polyline points="10 9 9 9 8 9"/>
        </svg>
      </div>

      <p className="text-xs font-mono text-accent uppercase tracking-widest mb-3">Resources</p>
      <h1 className="text-3xl font-extrabold text-ink mb-4">Papers</h1>
      <p className="text-lg text-muted mb-2 leading-relaxed">
        Great things are coming soon.
      </p>
      <p className="text-sm text-quiet max-w-md leading-relaxed">
        We're compiling a curated reading list — foundational game theory papers,
        empirical studies on LLM strategic reasoning, and new research produced
        using OutplayArena. Check back soon.
      </p>

      {/* Divider */}
      <div className="w-12 h-px bg-line my-10" />

      {/* Placeholder cards */}
      <div className="w-full space-y-3 opacity-40 pointer-events-none select-none">
        {[
          "Nash, J. (1950). Equilibrium Points in N-Person Games",
          "Osborne & Rubinstein (1994). A Course in Game Theory",
          "Aumann, R. (1974). Subjectivity and Correlation in Randomized Strategies",
        ].map((title) => (
          <div
            key={title}
            className="flex items-start gap-4 rounded-[var(--radius-card)] border border-line bg-surface p-4 text-left"
          >
            <div className="w-8 h-8 shrink-0 rounded-md bg-surface-soft border border-line" />
            <div className="flex-1 space-y-1.5">
              <div className="h-3 rounded-full bg-surface-container w-4/5" />
              <div className="h-2.5 rounded-full bg-surface-container w-2/5" />
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
