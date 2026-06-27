import { memo } from "react";
import { Link } from "react-router-dom";
import { useSiteConfig } from "../hooks/useSiteConfig";


export const Footer = memo(function Footer() {
  const { github_url, docs_url, privacy_notice_url } = useSiteConfig();

  return (
    <footer className="border-t border-line bg-surface-soft">
      <div className="max-w-6xl mx-auto px-6 py-12 grid grid-cols-2 md:grid-cols-4 gap-8">
        {/* Col 1: Brand */}
        <div className="col-span-2 md:col-span-1">
          <Link to="/" className="flex items-center gap-2 no-underline mb-3">
            <img src="/img/logo_only_outplayarena.png" alt="OutplayArena" className="h-6 w-auto" />
            <span className="text-sm font-bold text-ink">OutplayArena</span>
          </Link>
          <p className="text-xs text-muted leading-relaxed max-w-[180px]">
            Rigorous, reproducible benchmarks for strategic AI behavior.
          </p>
        </div>

        {/* Col 2: Platform */}
        <div>
          <p className="text-xs font-semibold text-ink mb-3 uppercase tracking-wider">Platform</p>
          <ul className="space-y-2">
            <li><Link to="/dashboard" className="text-xs text-muted hover:text-ink transition-colors no-underline">Dashboard</Link></li>
            <li><Link to="/keys" className="text-xs text-muted hover:text-ink transition-colors no-underline">API Keys</Link></li>
            <li><Link to="/games" className="text-xs text-muted hover:text-ink transition-colors no-underline">Games</Link></li>
          </ul>
        </div>

        {/* Col 3: Community */}
        <div>
          <p className="text-xs font-semibold text-ink mb-3 uppercase tracking-wider">Community</p>
          <ul className="space-y-2">
            {github_url && (
              <>
                <li><a href={github_url} target="_blank" rel="noopener noreferrer" className="text-xs text-muted hover:text-ink transition-colors no-underline">GitHub</a></li>
                <li><a href={`${github_url}/issues`} target="_blank" rel="noopener noreferrer" className="text-xs text-muted hover:text-ink transition-colors no-underline">Issues</a></li>
              </>
            )}
            {privacy_notice_url && <li><a href={privacy_notice_url} target="_blank" rel="noopener noreferrer" className="text-xs text-muted hover:text-ink transition-colors no-underline">Privacy</a></li>}
          </ul>
        </div>

        {/* Col 4: Resources */}
        <div>
          <p className="text-xs font-semibold text-ink mb-3 uppercase tracking-wider">Resources</p>
          <ul className="space-y-2">
            {docs_url && <li><Link to="/docs" className="text-xs text-muted hover:text-ink transition-colors no-underline">Docs</Link></li>}
            {github_url && <li><a href={`${github_url}/tree/main/examples`} target="_blank" rel="noopener noreferrer" className="text-xs text-muted hover:text-ink transition-colors no-underline">Examples</a></li>}
            <li><Link to="/papers" className="text-xs text-muted hover:text-ink transition-colors no-underline">Papers</Link></li>
          </ul>
        </div>
      </div>

      {/* Bottom bar */}
      <div className="border-t border-line px-6 py-4 max-w-6xl mx-auto flex flex-col sm:flex-row items-center justify-between gap-3">
        <p className="text-xs text-muted">
          © 2026 -{" "}
          <a
            href="https://github.com/OutplayArena/arena/graphs/contributors"
            target="_blank"
            rel="noopener noreferrer"
            className="text-muted hover:text-ink transition-colors"
          >
            OutplayArena Contributors
          </a>
        </p>
        <div className="flex items-center gap-2">
          <span
            className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded-[var(--radius-chip)] border border-line text-xs font-mono text-muted"
            title="SPDX-License-Identifier: Apache-2.0 OR GPL-3.0-or-later"
          >
            Apache 2.0 / GPL-3.0
          </span>
          <span className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded-[var(--radius-chip)] border border-line text-xs font-mono text-muted">
            Open science, made with ❤️
          </span>
        </div>
      </div>
    </footer>
  );
});
