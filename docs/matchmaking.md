# feat: matchmaking lobby + invite links

Implements cross-user matchmaking. A user can host a game with one (or more) opponent slots deliberately left open, start their own LLM agent, and wait in the lobby. Other authenticated users discover the match either via a public lobby or an invite link, claim an open slot, and start their own agent. The game auto-starts once all open slots are filled.

Closes the problem described in the companion issue: a user can only ever play against agents they coordinate with out-of-band today. This PR adds the missing discover + join surface while keeping the existing single-user flows intact.

## Scope

**In scope**

- A `public` visibility mode for sessions with one or more `open_slots`.
- A public **Lobby** page listing open matches (filterable by game).
- **Invite links**: a short opaque `invite_code` is generated for public matches; a landing page at `/lobby/invite/{code}` lets an authenticated user claim a slot.
- 2-player and N-player games both supported: the match starts only when every open slot is filled.
- Remote LLM agents only (the existing "remote" agent type). Built-in and interactive agents are explicitly out of scope for matchmaking.
- **No spectators**: state/observation/summary/results endpoints are hardened so only `participant_user_ids` members (or holders of a valid `nks_` token) can read them.
- Local-mode (no OAuth) is detected and the lobby/toggle/join endpoints are disabled with a clear message.
- Agent SDK gets `create_open_match`, `join_match`, `list_open_matches`, `get_match`, and a `wait_for_opponent()` helper.
- A race-safe join path (atomic update) so two simultaneous Join clicks produce exactly one winner.
- Auto-expiry of stale open matches (default 24h, configurable).

**Out of scope**

- Built-in / interactive agents in matchmaking.
- Skill-based matchmaking / Elo pairing.
- Spectators / read-only observers.
- Tournament / round-robin.

## Approach

### Data model

New Alembic migration. Defaults keep all existing rows compatible.

`backend/arena/models/session.py:11-30` — extend `SessionModel`:

| Column | Type | Default | Meaning |
|---|---|---|---|
| `visibility` | `String(16)` | `"private"` | `"private"` (existing) or `"public"` (matchmaking) |
| `open_slots` | `JSONB` (list of `str`) | `[]` | Player IDs still waiting for an opponent, e.g. `["B"]` or `["B","C"]` |
| `invite_code` | `String(16) UNIQUE NULL` | `NULL` | Short opaque code for invite links |
| `participant_user_ids` | `JSONB` (list of `str` UUIDs) | `[]` | All users in the session: host first, then joiners in fill order |
| `slot_owners` | `JSONB` (map `player_id -> user_id`) | `{}` | Which user controls which slot, for results attribution |

`SessionModel.user_id` remains the host/creator. `participant_user_ids` is the new authoritative "is this user in the match" set for history queries.

### Backend endpoints

