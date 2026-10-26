# Research telemetry

Research telemetry records what happened inside an Arena session and makes those
observations available for agent debugging and benchmark analysis. It is stored in
your Arena database; no external analytics service is required.

## View a session

Open **History**, open the session actions menu, and select **Research telemetry**
for a completed or failed session. The report contains:

- Outcomes and completed rounds alongside observed accepted actions, rejections,
  and forfeits.
- A player comparison with normalized action distributions, consecutive-action
  repetition, and mean server action-processing time.
- Pattern findings with their evidence and thresholds.
- A filterable, cursor-paginated event trace.
- Downloads of the report as JSON or the report plus event trail as JSON Lines.

The trace is private to the session owner, even when a session contributes to the
public leaderboard. A platform API key or user access token authenticates research
requests. Player session keys grant game participation, not access to the research
report. Reports become available after completion or failure to avoid exposing
hidden simultaneous actions during a running game. Matchmaking participants who
do not own the session cannot currently retrieve its full trace.

## What is recorded

The version 1 event envelope has these fields:

| Field | Meaning |
| --- | --- |
| `id` | Database-generated, monotonically allocated event ID; gaps are normal |
| `schema_version` | Event schema version, currently `1` |
| `session_id` | Session the event belongs to |
| `event_type` | One of the types below |
| `occurred_at` | UTC timestamp captured by the server |
| `player_id`, `agent_id` | Player role and configured agent identifier, when applicable |
| `round_number` | Associated round or hand, when applicable |
| `payload` | Type-specific, allowlisted data |

| Event type | Payload |
| --- | --- |
| `session.created` | Arena version, config hash, game type, seed, player roles |
| `action.accepted` | Normalized action, explicit forfeit flag, `server_apply_ms` |
| `action.rejected` | Error class, rejection category, forfeit flag, server processing time |
| `round.completed` | Allowlisted resolved game record, including actions and payoffs where supported |
| `session.completed` | Final scores, game-reported winner, number of resolved rounds |
| `session.failed` | Error class/category, without the raw error message |

Accepted actions and terminal state changes are persisted in the same database
transaction as their events. Submissions lock their session row so simultaneous
players cannot overwrite one another's state or trace. Rejected submissions by a
validated player commit their rejection observation without changing game state.
Authentication failures are not included in behavioral measurements.

REST, MCP (which submits through REST), and interactive actions share the same
capture layer. Explicit failures are saved synchronously before acknowledgement.
New-session creation also captures sessions started by matchmaking.

Events are append-only through the application model. Deleting a session or
account cascades to its events. No database trigger prevents administrators from
updating rows directly.

## Interpret the measurements

`server_apply_ms` measures only application of an action inside the server's
game engine. It excludes model inference, provider calls, network time, and waiting
for the database lock. Do not use it as a measure of model reasoning speed.

Repetition is the fraction of consecutive recorded, non-forfeit action pairs that
are identical, calculated separately for each player. The default repeated-action
finding needs at least five actions and a repetition rate of at least 0.8.
Repetition can be a deliberate strategy; the finding is an observation, not a
quality judgment.

Rejection and forfeit findings identify observed behavior and point to the event
trace. They do not assign causes to provider failures or infer intent. Existing
game-specific metrics remain available from the results API and complement these
observations.

### Coverage and historical sessions

Old sessions have no event trail to backfill. They still show saved scores,
resolved history, configuration identity, and agent identifiers. Unobserved
action, rejection, and forfeit counts are `null`, not zero. Historical Arena
versions are also unknown unless a creation event recorded the version.

A session started before this feature and finished afterward may have partial
telemetry. `coverage.complete` is true only when both creation and terminal events
are present; the report warns when coverage is incomplete. Counts always describe
recorded events.

`coverage.history_entries` counts raw history entries, while
`coverage.history_rounds` counts resolved entries marked with `total_scores`.
This distinction matters for Centipede steps and Public Goods punishment phases.
The same completion marker is used for `summary.rounds_completed`; an unfinished
round is not counted as completed.

### Normalization and provenance

Capture permits known categorical actions, finite numeric actions and allocations,
and reviewed structured-action fields. Unknown free-text action values are
omitted. Battle of the Sexes labels become stable `option_a`/`option_b` values.
Custom games should extend the reviewed allowlist when they introduce new action
semantics.

Raw provider responses, prompts, reasoning, authentication credentials, unrevealed
cards, live private values, and mailbox text are not copied into telemetry. Resolved
auction valuations can be included once they are part of a finalized round record. Rejection events
omit rejected input and raw errors. Exported configuration includes reviewed game
parameters rather than private runtime options.

