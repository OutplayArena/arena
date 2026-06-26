import { useRef, useState } from "react";
import { useLocation, useParams } from "react-router-dom";
import { useSiteConfig } from "../hooks/useSiteConfig";

/**
 * Renders the mkdocs-built documentation inside an iframe.
 *
 * The route is /docs/* in the React SPA. The `*` splat is forwarded to the
 * docs service as the iframe's `src`, so the full mkdocs URL space is
 * navigable from the SPA (e.g. /docs/sdk/overview/, /docs/getting-started/).
 *
 * In dev, Vite proxies /docs to the docs pod (see vite.config.ts). In prod,
 * Traefik routes /docs to the docs service with a strip-prefix middleware.
 * Either way, the iframe `src` is a same-origin relative URL.
 */
export function DocsPage() {
  const { "*": splat } = useParams();
  const location = useLocation();
  const { docs_url } = useSiteConfig();
  const iframeRef = useRef<HTMLIFrameElement>(null);
  const [loaded, setLoaded] = useState(false);

  const subPath = splat ?? "";
  const iframeSrc = `/docs/${subPath}${location.search}${location.hash}`;

  // Fallback for users who land on /docs without the docs service running
  // (e.g. they forgot to run dev-tunnel.sh): show a hint with the external
  // docs URL if one is configured.
  const externalHref = docs_url && docs_url.startsWith("http") ? docs_url : null;

  return (
    <div
      className="flex flex-col flex-1 min-h-0"
      data-testid="docs-page"
    >
      <iframe
        ref={iframeRef}
        src={iframeSrc}
        title="Documentation"
        className="flex-1 w-full border-0 bg-surface min-h-[60vh]"
        onLoad={() => setLoaded(true)}
      />
      {!loaded && externalHref && (
        <div className="absolute inset-x-0 bottom-4 mx-auto w-fit max-w-md px-4 py-2 rounded-card border border-line bg-surface shadow-elevation-2 text-xs text-muted text-center">
          Docs service unreachable. See the published docs at{" "}
          <a
            href={externalHref}
            target="_blank"
            rel="noopener noreferrer"
            className="text-accent hover:underline"
          >
            {externalHref}
          </a>{" "}
          instead.
        </div>
      )}
    </div>
  );
}