**`POST /api/experiment`** (`main.py:431-480`) — extended:
- New request fields: `visibility: "private"|"public"`, `open_slots: [str]`, `invite_code: str (optional)`.
- Server-side validations: at least one slot is filled (the host's own); `open_slots` references real player IDs from the game config; `visibility="public"` requires `open_slots` non-empty; generate a fresh 10-char `invite_code` if absent and `visibility="public"`.
- The `nks_` token is only generated for slots filled at creation. Open slots get their token when filled.
- `save_new` sets the new columns.

**`GET /api/lobby/matches`** (new) — `main.py` near the catalog endpoints (around line 354):
- Query params: `game: str | None`, `limit: int = 50`, `offset: int = 0`.
- Returns: `[{session_id, game_slug, invite_code, host_display_name, host_agent_name, num_open_slots, total_slots, game_config_summary, created_at}]`.
- Filter: `visibility="public"`, `open_slots != []`, `status="ready"`, `created_at` within the last N hours.
- **Auth required** (logged in). Returns 404 in single-user local mode.

**`GET /api/lobby/matches/{invite_code}`** (new) — same as above but for one match.

**`POST /api/sessions/{id}/join`** (new) — `main.py` near `DELETE /api/sessions/{id}` (line 1010):
- Auth: `require_user`; reject if `user.id == session.user_id`.
- Accepts either a `session_id` or `invite_code` in the URL.
- Body: `{agent_id, agent_name, agent_config?}` describing the joiner's remote LLM agent.
- Atomic operation (`UPDATE ... WHERE open_slots != '[]'`): pops the first player ID from `open_slots`, appends `str(user.id)` to `participant_user_ids`, sets `slot_owners[player_id] = str(user.id)`, updates `agents_json[player_id]`, generates a new `nks_` key, and — if `open_slots` is now empty — sets `status = "running"`.
- Publishes `session.updated` over the Redis broker.
- Returns `{session_id, player_id, player_token, game_config, status}`. On race-loss: 409.

**`DELETE /api/sessions/{id}`** (`main.py:1010-1029`) — extended:
- If `visibility="public"`, `status="ready"`, no one has joined: host may cancel; clears the lobby entry.

**`GET /api/sessions`** (`main.py:955-1007`) and **`GET /api/dashboard`** (`main.py:1032-1073`) — relax filter to `user_id == me OR participant_user_ids @> [me]`. Add a derived `role: "host"|"opponent"` field.

**`GET /api/session/{id}/state`** (`main.py:483-495`) and **`GET /api/session/{id}/observation`** (`main.py:498-516`) — **privacy hardening**: caller must be in `participant_user_ids` OR hold a valid `nks_` token for the session, else 403. This closes the URL-leak hole.

### Game-start semantics

Add a small helper `await_session_ready(session_id, player_id)` that returns `False` until `status="running"`. The host's `BaseAgent` calls `wait_for_opponent()` before its first `submit_action()`; the helper polls `GET /api/session/{id}/summary` every 2s.

### Match expiry

Add `MATCHMAKING_TTL_HOURS=24` to `backend/arena/config.py`. A lifespan task on a 1-hour interval:

```python
async def expire_stale_matches():
    cutoff = utcnow() - timedelta(hours=settings.matchmaking_ttl_hours)
    await db.execute(
        update(SessionModel)
        .where(SessionModel.visibility == "public",
               SessionModel.status == "ready",
               SessionModel.created_at < cutoff)
        .values(status="failed", error_message="Match expired: no opponent joined")
    )
```

### Agent SDK

`agent-sdk/src/outplayarena_sdk/client.py` — add to `ArenaClient` (alongside `create_experiment` at `client.py:60-115`):

```python
async def list_open_matches(self, game: str | None = None) -> list[MatchSummary]: ...
async def get_match(self, session_id_or_invite_code: str) -> MatchSummary: ...
async def create_open_match(
    self, config: dict, host_agent: str, host_name: str,
    open_slots: list[str], invite_code: str | None = None,
) -> OpenMatchCreated: ...
async def join_match(
    self, session_id_or_invite_code: str, agent_id: str, agent_name: str,
    agent_config: dict | None = None,
) -> JoinResult: ...
```

`agent-sdk/src/outplayarena_sdk/base.py` (`BaseAgent.run`, around `base.py:82-217`): after `create_open_match`, call `await self.client.wait_for_opponent(session_id)` if `open_slots` was non-empty; then proceed with the normal game loop.

Add a new `MatchmakerAgent` example under `agent-sdk/src/outplayarena_sdk/agents/matchmaking/`.

`agent-sdk/src/outplayarena_sdk/quick_play.py` — leave untouched.

### Frontend

- New `LobbyPage` (`frontend/src/pages/LobbyPage.tsx`): cards with game, host display name, host agent, # open slots, total slots, rounds, time-since-created, **Join** button. Filters: game dropdown, "Hide full" toggle. Polls every 10s. "My active matches" section at top (sessions where I'm host or joiner with `status in ("ready","running")`).
- New `/lobby/invite/{inviteCode}` route → `LobbyInvitePage`: shows match summary, **Claim slot & start agent** button. After auth, calls `joinMatch()` and redirects to the play view with the returned `player_token` stored in `state.pendingGame`.
- `LobbyConfigShell` (`frontend/src/components/LobbyConfigShell.tsx:24-194`): new "Open for matchmaking" toggle near the **Start** button. When on, the open slots' `PlayerSetupCard`s are replaced with a disabled "Waiting for opponent" card. A "Make this match public" checkbox is on by default. On submit, surface the returned `invite_code` + a **Copy link** button.
- The host's chosen config (rounds, fields, etc.) is the match's config — `AutoConfigForm` already exposes the full `config_schema`, so no new config UI is needed.
- `WaitingForOpponentPage` (new, or a "waiting" tab in `GamePlayPage`): shows invite link + copy, polls for opponent joining, then switches to the play view.
- `GamePlayView` (`frontend/src/components/GamePlayView.tsx:37-595`): new header badge `Hosting (waiting)` / `Joined` / `Live` based on `status` and `role`.
- `api.ts` and `state.tsx` (`frontend/src/state.tsx:29-86, 156-161`): new wrappers and `pendingGame` fields for `visibility` and `invite_code`.
- `NavBar` (`frontend/src/components/NavBar.tsx:1-170`): top-level **Lobby** link with a small badge for the number of open matches in the user's games.

### Auth & local-mode handling

The current local-mode sentinel `LOCAL_USER_ID` (`auth/dependencies.py:15-117`) means there's only one effective user — matchmaking is meaningless. Add a sibling `require_multiplayer_user` dependency that raises 403 in local mode; use it on `/api/lobby/*` and `POST /api/sessions/{id}/join`. The lobby UI shows a banner: "Multiplayer matchmaking requires GitHub or Google sign-in." The matchmaking toggle in `AutoConfigForm` is disabled with a tooltip.

### Display names & privacy

For lobby entries, do **not** expose the host's `user_id` or `nks_` key. The lobby API returns only:
- `host_display_name` (from `User.name` or fallback `"anonymous-{short_id}"`)
- `host_agent_name` (the string the host put in their `PlayerSetupCard`)
- Game + sanitized config (round count, public config fields)

Same for the join view: when a joiner is shown to a host, only display name + agent name.

## Phased implementation

I recommend shipping in this order so each step is independently demoable.

### Phase 1 — Backend matchmaking core (~1.5d)
- Migration with the 5 new columns.
- Extend `GameSession.create` and `save_new` (`session.py:111-126`).
- New endpoints: `GET /api/lobby/matches`, `GET /api/lobby/matches/{invite_code}`, `POST /api/sessions/{id}/join`.
- Extend `POST /api/experiment` for `visibility` / `open_slots` / `invite_code`.
- Relax `GET /api/sessions` and `GET /api/dashboard` to include joined sessions.
- Tighten `GET /api/session/{id}/state` and `/observation` with participant check.
- Local-mode guard for new endpoints.
- Background sweeper for stale matches.
- Unit tests for: race-on-join, host-cannot-join-own, N-player partial fill, state-leak blocked for non-participants.

### Phase 2 — Agent SDK support (~0.5d)
- `ArenaClient.create_open_match`, `join_match`, `list_open_matches`, `get_match`.
- `wait_for_opponent()` helper.
- A `matchmaking` example agent in `agent-sdk/examples/`.

### Phase 3 — Frontend lobby + create toggle (~1.5d)
- `LobbyPage` with cards, filters, polling.
- `/lobby/invite/{code}` landing page.
- "Open for matchmaking" toggle in `LobbyConfigShell`/`AutoConfigForm`.
- Waiting-room UI with copy-link.
- `GamePlayView` role badge.
- NavBar entry.

### Phase 4 — Polish (~0.5d)
- Lobby SSE for real-time updates (optional, replace polling).
- Disable toggle in local mode with a clear message.
- Docs: new page under `docs/` explaining matchmaking flow + SDK snippet.
- End-to-end test: two browser sessions, host creates, joiner joins, game plays to completion, both see it in history.

## File touch list

**Backend**
- `backend/arena/models/session.py:11-30` — new columns
- `backend/arena/session.py:111-126` — `create` / `save_new` signature
- `backend/arena/main.py:431-480` — `POST /api/experiment`
- `backend/arena/main.py:354-411` — add `lobby` endpoints nearby
- `backend/arena/main.py:483-516` — participant check on `state` / `observation`
- `backend/arena/main.py:955-1073` — `sessions` & `dashboard` filters
- `backend/arena/main.py:1010-1029` — delete + cancel semantics
- `backend/arena/auth/dependencies.py:111-117` — add `require_multiplayer_user`
- `backend/arena/config.py` — `MATCHMAKING_TTL_HOURS`
- `backend/migrations/versions/` — new migration

**Agent SDK**
- `agent-sdk/src/outplayarena_sdk/client.py:60-115` — new methods
- `agent-sdk/src/outplayarena_sdk/base.py:82-217` — `wait_for_opponent`
- `agent-sdk/src/outplayarena_sdk/agents/matchmaking/` — example

**Frontend**
- `frontend/src/pages/LobbyPage.tsx` — new
- `frontend/src/pages/LobbyInvitePage.tsx` — new
- `frontend/src/pages/WaitingForOpponentPage.tsx` — new
- `frontend/src/components/LobbyConfigShell.tsx:24-194` — toggle
- `frontend/src/components/GamePlayView.tsx:37-595` — role badge
- `frontend/src/components/NavBar.tsx:1-170` — Lobby link
- `frontend/src/api.ts:65-72` — new wrappers
- `frontend/src/state.tsx:29-86, 156-161` — `pendingGame` fields

## Test plan

- **Unit (backend)**:
  - Two concurrent `POST /api/sessions/{id}/join` calls: exactly one returns 200, the other 409.
  - Host calling `POST /api/sessions/{own_id}/join` returns 403/409.
  - Non-participant calling `GET /api/session/{id}/state` returns 403.
  - N-player partial fill: after one of two open slots is filled, status remains `"ready"`, `open_slots=["C"]`.
  - Match older than TTL is set to `status="failed"` by the sweeper.
- **SDK**:
  - `create_open_match` returns a token usable in `submit_action`.
  - `wait_for_opponent` resolves when status flips to `running`.
  - `join_match` works with either `session_id` or `invite_code`.
- **End-to-end**:
  - Two browser sessions (or two CLI agents), host creates open match, joiner claims via lobby, both agents play to completion, both see the match in their history, both are credited on the leaderboard.
  - Non-participant with the session URL cannot read state.
  - Local mode: lobby banner shows, toggle disabled, `/api/lobby/matches` returns 404.
