import { describe, it, expect, vi, beforeEach } from "vitest";
import {
  request,
  ApiError,
  createExperiment,
  getState,
  submitAction,
  getResults,
  getProviders,
  getSiteConfig,
  getDashboard,
  listSessions,
  getSessionSummary,
  failSession,
  deleteSession,
  listKeys,
  createKey,
  deleteKey as deleteApiKey,
  disableKey,
  enableKey,
  listGames,
  getGameMetadata,
  getGameAgents,
  getGameMetrics,
  getGameScenarios,
} from "../api";

beforeEach(() => {
  vi.restoreAllMocks();
  localStorage.clear();
});

describe("request base function", () => {
  it("adds Bearer token from localStorage", async () => {
    localStorage.setItem("nasharena_token", "test-token");
    const mockFetch = vi.spyOn(globalThis, "fetch").mockResolvedValue({
      ok: true,
      text: () => Promise.resolve('{"data": 1}'),
    } as Response);

    await request("/api/test");
    const headers = mockFetch.mock.calls[0][1]?.headers as Record<string, string>;
    expect(headers.Authorization).toBe("Bearer test-token");
  });

  it("throws ApiError on non-ok response", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue({
      ok: false,
      status: 500,
      text: () => Promise.resolve('{"detail":"Server error"}'),
    } as Response);

    await expect(request("/api/test")).rejects.toThrow(ApiError);
    await expect(request("/api/test")).rejects.toMatchObject({ status: 500 });
  });

  it("throws ApiError with fallback message on non-ok without detail", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue({
      ok: false,
      status: 404,
      text: () => Promise.resolve("{}"),
    } as Response);

    await expect(request("/api/test")).rejects.toThrow("HTTP 404");
  });

  it("throws on invalid JSON response", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue({
      ok: true,
      text: () => Promise.resolve("not json"),
    } as Response);

    await expect(request("/api/test")).rejects.toThrow("Invalid JSON response");
  });

  it("sets Content-Type on POST requests", async () => {
    const mockFetch = vi.spyOn(globalThis, "fetch").mockResolvedValue({
      ok: true,
      text: () => Promise.resolve("{}"),
    } as Response);
    await request("/api/test", { method: "POST", body: "{}" });
    const headers = mockFetch.mock.calls[0][1]?.headers as Record<string, string>;
    expect(headers["Content-Type"]).toBe("application/json");
  });

  it("sends no Authorization when no token", async () => {
    const mockFetch = vi.spyOn(globalThis, "fetch").mockResolvedValue({
      ok: true,
      text: () => Promise.resolve("{}"),
    } as Response);
    await request("/api/test");
    const headers = mockFetch.mock.calls[0][1]?.headers as Record<string, string>;
    expect(headers.Authorization).toBeUndefined();
  });
});

