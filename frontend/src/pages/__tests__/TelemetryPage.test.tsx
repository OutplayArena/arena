import { afterEach, describe, expect, it, vi } from "vitest";
import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Link, Route, Routes } from "react-router-dom";
import { http, HttpResponse } from "msw";
import { server } from "../../mocks/server";
import { renderWithProviders } from "../../test-utils";
import * as telemetry from "../../telemetry";
import type { TelemetryReport, TelemetryEvent } from "../../telemetry";
import { TelemetryPage } from "../TelemetryPage";
import { HistoryPage } from "../HistoryPage";

const REPORT: TelemetryReport = {
  schema_version: 1,
  session_id: "session-one",
  game: "rock_paper_scissors",
  status: "completed",
  provenance: { arena_version: "0.4.2", config_hash: "reproducible-hash", seed: 7, config: { rounds: 10 }, agents: { A: "baseline-one", B: "baseline-two" } },
  coverage: { event_count: 26, recorded_actions: 20, history_rounds: 10, history_entries: 10, legacy: false, action_source: "events", complete: true },
  summary: { rounds_completed: 10, action_count: 20, rejected_actions: 1, forfeits: 0, scores: { A: 8, B: 2 }, winner: "A" },
  players: [{
    player_id: "A", agent_id: "baseline-one", accepted_actions: 10, rejected_actions: 1, forfeits: 0,
    mean_apply_latency_ms: 1.25, action_distribution: [{ action: '"rock"', count: 9 }, { action: '"paper"', count: 1 }],
    repeated_action_rate: 8 / 9, score: 8,
  }, {
    player_id: "B", agent_id: "baseline-two", accepted_actions: 10, rejected_actions: 0, forfeits: 0,
    mean_apply_latency_ms: null, action_distribution: [{ action: '"scissors"', count: 10 }], repeated_action_rate: 1, score: 2,
  }],
  patterns: [{ code: "repeated_action", severity: "info", title: "Repeated actions", detail: "Player A repeated an exact action frequently.", player_id: "A", evidence: { action_count: 10, repeat_rate: 8 / 9 } }],
};

function event(id: number, type = "action.accepted"): TelemetryEvent {
  return { id, session_id: "session-one", schema_version: 1, event_type: type, occurred_at: "2026-10-15T12:00:00Z", player_id: "A", round_number: id, agent_id: "baseline-one", payload: { action: "rock", round: id } };
}

function mockReport(report: TelemetryReport = REPORT) {
  server.use(
    http.get("/api/session/:id/telemetry", () => HttpResponse.json(report)),
    http.get("/api/session/:id/telemetry/events", () => HttpResponse.json({ schema_version: 1, session_id: report.session_id, events: [], next_after_id: null })),
  );
}

function renderTelemetry() {
  return renderWithProviders(
    <>
      <Link to="/telemetry/session-two">Next session</Link>
      <Routes><Route path="/telemetry/:sessionId" element={<TelemetryPage />} /></Routes>
    </>,
    { initialRoute: "/telemetry/session-one" },
  );
}

afterEach(() => { vi.restoreAllMocks(); });

