# MCP Examples

Examples of running games with MCP-based agents.

## Overview

MCP (Model Context Protocol) examples demonstrate how LLM agents can interact with NashArena through structured tools. Each example shows the orchestrator/agent pattern where an orchestrator creates the session and agents use MCP tools to play.

## Setup

All examples require:

```bash
# Set environment variables
export NASH_ARENA_API_KEY="your-api-key"
export OPENCODE_GO_API_KEY="your-llm-api-key"

# Start the backend
uv run uvicorn nash_arena.main:app --host 0.0.0.0 --port 8000
```

## Colonel Blotto

```bash
uv run python examples/MCP/colonel_blotto_glm_vs_deepseek.py
```

Two LLM agents allocate troops across battlefields via MCP.

## Ultimatum Game

```bash
uv run python examples/MCP/ultimatum_glm_vs_deepseek.py
```

Sequential proposer/responder game with alternating roles.

## Prisoner's Dilemma

```bash
uv run python examples/MCP/pd_glm_vs_deepseek.py
```

Classic cooperation/defection game with multiple scenario framings.

## Public Goods Game

```bash
uv run python examples/MCP/public_goods_glm_vs_deepseek.py
```

4-player simultaneous contribution game.

## Centipede Game

```bash
uv run python examples/MCP/centipede_glm_vs_deepseek.py
```

Sequential TAKE/PASS with growing pots.

## Battle of the Sexes

```bash
uv run python examples/MCP/battle_of_the_sexes_glm_vs_deepseek.py
```

Coordination game with conflicting preferences.

## Cournot Duopoly

```bash
uv run python examples/MCP/cournot_duopoly_glm_vs_deepseek.py
```

Simultaneous quantity-setting game.

## Stag Hunt

```bash
uv run python examples/MCP/stag_hunt_glm_vs_deepseek.py
```

Coordination/trust game with two equilibria.

## Example Structure

All MCP examples follow this pattern:

```python
"""
ORCHESTRATOR
============
1. Create experiment via ArenaClient
2. Get session_id and player_tokens
3. Create MCPAgent for each player

AGENT
=====
1. get_observation() — Get system + turn prompts
2. Parse observation to understand game state
3. Decide action using LLM
4. submit_action() — Submit action via MCP
5. Repeat until game is terminal
6. get_results() — Get final results
"""
from nash_arena_sdk import ArenaClient, MCPAgent

# Orchestrator creates session
client = ArenaClient("http://127.0.0.1:8000/api")
created = client.create_experiment(config, api_key=api_key)

# Agents play via MCP
agent_a = MCPAgent(
    player_token=created["player_tokens"]["A"],
    mcp_url=created.get("mcp_url"),
)
agent_b = MCPAgent(
    player_token=created["player_tokens"]["B"],
    mcp_url=created.get("mcp_url"),
)

# Game loop
for round in range(config["rounds"]):
    obs_a = agent_a.get_observation()
    action_a = decide_action(obs_a)  # LLM call
    agent_a.submit_action(action_a)
    
    obs_b = agent_b.get_observation()
    action_b = decide_action(obs_b)  # LLM call
    agent_b.submit_action(action_b)

results = agent_a.get_results()
```

## Next Steps

- [REST Examples](quickstart-rest.md) — REST-based agent examples
- [SDK Guide](../sdk/mcp-agent.md) — MCPAgent documentation
- [MCP Overview](../mcp/overview.md) — MCP architecture
