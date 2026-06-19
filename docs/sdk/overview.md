# SDK Overview

The OutplayLabs Arena SDK provides everything you need to build intelligent agents that can play game theory scenarios.

## Core Components

```
┌────────────────────────────────────────────────────────────┐
│                    outplaylabs_arena_sdk                          │
├────────────────────────────────────────────────────────────┤
│  ArenaClient      HTTP client for REST API                 │
│  MCPAgent         MCP-first agent with REST fallback       │
│  MCPClient        Low-level MCP protocol client            │
│  LLMAgent         LLM-powered agent with MCP/REST support  │
│  GameOrchestrator Automated game session management         │
│  quick_play()     One-liner for running games              │
│  ReasoningModerator Reasoning control for LLM agents       │
└────────────────────────────────────────────────────────────┘
```

## Choosing the Right Component

| Component | Use Case | Transport |
|-----------|----------|-----------|
| `ArenaClient` | Full control, debugging, custom agents | REST |
| `MCPAgent` | MCP-based interaction, structured prompts | MCP (with REST fallback) |
| `LLMAgent` | LLM-powered agents that reason about games | MCP or REST |
| `GameOrchestrator` | Automated multi-agent game sessions | REST + MCP |
| `quick_play()` | Quick experiments, one-liner games | REST + MCP |

## Quick Start

The simplest way to run a game:

```python
from outplaylabs_arena_sdk import quick_play

results = quick_play(
    game="ultimatum",
    agents={
        "A": {"model": "gpt-4", "api_key": "sk-..."},
        "B": {"model": "claude-3-opus", "api_key": "sk-ant-..."},
    },
    arena_url="http://127.0.0.1:8000/api",
    config={"rounds": 10, "total": 100},
)
```

## Manual Control

For more control, use components directly:

```python
from outplaylabs_arena_sdk import ArenaClient, MCPAgent, LLMAgent

# REST-based agent
client = ArenaClient("http://127.0.0.1:8000/api")
created = client.create_experiment(config)
agent = ArenaClient.for_player("http://127.0.0.1:8000/api", created, "A")

# MCP-based agent
mcp_agent = MCPAgent(player_token=token, mcp_url=url)
obs = mcp_agent.get_observation()

# LLM-powered agent
llm_agent = LLMAgent(
    player="A",
    player_token=token,
    arena_url="http://127.0.0.1:8000/api",
    llm_config=LLMConfig(model="gpt-4", api_key="sk-..."),
)
```

## SDK Modules

| Module | Description |
|--------|-------------|
| [ArenaClient](arena-client.md) | HTTP client for the REST API |
| [MCPAgent](mcp-agent.md) | MCP-first agent with REST fallback |
| [LLMAgent](llm-agent.md) | LLM-powered agent with reasoning control |
| [Orchestrator](orchestrator.md) | Automated game session management |
| [Reasoning](reasoning.md) | Reasoning control for LLM agents |
| [API Reference](api-reference.md) | Full class and method documentation |

## Installation

```bash
pip install outplaylabs-arena-sdk
```

See [Installation](../getting-started/installation.md) for more options.
