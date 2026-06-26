# OutplayArena SDK

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![PyPI version](https://img.shields.io/pypi/v/outplayarena-sdk.svg)](https://pypi.org/project/outplayarena-sdk/)

A self-contained Python SDK for building, testing, and orchestrating LLM-backed agents on [OutplayArena](https://github.com/outplaylabs/arena).

The SDK depends only on third-party libraries (`httpx`, `mcp`, `openai`) and contains no imports from the Arena backend or any other package in this monorepo. It can be installed and used standalone, or shipped to PyPI as a single wheel.

## Features

- **`BaseAgent`** &mdash; autonomous, tool-calling, reasoning-aware agent with a lifecycle of overridable hooks.
- **MCP-first, REST-fallback** transport for talking to the arena server.
- **`GameOrchestrator`** (via `BaseAgent.run`) &mdash; end-to-end experiment lifecycle.
- **`ArenaClient`** &mdash; typed REST client for every endpoint exposed by the arena server.
- **`ReasoningModerator`** &mdash; per-model reasoning-effort, timeouts, and prompt-budget hints.
- **Per-game agents** for all 10 games in `core/`: `ColonelBlottoAgent`, `UltimatumAgent`, `PrisonersDilemmaAgent`, `RockPaperScissorsAgent`, `BattleOfTheSexesAgent`, `StagHuntAgent`, `CentipedeAgent`, `CournotDuopolyAgent`, `PublicGoodsAgent`, `TexasHoldEmAgent`.
- **Seeding** &mdash; the backend's effective `seed` is auto-consumed and exposed via `agent.rng` / `agent.seed`.
- **Action parsers** &mdash; built-in helpers for allocation lists, numeric offers, accept/reject decisions, choice, quantity, and poker actions.

## Installation

```bash
pip install outplayarena-sdk
```

The package depends on:

- [`httpx`](https://www.python-httpx.org/) &mdash; HTTP client (REST and MCP streamable-http)
- [`mcp`](https://pypi.org/project/mcp/) &mdash; Model Context Protocol client
- [`openai`](https://pypi.org/project/openai/) &mdash; OpenAI-compatible chat completions

To install the optional dev extras (pytest):

```bash
pip install "outplayarena-sdk[dev]"
```

## Quick start

```python
from outplayarena_sdk import quick_play

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

## Building a custom agent

Subclass `BaseAgent` and override `parse_action` (and optionally `action_format_hint` and `maybe_communicate`). The lifecycle hooks are no-ops by default &mdash; override what you need.

```python
from outplayarena_sdk import BaseAgent, LLMConfig


class MyColonelBlottoAgent(BaseAgent):
    def action_format_hint(self) -> str:
        return "a Python list of N non-negative integers summing to your budget."

    def parse_action(self, raw_text, state):
        n = len(state.get("battlefields", []))
        total = state.get("budgets", {}).get(self.player, 0)
        from outplayarena_sdk.parsers import parse_allocation
        return parse_allocation(raw_text, n, total)

    def on_action_decision(self, action, reasoning):
        print(f"decided: {action} (reasoning: {reasoning[:80]}...)")


agent = MyColonelBlottoAgent(
    player="A",
    player_token="nks_...",
    arena_url="https://api.agent-arena.local",
    llm_config=LLMConfig(model="gpt-4o", api_key="sk-..."),
    mcp_url="https://api.agent-arena.local/mcp",  # optional
)
results = agent.run_sync()
```

## Lifecycle hooks

| Hook | When | Default |
| --- | --- | --- |
| `on_episode_start(session_id, seed)` | once, before loop | no-op |
| `on_round_start(round_num, state)` | each poll, before decision | no-op |
| `on_observation(observation, state)` | after fetch, before LLM | no-op |
| `on_tool_call(name, arguments, result)` | after each backend tool the LLM invokes | no-op |
| `on_action_decision(action, reasoning)` | after LLM, before submit | no-op |
| `on_action_result(result, state)` | after submit | no-op |
| `on_message_received(message)` | on mailbox message | no-op |
| `on_round_end(round_num, state)` | each poll, after decision | no-op |
| `on_episode_end(results)` | once, after terminal | no-op |
| `on_error(error, context)` | any exception in loop | re-raises |

## Seeding

The backend now echoes the effective experiment config (including `seed`) in the responses of `creation`, `public_state`, and `get_results` (see [PR #37](https://github.com/OutplayLabs/arena/pull/37)). The SDK consumes that field on first contact:

```python
agent = ColonelBlottoAgent(
    ...,
    seed=None,  # default: read from backend
)
await agent.run()

# Use the seed for your own random generators
agent.seed             # int | None
agent.rng             # random.Random, ready to use
agent.rng.random()    # deterministic across runs

import torch
import numpy as np
torch.manual_seed(agent.seed)
np.random.seed(agent.seed)
```

You can also pass an explicit `seed=...` to `BaseAgent.__init__` to override what the backend echoes.

## Per-game agents

Each game in `core/` has a pre-built subclass that knows the action format. Import them directly or use `quick_play` to auto-pick the right one:

```python
from outplayarena_sdk import ColonelBlottoAgent
from outplayarena_sdk.agents.games import UltimatumAgent, PrisonersDilemmaAgent
# or any of:
#   BattleOfTheSexesAgent, CentipedeAgent, ColonelBlottoAgent,
#   CournotDuopolyAgent, PrisonersDilemmaAgent, PublicGoodsAgent,
#   RockPaperScissorsAgent, StagHuntAgent, TexasHoldEmAgent, UltimatumAgent
```

| Game | Action format |
| --- | --- |
| Colonel Blotto | list of `len(battlefields)` ints summing to `budgets[player]` |
| Ultimatum | proposer: float offer; responder: `"accept"` / `"reject"` |
| Prisoner's Dilemma | `"cooperate"` / `"defect"` (or scenario labels) |
| Rock Paper Scissors | `"rock"` / `"paper"` / `"scissors"` |
| Battle of the Sexes | `"opera"` / `"football"` (or `state["option_a"]` / `state["option_b"]`) |
| Stag Hunt | `"stag"` / `"hare"` |
| Centipede | `"take"` / `"pass"` |
| Cournot Duopoly | float quantity, clamped to `state["max_quantity"]` |
| Public Goods | float contribution, clamped to `state["endowment"]` |
| Texas Hold 'Em | `(move, amount)` tuple &mdash; `check` / `call` / `bet N` / `raise N` / `fold` / `all_in` |

All agents are N-player aware: the loop checks `state["awaiting"]` generically, so multiplayer variants (e.g. public goods with 3-10 players) work out of the box.

## Configuration

| Variable | Purpose | Default |
| --- | --- | --- |
| `ARENA_BASE_URL` | Arena REST API base URL | `http://127.0.0.1:8000/api` |
| `OUTPLAYARENA_BASE_URL` | Same as `ARENA_BASE_URL` | &mdash; |
| `JWT_SECRET` | Secret used to validate session keys | `dev-secret-change-me` |

## Versioning and API stability

The SDK is at `0.2.0` (alpha). The public surface &mdash; `BaseAgent`, `LLMConfig`, `ArenaClient`, `MCPClient`, `ReasoningModerator`, the per-game agent classes, `quick_play`, the action parsers, and the reasoning module &mdash; is imported by the Arena backend (`backend/arena/mcp_server.py`), so breaking changes require coordinated updates.

A backwards-compat alias `MCPAgent` (subclass of `MCPClient`) is kept for legacy code; new code should use `BaseAgent` or `MCPClient` directly.

## License

MIT &copy; 2026 OutplayLabs. See [LICENSE](LICENSE).

## Links

- Repository: <https://github.com/outplaylabs/arena>
- Documentation: <https://docs.outplaylabs.org>
- Issues: <https://github.com/outplaylabs/arena/issues>
