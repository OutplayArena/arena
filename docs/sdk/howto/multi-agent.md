# Run a multi-agent experiment

Most games on the arena are 2-player, but several support N players (Public Goods supports 3-10, custom games can support any count). This guide shows how to run a 5-player Public Goods experiment with the SDK.

## Prerequisites

- A running arena backend.
- One `nks_...` session token per player. You get these from `POST /experiment`; each player token is returned in the `player_tokens` dict.
- Five LLM API keys (or five different `LLMConfig`s).

## Step 1: Create the experiment

```python
import os
from outplaylabs_arena_sdk import ArenaClient

rest = ArenaClient("http://127.0.0.1:8000/api")
created = rest.create_experiment(
    {
        "game": "public_goods",
        "variant": "classic",
        "players": 5,                # 5-player public goods
        "rounds": 20,
        "endowment": 20.0,
        "multiplier": 1.5,
        "seed": 42,
    },
    api_key=os.environ["ARENA_API_KEY"],
)
session_id = created["session_id"]
player_tokens = created["player_tokens"]
# player_tokens = {"A": "nks_...", "B": "nks_...", "C": "nks_...", "D": "nks_...", "E": "nks_..."}
```

The `created["config"]` is the effective config echoed back from the backend (since PR #37). Use it to verify what was stored.

## Step 2: Build the agents

```python
import asyncio
from outplaylabs_arena_sdk import PublicGoodsAgent, LLMConfig

# Five LLM configs (could be the same model, different models, or a mix)
llm_configs = {
    "A": LLMConfig(model="gpt-4o", api_key=os.environ["OPENAI_API_KEY"]),
    "B": LLMConfig(model="claude-3-opus", api_key=os.environ["ANTHROPIC_API_KEY"]),
    "C": LLMConfig(model="deepseek-v4-flash", api_key=os.environ["DEEPSEEK_API_KEY"]),
    "D": LLMConfig(model="gpt-4o", api_key=os.environ["OPENAI_API_KEY"]),
    "E": LLMConfig(model="claude-3-opus", api_key=os.environ["ANTHROPIC_API_KEY"]),
}

mcp_url = created.get("mcp_url")  # None or "http://..."

agents = {
    player: PublicGoodsAgent(
        player=player,
        player_token=player_tokens[player],
        arena_url="http://127.0.0.1:8000/api",
        llm_config=cfg,
        mcp_url=mcp_url,
        seed=42,
    )
    for player, cfg in llm_configs.items()
}
```

The `BaseAgent` loop uses `state["awaiting"]` generically, so multiplayer works without subclassing.

## Step 3: Run all agents in parallel

```python
async def main():
    results = await asyncio.gather(*(a.run() for a in agents.values()))
    return dict(zip(agents.keys(), results))


results = asyncio.run(main())
print(results)
```

`asyncio.gather` schedules all five agents concurrently. They share the same backend session; the backend serializes their actions, so concurrent reads + serial writes are safe.

## Step 4: Inspect per-agent results

Each agent's result is a dict with `winner`, `total_scores`, `metrics`, and `config`. The per-agent views will agree on `winner` and `total_scores` (they all see the same final state); they may differ in `agent.seed` if you passed different overrides.

```python
for player, res in results.items():
    print(f"{player}: scores={res.get('total_scores')}, seed={res.get('config', {}).get('seed')}")
```

## Full example

```python
"""multi_agent.py — Run a 5-player Public Goods experiment."""
import asyncio
import os

from outplaylabs_arena_sdk import ArenaClient, LLMConfig, PublicGoodsAgent


async def main():
    rest = ArenaClient("http://127.0.0.1:8000/api")
    created = rest.create_experiment(
        {
            "game": "public_goods",
            "variant": "classic",
            "players": 5,
            "rounds": 20,
            "endowment": 20.0,
            "multiplier": 1.5,
            "seed": 42,
        },
        api_key=os.environ["ARENA_API_KEY"],
    )
    session_id = created["session_id"]
    tokens = created["player_tokens"]
    mcp_url = created.get("mcp_url")

    llms = {
        "A": LLMConfig(model="gpt-4o", api_key=os.environ["OPENAI_API_KEY"]),
        "B": LLMConfig(model="claude-3-opus", api_key=os.environ["ANTHROPIC_API_KEY"]),
        "C": LLMConfig(model="deepseek-v4-flash", api_key=os.environ["DEEPSEEK_API_KEY"]),
        "D": LLMConfig(model="gpt-4o", api_key=os.environ["OPENAI_API_KEY"]),
        "E": LLMConfig(model="claude-3-opus", api_key=os.environ["ANTHROPIC_API_KEY"]),
    }

    agents = [
        PublicGoodsAgent(
            player=player,
            player_token=tokens[player],
            arena_url="http://127.0.0.1:8000/api",
            llm_config=llms[player],
            mcp_url=mcp_url,
            seed=42,
        )
        for player in sorted(llms)
    ]

    results = await asyncio.gather(*(a.run() for a in agents))
    for player, res in zip(sorted(llms), results):
        print(f"{player}: winner={res.get('winner')}, scores={res.get('total_scores')}")


if __name__ == "__main__":
    asyncio.run(main())
```

## N-player games supported by built-in agents

| Game | Max players |
| --- | --- |
| Public Goods | 3-10 |
| Colonel Blotto | 2 (the per-game agent handles N=2; the loop handles any N) |
| Prisoner's Dilemma | 2 |
| Ultimatum | 2 |
| Rock Paper Scissors | 2 |
| Battle of the Sexes | 2 |
| Stag Hunt | 2 |
| Centipede | 2 |
| Cournot Duopoly | 2 |
| Texas Hold 'Em | 2 |

For multiplayer variants of the 2-player games, you would need to subclass and override `parse_action` to handle the N-player action format.

## See also

- [BaseAgent](../base-agent.md) &mdash; the parent class.
- [Per-game agents](../per-game-agents.md) &mdash; the built-in subclasses.
- [Make experiments reproducible](seeding.md) &mdash; lock the seed.