describe("TelemetryPage", () => {
  it("shows player comparisons, action frequencies, evidence and reproducibility details", async () => {
    mockReport();
    const user = userEvent.setup();
    renderTelemetry();
    expect(screen.getByRole("status")).toHaveTextContent("Loading research telemetry");
    await screen.findByRole("heading", { name: "Research telemetry", exact: true });
    const table = screen.getByRole("table");
    expect(within(table).getByText("1.25 ms")).toBeInTheDocument();
    expect(within(table).getByText("88.9%")).toBeInTheDocument();
    expect(screen.getByText("9 (90.0%)")).toBeInTheDocument();
    expect(screen.getByText("Player A repeated an exact action frequently.")).toBeInTheDocument();
    await user.click(screen.getByText("View pattern evidence"));
    expect(screen.getByText(/"action_count": 10/)).toBeVisible();
    await user.click(screen.getByText("View configuration and agents"));
    expect(screen.getByText(/"rounds": 10/)).toBeVisible();
    expect(screen.getByText("reproducible-hash")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "View session replay" })).toHaveAttribute("href", "/play/rock_paper_scissors/session-one");
    expect(screen.getByText("No events were recorded for this session.")).toBeInTheDocument();
  });

  it("marks legacy counters as missing rather than inventing measurements", async () => {
    mockReport({
      ...REPORT,
      coverage: { ...REPORT.coverage, legacy: true, complete: false, action_source: "unavailable", event_count: 0, recorded_actions: 0 },
      summary: { ...REPORT.summary, action_count: null, rejected_actions: null, forfeits: null },
      players: REPORT.players.map((player) => ({ ...player, accepted_actions: null, rejected_actions: null, forfeits: null, repeated_action_rate: null, mean_apply_latency_ms: null, action_distribution: [] })),
      patterns: [],
    });
    renderTelemetry();
    await screen.findByText("Historical session: limited telemetry");
    const table = screen.getByRole("table");
    expect(within(table).queryByText("0")).not.toBeInTheDocument();
    expect(within(table).getAllByText("Not recorded")).toHaveLength(10);
    expect(screen.getByText("No configured patterns were detected in the available data.")).toBeInTheDocument();
  });

  it("shows tied outcomes without inventing a player and sorts distributions by frequency", async () => {
    mockReport({
      ...REPORT,
      summary: { ...REPORT.summary, winner: "Tie" },
      players: [{ ...REPORT.players[0], action_distribution: [{ action: '"paper"', count: 1 }, { action: '"rock"', count: 9 }] }],
    });
    renderTelemetry();
    await screen.findByText("Tie");
    expect(screen.queryByText("Player Tie")).not.toBeInTheDocument();
    const frequencies = screen.getByText("Player A: action distribution").parentElement!;
    const items = within(frequencies).getAllByRole("listitem");
    expect(items[0]).toHaveTextContent('rock');
    expect(items[1]).toHaveTextContent('paper');
  });

  it("warns when a report has incomplete lifecycle coverage", async () => {
    mockReport({ ...REPORT, coverage: { ...REPORT.coverage, complete: false } });
    renderTelemetry();
    expect(await screen.findByText("Partial event coverage")).toBeInTheDocument();
  });

  it("appends cursor pages and resets the cursor when filtering event types", async () => {
    mockReport();
    const requests: URL[] = [];
    server.use(http.get("/api/session/:id/telemetry/events", ({ request }) => {
      const url = new URL(request.url);
      requests.push(url);
      const events = url.searchParams.get("event_type") ? [event(5, "action.rejected")] : url.searchParams.has("after_id") ? [event(2)] : [event(1)];
      return HttpResponse.json({ schema_version: 1, session_id: "session-one", events, next_after_id: events[0].id === 1 ? 1 : null });
    }));
    const user = userEvent.setup();
    renderTelemetry();
    await screen.findByText("Event #1 details");
    await user.click(screen.getByRole("button", { name: "Load more events" }));
    await screen.findByText("Event #2 details");
    expect(screen.getByText("Event #1 details")).toBeInTheDocument();
    expect(requests[1].searchParams.get("after_id")).toBe("1");
    await user.selectOptions(screen.getByLabelText("Event type"), "action.rejected");
    await screen.findByText("Event #5 details");
    expect(screen.queryByText("Event #1 details")).not.toBeInTheDocument();
    expect(requests.at(-1)!.searchParams.get("event_type")).toBe("action.rejected");
    expect(requests.at(-1)!.searchParams.has("after_id")).toBe(false);
  });

  it("preserves already loaded events and retries the same cursor after a page failure", async () => {
    mockReport();
    let failed = false;
    server.use(http.get("/api/session/:id/telemetry/events", ({ request }) => {
      const cursor = new URL(request.url).searchParams.get("after_id");
      if (cursor && !failed) { failed = true; return HttpResponse.json({ detail: "Temporary event error" }, { status: 500 }); }
      return HttpResponse.json({ schema_version: 1, session_id: "session-one", events: [event(cursor ? 2 : 1)], next_after_id: cursor ? null : 1 });
    }));
    const user = userEvent.setup();
    renderTelemetry();
    await screen.findByText("Event #1 details");
    await user.click(screen.getByRole("button", { name: "Load more events" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Temporary event error");
    expect(screen.getByText("Event #1 details")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Retry events" }));
    await screen.findByText("Event #2 details");
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });

  it("displays the active-session message and can retry the report", async () => {
    mockReport();
    let active = true;
    server.use(http.get("/api/session/:id/telemetry", () => active
      ? HttpResponse.json({ detail: "Research telemetry is available after the session completes or fails." }, { status: 409 })
      : HttpResponse.json(REPORT)));
    const user = userEvent.setup();
    renderTelemetry();
    expect(await screen.findByRole("alert")).toHaveTextContent("after the session completes or fails");
    active = false;
    await user.click(screen.getByRole("button", { name: "Retry report" }));
    expect(await screen.findByRole("heading", { name: "Research telemetry", exact: true })).toBeInTheDocument();
  });

  it("discards a stale report when navigating to another session", async () => {
    mockReport();
    let release!: (report: TelemetryReport) => void;
    const pending = new Promise<TelemetryReport>((resolve) => { release = resolve; });
    vi.spyOn(telemetry, "getTelemetryReport")
      .mockReturnValueOnce(pending)
      .mockResolvedValueOnce({ ...REPORT, session_id: "session-two" });
    const user = userEvent.setup();
    renderTelemetry();
    await user.click(screen.getByRole("link", { name: "Next session" }));
    await screen.findByText("session-two");
    release(REPORT);
    await waitFor(() => expect(screen.queryByText("session-one")).not.toBeInTheDocument());
    expect(screen.getByText("session-two")).toBeInTheDocument();
  });

  it("exports the requested format and surfaces export failures", async () => {
    mockReport();
    const download = vi.spyOn(telemetry, "downloadTelemetry")
      .mockResolvedValueOnce(undefined)
      .mockRejectedValueOnce(new Error("Export unavailable"));
    const user = userEvent.setup();
    renderTelemetry();
    await screen.findByRole("heading", { name: "Research telemetry", exact: true });
    await user.click(screen.getByRole("button", { name: "Export JSON" }));
    expect(download).toHaveBeenCalledWith("session-one", "json", expect.any(AbortSignal));
    await user.click(screen.getByRole("button", { name: "Export JSONL" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Export unavailable");
    expect(download).toHaveBeenLastCalledWith("session-one", "jsonl", expect.any(AbortSignal));
  });

  it.each(["completed", "failed"])("links a %s session from history to its research report", async (status) => {
    server.use(http.get("/api/sessions", () => HttpResponse.json({ total: 1, sessions: [{
      id: "session-one", game_slug: "rock_paper_scissors", agents: {}, agent_a: "one", agent_b: "two",
      winner: "A", total_score_a: 1, total_score_b: 0, created_at: "2026-10-15T12:00:00Z", status, locked: false, is_public: false,
    }] })));
    const user = userEvent.setup();
    renderWithProviders(<Routes><Route path="/history" element={<HistoryPage />} /><Route path="/telemetry/:sessionId" element={<p>Research report opened</p>} /></Routes>, { initialRoute: "/history" });
    await user.click(await screen.findByRole("button", { name: "Session actions" }));
    await user.click(screen.getByRole("button", { name: "Research telemetry" }));
    expect(await screen.findByText("Research report opened")).toBeInTheDocument();
  });
});
