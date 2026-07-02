import { describe, it, expect } from "vitest";
import { resolveAgentId } from "../playerAgentResolver";
import type { GameAgent } from "../../types";

const AGENTS: GameAgent[] = [
  { id: "uniform", label: "Uniform Distribution" },
  { id: "random", label: "Random" },
  { id: "greedy", label: "Greedy" },
  { id: "remote", label: "Remote Agent" },
  { id: "interactive", label: "Interactive (Human)" },
];

describe("resolveAgentId", () => {
  it("returns 'interactive' for an empty or null display name", () => {
    expect(resolveAgentId(null, AGENTS)).toBe("interactive");
    expect(resolveAgentId(undefined, AGENTS)).toBe("interactive");
    expect(resolveAgentId("", AGENTS)).toBe("interactive");
  });

  it("returns 'interactive' when the display name is the human sentinel 'You'", () => {
    expect(resolveAgentId("You", AGENTS)).toBe("interactive");
  });

  it("returns the agent id when the display name matches a registered id", () => {
    // Some games / callers store the id verbatim as the display name.
    expect(resolveAgentId("uniform", AGENTS)).toBe("uniform");
    expect(resolveAgentId("greedy", AGENTS)).toBe("greedy");
  });

  it("returns the registered id when the display name matches a label (case-insensitive)", () => {
    expect(resolveAgentId("Uniform Distribution", AGENTS)).toBe("uniform");
    expect(resolveAgentId("uniform distribution", AGENTS)).toBe("uniform");
    expect(resolveAgentId("RANDOM", AGENTS)).toBe("random");
  });

  it("returns 'remote' for arbitrary external LLM model names", () => {
    // The common case: user picked the "Remote Agent (LLM/MCP)"
    // dropdown and typed a custom display name.
    expect(resolveAgentId("deepseek-v4-pro", AGENTS)).toBe("remote");
    expect(resolveAgentId("glm-5.1", AGENTS)).toBe("remote");
    expect(resolveAgentId("gpt-4o-mini", AGENTS)).toBe("remote");
  });

  it("prefers an exact id match over a label match", () => {
    // Hypothetical: a game has both an id and a label that happen to
    // share the same string.  The id should win to keep round-tripping
    // deterministic.
    const agents: GameAgent[] = [
      { id: "remote", label: "Remote Agent" },
      { id: "samelabel", label: "remote" }, // label collides with another id
    ];
    expect(resolveAgentId("remote", agents)).toBe("remote");
  });
});
