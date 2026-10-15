import { afterEach, describe, expect, it, vi } from "vitest";
import { ApiError } from "../api";
import { downloadTelemetry, getTelemetryEvents, getTelemetryReport } from "../telemetry";

afterEach(() => { vi.restoreAllMocks(); });

describe("telemetry API", () => {
  it("encodes session identifiers and sends event cursors and filters with authentication", async () => {
    localStorage.setItem("arena-token", "researcher-token");
    const fetch = vi.spyOn(globalThis, "fetch").mockImplementation(async () => new Response("{}"));
    await getTelemetryReport("session/one");
    expect(fetch).toHaveBeenLastCalledWith("/api/session/session%2Fone/telemetry", expect.objectContaining({
      headers: expect.objectContaining({ Authorization: "Bearer researcher-token" }),
    }));
    await getTelemetryEvents("session/one", { afterId: 0, limit: 20, eventType: "action.rejected" });
    const path = fetch.mock.calls.at(-1)![0] as string;
    expect(path).toContain("after_id=0");
    expect(path).toContain("limit=20");
    expect(path).toContain("event_type=action.rejected");
  });

  it.each(["json", "jsonl"] as const)("downloads %s with the bearer token and cleans up the browser URL", async (format) => {
    localStorage.setItem("arena-token", "private-token");
    const fetch = vi.spyOn(globalThis, "fetch").mockImplementation(async () => new Response("{}"));
    const create = vi.fn().mockReturnValue("blob:telemetry");
    const revoke = vi.fn();
    const createDescriptor = Object.getOwnPropertyDescriptor(URL, "createObjectURL");
    const revokeDescriptor = Object.getOwnPropertyDescriptor(URL, "revokeObjectURL");
    Object.defineProperty(URL, "createObjectURL", { value: create, configurable: true });
    Object.defineProperty(URL, "revokeObjectURL", { value: revoke, configurable: true });
    const click = vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(() => {});
    try {
      await downloadTelemetry("private-session", format);
      expect(fetch).toHaveBeenCalledWith(`/api/session/private-session/telemetry/export?format=${format}`, expect.objectContaining({
        headers: expect.objectContaining({ Authorization: "Bearer private-token" }),
      }));
      expect(click).toHaveBeenCalledOnce();
      expect(create).toHaveBeenCalledWith(expect.objectContaining({ size: 2 }));
      expect(revoke).toHaveBeenCalledWith("blob:telemetry");
      expect(document.querySelector('a[download]')).toBeNull();
    } finally {
      if (createDescriptor) Object.defineProperty(URL, "createObjectURL", createDescriptor);
      else Reflect.deleteProperty(URL, "createObjectURL");
      if (revokeDescriptor) Object.defineProperty(URL, "revokeObjectURL", revokeDescriptor);
      else Reflect.deleteProperty(URL, "revokeObjectURL");
    }
  });

  it("surfaces ownership/authorization errors instead of downloading an error response", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response('{"detail":"Not authorized"}', { status: 403 }));
    const click = vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(() => {});
    await expect(downloadTelemetry("someone-else", "json")).rejects.toEqual(new ApiError("Not authorized", 403));
    expect(click).not.toHaveBeenCalled();
  });
});
