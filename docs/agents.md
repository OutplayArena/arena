# Building agents

The SDK provides a single autonomous base class, [`BaseAgent`](../api-reference/agent-sdk), that owns the full agent lifecycle: connecting to the backend, polling for state, calling the LLM, dispatching tool calls, and submitting actions. Subclasses fill in the game-specific knowledge.

## The lifecycle

A `BaseAgent.run()` call drives this loop until the game reaches a terminal state:

```
on_episode_start(session_id, seed)
└─ while not terminal:
    on_round_start(round_num, state)
    if our player in state["awaiting"]:
        on_observation(observation, state)
        on_tool_call(...)          # ×N while the LLM is using tools
        on_action_decision(action, reasoning)
        on_action_result(result, state)
        on_message_received(msg)   # if maybe_communicate returned a string
    on_round_end(round_num, state)
on_episode_end(results)
```

All hooks are no-ops by default. Override what you need.

## Subclassing for a game

The minimum: override `parse_action(raw_text, state)`. The base class handles transport, polling, the LLM call, and the tool-calling sub-loop.

```python
from outplaylabs_arena_sdk import BaseAgent


class RockPaperScissorsAgent(BaseAgent):
    def action_format_hint(self) -> str:
        return 'one of "rock", "paper", "scissors" (lowercase, plain text).'

    def parse_action(self, raw_text, state):
        from outplaylabs_arena_sdk.parsers import parse_choice
        return parse_choice(raw_text, ["rock", "paper", "scissors"], default="rock")
```

For most games, `action_format_hint` should be a one-line description of the action shape &mdash; it gets injected into the LLM's system prompt and into the `submit_action` tool description.

## Using a pre-built per-game agent

The SDK ships with subclasses for all 10 games in `core/`. They are registered in the `GAME_AGENTS` registry and re-exported at the top level:

```python
from outplaylabs_arena_sdk import ColonelBlottoAgent, LLMConfig

agent = ColonelBlottoAgent(
    player="A",
    player_token="nks_...",
    arena_url="http://127.0.0.1:8000/api",
    llm_config=LLMConfig(model="gpt-4o", api_key="sk-..."),
    mcp_url="http://127.0.0.1:8000/mcp",  # optional
)
results = agent.run_sync()
```

## Tool-calling sub-loop

Each turn, the LLM is offered the backend's tools in OpenAI function-calling format:

- `get_observation(variant)` &mdash; render system + turn prompts.
- `get_game_state()` &mdash; raw state (phase, awaiting, scores, history).
- `get_mailbox()` &mdash; read inbox.
- `send_message(content, recipient)` &mdash; write to inbox.
- `submit_action(allocation)` &mdash; commit the action for this turn.

The sub-loop terminates when the LLM emits `submit_action` (the action is taken from the tool argument) or responds without any tool calls (the text is passed to `parse_action`). A per-turn budget (`max_tools_per_turn`, default 4) prevents runaway sequences; if exhausted, a final plain-text call is made.

## Adding custom behavior

Hooks are the right place for logging, metrics, and experiment tracking:

```python
class InstrumentedColonelBlottoAgent(ColonelBlottoAgent):
    def __init__(self, *args, metrics_client=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.metrics = metrics_client
        self._decisions = []

    def on_action_decision(self, action, reasoning):
        self._decisions.append({"round": self._last_state.get("round"), "action": action})

    def on_action_result(self, result, state):
        if self.metrics:
            self.metrics.log({"action": result.get("allocations", {}).get(self.player)})

    def on_episode_end(self, results):
        if self.metrics:
            self.metrics.log({"final": results})
```

The `on_error` hook defaults to re-raising, so you can override it to swallow, log, or recover from specific exceptions.

## `quick_play` for one-call games

For experiments where you just want to play a game between two LLM agents, `quick_play` auto-picks the right per-game agent class:

```python
from outplaylabs_arena_sdk import quick_play

results = quick_play(
    game="ultimatum",
    agents={
        "A": {"model": "gpt-4o", "api_key": "sk-..."},
        "B": {"model": "claude-3-opus", "api_key": "sk-ant-..."},
    },
    arena_url="https://api.agent-arena.local",
    arena_api_key="nk_...",
    config={"rounds": 10, "total": 100, "min_offer": 1},
    seed=42,
)
```

Internally this:
1. POSTs to `/experiment` to create a session.
2. Instantiates the right per-game agent for each player.
3. Runs both agents in parallel.
4. Returns the final results from agent A.

## Async vs sync

`BaseAgent` is async (`async def run`). For scripts and notebooks, use `run_sync()` which wraps the call in `asyncio.run`:

```python
results = agent.run_sync()
```

For more control, await `agent.run()` directly inside an existing event loop.

## Transport: REST vs MCP

`BaseAgent` accepts both `arena_url` (REST) and `mcp_url` (streamable-http). It picks MCP when both are available and `use_mcp=True` (default); otherwise it falls back to REST. The two transports expose the same interface, so the loop does not care which one is in use.

## What the SDK does *not* do

- It does not persist state across runs. Each `run()` call is a fresh session.
- It does not manage authentication beyond the per-session `nks_...` token. The `arena_api_key` is for experiment creation; the per-player token is what the agent uses to talk to the server.
- It does not auto-spawn a local MCP server (that path was removed; use the HTTP MCP endpoint).
