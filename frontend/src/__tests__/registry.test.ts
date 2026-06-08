import { describe, it, expect, vi } from "vitest";

const mockGlob = vi.fn();

vi.mock("@games/**/ui/*.tsx", () => ({
  default: {},
  __esModule: true,
}));

describe("registry — parseGameSlug / parseComponentName", () => {
  function parseGameSlug(key: string): string {
    const parts = key.split("/");
    const uiIdx = parts.indexOf("ui");
    if (uiIdx === -1 || uiIdx === 0) return "";
    return parts[uiIdx - 1] ?? "";
  }

  function parseComponentName(key: string): string {
    const basename = key.split("/").pop() ?? "";
    return basename.replace(".tsx", "");
  }

  it("extracts game slug from path", () => {
    expect(parseGameSlug("/games/core/colonelblotto/ui/LiveView.tsx")).toBe("colonelblotto");
    expect(parseGameSlug("/games/core/prisonersdilemma/ui/ConfigForm.tsx")).toBe("prisonersdilemma");
  });

  it("returns empty string for invalid paths", () => {
    expect(parseGameSlug("nothing/here")).toBe("");
    expect(parseGameSlug("/ui/LiveView.tsx")).toBe("");
  });

  it("extracts component name from path", () => {
    expect(parseComponentName("/games/core/colonelblotto/ui/LiveView.tsx")).toBe("LiveView");
    expect(parseComponentName("/games/core/colonelblotto/ui/ConfigForm.tsx")).toBe("ConfigForm");
    expect(parseComponentName("/games/core/colonelblotto/ui/HistoryView.tsx")).toBe("HistoryView");
  });
});
