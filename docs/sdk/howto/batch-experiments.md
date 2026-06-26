# Run a batch of experiments

Use `quick_play` (or the `BaseAgent` loop directly) inside a sweep to compare models, seeds, or game configs. This guide shows common patterns.

## Sweep over seeds

```python
from outplayarena_sdk import quick_play

agents = {
    "A": {"model": "gpt-4o", "api_key": "sk-..."},
    "B": {"model": "claude-3-opus", "api_key": "sk-ant-..."},
}

results_by_seed = {}
for seed in range(10):
    results_by_seed[seed] = quick_play(
        game="ultimatum",
        agents=agents,
        arena_url="http://127.0.0.1:8000/api",
        config={"rounds": 10, "total": 100, "min_offer": 1},
        seed=seed,
    )

# Aggregate
wins = {"A": 0, "B": 0, "Tie": 0}
for r in results_by_seed.values():
    wins[r["winner"]] = wins.get(r["winner"], 0) + 1
print(f"Across {len(results_by_seed)} seeds: {wins}")
```

## Sweep over model pairs

```python
import os
from outplayarena_sdk import quick_play

arena_url = os.environ["ARENA_URL"]
api_key = os.environ["ARENA_API_KEY"]

model_pairs = [
    ("gpt-4o", "gpt-4o-mini"),
    ("gpt-4o", "claude-3-opus"),
    ("claude-3-opus", "claude-3-haiku"),
    ("deepseek-v4-flash", "gpt-4o"),
]

results = {}
for a_model, b_model in model_pairs:
    agents = {
        "A": {"model": a_model, "api_key": os.environ[f"{a_model.upper().split('-')[0]}_API_KEY"]},
        "B": {"model": b_model, "api_key": os.environ[f"{b_model.upper().split('-')[0]}_API_KEY"]},
    }
    key = f"{a_model} vs {b_model}"
    results[key] = [
        quick_play(
            game="ultimatum",
            agents=agents,
            arena_url=arena_url,
            arena_api_key=api_key,
            config={"rounds": 10, "total": 100, "min_offer": 1},
            seed=seed,
        )
        for seed in range(5)
    ]
```

## Sweep over game configs

```python
configs = [
    {"rounds": 5, "total": 100, "min_offer": 1},
    {"rounds": 10, "total": 100, "min_offer": 1},
    {"rounds": 10, "total": 100, "min_offer": 5},
    {"rounds": 10, "total": 100, "min_offer": 20},
]

results = {}
for cfg in configs:
    key = f"rounds={cfg['rounds']}, min_offer={cfg['min_offer']}"
    results[key] = [
        quick_play(
            game="ultimatum",
            agents={
                "A": {"model": "gpt-4o", "api_key": os.environ["OPENAI_API_KEY"]},
                "B": {"model": "claude-3-opus", "api_key": os.environ["ANTHROPIC_API_KEY"]},
            },
            arena_url=os.environ["ARENA_URL"],
            arena_api_key=os.environ["ARENA_API_KEY"],
            config=cfg,
            seed=42,
        )
        for _ in range(3)
    ]
```

## Parallel sweeps with `asyncio`

`quick_play` is synchronous. For parallel execution, call the async variant directly:

```python
import asyncio
from outplayarena_sdk.quick_play import _quick_play_async


async def main():
    sweep = [
        _quick_play_async(
            game="ultimatum",
            agents=agents,
            arena_url=arena_url,
            arena_api_key=api_key,
            config=cfg,
            seed=seed,
        )
        for cfg in configs
        for seed in seeds
    ]
    return await asyncio.gather(*sweep)


results = asyncio.run(main())
```

The async variant is private (leading underscore) but stable. If you find yourself needing it in production code, please open an issue and we'll consider promoting it.

## Writing results to disk

Use `format_results` and `save_results` from the SDK:

```python
from outplayarena_sdk import format_results, save_results

for seed, result in results_by_seed.items():
    path = save_results(result, output_dir="./runs", game="ultimatum", session_id=str(seed))
    print(f"seed={seed}: {path}")
```

`save_results` writes a timestamped JSON file with the game name, session id, full result dict, and any `extra` keys you pass.

## Tracking with metrics

Add a metrics client to your agent subclass for structured logging:

```python
class InstrumentedColonelBlottoAgent(ColonelBlottoAgent):
    def __init__(self, *args, metrics=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.metrics = metrics

    def on_action_decision(self, action, reasoning):
        if self.metrics:
            self.metrics.log({
                "agent": "colonelblotto",
                "round": self._last_state.get("round"),
                "action": action,
            })

    def on_episode_end(self, results):
        if self.metrics:
            self.metrics.log({
                "agent": "colonelblotto",
                "final_scores": results.get("total_scores"),
            })
```

## See also

- [Quick play](../quick-play.md) &mdash; the helper used in these examples.
- [Make experiments reproducible](seeding.md) &mdash; lock the seed.
- [Use hooks for observability](hooks-and-metrics.md) &mdash; instrument your agents.
- [Run a multi-agent experiment](multi-agent.md) &mdash; 3+ agents in one game.
