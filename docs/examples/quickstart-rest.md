# REST Examples

Examples of running games with REST-based agents.

## Overview

REST examples demonstrate direct HTTP interaction with the NashArena API. These examples use `ArenaClient` for full control over API calls.

## Setup

All examples require:

```bash
# Set environment variables
export NASH_ARENA_API_KEY="your-api-key"
export OPENCODE_GO_API_KEY="your-llm-api-key"

# Start the backend
uv run uvicorn nash_arena.main:app --host 0.0.0.0 --port 8000
```

## Hello World: Colonel Blotto

The simplest possible example — no LLM, just hardcoded actions:

```python
from nash_arena_sdk import ArenaClient

client = ArenaClient("http://127.0.0.1:8000/api")

# Create experiment
created = client.create_experiment({
    "game": "colonelblotto",
    "num_battlefields": 3,
    "total_resources": 10,
    "rounds": 1,
})

# Create player clients
agent_a = ArenaClient.for_player("http://127.0.0.1:8000/api", created, "A")
agent_b = ArenaClient.for_player("http://127.0.0.1:8000/api", created, "B")

# Submit actions
agent_a.submit_action([10, 0, 0])
agent_b.submit_action([0, 5, 5])

# Get results
print(agent_a.get_results())
```

```bash
uv run python examples/REST/play_colonel_blotto_game.py
```

## LLM vs LLM: Colonel Blotto

Full example with two LLM agents:

```bash
uv run python examples/REST/glm_vs_deepseek.py
```

Demonstrates:
- LLM API warmup
- Prompt construction with history
- Action parsing from LLM output
- Results formatting

## LLM vs Built-in Agent

```bash
uv run python examples/REST/colonel_blotto_example_llm_vs_uniform_random.py
```

LLM agent plays against a built-in `UniformAgent`.

## Prisoner's Dilemma Scenarios

Multiple framing scenarios:

```bash
# Classic prison framing
uv run python examples/REST/pd_prison_glm_vs_deepseek.py

# Climate change framing
uv run python examples/REST/pd_climate_glm_vs_deepseek.py

# Arms race framing
uv run python examples/REST/pd_arms_race_glm_vs_deepseek.py

# Business competition framing
uv run python examples/REST/pd_business_glm_vs_deepseek.py

# Roommate chore framing
uv run python examples/REST/pd_roommates_glm_vs_deepseek.py
```

## All Games

| Game | Command |
|------|---------|
| Colonel Blotto | `uv run python examples/REST/glm_vs_deepseek.py` |
| Ultimatum | `uv run python examples/REST/ultimatum_glm_vs_deepseek.py` |
| Prisoner's Dilemma | `uv run python examples/REST/pd_glm_vs_deepseek.py` |
| Public Goods | `uv run python examples/REST/public_goods_glm_vs_deepseek.py` |
| Centipede | `uv run python examples/REST/centipede_glm_vs_deepseek.py` |
| Battle of the Sexes | `uv run python examples/REST/battle_of_the_sexes_glm_vs_deepseek.py` |
| Cournot Duopoly | `uv run python examples/REST/cournot_duopoly_glm_vs_deepseek.py` |
| Stag Hunt | `uv run python examples/REST/stag_hunt_glm_vs_deepseek.py` |
| Texas Hold'em | `uv run python examples/REST/texas_hold_em_llm_vs_llm.py` |

## Example Structure

REST examples follow this pattern:

```python
from nash_arena_sdk import ArenaClient

# Create experiment
client = ArenaClient("http://127.0.0.1:8000/api")
created = client.create_experiment(config, api_key=api_key)

# Create player clients
agent_a = ArenaClient.for_player("http://127.0.0.1:8000/api", created, "A")
agent_b = ArenaClient.for_player("http://127.0.0.1:8000/api", created, "B")

# Game loop
for round in range(config["rounds"]):
    state_a = agent_a.get_state()
    action_a = llm_call(state_a)  # Your LLM logic
    agent_a.submit_action(action_a)
    
    state_b = agent_b.get_state()
    action_b = llm_call(state_b)
    agent_b.submit_action(action_b)

# Get results
results = agent_a.get_results()
```

## Results

All examples save results to `results/` directory:

```python
from nash_arena_sdk import save_results

save_results(results, output_dir="results", game="ultimatum")
# Saves to: results/ultimatum_20240101_120000.json
```

## Next Steps

- [MCP Examples](quickstart-mcp.md) — MCP-based agent examples
- [SDK Guide](../sdk/arena-client.md) — ArenaClient documentation
- [API Reference](../api/overview.md) — REST API documentation
