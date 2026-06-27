# Changelog

All notable changes to the OutplayArena Python SDK are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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

[Unreleased]: https://github.com/OutplayArena/arena/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/OutplayArena/arena/releases/tag/v0.1.0
