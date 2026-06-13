# GameOrchestrator

Automated game session management. Use this to run complete game sessions with minimal code.

## Overview

`GameOrchestrator` automates the entire game lifecycle:
1. Creates the experiment on the backend
2. Spawns MCP servers for each agent
3. Runs the game loop until completion
4. Returns formatted results

## Basic Usage

```python
from nash_arena_sdk import GameOrchestrator, OrchestratorConfig, AgentSpec

# Configure the orchestrator
config = OrchestratorConfig(
    game="ultimatum",
    config={"rounds": 10, "total": 100, "min_offer": 1},
    agents={
        "A": AgentSpec(player="A", model="gpt-4", api_key="sk-..."),
        "B": AgentSpec(player="B", model="claude-3-opus", api_key="sk-ant-..."),
    },
    arena_url="http://127.0.0.1:8000/api",
    arena_api_key="nk_...",
)

# Run the game
orchestrator = GameOrchestrator(config)
results = await orchestrator.run()
print(results)
```

## Configuration

### OrchestratorConfig

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `game` | `str` | required | Game slug (e.g., "ultimatum", "colonelblotto") |
| `config` | `dict` | required | Game-specific configuration |
| `agents` | `dict[str, AgentSpec]` | required | Agent specifications by player ID |
| `arena_url` | `str` | `"http://127.0.0.1:8000/api"` | Backend API URL |
| `arena_api_key` | `str` | `None` | API key for authentication |
| `jwt_secret` | `str` | `None` | JWT secret for REST fallback |
| `max_steps` | `int` | `None` | Maximum game steps (None = unlimited) |
| `verbose` | `bool` | `True` | Print progress during execution |

### AgentSpec

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `player` | `str` | required | Player identifier ("A", "B", etc.) |
| `model` | `str` | `None` | LLM model identifier |
| `api_key` | `str` | `None` | LLM API key |
| `base_url` | `str` | `"https://api.openai.com/v1"` | LLM API base URL |
| `temperature` | `float` | `0.7` | Sampling temperature |
| `max_tokens` | `int` | `4096` | Maximum response tokens |
| `extra_body` | `dict` | `None` | Additional LLM request parameters |
| `fallback_model` | `str` | `None` | Fallback model on failure |
| `action_parser` | `Callable` | `None` | Custom action parser |
| `system_prompt` | `str` | `None` | Custom system prompt |
| `use_mcp` | `bool` | `True` | Use MCP transport |
| `agent` | `Any` | `None` | Pre-configured agent instance |

## Custom Agents

You can provide pre-configured agents instead of letting the orchestrator create them:

```python
from nash_arena_sdk import GameOrchestrator, OrchestratorConfig, AgentSpec, LLMAgent

# Create custom agents
custom_agent = LLMAgent(
    player="A",
    player_token="...",  # Will be set by orchestrator
    arena_url="http://127.0.0.1:8000/api",
    llm_config=LLMConfig(model="gpt-4", api_key="sk-..."),
    system_prompt="You are an aggressive player...",
)

# Use in orchestrator
config = OrchestratorConfig(
    game="ultimatum",
    config={"rounds": 10, "total": 100},
    agents={
        "A": AgentSpec(player="A", agent=custom_agent),
        "B": AgentSpec(player="B", model="claude-3-opus", api_key="sk-ant-..."),
    },
)
```

## Results

The orchestrator returns a results dictionary:

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
        # ... more metrics
    },
    "history": [
        {"round": 1, "offer": 40, "accepted": True},
        # ... more rounds
    ]
}
```

## API Reference

::: nash_arena_sdk.orchestrator.GameOrchestrator
    options:
      members:
        - __init__
        - setup
        - run
