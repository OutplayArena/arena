import { useSiteConfig } from "../hooks/useSiteConfig";

export function Footer() {
  const { github_url, privacy_notice_url, footer } = useSiteConfig();

  return (
    <footer className="border-t border-line/50 bg-surface/60 backdrop-blur-sm px-5 py-4">
      <div className="max-w-3xl mx-auto flex flex-col sm:flex-row items-center justify-between gap-2 text-xs text-muted">
        <span>{footer.copyright}</span>

        <div className="flex items-center gap-3">
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

          <span>{footer.privacy_notice}</span>
        </div>
      </div>
    </footer>
  );
}
