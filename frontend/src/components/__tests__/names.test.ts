import { describe, it, expect, vi, beforeEach } from "vitest";
import { randomAgentName } from "../names";

describe("randomAgentName", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it("returns a string in the format adjective-noun", () => {
    const name = randomAgentName();
    expect(name).toMatch(/^[a-z]+-[a-z]+$/);
  });

  it("does not contain spaces", () => {
    const name = randomAgentName();
    expect(name).not.toContain(" ");
  });

  it("returns different names on multiple calls (probabilistic)", () => {
    const names = new Set(Array.from({ length: 10 }, () => randomAgentName()));
    expect(names.size).toBeGreaterThan(1);
  });

  it("always produces two parts separated by hyphen", () => {
    for (let i = 0; i < 20; i++) {
      const parts = randomAgentName().split("-");
      expect(parts).toHaveLength(2);
      expect(parts[0].length).toBeGreaterThan(0);
      expect(parts[1].length).toBeGreaterThan(0);
    }
  });
});
