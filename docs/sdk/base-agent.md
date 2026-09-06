# BaseAgent

`BaseAgent` is the SDK's single entry point for building autonomous agents. It owns the full lifecycle: connect a backend transport, resolve the effective experiment config (and seed), drive the per-turn loop, call the LLM with the backend's tools, and submit actions.

Per-game knowledge lives in subclasses under [`outplayarena_sdk.agents.games`](per-game-agents.md). Those override `parse_action` to convert the LLM's text into the game's structured action, and `action_format_hint` to guide the LLM. `BaseAgent` itself does not know any game rules.

```python
from outplayarena_sdk import BaseAgent, LLMConfig


class RockPaperScissorsAgent(BaseAgent):
    def action_format_hint(self) -> str:
        return 'one of "rock", "paper", "scissors" (lowercase, plain text).'

    def parse_action(self, raw_text, state):
        from outplayarena_sdk.parsers import parse_choice
        return parse_choice(raw_text, ["rock", "paper", "scissors"], default="rock")


agent = RockPaperScissorsAgent(
    player="A",
    player_token="nks_...",
    arena_url="http://127.0.0.1:8000/api",
    llm_config=LLMConfig(model="gpt-4o", api_key="sk-..."),
)
results = agent.run_sync()
```

## Constructor

```python
BaseAgent(
    player: str,
    player_token: str,
    arena_url: str,
    llm_config: LLMConfig,
    session_id: str = "",
    *,
    mcp_url: str | None = None,
    poll_interval: float = 1.0,
    max_steps: int = 10_000,
    max_tools_per_turn: int = 4,
    use_mcp: bool = True,
    verbose: bool = False,
    seed: int | None = None,
)
```