describe("API endpoint functions", () => {
  beforeEach(() => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue({
      ok: true,
      text: () => Promise.resolve("{}"),
    } as Response);
  });

  it("createExperiment sends POST to /api/experiment", async () => {
    await createExperiment({ game: "blotto", variant: "", players: 2, rounds: 10 });
    expect(globalThis.fetch).toHaveBeenCalledWith(
      "/api/experiment",
      expect.objectContaining({ method: "POST" }),
    );
  });

  it("getState calls correct URL", async () => {
    await getState("session-1");
    expect(globalThis.fetch).toHaveBeenCalledWith(
      "/api/session/session-1/state",
      expect.anything(),
    );
  });

  it("submitAction sends correct method and token", async () => {
    await submitAction("session-1", [1, 2, 3], "player-token");
    expect(globalThis.fetch).toHaveBeenCalledWith(
      "/api/session/session-1/action",
      expect.objectContaining({
        method: "POST",
        headers: expect.objectContaining({ Authorization: "Bearer player-token" }),
      }),
    );
  });

  it("getResults calls correct URL", async () => {
    await getResults("session-1");
    expect(globalThis.fetch).toHaveBeenCalledWith(
      "/api/session/session-1/results",
      expect.anything(),
    );
  });

  it("getProviders calls /api/auth/providers", async () => {
    await getProviders();
    expect(globalThis.fetch).toHaveBeenCalledWith(
      "/api/auth/providers",
      expect.anything(),
    );
  });

  it("getSiteConfig calls /api/site-config", async () => {
    await getSiteConfig();
    expect(globalThis.fetch).toHaveBeenCalledWith(
      "/api/site-config",
      expect.anything(),
    );
  });

  it("getDashboard calls /api/dashboard", async () => {
    await getDashboard();
    expect(globalThis.fetch).toHaveBeenCalledWith(
      "/api/dashboard",
      expect.anything(),
    );
  });

  it("listSessions calls /api/sessions with no params", async () => {
    await listSessions();
    expect(globalThis.fetch).toHaveBeenCalledWith(
      "/api/sessions",
      expect.anything(),
    );
  });

  it("listSessions encodes query params", async () => {
    await listSessions({ game: "blotto", agent: "remote", limit: 10, offset: 5, date_from: "2025-01-01", date_to: "2025-06-01" });
    const url = (globalThis.fetch as ReturnType<typeof vi.fn>).mock.calls.at(-1)[0] as string;
    expect(url).toContain("game=blotto");
    expect(url).toContain("agent=remote");
    expect(url).toContain("limit=10");
    expect(url).toContain("offset=5");
  });

  it("getSessionSummary calls correct URL", async () => {
    await getSessionSummary("s1");
    expect(globalThis.fetch).toHaveBeenCalledWith(
      "/api/session/s1/summary",
      expect.anything(),
    );
  });

  it("failSession sends POST with error body", async () => {
    await failSession("s1", "something broke");
    expect(globalThis.fetch).toHaveBeenCalledWith(
      "/api/session/s1/fail",
      expect.objectContaining({ method: "POST" }),
    );
  });

  it("deleteSession sends DELETE", async () => {
    await deleteSession("s1");
    expect(globalThis.fetch).toHaveBeenCalledWith(
      "/api/sessions/s1",
      expect.objectContaining({ method: "DELETE" }),
    );
  });

  it("listKeys calls /api/keys", async () => {
    await listKeys();
    expect(globalThis.fetch).toHaveBeenCalledWith(
      "/api/keys",
      expect.anything(),
    );
  });

  it("createKey sends POST with name", async () => {
    await createKey("my-key");
    expect(globalThis.fetch).toHaveBeenCalledWith(
      "/api/keys",
      expect.objectContaining({ method: "POST" }),
    );
  });

  it("createKey sends POST with null name", async () => {
    await createKey();
    expect(globalThis.fetch).toHaveBeenCalledWith(
      "/api/keys",
      expect.objectContaining({ method: "POST" }),
    );
  });

  it("deleteApiKey sends DELETE", async () => {
    await deleteApiKey("key-1");
    expect(globalThis.fetch).toHaveBeenCalledWith(
      "/api/keys/key-1",
      expect.objectContaining({ method: "DELETE" }),
    );
  });

  it("disableKey sends POST", async () => {
    await disableKey("key-1");
    expect(globalThis.fetch).toHaveBeenCalledWith(
      "/api/keys/key-1/disable",
      expect.objectContaining({ method: "POST" }),
    );
  });

  it("enableKey sends POST", async () => {
    await enableKey("key-1");
    expect(globalThis.fetch).toHaveBeenCalledWith(
      "/api/keys/key-1/enable",
      expect.objectContaining({ method: "POST" }),
    );
  });

  it("listGames calls /api/games", async () => {
    await listGames();
    expect(globalThis.fetch).toHaveBeenCalledWith(
      "/api/games",
      expect.anything(),
    );
  });

  it("getGameMetadata calls correct URL", async () => {
    await getGameMetadata("colonelblotto");
    expect(globalThis.fetch).toHaveBeenCalledWith(
      "/api/games/colonelblotto",
      expect.anything(),
    );
  });

  it("getGameAgents calls correct URL", async () => {
    await getGameAgents("colonelblotto");
    expect(globalThis.fetch).toHaveBeenCalledWith(
      "/api/games/colonelblotto/agents",
      expect.anything(),
    );
  });

  it("getGameMetrics calls correct URL", async () => {
    await getGameMetrics("colonelblotto");
    expect(globalThis.fetch).toHaveBeenCalledWith(
      "/api/games/colonelblotto/metrics",
      expect.anything(),
    );
  });

  it("getGameScenarios calls correct URL", async () => {
    await getGameScenarios("colonelblotto");
    expect(globalThis.fetch).toHaveBeenCalledWith(
      "/api/games/colonelblotto/scenarios",
      expect.anything(),
    );
  });
});