The config hash identifies the original full configuration, but the sanitized
manifest is not sufficient to reconstruct custom prompts or arbitrary labels.
Researchers should retain their original experiment specification privately.
Agent identifiers are the submitted labels, not independently verified model
identities. This foundation does not yet record provider token usage, inference
latency, per-request cost, prompt contents, or training-time internals.

## REST API

All paths below use the default `/api` prefix.

| Request | Result |
| --- | --- |
| `GET /session/{id}/telemetry` | Versioned research report |
| `GET /session/{id}/telemetry/events?after_id=0&limit=100` | Event page |
| `GET /session/{id}/telemetry/events?event_type=action.rejected` | Filtered event page |
| `GET /session/{id}/telemetry/export?format=json` | Download report |
| `GET /session/{id}/telemetry/export?format=jsonl` | Stream manifest and events |

The event page contains `events` and `next_after_id`. Follow a non-null cursor
using the same filter; null means there are no more events. Page limits are
between 1 and 500. Unknown event filters and invalid query bounds return 422.
Active sessions return 409. Sessions not owned by the requester return 404.
Responses use `Cache-Control: no-store`.

JSONL begins with a `record_type: "manifest"` record containing the report and
`through_event_id`; subsequent records have `record_type: "event"`. The export
fixes its maximum event ID before reading. Events are read in chunks of 500, so
the export never assembles the full trace in memory. Report aggregation retains
per-player counts and distinct normalized actions; memory therefore grows with
the number of distinct actions.

```bash
curl -H "Authorization: Bearer $ARENA_OWNER_KEY" \
  "$ARENA_BASE_URL/api/session/$SESSION_ID/telemetry"

curl -H "Authorization: Bearer $ARENA_OWNER_KEY" \
  "$ARENA_BASE_URL/api/session/$SESSION_ID/telemetry/export?format=jsonl" \
  -o telemetry.jsonl
```

## Python SDK

Use the session owner's credential explicitly, separate from a player's key:

```python
import os
from outplayarena_sdk.client import ArenaClient

client = ArenaClient("http://localhost:8000/api", session_id=session_id)
owner_key = os.environ["ARENA_OWNER_KEY"]

report = client.get_telemetry(api_key=owner_key)
for event in client.iter_telemetry_events(
    api_key=owner_key, event_type="action.rejected", page_size=200
):
    print(event["player_id"], event["payload"])
```

## Extend research patterns

Capture, storage, analysis, and presentation are separate modules:

- `arena.telemetry.capture` owns versioned event and action allowlists.
- `TelemetryEvent` and its Alembic migration own durable storage.
- `ResearchReportBuilder` aggregates ordered events.
- Pattern detectors consume a sanitized report and return evidence-backed findings.
- `arena.telemetry.api` owns access control, pagination, and export.

A detector is a callable returning findings with `code`, `severity`, `title`,
`detail`, and `evidence`, plus optional `player_id`. Pass a detector tuple to
`build_report` or `ResearchReportBuilder.finish` for analysis code. Add a reviewed
detector to `DEFAULT_DETECTORS` to expose it in the application.

```python
from arena.telemetry.report import DEFAULT_DETECTORS, build_report

def frequent_rejections(report):
    for player in report["players"]:
        rejected = player["rejected_actions"]
        if rejected is not None and rejected >= 3:
            yield {
                "code": "research.frequent_rejections",
                "severity": "warning",
                "title": "Repeated submission failures",
                "detail": "Review recorded rejection categories before comparing scores.",
                "player_id": player["player_id"],
                "evidence": {"rejected_actions": rejected, "threshold": 3},
            }

report = build_report(
    session_row, ordered_events,
    detectors=(*DEFAULT_DETECTORS, frequent_rejections),
)
```

Custom games should store `total_scores` on finalized history records and expose
their terminal winner through `compute_results`. If an event schema gains new
fields or event types, update capture, database constraints/migration, report
sanitization, frontend types, and compatibility tests together.

## Deployment and verification

The application applies the new Alembic migration on startup, creating
`telemetry_events` with a session/cursor index and cascading session foreign key.
No external telemetry service or new runtime configuration is required.

Run the usual backend/SDK tests and frontend checks. The PostgreSQL transaction
tests are opt-in and create/drop only their own randomly named schemas:

```bash
TELEMETRY_TEST_DATABASE_URL=postgresql+asyncpg://user:pass@localhost/arena_test \
  uv run pytest backend/tests/test_telemetry_postgres.py
```

The backend CI job enables these tests against its existing test database.
The test database user needs permission to create schemas. These tests verify
concurrent submissions, rollback of state and events together, rejection
persistence, interactive/failure paths, streamed export, and deletion cascades.
