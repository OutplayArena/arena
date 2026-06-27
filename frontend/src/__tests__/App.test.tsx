import { describe, it, expect } from "vitest";
import { screen } from "@testing-library/react";
import { renderWithProviders } from "../test-utils";
import App from "../App";

/**
 * The /docs/* route wraps the mkdocs Material site in an iframe. The React
 * NavBar and Footer would sit above/below the iframe, giving the user two
 * stacked headers and two stacked footers (React + mkdocs). App hides both
 * pieces of chrome when the URL is a /docs path so the iframe fills the
 * viewport and only the mkdocs chrome (header, sidebar, content) shows.
 */
describe("App layout — /docs chrome", () => {
  it("hides NavBar and Footer on /docs", () => {
    renderWithProviders(<App />, { initialRoute: "/docs" });
    expect(screen.queryByRole("navigation")).toBeNull();
    expect(screen.queryByRole("contentinfo")).toBeNull();
  });

  it("hides NavBar and Footer on /docs/sdk/overview/", () => {
    renderWithProviders(<App />, { initialRoute: "/docs/sdk/overview/" });
    expect(screen.queryByRole("navigation")).toBeNull();
    expect(screen.queryByRole("contentinfo")).toBeNull();
  });

  it("shows NavBar and Footer on /", () => {
    renderWithProviders(<App />, { initialRoute: "/" });
    expect(screen.getByRole("navigation")).toBeInTheDocument();
    expect(screen.getByRole("contentinfo")).toBeInTheDocument();
  });

  it("shows NavBar and Footer on /leaderboard", () => {
    renderWithProviders(<App />, { initialRoute: "/leaderboard" });
    expect(screen.getByRole("navigation")).toBeInTheDocument();
    expect(screen.getByRole("contentinfo")).toBeInTheDocument();
  });
});
