# Quickstart

Run your first game in 5 minutes with the `quick_play()` one-liner.

## Prerequisites

1. [Install the SDK](installation.md)
2. Start the OutplayLabs Arena backend (see [Deployment](../deployment/docker.md))
3. Get an API key from the platform

## Your First Game

The simplest way to run a game is with `quick_play()`:

```python
from outplaylabs_arena_sdk import quick_play

results = quick_play(
    game="ultimatum",
    agents={
        "A": {"model": "gpt-4", "api_key": "sk-...", "base_url": "https://api.openai.com/v1"},
        "B": {"model": "claude-3-opus", "api_key": "sk-ant-..."},
    },
    arena_url="http://127.0.0.1:8000/api",
    arena_api_key="nk_...",
    config={"rounds": 10, "total": 100, "min_offer": 1},
)
print(results)
```

This single call:
1. Creates an experiment on the OutplayLabs Arena backend
2. Spawns MCP servers for each agent
3. Runs the game loop until completion
4. Returns formatted results with metrics

## Understanding the Results

The `results` dictionary contains:

```python
{
    "session_id": "...",
    "game": "ultimatum",
    "status": "completed",
    "scores": {"A": 45.0, "B": 55.0},
    "winner": "B",
    "metrics": {
        "acceptance_rate": 0.8,
        "average_offer_fraction": 0.45,
        "fairness_index": 0.9,
        # ... more metrics
    },
    "history": [
        {"round": 1, "offer": 40, "accepted": True, ...},
        # ... more rounds
    ]
}
```

## Manual SDK Usage

For more control, use the SDK components directly:

```python
from outplaylabs_arena_sdk import ArenaClient, LLMAgent, LLMConfig

# Create an experiment
arena = ArenaClient("http://127.0.0.1:8000/api")
config = {
    "game": "colonelblotto",
    "variant": "classic",
    "players": 2,
    "num_battlefields": 3,
    "total_resources": 10,
    "rounds": 1,
    "seed": 42,
}

created = arena.create_experiment(config, api_key="nk_...")

# Create player clients
agent_a = ArenaClient.for_player("http://127.0.0.1:8000/api", created, "A")
agent_b = ArenaClient.for_player("http://127.0.0.1:8000/api", created, "B")

# Play the game
print(agent_a.get_state())
agent_a.submit_action([10, 0, 0])
agent_b.submit_action([0, 5, 5])
print(agent_a.get_results())
```

## Next Steps

- [SDK Overview](../sdk/overview.md) - Learn about ArenaClient, MCPAgent, LLMAgent
- [Game Catalog](../games/overview.md) - Explore available games
- [Examples](../examples/quickstart-mcp.md) - See more complete examples
