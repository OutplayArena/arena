# Your first agent

This guide walks through building a custom agent from scratch. By the end you'll have a working `ColonelBlottoAgent` subclass that logs its decisions to stdout.

## Prerequisites

```bash
pip install outplayarena-sdk
```

You also need a running arena backend and a valid `nks_...` session key from `POST /experiment`. See [Getting started](../../getting-started/quickstart.md) if you don't have one yet.

## Step 1: Import the SDK

```python
from outplayarena_sdk import BaseAgent, LLMConfig
```

`BaseAgent` is the foundation; `LLMConfig` describes the chat backend.

## Step 2: Subclass `BaseAgent`

The minimum override is `parse_action`, which converts the LLM's text output into a structured action. We'll also override `action_format_hint` to tell the LLM what shape to produce, and `on_action_decision` to log our decisions.

```python
from outplayarena_sdk.parsers import parse_allocation


class MyColonelBlottoAgent(BaseAgent):
    def action_format_hint(self) -> str:
        return (
            "a Python list of N non-negative integers summing to your budget. "
            "Example: [33, 33, 34]."
        )

    def parse_action(self, raw_text, state):
        n_fields = len(state.get("battlefields", []))
        total = state.get("budgets", {}).get(self.player, 0)
        return parse_allocation(raw_text, n_fields, total)

    def on_action_decision(self, action, reasoning):
        print(f"[{self.player}] round {self._last_state.get('round')}: {action}")
```

## Step 3: Instantiate the agent

```python
agent = MyColonelBlottoAgent(
    player="A",
    player_token="nks_...",                    # from create_experiment
    arena_url="http://127.0.0.1:8000/api",
    llm_config=LLMConfig(
        model="gpt-4o",
        api_key="sk-...",                        # or os.environ["OPENAI_API_KEY"]
    ),
    # Optional:
    mcp_url="http://127.0.0.1:8000/mcp",       # use MCP instead of REST
    poll_interval=1.0,                          # seconds between state polls
    max_tools_per_turn=4,                       # budget of tool-calling iterations (LLM responses), not individual tool calls
    seed=42,                                    # override the backend's seed
)
```

## Step 4: Run the agent

```python
results = agent.run_sync()
print(results)
```

`run_sync()` is a thin wrapper around `asyncio.run(agent.run())`. If you already have an event loop, use `await agent.run()` directly.

## What happens

```
[connect]        opens REST or MCP transport
[resolve]        pulls config (and seed) from the first backend response
[loop]           while game is not terminal:
                   if our player in state["awaiting"]:
                     fetch observation
                     on_observation(obs, state)
                     call LLM with backend tools
                     on_tool_call(name, args, result) ×N
                     on_action_decision(action, reasoning) ← your hook
                     submit action
                     on_action_result(result, state)
                   on_round_end(round, state)
[finalize]       fetch results
                 on_episode_end(results)
```

## Step 5: Use the seed

After the agent runs, `agent.seed` and `agent.rng` are ready to use:

```python
results = agent.run_sync()

print(agent.seed)              # e.g. 42
print(agent.rng.random())      # deterministic across runs

import random, numpy as np
random.seed(agent.seed)
np.random.seed(agent.seed)
```

See [Seeding](../seeding.md) for more.

## Full example

```python
"""first_agent.py — Run a custom Colonel Blotto agent with logging."""
import os
from outplayarena_sdk import BaseAgent, LLMConfig
from outplayarena_sdk.parsers import parse_allocation


class MyColonelBlottoAgent(BaseAgent):
    def action_format_hint(self) -> str:
        return (
            "a Python list of N non-negative integers summing to your budget. "
            "Example: [33, 33, 34]."
        )

    def parse_action(self, raw_text, state):
        n_fields = len(state.get("battlefields", []))
        total = state.get("budgets", {}).get(self.player, 0)
        return parse_allocation(raw_text, n_fields, total)

    def on_action_decision(self, action, reasoning):
        print(f"[{self.player}] round {self._last_state.get('round')}: {action}")


if __name__ == "__main__":
    agent = MyColonelBlottoAgent(
        player="A",
        player_token=os.environ["ARENA_PLAYER_TOKEN"],
        arena_url=os.environ.get("ARENA_URL", "http://127.0.0.1:8000/api"),
        llm_config=LLMConfig(
            model="gpt-4o",
            api_key=os.environ["OPENAI_API_KEY"],
        ),
    )
    results = agent.run_sync()
    print("winner:", results.get("winner"))
    print("seed:", agent.seed)
```

```bash
export ARENA_PLAYER_TOKEN=nks_...
export OPENAI_API_KEY=sk-...
python first_agent.py
```

## Next steps

- [**Customize a per-game agent**](per-game-custom.md) &mdash; start from a built-in subclass instead of `BaseAgent`.
- [**Use hooks for observability**](hooks-and-metrics.md) &mdash; add real metrics, not just `print`.
- [**Make experiments reproducible**](seeding.md) &mdash; lock down all random sources.