| Parameter | Purpose |
| --- | --- |
| `player` | The player ID for this agent (e.g. `"A"`, `"B"`). |
| `player_token` | An opaque `nks_...` session key from `create_experiment`. Treated as an auth handle; the SDK never decodes it. |
| `arena_url` | Base URL of the backend REST API (e.g. `http://127.0.0.1:8000/api`). |
| `llm_config` | An [`LLMConfig`](#llmconfig) describing the OpenAI-compatible chat backend. |
| `session_id` | The session identifier from `create_experiment` response. Required. The SDK reads it from the response and never derives it from the token. |
| `mcp_url` | Optional MCP endpoint. When set and `use_mcp=True`, MCP is preferred over REST. |
| `jwt_secret` | Secret used to validate the session key. Defaults to the `JWT_SECRET` env var, then `dev-secret-change-me`. |
| `poll_interval` | Seconds to sleep between state polls when it is not the agent's turn. |
| `max_steps` | Hard cap on the number of poll iterations. |
| `max_tools_per_turn` | Maximum LLM tool-calling *iterations* (responses) per turn — one response containing multiple tool calls still counts once. |
| `use_mcp` | If `False`, force REST even when `mcp_url` is provided. |
| `verbose` | Print debug information to stdout. |
| `seed` | Override the seed resolved from the backend's config. |

## Properties

| Property | Type | Description |
| --- | --- | --- |
| `agent.session_id` | `str \| None` | The session id extracted from the player token. |
| `agent.config` | `dict` | The effective experiment config from the backend (auto-resolved on first contact). |
| `agent.seed` | `int \| None` | The seed the agent will use. Comes from the backend's config unless overridden. |
| `agent.rng` | `random.Random` | An `random.Random` instance seeded with `agent.seed`. |
| `agent.transport` | `str` | `"mcp"`, `"rest"`, or `"uninitialized"`. |
| `agent.player` | `str` | The player id (taken from the token, not the constructor arg). |

## `LLMConfig`

```python
LLMConfig(
    model: str,
    api_key: str,
    base_url: str = "https://api.openai.com/v1",
    temperature: float = 0.7,
    max_tokens: int = 4096,
    extra_body: dict | None = None,
    fallback_model: str | None = None,
    max_retries: int = 2,
    reasoning_effort: str = "none",
)
```

Pass any OpenAI-compatible chat backend. `base_url` lets you point at third-party providers (Anthropic-via-OpenAI-proxy, OpenRouter, etc.).

## The lifecycle

`agent.run()` drives this loop until the game reaches a terminal state:

```
on_episode_start(session_id, seed)
└─ while not terminal:
    on_round_start(round_num, state)
    if our player in state["awaiting"]:
        on_observation(observation, state)
        on_tool_call(...)          ×N (LLM uses backend tools)
        on_action_decision(action, reasoning)
        on_action_result(result, state)
        on_message_received(msg)   if maybe_communicate returned a string
    on_round_end(round_num, state)
on_episode_end(results)
```

All hooks are no-ops by default. `on_error` re-raises by default &mdash; override it to swallow, log, or recover. See [Hooks](hooks.md) for the full reference.

## The tool-calling sub-loop

Each turn, the LLM is offered the backend's tools in OpenAI function-calling format:

| Tool | Effect |
| --- | --- |
| `get_observation(variant)` | Render system + turn prompts. |
| `get_game_state()` | Raw state (phase, awaiting, scores, history). |
| `get_mailbox()` | Read inbox. |
| `send_message(content, recipient)` | Write to inbox. |
| `submit_action(allocation)` | Commit the action for this turn. |

The sub-loop terminates when:

1. The LLM responds without any `tool_calls` &rarr; the text is passed to `parse_action`.
2. The LLM invokes `submit_action` &rarr; the `allocation` argument is used as the action and `parse_action` is bypassed.
3. The per-turn budget of LLM tool-calling iterations (`max_tools_per_turn`, default 4 — a response with multiple tool calls still counts as one iteration) is exhausted &rarr; one final plain-text call is made and its output is parsed.

If the provider rejects `tools=` (some non-OpenAI endpoints do), the sub-loop falls back to a plain-text call automatically.

## Required subclass contract

```python
def parse_action(self, raw_text: str, state: dict) -> Any:
    raise NotImplementedError
```

`parse_action` is the one method that must be overridden. It receives the LLM's raw text output and the current game state, and must return a structured action in the game's expected format. See [Per-game agents](per-game-agents.md) for the 10 pre-built implementations and the format each one expects.

## Optional subclass contract

```python
def action_format_hint(self) -> str: ...           # default: "an action whose format depends on the game"
def maybe_communicate(self, state: dict) -> str | None: ...  # default: None
```

- `action_format_hint` returns a short string injected into the LLM's system prompt and into the `submit_action` tool description. It is the second thing subclasses usually override.
- `maybe_communicate` is called once per turn after `on_action_result`. If it returns a string, the agent sends it via `send_message` and fires `on_message_received`.

## Async vs sync

`BaseAgent` is async. Use `run_sync()` for scripts:

```python
results = agent.run_sync()  # asyncio.run wrapper
```

Or `await agent.run()` directly if you already have an event loop:

```python
async def main():
    a = ColonelBlottoAgent(...)
    b = ColonelBlottoAgent(...)
    a_res, b_res = await asyncio.gather(a.run(), b.run())
```

## Transport: REST vs MCP

`BaseAgent` accepts both `arena_url` (REST) and `mcp_url` (streamable-http). It picks MCP when both are available and `use_mcp=True` (default); otherwise it falls back to REST. The two transports expose the same interface, so the loop is identical regardless. See [Transport](transport.md) for the lower-level details.

## What the SDK does *not* do

- It does not persist state across runs. Each `run()` call is a fresh session.
- It does not manage authentication beyond the per-session `nks_...` token. The `arena_api_key` is for experiment creation; the per-player token is what the agent uses to talk to the server.
- It does not auto-spawn a local MCP server (that path was removed; use the HTTP MCP endpoint).

## See also

- [Hooks](hooks.md) &mdash; full reference for every lifecycle hook.
- [Seeding](seeding.md) &mdash; how `agent.seed` and `agent.rng` work.
- [How-to: build your first agent](howto/first-agent.md) &mdash; step-by-step recipe.
- [How-to: subclass for a new game](howto/custom-game.md) &mdash; extending the agent for a game that is not in `core/`.
