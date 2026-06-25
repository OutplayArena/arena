import { describe, it, expect, beforeEach, vi } from "vitest";
import { renderHook, waitFor } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { server } from "../../mocks/server";
import { useGameNames, gameName, prettifySlug } from "../useGameNames";

describe("useGameNames", () => {
  beforeEach(() => {
    server.resetHandlers();
    // Reset the module-level cache between tests by reloading the module.
    vi.resetModules();
  });

  it("returns an empty map until the games list resolves", async () => {
    // Slow handler so we can observe the loading state.
    server.use(
      http.get("/api/games", async () => {
        await new Promise((r) => setTimeout(r, 50));
        return HttpResponse.json([
          { slug: "ultimatum", name: "Ultimatum Game" },
        ]);
      }),
    );
    const { result } = renderHook(() => useGameNames());
    // Initially the cache is empty; useGameNames returns a new empty Map.
    expect(result.current.size).toBe(0);
    await waitFor(() => {
      expect(result.current.get("ultimatum")).toBe("Ultimatum Game");
    });
  });

  it("populates the slug → name map from /api/games", async () => {
    server.use(
      http.get("/api/games", () =>
        HttpResponse.json([
          { slug: "ultimatum", name: "Ultimatum Game" },
          { slug: "colonelblotto", name: "Colonel Blotto" },
          { slug: "battle_of_the_sexes", name: "Battle of the Sexes" },
        ]),
      ),
    );
    const { result } = renderHook(() => useGameNames());
    await waitFor(() => {
      expect(result.current.get("ultimatum")).toBe("Ultimatum Game");
    });
    expect(result.current.get("colonelblotto")).toBe("Colonel Blotto");
    expect(result.current.get("battle_of_the_sexes")).toBe("Battle of the Sexes");
    expect(result.current.size).toBe(3);
  });

  it("returns an empty map if /api/games fails", async () => {
    server.use(http.get("/api/games", () => new HttpResponse("boom", { status: 500 })));
    const { result } = renderHook(() => useGameNames());
    // Give the failed fetch a moment to settle.
    await new Promise((r) => setTimeout(r, 50));
    expect(result.current.size).toBe(0);
  });
});

describe("gameName helper", () => {
  it("prettifies the slug when the map is empty (no raw underscores)", () => {
    expect(gameName("ultimatum", new Map())).toBe("Ultimatum");
  });

  it("returns 'Overall' for undefined", () => {
    expect(gameName(undefined, new Map())).toBe("Overall");
  });

  it("returns the human-readable name when present in the map", () => {
    const names = new Map([["ultimatum", "Ultimatum Game"]]);
    expect(gameName("ultimatum", names)).toBe("Ultimatum Game");
  });

  it("prettifies the slug if the slug is not in the map (no raw underscores)", () => {
    const names = new Map([["ultimatum", "Ultimatum Game"]]);
    expect(gameName("unknown_game", names)).toBe("Unknown Game");
  });

  it("prefers the map value over a prettified slug when both apply", () => {
    const names = new Map([["battle_of_the_sexes", "Battle of the Sexes"]]);
    // Map value wins even if prettifySlug would produce the same string.
    expect(gameName("battle_of_the_sexes", names)).toBe("Battle of the Sexes");
  });
});

describe("prettifySlug", () => {
  it("replaces underscores with spaces and title-cases each word", () => {
    expect(prettifySlug("battle_of_the_sexes")).toBe("Battle Of The Sexes");
  });

  it("replaces dashes with spaces and title-cases each word", () => {
    expect(prettifySlug("rock-paper-scissors")).toBe("Rock Paper Scissors");
  });

  it("handles a single word", () => {
    expect(prettifySlug("ultimatum")).toBe("Ultimatum");
  });

  it("collapses repeated separators", () => {
    expect(prettifySlug("foo__bar--baz")).toBe("Foo Bar Baz");
  });

  it("returns an empty string for an empty slug", () => {
    expect(prettifySlug("")).toBe("");
  });
});
