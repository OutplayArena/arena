# OutplayLabs Arena SDK

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![PyPI version](https://img.shields.io/pypi/v/outplaylabs-arena-sdk.svg)](https://pypi.org/project/outplaylabs-arena-sdk/)

A self-contained Python SDK for building, testing, and orchestrating LLM-backed agents on [OutplayLabs Arena](https://github.com/outplaylabs/arena).

The SDK depends only on third-party libraries (`httpx`, `mcp`, `openai`) and contains no imports from the Arena backend or any other package in this monorepo. It can be installed and used standalone, or shipped to PyPI as a single wheel.

## Features

- **Zero project coupling** &mdash; no imports from the Arena backend; only third-party runtime dependencies.
- **MCP-first, REST-fallback** transport for talking to the arena server.
- **`quick_play`** &mdash; one-call helper to spin up a game between two LLM agents.
- **`LLMAgent`** &mdash; full async LLM agent with retries, fallback models, and reasoning control.
- **`GameOrchestrator`** &mdash; end-to-end experiment lifecycle (create &rarr; play &rarr; collect &rarr; teardown).
- **`ArenaClient`** &mdash; typed REST client for every endpoint exposed by the arena server.
- **`ReasoningModerator`** &mdash; per-model reasoning-effort, timeouts, and prompt-budget hints.
- **Action parsers** &mdash; built-in helpers for allocation lists, numeric offers, and accept/reject decisions.

## Installation

```bash
pip install outplaylabs-arena-sdk
```

The package depends on:

- [`httpx`](https://www.python-httpx.org/) &mdash; HTTP client (REST and MCP streamable-http)
- [`mcp`](https://pypi.org/project/mcp/) &mdash; Model Context Protocol client
- [`openai`](https://pypi.org/project/openai/) &mdash; OpenAI-compatible chat completions

To install the optional dev extras (pytest):

```bash
pip install "outplaylabs-arena-sdk[dev]"
```

## Quick start

```python
from outplaylabs_arena_sdk import quick_play

results = quick_play(
    game="ultimatum",
    agents={
        "A": {"model": "gpt-4", "api_key": "sk-...", "base_url": "https://api.openai.com/v1"},
        "B": {"model": "claude-3-opus", "api_key": "sk-ant-..."},
    },
    arena_url="https://api.agent-arena.local",
    arena_api_key="nk_...",
    config={"rounds": 10, "total": 100, "min_offer": 1},
)
print(results)
```

## Core concepts

### `ArenaClient` &mdash; typed REST client

`ArenaClient` is a thin wrapper around the Arena HTTP API. It supports session creation, action submission, state queries, result collection, game metadata, observations, mailbox access, and the agent manifest endpoint.

```python
from outplaylabs_arena_sdk import ArenaClient

client = ArenaClient("http://127.0.0.1:8000/api")
created = client.create_experiment(
    {"game": "ultimatum", "rounds": 10, "total": 100},
    api_key="nk_...",
)
agent_a = ArenaClient.for_player("http://127.0.0.1:8000/api", created, "A")
state = agent_a.get_state()
agent_a.submit_action(40.0)
```

### `MCPAgent` and `RESTAgent` &mdash; transport-aware agents

`MCPAgent` connects to the arena over MCP (streamable-http) when an MCP URL is available, and falls back to REST otherwise. `RESTAgent` always uses HTTP.

```python
from outplaylabs_arena_sdk import MCPAgent

with MCPAgent(
    player_token=created["player_tokens"]["A"],
    mcp_url=created.get("mcp_url"),
    base_url="http://127.0.0.1:8000/api",
) as agent:
    obs = agent.get_observation()
    agent.submit_action([5, 3, 2])
    results = agent.get_results()
```

### `LLMAgent` &mdash; LLM-powered agent

`LLMAgent` wraps an OpenAI-compatible chat backend, supports retries and a fallback model, and is reasoning-aware via the `ReasoningModerator`.

```python
from outplaylabs_arena_sdk import LLMAgent, LLMConfig

agent = LLMAgent(
    player="A",
    player_token=created["player_tokens"]["A"],
    arena_url="http://127.0.0.1:8000/api",
    llm_config=LLMConfig(model="gpt-4o", api_key="sk-..."),
    action_parser=lambda text, state: [int(x) for x in text.strip("[]").split(",")],
)
```

### `GameOrchestrator` &mdash; end-to-end experiment runner

`GameOrchestrator` runs the whole loop: create an experiment, build agents, drive turns until completion, fetch final results, and tear down MCP connections.

```python
from outplaylabs_arena_sdk import (
    AgentSpec,
    GameOrchestrator,
    OrchestratorConfig,
)

config = OrchestratorConfig(
    game="colonel_blotto",
    config={"n_fields": 5, "total_troops": 100},
    agents={
        "player_0": AgentSpec(player="player_0", model="gpt-4o"),
        "player_1": AgentSpec(player="player_1", model="gpt-4o-mini"),
    },
    arena_url="http://127.0.0.1:8000/api",
    arena_api_key="nk_...",
)

results = await GameOrchestrator(config).run()
```

### Action parsers

Built-in parsers turn raw LLM text into structured game actions:

| Parser | Game | Output |
| --- | --- | --- |
| `parse_allocation(text, n_fields, total)` | Colonel Blotto | `list[int]` of length `n_fields` summing to `total` |
| `parse_offer(text, total, min_offer=0.0)` | Ultimatum | `float` clamped to `[min_offer, total]` |
| `parse_accept_reject(text)` | Ultimatum | `"accept"` or `"reject"` |

All parsers fall back to a safe default if the LLM response is unparseable.

### Reasoning control

`ReasoningModerator` selects the right reasoning-control mechanism for a given model and lets you cap `max_tokens` and timeouts by effort level.

```python
from outplaylabs_arena_sdk.reasoning import (
    ReasoningEffort,
    ReasoningModerator,
)

mod = ReasoningModerator("gpt-5", effort=ReasoningEffort.LOW)
api_params = mod.get_api_params()       # {"reasoning_effort": "low"}
limits = mod.get_limits()               # {"max_tokens": ..., "timeout": ...}
prompt = mod.build_system_prompt("...") # possibly augmented with budget hints
```

The SDK ships with profiles for major models from OpenAI, Anthropic, Google, DeepSeek, Mistral, Meta, Cohere, Alibaba (Qwen), Zhipu (GLM), Moonshot (Kimi), Xiaomi (MiMo), and MiniMax. Unknown models fall back to a safe default profile using prompt-level budget hints.

## Configuration

| Variable | Purpose | Default |
| --- | --- | --- |
| `ARENA_BASE_URL` | Arena REST API base URL | `http://127.0.0.1:8000/api` |
| `OUTPLAYLABS_ARENA_BASE_URL` | Same as `ARENA_BASE_URL` (used by the backend) | &mdash; |
| `JWT_SECRET` | Secret used to validate session keys | `dev-secret-change-me` |
| `OUTPLAYLABS_ARENA_KEY` | Used when the SDK spawns a local MCP server via stdio | &mdash; |

## Versioning and API stability

The SDK is currently at `0.1.0` (alpha). The public surface &mdash; `ArenaClient`, `MCPAgent`, `RESTAgent`, `LLMAgent`, `LLMConfig`, `AgentSpec`, `GameOrchestrator`, `OrchestratorConfig`, `quick_play`, the action parsers, and the reasoning module &mdash; is imported by the Arena backend, so breaking changes require coordinated updates.

## License

MIT &copy; 2026 OutplayLabs. See [LICENSE](LICENSE).

## Links

- Repository: <https://github.com/outplaylabs/arena>
- Documentation: <https://docs.outplaylabs.org>
- Issues: <https://github.com/outplaylabs/arena/issues>
