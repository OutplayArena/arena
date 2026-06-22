# Build a custom agent loop

`BaseAgent` covers the common case: an autonomous LLM-powered agent that drives a complete game from start to finish. For some use cases you may want to bypass it and drive the backend directly. This guide shows when and how.

## When to bypass `BaseAgent`

| Use case | Use |
| --- | --- |
| Standard autonomous agent | `BaseAgent` |
| Real-time UI / human-in-the-loop | `BaseAgent` + custom hooks or a custom loop |
| Non-LLM experiment (e.g. fixed strategies) | `BaseAgent` with `parse_action` returning a constant |
| One-off script with no polling | `ArenaClient` directly |
| Step-by-step control of every state transition | `ArenaClient` or `AsyncBackend` |
| Custom async agent loop (e.g. multi-step reasoning across turns) | `BaseAgent` with a custom tool registry |

`BaseAgent` is optimized for the standard case. If your needs are within ±20% of the standard flow, subclass and override hooks. If your needs diverge more, build a custom loop using `ArenaClient` (sync) or `AsyncBackend` (async).

## Pattern 1: hand-rolled synchronous loop

Use `ArenaClient` when you don't need async.

```python
from outplaylabs_arena_sdk import ArenaClient


def play_game(arena_url, player_token, action_fn, max_rounds=1000):
    """Drive a game loop with a custom action function."""
    rest = ArenaClient(arena_url)
    session_id, player = rest.session_id, rest.player  # set after for_player()

    for _ in range(max_rounds):
        state = rest.get_state()
        if state.get("phase") == "complete":
            return rest.get_results()
        if player in state.get("awaiting", []):
            action = action_fn(state)
            rest.submit_action(action)
        # No async sleep needed; the loop runs as fast as the LLM/strategy decides.


def fixed_strategy(state):
    """A trivial agent: always submit the same allocation."""
    return [1] * len(state.get("battlefields", []))
```

## Pattern 2: hand-rolled async loop with `AsyncBackend`

Use `AsyncBackend` when you want `await` semantics (e.g. for real LLM calls in a custom loop).

```python
import asyncio
from outplaylabs_arena_sdk import ArenaClient, AsyncBackend


async def play_game(arena_url, player_token, decide_fn, poll_interval=1.0):
    rest = ArenaClient(arena_url, session_id=..., token=player_token)
    backend = AsyncBackend(rest, player_id="A")
    step = 0
    while step < 1000:
        state = await backend.get_state()
        if state.get("phase") == "complete":
            return await backend.get_results()
        if "A" in state.get("awaiting", []):
            obs = await backend.get_observation()
            action = await decide_fn(obs, state)
            await backend.submit_action(action)
        else:
            await asyncio.sleep(poll_interval)
        step += 1
```

## Pattern 3: extending `BaseAgent` with a custom LLM

`BaseAgent` is designed to be subclassed. To use a different LLM SDK (e.g. `anthropic`, `cohere`), override `_call_llm_with_tools` and `_call_llm_plain`:

```python
from outplaylabs_arena_sdk import ColonelBlottoAgent


class AnthropicColonelBlottoAgent(ColonelBlottoAgent):
    def __init__(self, *args, anthropic_client=None, **kwargs):
        super().__init__(*args, **kwargs)
        self._anthropic = anthropic_client

    def _call_llm_with_tools(self, messages, tools):
        # Convert OpenAI-style tools to Anthropic's format if needed.
        # (Anthropic has a similar but not identical tool schema.)
        ...
        return self._anthropic.messages.create(...)

    def _call_llm_plain(self, messages):
        ...
        return self._anthropic.messages.create(...)
```

For OpenAI-compat providers (OpenRouter, Anthropic-via-OpenAI-proxy), you can usually just point `LLMConfig.base_url` at them and use the default `BaseAgent` flow.

## Pattern 4: custom tool registry

If you want the LLM to be able to call tools that aren't part of the standard backend tool set, override `_decide_with_tools` (see [Customize the tool-calling sub-loop](tool-calling.md) for details).

## Pattern 5: human-in-the-loop

Sometimes you want a human to make the decision. Override `parse_action` to prompt the human:

```python
class HumanColonelBlottoAgent(ColonelBlottoAgent):
    def parse_action(self, raw_text, state):
        # Ignore the LLM; ask the human.
        battlefields = state.get("battlefields", [])
        budgets = state.get("budgets", {})
        n = len(battlefields)
        total = budgets.get(self.player, 0)
        print(f"\n--- round {state.get('round')} ---")
        print(f"battlefields: {battlefields}")
        print(f"budget: {total}")
        while True:
            raw = input(f"Enter {n} non-negative ints summing to {total}: ")
            try:
                from outplaylabs_arena_sdk.parsers import parse_allocation
                return parse_allocation(raw, n, total)
            except Exception as exc:
                print(f"  invalid: {exc}, try again")
```

This is a great way to evaluate LLM suggestions against your own intuition, or to debug a specific game state.

## See also

- [BaseAgent](../base-agent.md) &mdash; the high-level class.
- [Transport](../transport.md) &mdash; the `AsyncBackend` reference.
- [ArenaClient](../arena-client.md) &mdash; the synchronous REST client.
- [MCPClient](../mcp-client.md) &mdash; the synchronous MCP client.
- [Customize the tool-calling sub-loop](tool-calling.md) &mdash; for custom LLM/tool integrations.
