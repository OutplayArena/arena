# LLMAgent

LLM-powered agent that can play via MCP or REST. Includes built-in reasoning control and action parsing.

## Overview

`LLMAgent` wraps an LLM to automatically generate actions from game observations. It handles:
- Prompt construction from observations
- LLM API calls with configurable parameters
- Action parsing from LLM output
- Reasoning control (budget, effort levels)
- MCP server lifecycle management

## Basic Usage

```python
from outplaylabs_arena_sdk import LLMAgent, LLMConfig

# Configure the LLM
llm_config = LLMConfig(
    model="gpt-4",
    api_key="sk-...",
    base_url="https://api.openai.com/v1",
    temperature=0.7,
    max_tokens=4096,
)

# Create the agent
agent = LLMAgent(
    player="A",
    player_token="nks_...",
    arena_url="http://127.0.0.1:8000/api",
    llm_config=llm_config,
    use_mcp=True,  # Use MCP if available
)

# Start MCP server (if using MCP)
await agent.start_mcp()

# Get observation and generate action
obs = await agent.get_observation()
state = await agent.get_game_state()
action = agent.act(obs, state)

# Submit the action
await agent.submit_action(action)

# Cleanup
await agent.stop_mcp()
```

## Configuration

### LLMConfig

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `model` | `str` | required | Model identifier (e.g., "gpt-4", "claude-3-opus") |
| `api_key` | `str` | required | API key for the LLM provider |
| `base_url` | `str` | `"https://api.openai.com/v1"` | API base URL |
| `temperature` | `float` | `0.7` | Sampling temperature |
| `max_tokens` | `int` | `4096` | Maximum response tokens |
| `extra_body` | `dict` | `None` | Additional request body parameters |
| `fallback_model` | `str` | `None` | Fallback model on failure |
| `max_retries` | `int` | `2` | Number of retries on failure |
| `reasoning_effort` | `ReasoningEffort` | `NONE` | Reasoning control level |

### LLMAgentConfig

For more advanced configuration:

```python
from outplaylabs_arena_sdk import LLMAgent, LLMConfig, LLMAgentConfig

config = LLMAgentConfig(
    player="A",
    llm=LLMConfig(model="gpt-4", api_key="sk-..."),
    action_parser=custom_parser,  # Custom action parsing
    system_prompt="You are a strategic player...",  # Custom system prompt
    use_mcp=True,
)

agent = LLMAgent.from_config(config, player_token="nks_...", arena_url="...")
```

## Action Parsing

Built-in parsers for common action formats:

```python
from outplaylabs_arena_sdk import parse_allocation, parse_offer, parse_accept_reject

# Parse list allocation (e.g., Colonel Blotto)
allocation = parse_allocation("[10, 0, 0]", n_fields=3, total=10)

# Parse numeric offer (e.g., Ultimatum)
offer = parse_offer("I offer 40 tokens", total=100, min_offer=1)

# Parse accept/reject (e.g., Ultimatum responder)
decision = parse_accept_reject("I accept the offer")
```

## Reasoning Control

Control how much the LLM reasons before acting:

```python
from outplaylabs_arena_sdk import LLMConfig, ReasoningEffort

config = LLMConfig(
    model="gpt-4",
    api_key="sk-...",
    reasoning_effort=ReasoningEffort.HIGH,  # NONE, LOW, MEDIUM, HIGH
)
```

See [Reasoning Control](reasoning.md) for details on how this works across different models.

## API Reference

::: outplaylabs_arena_sdk.llm_agent.LLMAgent
    options:
      members:
        - __init__
        - start_mcp
        - stop_mcp
        - get_observation
        - get_game_state
        - submit_action
        - get_results
        - call_llm
        - act
