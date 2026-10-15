import { useEffect, useRef, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { LoadingSpinner } from "../components/LoadingSpinner";
import { inputClass } from "../components/formStyles";
import { statusBadge } from "../components/badges";
import { gameName, useGameNames } from "../hooks/useGameNames";
import {
  downloadTelemetry,
  getTelemetryEvents,
  getTelemetryReport,
  TELEMETRY_EVENT_TYPES,
  type TelemetryEvents,
  type TelemetryReport,
} from "../telemetry";

const panel = "rounded-[var(--radius-card)] border border-line bg-surface";
const button = "inline-flex items-center justify-center rounded-[var(--radius-button)] border border-line px-3 py-2 text-xs font-medium text-ink hover:bg-surface-soft focus-visible:outline-2 focus-visible:outline-accent disabled:opacity-50 disabled:cursor-not-allowed";
const errorMessage = (error: unknown) => error instanceof Error ? error.message : "Unable to load telemetry.";
const percentage = (value: number | null) => value == null ? "Not recorded" : `${(value * 100).toFixed(1)}%`;

function JsonDetails({ label, value }: { label: string; value: unknown }) {
  return (
    <details className="mt-3">
      <summary className="cursor-pointer text-xs font-medium text-accent focus-visible:outline-2 focus-visible:outline-accent">{label}</summary>
      <pre className="mt-2 max-h-80 overflow-auto rounded-[var(--radius-input)] bg-surface-soft p-3 text-[11px] font-mono text-muted whitespace-pre-wrap break-all">{JSON.stringify(value, null, 2)}</pre>
    </details>
  );
}

function Metric({ label, value }: { label: string; value: number | string | null }) {
  return (
    <div className={`${panel} p-4`}>
      <dt className="text-xs text-muted">{label}</dt>
      <dd className="mt-1 text-xl font-semibold text-ink tabular-nums">{value ?? "Not recorded"}</dd>
    </div>
  );
}

function EventTimeline({ sessionId, eventType }: { sessionId: string; eventType: string }) {
  const [page, setPage] = useState<TelemetryEvents | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const controller = useRef<AbortController | null>(null);

  useEffect(() => {
    const abort = new AbortController();
    controller.current = abort;
    getTelemetryEvents(sessionId, { eventType, signal: abort.signal })
      .then((result) => { if (!abort.signal.aborted) setPage(result); })
      .catch((reason: unknown) => { if (!abort.signal.aborted) setError(errorMessage(reason)); })
      .finally(() => { if (!abort.signal.aborted) setLoading(false); });
    return () => { abort.abort(); controller.current?.abort(); };
  }, [sessionId, eventType]);

  async function loadMore() {
    if (loading) return;
    const abort = new AbortController();
    controller.current = abort;
    setLoading(true);
    setError(null);
    try {
      const next = await getTelemetryEvents(sessionId, {
        eventType,
        afterId: page?.next_after_id ?? undefined,
        signal: abort.signal,
      });
      if (!abort.signal.aborted) {
        setPage((previous) => ({
          ...next,
          events: [...(previous?.events ?? []), ...next.events],
        }));
      }
    } catch (reason) {
      if (!abort.signal.aborted) setError(errorMessage(reason));
    } finally {
      if (!abort.signal.aborted) setLoading(false);
    }
  }

  return (
    <div aria-busy={loading}>
      {loading && !page && <p role="status" className="py-6 text-sm text-muted">Loading events...</p>}
      {error && <p role="alert" className="my-3 text-sm text-danger">{error}</p>}
      {page?.events.length === 0 && <p className="py-6 text-sm text-muted">{eventType ? "No recorded events match this filter." : "No events were recorded for this session."}</p>}
      {page && page.events.length > 0 && (
        <>
          <p className="my-3 text-xs text-muted" aria-live="polite">Showing {page.events.length} events in recorded order.</p>
          <ol className="divide-y divide-line">
            {page.events.map((event) => (
              <li key={event.id} className="py-4">
                <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-xs">
                  <span className="font-mono text-muted">#{event.id}</span>
                  <span className="font-medium text-ink">{event.event_type}</span>
                  {event.round_number != null && <span className="text-muted">Round {event.round_number}</span>}
                  {event.player_id && <span className="text-muted">Player {event.player_id}</span>}
                  {event.agent_id && <span className="text-muted break-all">{event.agent_id}</span>}
                  <time dateTime={event.occurred_at} className="text-muted">{event.occurred_at}</time>
                </div>
                <JsonDetails label={`Event #${event.id} details`} value={event.payload} />
              </li>
            ))}
          </ol>
        </>
      )}
      {(page?.next_after_id != null || error) && (
        <button type="button" className={`${button} mt-4`} disabled={loading} onClick={() => void loadMore()}>
          {loading ? "Loading events..." : error ? "Retry events" : "Load more events"}
        </button>
      )}
    </div>
  );
}

function SessionTelemetry({ sessionId }: { sessionId: string }) {
  const [report, setReport] = useState<TelemetryReport | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [attempt, setAttempt] = useState(0);
  const [eventType, setEventType] = useState("");
  const [exporting, setExporting] = useState<"json" | "jsonl" | null>(null);
  const [exportError, setExportError] = useState<string | null>(null);
  const downloadController = useRef<AbortController | null>(null);
  const games = useGameNames();

  useEffect(() => {
    const abort = new AbortController();
    getTelemetryReport(sessionId, abort.signal)
      .then((value) => { if (!abort.signal.aborted) setReport(value); })
      .catch((reason: unknown) => { if (!abort.signal.aborted) setError(errorMessage(reason)); });
    return () => { abort.abort(); };
  }, [sessionId, attempt]);

  useEffect(() => () => { downloadController.current?.abort(); }, []);

  async function exportData(format: "json" | "jsonl") {
    const abort = new AbortController();
    downloadController.current = abort;
    setExporting(format);
    setExportError(null);
    try {
      await downloadTelemetry(sessionId, format, abort.signal);
    } catch (reason) {
      if (!abort.signal.aborted) setExportError(errorMessage(reason));
    } finally {
      if (!abort.signal.aborted) setExporting(null);
    }
  }

  if (error) {
    return (
      <div className={`${panel} p-6`}>
        <h1 className="text-xl font-semibold text-ink">Research telemetry unavailable</h1>
        <p role="alert" className="mt-3 text-sm text-muted">{error}</p>
        <button type="button" className={`${button} mt-4`} onClick={() => { setError(null); setAttempt((value) => value + 1); }}>Retry report</button>
      </div>
    );
  }

  if (!report) {
    return <div role="status" className="py-16 text-center"><LoadingSpinner /><p className="mt-3 text-sm text-muted">Loading research telemetry...</p></div>;
  }

  return (
    <>
      <header className="mb-6 flex flex-wrap items-start justify-between gap-4">
        <div>
          <div className="flex flex-wrap items-center gap-3">
            <h1 className="text-2xl font-bold text-ink tracking-tight">Research telemetry</h1>
            {statusBadge(report.status)}
          </div>
          <p className="mt-2 text-sm text-muted">{gameName(report.game, games)} <span aria-hidden="true">/</span> <span className="font-mono break-all">{report.session_id}</span></p>
          <Link to={`/play/${report.game}/${encodeURIComponent(sessionId)}`} className="mt-2 inline-block text-xs text-accent hover:underline">View session replay</Link>
        </div>
        <div className="flex gap-2">
          {(["json", "jsonl"] as const).map((format) => (
            <button type="button" key={format} className={button} disabled={exporting != null} onClick={() => void exportData(format)}>
              {exporting === format ? "Exporting..." : `Export ${format.toUpperCase()}`}
            </button>
          ))}
        </div>
      </header>

      {exportError && <p role="alert" className="mb-4 text-sm text-danger">{exportError}</p>}
      {report.coverage.legacy && (
        <div className={`${panel} mb-6 border-warning/40 bg-warning/5 p-4`}>
          <h2 className="text-sm font-semibold text-ink">Historical session: limited telemetry</h2>
          <p className="mt-1 text-sm text-muted">This session predates event recording. Round results are derived from saved game history. Rejections, timing, and other unrecorded behavior cannot be inferred.</p>
        </div>
      )}

      {!report.coverage.legacy && !report.coverage.complete && (
        <div className={`${panel} mb-6 border-warning/40 bg-warning/5 p-4`}>
          <h2 className="text-sm font-semibold text-ink">Partial event coverage</h2>
          <p className="mt-1 text-sm text-muted">Some lifecycle events are missing. Counts and detected patterns reflect only the recorded portion, so compare them with the saved round history.</p>
        </div>
      )}

      <section aria-labelledby="overview-heading" className="mb-8">
        <h2 id="overview-heading" className="mb-3 text-sm font-semibold text-ink">Session overview</h2>
        <dl className="grid grid-cols-2 gap-3 lg:grid-cols-5">
          <Metric label="Rounds completed" value={report.summary.rounds_completed} />
          <Metric label="Accepted actions" value={report.summary.action_count} />
          <Metric label="Rejected actions" value={report.summary.rejected_actions} />
          <Metric label="Forfeits" value={report.summary.forfeits} />
          <Metric label="Winner" value={report.summary.winner ? (report.players.some((player) => player.player_id === report.summary.winner) ? `Player ${report.summary.winner}` : report.summary.winner) : "Not recorded"} />
        </dl>
        <p className="mt-3 text-xs text-muted">Coverage: {report.coverage.event_count} events, {report.coverage.recorded_actions} recorded actions, {report.coverage.history_rounds} finalized history rounds{report.coverage.history_entries !== report.coverage.history_rounds ? ` (${report.coverage.history_entries} history entries)` : ""}. Missing measurements are shown as not recorded.</p>
      </section>

      <section aria-labelledby="players-heading" className="mb-8">
        <h2 id="players-heading" className="mb-3 text-sm font-semibold text-ink">Player comparison</h2>
        <p className="mb-3 text-xs text-muted">Repeated action rate measures consecutive identical accepted actions, excluding forfeits. Apply latency measures server action processing, excluding model inference and network time.</p>
        <div className={`${panel} overflow-x-auto`}>
          <table className="w-full text-left text-xs">
            <caption className="sr-only">Scores and recorded behavior by player</caption>
            <thead className="bg-surface-soft text-muted">
              <tr>{["Player / agent", "Score", "Accepted", "Rejected", "Forfeits", "Repeated actions", "Mean apply latency"].map((label) => <th scope="col" key={label} className="px-4 py-3 font-medium whitespace-nowrap">{label}</th>)}</tr>
            </thead>
            <tbody className="divide-y divide-line">
              {report.players.map((player) => (
                <tr key={player.player_id} className="text-ink">
                  <th scope="row" className="px-4 py-3 font-medium"><span>Player {player.player_id}</span><span className="mt-1 block text-muted font-normal break-all">{player.agent_id ?? "Unknown agent"}</span></th>
                  <td className="px-4 py-3 tabular-nums">{player.score ?? "Not recorded"}</td>
                  <td className="px-4 py-3 tabular-nums">{player.accepted_actions ?? "Not recorded"}</td>
                  <td className="px-4 py-3 tabular-nums">{report.coverage.legacy ? "Not recorded" : player.rejected_actions ?? "Not recorded"}</td>
                  <td className="px-4 py-3 tabular-nums">{report.coverage.legacy ? "Not recorded" : player.forfeits ?? "Not recorded"}</td>
                  <td className="px-4 py-3 tabular-nums">{percentage(player.repeated_action_rate)}</td>
                  <td className="px-4 py-3 tabular-nums whitespace-nowrap">{player.mean_apply_latency_ms == null ? "Not recorded" : `${player.mean_apply_latency_ms.toFixed(2)} ms`}</td>
                </tr>
              ))}
            </tbody>
          </table>
          {report.players.length === 0 && <p className="p-4 text-sm text-muted">No player measurements available.</p>}
        </div>
        <div className="mt-3 grid gap-3 md:grid-cols-2">
          {report.players.map((player) => {
            const total = player.action_distribution.reduce((sum, item) => sum + item.count, 0);
            return (
              <div key={player.player_id} className={`${panel} p-4`}>
                <h3 className="text-xs font-medium text-ink">Player {player.player_id}: action distribution</h3>
                <p className="mt-1 text-xs text-muted">Exact recorded actions, by frequency.</p>
                {player.action_distribution.length === 0 ? <p className="mt-3 text-xs text-muted">No accepted actions recorded.</p> : (
                  <ul className="mt-3 max-h-60 space-y-3 overflow-auto">
                    {[...player.action_distribution].sort((a, b) => b.count - a.count || a.action.localeCompare(b.action)).map((item) => (
                      <li key={item.action}>
                        <div className="mb-1 flex justify-between gap-3 text-xs"><code className="break-all text-muted">{item.action}</code><span className="shrink-0 text-ink tabular-nums">{item.count} ({total ? (100 * item.count / total).toFixed(1) : "0.0"}%)</span></div>
                        <div aria-hidden="true" className="h-1.5 rounded-full bg-surface-container"><div className="h-full rounded-full bg-accent" style={{ width: `${total ? 100 * item.count / total : 0}%` }} /></div>
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            );
          })}
        </div>
      </section>

      <section aria-labelledby="patterns-heading" className="mb-8">
        <h2 id="patterns-heading" className="mb-2 text-sm font-semibold text-ink">Patterns to investigate</h2>
        <p className="mb-3 text-xs text-muted">Descriptive signals from this session. Review the evidence and compare controlled runs before drawing conclusions about agent quality.</p>
        {report.patterns.length === 0 ? <p className={`${panel} p-4 text-sm text-muted`}>No configured patterns were detected in the available data.</p> : (
          <ul className="space-y-3">
            {report.patterns.map((pattern, index) => (
              <li key={`${pattern.code}-${pattern.player_id ?? "session"}-${index}`} className={`${panel} p-4`}>
                <div className="flex flex-wrap items-center gap-2">
                  <h3 className="text-sm font-medium text-ink">{pattern.title}</h3>
                  <span className="rounded-[var(--radius-chip)] bg-surface-soft px-2 py-0.5 text-[10px] font-mono text-muted">{pattern.severity}</span>
                  {pattern.player_id && <span className="text-xs text-muted">Player {pattern.player_id}</span>}
                </div>
                <p className="mt-2 text-sm text-muted">{pattern.detail}</p>
                <p className="mt-2 text-[10px] font-mono text-muted">{pattern.code}</p>
                <JsonDetails label="View pattern evidence" value={pattern.evidence} />
              </li>
            ))}
          </ul>
        )}
      </section>

      <section aria-labelledby="provenance-heading" className={`${panel} mb-8 p-4`}>
        <h2 id="provenance-heading" className="text-sm font-semibold text-ink">Reproducibility</h2>
        <p className="mt-1 text-xs text-muted">Saved game parameters and agent IDs. Prompts, custom text labels, and private runtime settings are excluded; retain the original configuration for exact reproduction.</p>
        <dl className="mt-3 grid gap-3 text-xs sm:grid-cols-3">
          <div><dt className="text-muted">Arena version</dt><dd className="mt-1 font-mono text-ink">{report.provenance.arena_version ?? "Not recorded"}</dd></div>
          <div><dt className="text-muted">Seed</dt><dd className="mt-1 font-mono text-ink">{report.provenance.seed ?? "Not recorded"}</dd></div>
          <div><dt className="text-muted">Configuration hash</dt><dd className="mt-1 break-all font-mono text-ink">{report.provenance.config_hash ?? "Not recorded"}</dd></div>
        </dl>
        <JsonDetails label="View configuration and agents" value={{ config: report.provenance.config, agents: report.provenance.agents, schema_version: report.schema_version }} />
      </section>

      <section aria-labelledby="events-heading" className={`${panel} p-4 sm:p-5`}>
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div><h2 id="events-heading" className="text-sm font-semibold text-ink">Event timeline</h2><p className="mt-1 text-xs text-muted">Recorded lifecycle, decisions, and round outcomes.</p></div>
          <div className="flex items-center gap-2">
            <label htmlFor="event-type" className="text-xs text-muted">Event type</label>
            <select id="event-type" className={`${inputClass} w-auto`} value={eventType} onChange={(event) => setEventType(event.target.value)}>
              <option value="">All events</option>
              {TELEMETRY_EVENT_TYPES.map((type) => <option key={type} value={type}>{type}</option>)}
            </select>
          </div>
        </div>
        <EventTimeline key={eventType} sessionId={sessionId} eventType={eventType} />
      </section>
      <p className="mt-3 text-xs text-muted">JSON includes the research report. JSONL includes a manifest and the recorded event stream for notebook and pipeline analysis.</p>
    </>
  );
}

export function TelemetryPage() {
  const { sessionId } = useParams<{ sessionId: string }>();
  return (
    <div className="mx-auto w-full max-w-6xl px-6 py-10">
      <Link to="/history" className="mb-6 inline-block text-xs text-muted hover:text-ink">Back to history</Link>
      {sessionId ? <SessionTelemetry key={sessionId} sessionId={sessionId} /> : <p role="alert" className="text-sm text-muted">A session ID is required to view telemetry.</p>}
    </div>
  );
}
