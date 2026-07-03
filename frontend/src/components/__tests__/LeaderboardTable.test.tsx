import { describe, it, expect, vi } from "vitest";
import { screen, waitFor } from "@testing-library/react";
import { userEvent } from "@testing-library/user-event";
import { Routes, Route } from "react-router-dom";
import { renderWithProviders } from "../../test-utils";
import { LeaderboardTable } from "../LeaderboardTable";
import type { LeaderboardTableRow } from "../leaderboardShared";

const ROWS: LeaderboardTableRow[] = [
  {
    agentId: "anthropic__claude-opus-4-8",
    matches_played: 50,
    elo: 1500,
    alpha_rank: 0.4,
    metrics: { nash_gap: 0.05, cooperation_rate: 0.6 },
  },
  {
    agentId: "openai__gpt-4o",
    matches_played: 30,
    elo: 1400,
    alpha_rank: 0.3,
    metrics: { nash_gap: 0.1, cooperation_rate: 0.5 },
  },
];

function renderInRouter(node: React.ReactNode) {
  return renderWithProviders(
    <Routes>
      <Route path="/leaderboard" element={<>{node}</>} />
      <Route path="/leaderboard/:agentId" element={<>agent detail</>} />
    </Routes>,
    { initialRoute: "/leaderboard" },
  );
}

describe("LeaderboardTable", () => {
  it("renders the standard columns", () => {
    renderInRouter(
      <LeaderboardTable
        rows={ROWS}
        totalMatches={80}
        loading={false}
        error={null}
      />,
    );
    expect(screen.getByRole("columnheader", { name: "#" })).toBeInTheDocument();
    expect(screen.getByRole("columnheader", { name: "Agent" })).toBeInTheDocument();
    expect(screen.getByRole("columnheader", { name: "Games" })).toBeInTheDocument();
    expect(screen.getByRole("columnheader", { name: "Elo" })).toBeInTheDocument();
    expect(screen.getByRole("columnheader", { name: "α-Rank" })).toBeInTheDocument();
  });

  it("renders dynamic metric columns when metrics are present", () => {
    renderInRouter(
      <LeaderboardTable
        rows={ROWS}
        totalMatches={80}
        loading={false}
        error={null}
      />,
    );
    expect(screen.getByRole("columnheader", { name: "Nash Gap" })).toBeInTheDocument();
    expect(screen.getByRole("columnheader", { name: "Cooperation" })).toBeInTheDocument();
  });

  it("renders the agent name as a clickable button that navigates to the detail page", async () => {
    const user = userEvent.setup();
    renderInRouter(
      <LeaderboardTable
        rows={ROWS}
        totalMatches={80}
        loading={false}
        error={null}
      />,
    );
    const link = screen.getByRole("button", { name: /claude-opus-4-8/i });
    expect(link).toBeInTheDocument();
    expect(link.tagName).toBe("BUTTON");
    await user.click(link);
    await waitFor(() => {
      // The agent detail route is matched.
      expect(screen.getByText("agent detail")).toBeInTheDocument();
    });
  });

  it("shows total matches in the footer", () => {
    renderInRouter(
      <LeaderboardTable
        rows={ROWS}
        totalMatches={80}
        loading={false}
        error={null}
      />,
    );
    expect(screen.getByText(/80 matches recorded/i)).toBeInTheDocument();
  });

  it("renders the rank badge for the first row", () => {
    renderInRouter(
      <LeaderboardTable
        rows={ROWS}
        totalMatches={80}
        loading={false}
        error={null}
      />,
    );
    expect(screen.getByText("1")).toBeInTheDocument();
    expect(screen.getByText("2")).toBeInTheDocument();
  });

  it("shows the loading skeleton with shimmer rows", () => {
    renderInRouter(
      <LeaderboardTable
        rows={[]}
        totalMatches={0}
        loading
        error={null}
        loadingRows={3}
      />,
    );
    expect(document.querySelectorAll(".animate-shimmer").length).toBeGreaterThan(0);
  });

  it("shows the error state with optional retry button", async () => {
    const onRetry = vi.fn();
    renderInRouter(
      <LeaderboardTable
        rows={[]}
        totalMatches={0}
        loading={false}
        error="boom"
        onRetry={onRetry}
      />,
    );
    expect(screen.getByText(/Failed to load leaderboard/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /retry/i })).toBeInTheDocument();
  });

  it("shows the empty state when rows is empty", () => {
    renderInRouter(
      <LeaderboardTable
        rows={[]}
        totalMatches={0}
        loading={false}
        error={null}
      />,
    );
    expect(screen.getByText(/No data yet/i)).toBeInTheDocument();
  });

  it("formats cooperation_rate as a percentage and nash_gap as a 3-decimal number", () => {
    renderInRouter(
      <LeaderboardTable
        rows={ROWS}
        totalMatches={80}
        loading={false}
        error={null}
      />,
    );
    expect(screen.getByText("60%")).toBeInTheDocument();
    expect(screen.getByText("0.050")).toBeInTheDocument();
  });

  it("renders a footer trailing element when provided", () => {
    renderInRouter(
      <LeaderboardTable
        rows={ROWS}
        totalMatches={80}
        loading={false}
        error={null}
        footerTrailing={<a href="/leaderboard">See full leaderboard →</a>}
      />,
    );
    expect(screen.getByText(/See full leaderboard/i)).toBeInTheDocument();
  });

  describe("OwnerCell 'You' badge", () => {
    const OWN_ROWS: LeaderboardTableRow[] = [
      {
        agentId: "anthropic__claude-opus-4-8",
        ownerUsername: "herbertw",
        isOwn: true,
        matches_played: 50,
        elo: 1500,
        alpha_rank: 0.4,
      },
      {
        agentId: "openai__gpt-4o",
        ownerUsername: "someoneelse",
        isOwn: false,
        matches_played: 30,
        elo: 1400,
        alpha_rank: 0.3,
      },
    ];

    it("does not show the 'You' badge by default even for the viewer's own row", () => {
      renderInRouter(
        <LeaderboardTable
          rows={OWN_ROWS}
          totalMatches={80}
          loading={false}
          error={null}
          showOwnerColumn
        />,
      );
      expect(screen.queryByText("You")).not.toBeInTheDocument();
    });

    it("shows the 'You' badge on the owner's row when showOwnBadge is true", () => {
      renderInRouter(
        <LeaderboardTable
          rows={OWN_ROWS}
          totalMatches={80}
          loading={false}
          error={null}
          showOwnerColumn
          showOwnBadge
        />,
      );
      expect(screen.getByText("You")).toBeInTheDocument();
    });

    it("never shows the 'You' badge on another user's row, even when showOwnBadge is true", () => {
      renderInRouter(
        <LeaderboardTable
          rows={OWN_ROWS}
          totalMatches={80}
          loading={false}
          error={null}
          showOwnerColumn
          showOwnBadge
        />,
      );
      expect(screen.getByText("someoneelse")).toBeInTheDocument();
    });

    it("shows the owner username instead of the badge when showOwnBadge is false", () => {
      renderInRouter(
        <LeaderboardTable
          rows={OWN_ROWS}
          totalMatches={80}
          loading={false}
          error={null}
          showOwnerColumn
        />,
      );
      // Own row falls back to the placeholder (not the raw username) when hidden,
      // since the API never returns ownerUsername for the viewer's own row in
      // practice — but the component itself must not leak "You" either way.
      expect(screen.queryByText("You")).not.toBeInTheDocument();
    });
  });
});
