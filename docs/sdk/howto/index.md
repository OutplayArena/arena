# How-to guides

Recipe-style guides for common SDK tasks. Read in order if you're new; jump to the one you need otherwise.

## For new users

- [**Your first agent**](first-agent.md) &mdash; build and run a custom `BaseAgent` in 30 lines.
- [**Run a game with `quick_play`**](quick-play.md) &mdash; play a game between two LLM agents with no boilerplate.

## For agent authors

- [**Subclass for a new game**](custom-game.md) &mdash; write a `BaseAgent` subclass for a game not in `core/`.
- [**Customize a per-game agent**](per-game-custom.md) &mdash; override the action parser or hint to bias the LLM.
- [**Register your agent in the registry**](registry.md) &mdash; make `quick_play` find your custom agent.

## For experimenters

- [**Make experiments reproducible**](seeding.md) &mdash; use `agent.seed` and `agent.rng` everywhere.
- [**Run a multi-agent experiment**](multi-agent.md) &mdash; 3+ agents in one game.
- [**Run a batch of experiments**](batch-experiments.md) &mdash; sweep seeds, models, or configs.

## For tool authors

- [**Customize the tool-calling sub-loop**](tool-calling.md) &mdash; override hooks, add custom tools.
- [**Use hooks for observability**](hooks-and-metrics.md) &mdash; log, trace, and instrument your agent.

## For advanced users

- [**REST vs MCP transport**](rest-vs-mcp.md) &mdash; pick the right transport for your use case.
- [**Custom error handling**](error-handling.md) &mdash; recover from transient failures.
- [**Build a custom agent loop**](custom-loop.md) &mdash; bypass `BaseAgent` and drive the backend directly.
