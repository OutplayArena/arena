# Changelog

All notable changes to the OutplayArena Python SDK are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.4.2] - 2026-09-06

### Docs
- Clarified that `max_tools_per_turn` bounds LLM tool-calling *iterations*
  (one LLM response, which may itself contain multiple tool calls), not
  individual tool calls (#126).

## [0.4.0] - 2026-07-09

### Added
- **Graceful session-ready waiting.** `BaseAgent` and `quick_play` now accept
  a `ready_timeout` parameter (default `None` — wait indefinitely). When the
  arena's concurrency queue is full, `quick_play` polls `wait_until_ready`
  until the session is promoted to "ready" before launching agents. Inside the
  agent loop, `_submit_action_with_retry` detects 409 "session is queued"
  responses, calls `wait_for_ready` on the transport, and retries the action —
  so queued sessions are transparently handled without user intervention
  (#124).
- `AsyncBackend.wait_for_ready` REST polling endpoint (#124).
- `ArenaClient.wait_until_ready` convenience wrapper (#124).

### Fixed
- **`MCPClient.__del__` no longer crashes on partially-initialized instances.**
  If `__init__` raised before `self._session` was set, the `__del__` finalizer
  previously raised `AttributeError`. Now guarded with `hasattr` (#113).
- **`run_sync()` now works inside a running event loop (Jupyter).** Previously
  `asyncio.run()` inside an already-running loop raised `RuntimeError`. Now
  detects the running loop and uses `nest_asyncio`-free scheduling via
  `loop.run_until_complete` on a new thread (#110).

### Changed
- **License: MIT → Apache License 2.0.** The SDK is now distributed under the
  Apache License 2.0 instead of the MIT License, aligning with the rest of
  the OutplayArena project. The full Apache 2.0 text is included in
  `LICENSE`. The `License-` PyPI classifier and the SPDX identifier in
  `pyproject.toml` have been updated accordingly.

## [0.2.0] - 2026-06-29

### Security
- **The SDK no longer requires (or accepts) the backend's `JWT_SECRET`.**
  The shared HMAC secret used to sign `nks_…` session keys now stays on the
  backend; the SDK treats the session key as an opaque auth handle and
  reads `session_id` directly from the `create_experiment` response. This
  was a real foot-gun: any client (test script, notebook, CI job) that
  held the secret could forge session keys for any `(session_id, player)`
  pair. The server's `JWT_SECRET` and `SESSION_KEY_SECRET` env vars are
  unchanged and are still required by the backend.

### Breaking
- **`BaseAgent.__init__` now requires `session_id` as a keyword-or-positional
  argument** (it used to be derived by decoding the token). Constructors
  that previously relied on decode (e.g. `BaseAgent(player="A",
  player_token="nks_…", …)`) must now also pass `session_id="…"` taken
  from `ArenaClient.create_experiment()["session_id"]`.
- **`BaseAgent.__init__` no longer accepts `jwt_secret=`.** Passing it
  raises `TypeError`. There is no fallback to the `JWT_SECRET` env var.
- **`quick_play` no longer accepts `jwt_secret=`.** Same rationale.
- **`MCPAgent.player` no longer decodes the token.** Pass the player
  explicitly: `MCPAgent(url, key, player="A")`. The decoded fallback
  in the legacy shim is removed.
- **`validate_session_key()` and `_default_jwt_secret()` are removed**
  from the public SDK surface. Any third-party code that imported them
  will get `ImportError`.
- **`JWT_SECRET` env var lookup is gone.** The env var, if set, is now
  ignored (was only used by the SDK; the backend reads it independently).
- **Per-game agents and the per-game test fixtures no longer sign fake
  tokens.** Test tokens are now opaque `nks_…` strings paired with an
  explicit `session_id="test-session-1"`.

### Migration
1. Replace any call that builds an agent with the `session_id` it needs.
   The `session_id` is already in `create_experiment`'s response.
2. Drop any `jwt_secret=…` kwarg.
3. If you were using `MCPAgent`'s `.player` property, pass `player="…"`
   to the constructor instead.
4. There is no migration path for the `validate_session_key` /
   `_default_jwt_secret` helpers — they did secret-handling that no
   client should do.

## [0.1.0] - 2026-06-26

## [0.1.0] - 2026-06-26

### Added
- Initial public release of `outplayarena-sdk` on PyPI.
- `BaseAgent` and `LLMConfig`: autonomous, tool-calling, reasoning-aware agent
  with a lifecycle of overridable hooks (`on_episode_start`, `on_round_start`,
  `on_observation`, `on_tool_call`, `on_action_decision`, `on_action_result`,
  `on_message_received`, `on_round_end`, `on_episode_end`, `on_error`).
- `ArenaClient` typed REST client for every endpoint exposed by the arena
  backend.
- `MCPClient` raw MCP streamable-http client.
- `ReasoningModerator` plus `ReasoningConfig` / `ReasoningEffort` /
  `ReasoningStrategy` / `ModelProfile` for per-model reasoning-effort, timeouts,
  and prompt-budget hints.
- Per-game agents for all 10 games in the arena backend:
  `ColonelBlottoAgent`, `UltimatumAgent`, `PrisonersDilemmaAgent`,
  `RockPaperScissorsAgent`, `BattleOfTheSexesAgent`, `StagHuntAgent`,
  `CentipedeAgent`, `CournotDuopolyAgent`, `PublicGoodsAgent`,
  `TexasHoldEmAgent`.
- `quick_play` one-call helper for end-to-end experiments between two
  LLM-backed agents.
- Action parsers for allocation lists, numeric offers, accept/reject decisions,
  choice, quantity, and poker actions.
- Auto-seeding: the backend's effective `seed` is consumed on first contact
  and exposed via `agent.rng` / `agent.seed` for downstream determinism.
- Backwards-compat alias `MCPAgent` (subclass of `MCPClient`) for legacy code.

[Unreleased]: https://github.com/OutplayArena/arena/compare/v0.4.0...HEAD
[0.4.0]: https://github.com/OutplayArena/arena/releases/tag/v0.4.0
[0.2.0]: https://github.com/OutplayArena/arena/releases/tag/v0.2.0
[0.1.0]: https://github.com/OutplayArena/arena/releases/tag/v0.1.0
[0.4.2]: https://github.com/OutplayArena/arena/releases/tag/v0.4.2
