import { describe, it, expect } from "vitest";
import { screen } from "@testing-library/react";
import { renderWithProviders } from "../test-utils";
import { GameTimeline } from "./GameTimeline";
import type { MailboxMessage, MatchRound } from "../types";

function makeRound(overrides: Partial<MatchRound> = {}): MatchRound {
  return {
    round: 1,
    agent_a: "a",
    agent_b: "b",
    action_a: [1, 2, 3],
    action_b: [3, 2, 1],
    score_a: 1,
    score_b: 0,
    total_score_a: 1,
    total_score_b: 0,
    winner: "A",
    ...overrides,
  };
}

function makeMessage(overrides: Partial<MailboxMessage> = {}): MailboxMessage {
  return {
    id: "msg-1",
    sender: "A",
    recipient: "all",
    content: "hello",
    round: 1,
    ...overrides,
  };
}

describe("GameTimeline", () => {
  it("renders nothing when there is no history and no messages", () => {
    const { container } = renderWithProviders(<GameTimeline history={[]} messages={[]} />);
    expect(container.firstChild).toBeNull();
  });

  it("interleaves messages with their round in ascending chronological order", () => {
    const history = [makeRound({ round: 1 }), makeRound({ round: 2, winner: "B" })];
    const messages = [
      makeMessage({ id: "m1", round: 1, content: "round one chat" }),
      makeMessage({ id: "m2", round: 2, content: "round two chat" }),
    ];
    renderWithProviders(<GameTimeline history={history} messages={messages} agentA="a" agentB="b" />);

    const order = screen
      .getAllByText(/round one chat|round two chat|R1|R2/)
      .map((el) => el.textContent);

    expect(screen.getByText("round one chat")).toBeInTheDocument();
    expect(screen.getByText("round two chat")).toBeInTheDocument();
    expect(screen.getByText("R1")).toBeInTheDocument();
    expect(screen.getByText("R2")).toBeInTheDocument();

    // The round 1 chat message must appear before the round 2 chat message.
    const chatIdx1 = order.indexOf("round one chat");
    const chatIdx2 = order.indexOf("round two chat");
    expect(chatIdx1).toBeLessThan(chatIdx2);
  });

  it("renders a message missing created_at/turn_phase without crashing and without a badge", () => {
    const history = [makeRound({ round: 1 })];
    const messages = [makeMessage({ round: 1, content: "legacy message" })];
    expect(() =>
      renderWithProviders(<GameTimeline history={history} messages={messages} />),
    ).not.toThrow();

    expect(screen.getByText("legacy message")).toBeInTheDocument();
    expect(screen.queryByText(/before .* move/)).not.toBeInTheDocument();
    expect(screen.queryByText(/after .* move/)).not.toBeInTheDocument();
  });

  it("shows the correct before/after badge text for a known turn_phase", () => {
    const history = [makeRound({ round: 1 })];
    const beforeMsg = makeMessage({
      id: "before-msg",
      round: 1,
      sender: "A",
      turn_phase: "before",
      created_at: "2026-07-02T12:00:00Z",
      content: "acting soon",
    });
    const afterMsg = makeMessage({
      id: "after-msg",
      round: 1,
      sender: "B",
      turn_phase: "after",
      created_at: "2026-07-02T12:01:00Z",
      content: "already moved",
    });
    renderWithProviders(<GameTimeline history={history} messages={[beforeMsg, afterMsg]} />);

    expect(screen.getByText("before A's move")).toBeInTheDocument();
    expect(screen.getByText("after B's move")).toBeInTheDocument();
  });
});
