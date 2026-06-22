# `quick_play`

`quick_play()` is the one-call helper for running a game between two LLM agents. It auto-picks the right per-game agent class based on the `game=` argument, creates the experiment, runs both agents in parallel, and returns the final results.

```python
from outplaylabs_arena_sdk import quick_play

results = quick_play(
    game="ultimatum",
    agents={
        "A": {"model": "gpt-4o", "api_key": "sk-..."},
        "B": {"model": "claude-3-opus", "api_key": "sk-ant-..."},
    },
    arena_url="https://api.agent-arena.local",
    arena_api_key="nk_...",
    config={"rounds": 10, "total": 100, "min_offer": 1},
    seed=42,
)
print(results)
```

## Signature

```python
def quick_play(
    game: str,
    agents: dict[str, dict[str, Any]],
    arena_url: str = "http://127.0.0.1:8000/api",
    arena_api_key: str | None = None,
    config: dict[str, Any] | None = None,
    seed: int = 42,
    jwt_secret: str | None = None,
    mcp_url: str | None = None,
    poll_interval: float = 1.0,
    max_tools_per_turn: int = 4,
    verbose: bool = False,
) -> dict[str, Any]:
    ...
```

| Parameter | Purpose |
| --- | --- |
| `game` | Game slug. Must be a key in the [`GAME_AGENTS` registry](registry.md). |
| `agents` | Dict mapping player IDs to their LLM config. Each config supports: `model`, `api_key`, `base_url`, `temperature`, `max_tokens`, `extra_body`, `fallback_model`, `reasoning_effort`, `action_parser` (legacy), `system_prompt`, `use_mcp`. |
| `arena_url` | Backend REST API base URL. |
| `arena_api_key` | API key for experiment creation (the `OUTPLAYLABS_ARENA_API_KEY`). |
| `config` | Game-specific config dict. Defaults to `{"game": game, "seed": seed}` if not provided. |
| `seed` | Seed for the experiment. The same seed is passed to both agents so they see the same `agent.rng` stream. |
| `jwt_secret` | Optional JWT secret. Falls back to the `JWT_SECRET` env var. |
| `mcp_url` | Optional MCP endpoint. Defaults to the `mcp_url` from `create_experiment` if not provided. |
| `poll_interval` | Per-agent poll interval. |
| `max_tools_per_turn` | Per-turn tool-call budget for each agent. |
| `verbose` | Print debug information. |

## What it does

1. POSTs to `/experiment` with the merged config and gets back `session_id`, `player_tokens`, `mcp_url`, and the echoed `config` (including the effective seed).
2. Looks up the per-game agent class via the [`GAME_AGENTS` registry](registry.md).
3. Instantiates one agent per player.
4. Runs both agents in parallel with `asyncio.gather`.
5. Returns the results from player A (both agents see the same final state).

## Return value

The dict returned by `agent_a.run()` &mdash; the same as calling `get_results()` on the arena. Typically:

```python
{
    "session_id": "...",
    "winner": "A",  # or "B" or "Tie"
    "total_scores": {"A": 12.5, "B": 7.5},
    "metrics": {...},
    "config": {...},  # echoed experiment config
}
```

## Per-agent LLM configuration

Each entry in `agents` is a dict that gets passed to `LLMConfig`:

```python
agents = {
    "A": {
        "model": "gpt-4o",
        "api_key": "sk-...",
        "base_url": "https://api.openai.com/v1",  # default
        "temperature": 0.7,                         # default
        "max_tokens": 4096,                         # default
        "extra_body": None,                         # for provider-specific params
        "fallback_model": "gpt-4o-mini",            # retry with this on failure
        "reasoning_effort": "low",                  # "none" | "low" | "medium" | "high"
    },
    "B": {
        "model": "claude-3-opus",
        "api_key": "sk-ant-...",
        "base_url": "https://api.anthropic.com/v1",  # via OpenAI-compat proxy
    },
}
```

## Examples

### One-line game

```python
from outplaylabs_arena_sdk import quick_play

results = quick_play(
    game="colonelblotto",
    agents={
        "A": {"model": "gpt-4o", "api_key": "sk-..."},
        "B": {"model": "gpt-4o", "api_key": "sk-..."},
    },
    arena_url="http://127.0.0.1:8000/api",
    config={"rounds": 5, "total": 100},
)
```

### With env-var credentials

```python
import os
from outplaylabs_arena_sdk import quick_play

results = quick_play(
    game="ultimatum",
    agents={
        "A": {"model": "gpt-4o", "api_key": os.environ["OPENAI_API_KEY"]},
        "B": {"model": "claude-3-opus", "api_key": os.environ["ANTHROPIC_API_KEY"]},
    },
    arena_url=os.environ["ARENA_URL"],
    arena_api_key=os.environ["OUTPLAYLABS_ARENA_API_KEY"],
)
```

### Multi-round experiment

```python
from outplaylabs_arena_sdk import quick_play

results = []
for seed in range(10):
    res = quick_play(
        game="prisonersdilemma",
        agents={
            "A": {"model": "gpt-4o", "api_key": "sk-..."},
            "B": {"model": "claude-3-opus", "api_key": "sk-ant-..."},
        },
        arena_url="http://127.0.0.1:8000/api",
        config={"rounds": 50, "variant": "classic"},
        seed=seed,
    )
    results.append(res)
```

## When to use something else

`quick_play()` is for the common case: two agents, standard configs, full game from start to end. For more control, instantiate a per-game agent directly:

- **More than two agents** (e.g. public goods with 5 players) &mdash; build the agents yourself and run them with `asyncio.gather`.
- **Custom agent subclass** for a new game &mdash; instantiate the subclass directly.
- **Single-agent debugging** &mdash; instantiate one agent and call `run_sync()`.
- **Step-by-step control** &mdash; use `BaseAgent` with custom hooks to pause and inspect at any point.

## See also

- [BaseAgent](base-agent.md) &mdash; the underlying class.
- [Per-game agents](per-game-agents.md) &mdash; the auto-picked subclasses.
- [Registry](registry.md) &mdash; the `GAME_AGENTS` map.
- [How-to: run an experiment with `quick_play`](howto/quick-play.md) &mdash; a worked example.
