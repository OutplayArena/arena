import { memo } from "react";
import { useSiteConfig } from "../hooks/useSiteConfig";

export const Footer = memo(function Footer() {
  const { github_url, privacy_notice_url, footer } = useSiteConfig();

  return (
    <footer className="border-t border-line/50 bg-surface/60 backdrop-blur-sm px-5 py-4">
      <div className="max-w-3xl mx-auto flex items-center gap-4 text-xs text-muted">
        <span className="flex-1 whitespace-nowrap">
          {footer.copyright.replace("NashArena Contributors", "")}
          {github_url ? (
            <a
              href={`${github_url}/graphs/contributors`}
              target="_blank"
              rel="noopener noreferrer"
              className="hover:text-ink transition-colors duration-200"
            >
              NashArena Contributors
            </a>
          ) : (
            "NashArena Contributors"
          )}
        </span>

        {footer.tagline && (
          <span className="text-center">{footer.tagline}</span>
        )}

        <div className="flex items-center gap-3 flex-1 justify-end">
          {github_url && (
            <a
              href={github_url}
              target="_blank"
              rel="noopener noreferrer"
              className="hover:text-ink transition-colors duration-200"
            >
              GitHub
            </a>
          )}

          {privacy_notice_url && (
            <a
              href={privacy_notice_url}
              target="_blank"
              rel="noopener noreferrer"
              className="hover:text-ink transition-colors duration-200"
            >
              Privacy Notice
            </a>
          )}
        </div>
      </div>
    </footer>
  );
});
