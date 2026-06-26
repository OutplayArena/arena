import { describe, it, expect } from "vitest";
import { screen } from "@testing-library/react";
import { Route, Routes } from "react-router-dom";
import { renderWithProviders } from "../../test-utils";
import { DocsPage } from "../DocsPage";

/**
 * Renders DocsPage inside the real <Routes> tree, so `useParams()` can
 * resolve the `*` splat that captures the sub-path under /docs.
 */
function renderDocsPage(initialRoute: string) {
  // Two render strategies: with-splat (must go through <Routes>) and the
  // plain case (also via <Routes> for consistency).
  return renderWithProviders(
    <Routes>
      <Route path="/docs/*" element={<DocsPage />} />
    </Routes>,
    { initialRoute },
  );
}

describe("DocsPage", () => {
  it("renders an iframe with /docs/ src when the route has no splat", () => {
    renderDocsPage("/docs");
    const iframe = screen.getByTitle("Documentation") as HTMLIFrameElement;
    expect(iframe).toBeInTheDocument();
    expect(iframe.src).toMatch(/\/docs\/?$/);
    expect(iframe.tagName).toBe("IFRAME");
  });

  it("forwards the splat to the iframe src", () => {
    renderDocsPage("/docs/sdk/overview/");
    const iframe = screen.getByTitle("Documentation") as HTMLIFrameElement;
    expect(iframe.src).toMatch(/\/docs\/sdk\/overview\/$/);
  });

  it("preserves the query string in the iframe src", () => {
    renderDocsPage("/docs/search/?q=foo");
    const iframe = screen.getByTitle("Documentation") as HTMLIFrameElement;
    expect(iframe.src).toMatch(/\/docs\/search\/?\?q=foo$/);
  });

  it("preserves the hash in the iframe src", () => {
    renderDocsPage("/docs/sdk/overview/#installation");
    const iframe = screen.getByTitle("Documentation") as HTMLIFrameElement;
    expect(iframe.src).toMatch(/#installation$/);
  });

  it("fills the available space and has no border", () => {
    renderDocsPage("/docs");
    const iframe = screen.getByTitle("Documentation") as HTMLIFrameElement;
    expect(iframe.className).toMatch(/\bborder-0\b/);
    expect(iframe.className).toMatch(/\bw-full\b/);
    expect(iframe.className).toMatch(/\bflex-1\b/);
  });
});
