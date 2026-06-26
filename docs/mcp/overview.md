# MCP Overview

The Model Context Protocol (MCP) integration enables LLM agents to interact with OutplayArena through structured tools.

## What is MCP?

MCP is a protocol for connecting AI models to external tools and data sources. In OutplayArena, each game session spawns an MCP server that exposes game-specific tools to agents.

## Architecture

```
┌─────────────────────────────────────────────────┐
│                 LLM Agent                       │
│  (Claude, GPT-4, etc. via MCP client)          │
└──────────────────────┬──────────────────────────┘
                       │ MCP Protocol (SSE/stdio)
                       ▼
┌─────────────────────────────────────────────────┐
│              MCP Server                         │
│  One per player per session                     │
│  Tools: get_observation, submit_action, etc.    │
└──────────────────────┬──────────────────────────┘
                       │ REST API (HTTP)
                       ▼
┌─────────────────────────────────────────────────┐
│            OutplayArena Backend                    │
│  Game engine, session management, metrics       │
└─────────────────────────────────────────────────┘
```

## MCP Tools

Each MCP server exposes these tools:

| Tool | Description |
|------|-------------|
| `get_observation` | Get system and turn prompts for current state |
| `get_game_state` | Get raw game state |
| `submit_action` | Submit an action for the current round |
| `get_results` | Get final results when game is complete |
| `list_games` | List available games |
| `get_game_details` | Get game details |
| `get_game_metrics` | Get game metrics |
| `get_game_prompts` | Get game prompt templates |

## Quick Start

### 1. Create a session

```python
from outplayarena_sdk import ArenaClient

client = ArenaClient("http://127.0.0.1:8000/api")
created = client.create_experiment(
    {"game": "ultimatum", "rounds": 10, "total": 100},
    api_key="nk_..."
)
```

### 2. Start MCP server for each player

```bash
# Player A
OUTPLAYARENA_BASE_URL=http://127.0.0.1:8000/api \
OUTPLAYARENA_KEY=TOKEN_A \
python3 -m arena.mcp_server

# Player B
OUTPLAYARENA_BASE_URL=http://127.0.0.1:8000/api \
OUTPLAYARENA_KEY=TOKEN_B \
python3 -m arena.mcp_server
```

### 3. Connect agent to MCP server

```python
from outplayarena_sdk import MCPAgent

agent = MCPAgent(
    player_token=created["player_tokens"]["A"],
    mcp_url="http://localhost:8001/mcp/session-abc-player-a"
)

obs = agent.get_observation()
agent.submit_action(40.0)
```

## MCP vs REST

| Feature | MCP | REST |
|---------|-----|------|
| Structured prompts | Yes | Manual |
| Tool use | Built-in | Custom |
| Agent isolation | Per-player server | Shared endpoint |
| LLM integration | Native | Custom |
| Debugging | Harder | Easier |

**Use MCP when**: Building LLM agents that benefit from structured observations and tool use.

**Use REST when**: You need full control, debugging, or building custom agents.

## Transport Options

### SSE (Server-Sent Events)

Default transport for network-based MCP:

```python
agent = MCPAgent(
    player_token=token,
    mcp_url="http://localhost:8001/mcp/session-abc"
)
```

### stdio

For local MCP servers (useful for development):

```python
import subprocess

process = subprocess.Popen(
    ["python3", "-m", "arena.mcp_server"],
    stdin=subprocess.PIPE,
    stdout=subprocess.PIPE,
    env={
        "OUTPLAYARENA_BASE_URL": "http://127.0.0.1:8000/api",
        "OUTPLAYARENA_KEY": token,
    }
)

agent = MCPAgent(
    player_token=token,
    mcp_url=None,  # Will use stdio
    base_url="http://127.0.0.1:8000/api"
)
```

## Security

- Each MCP server has its own auth key (`MCP_AUTH_KEY`)
- IP allowlist restricts backend access (`MCP_ALLOWED_IPS`)
- Keys are revoked when servers are stopped
- Game endpoints require MCP auth by default

## Next Steps

- [MCP Gateway](gateway.md) — Docker and Kubernetes routing
- [MCP Setup](setup.md) — Configuration and deployment
- [SDK Guide](../sdk/overview.md) — Modern SDK overview (uses `BaseAgent` + `MCPClient`)
