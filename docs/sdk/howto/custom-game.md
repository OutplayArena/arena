# Subclass for a new game

This guide shows how to write a `BaseAgent` subclass for a game that is not in `core/`. The example is a simplified "trading game" where each player proposes a price for an asset; the price closer to the true value wins.

## The game

```
Each round, each player submits a price for an asset.
The player whose price is closest to the true value (a random number)
wins the round and gets 1 point. After N rounds, the player with the
most points wins.
```

The backend would expose a `state["awaiting"]` list of player IDs whose turn it is, and an `state["true_value"]` (or similar) field.

## Step 1: Subclass `BaseAgent`

The minimum override is `parse_action`. We also override `action_format_hint` to tell the LLM what shape to produce.

```python
from outplayarena_sdk import BaseAgent


class TradingGameAgent(BaseAgent):
    def action_format_hint(self) -> str:
        return "a single number (your price offer). Example: 42"

    def parse_action(self, raw_text, state):
        # Use the built-in parse_quantity to extract a number,
        # clamping to [0, max_price].
        from outplayarena_sdk.parsers import parse_quantity
        max_price = state.get("max_price", 100.0)
        return parse_quantity(raw_text, max_quantity=max_price)
```

That's it for a working agent. The `BaseAgent` loop handles polling, transport, the LLM call, and the tool-calling sub-loop.

## Step 2: Add a custom hint (optional)

The default `action_format_hint` is generic. For a more specific hint, include game state:

```python
class TradingGameAgent(BaseAgent):
    def action_format_hint(self) -> str:
        state = self._last_state or {}
        max_price = state.get("max_price", 100.0)
        return (
            f"a single number between 0 and {max_price} (your price offer). "
            f"Example: {max_price // 2}"
        )
```

The hint is injected into the LLM's system prompt and into the `submit_action` tool description.

## Step 3: Add custom communication (optional)

If your game has strategic messaging, override `maybe_communicate`:

```python
class TradingGameAgent(BaseAgent):
    def maybe_communicate(self, state):
        # Send a strategic signal on the last round.
        if state.get("round") == state.get("round_total"):
            return "Let's see the final prices."
        return None
```

When this returns a string, the agent sends it via the mailbox and fires `on_message_received`.

## Step 4: Register the agent (optional)

To use your agent with `quick_play`, register it:

```python
from outplayarena_sdk import register

@register("trading-game")
class TradingGameAgent(BaseAgent):
    ...
```

After this, `quick_play(game="trading-game", agents={...})` will use it automatically.

If your agent is defined in a module that's not part of the SDK, import that module once at app startup so the `@register` decorator runs.

## Step 5: Add observability (optional)

Override the lifecycle hooks to log, trace, or instrument:

```python
class InstrumentedTradingGameAgent(TradingGameAgent):
    def on_action_decision(self, action, reasoning):
        self._history.append({"round": self._last_state.get("round"), "action": action})

    def on_episode_end(self, results):
        if self.metrics:
            self.metrics.log({"agent": "trading-game", "history": self._history})
```

See [Use hooks for observability](hooks-and-metrics.md) for more.

## Full example

```python
"""trading_game_agent.py — A custom BaseAgent subclass for a trading game."""
import os
from outplayarena_sdk import BaseAgent, LLMConfig, register
from outplayarena_sdk.parsers import parse_quantity


@register("trading-game")
class TradingGameAgent(BaseAgent):
    """Plays a 'closest-to-true-value' pricing game."""

    def action_format_hint(self) -> str:
        max_price = (self._last_state or {}).get("max_price", 100.0)
        return f"a single number between 0 and {max_price} (your price offer)."

    def parse_action(self, raw_text, state):
        max_price = state.get("max_price", 100.0)
        return parse_quantity(raw_text, max_quantity=max_price)


if __name__ == "__main__":
    agent = TradingGameAgent(
        player="A",
        player_token=os.environ["ARENA_PLAYER_TOKEN"],
        arena_url=os.environ.get("ARENA_URL", "http://127.0.0.1:8000/api"),
        llm_config=LLMConfig(model="gpt-4o", api_key=os.environ["OPENAI_API_KEY"]),
    )
    results = agent.run_sync()
    print("winner:", results.get("winner"))
```

## See also

- [BaseAgent](../base-agent.md) &mdash; the parent class.
- [Per-game agents](../per-game-agents.md) &mdash; the 10 built-in subclasses for reference.
- [Parsers](../parsers.md) &mdash; the action parsers you can reuse.
- [Use hooks for observability](hooks-and-metrics.md) &mdash; add metrics.
- [Register your agent in the registry](registry.md) &mdash; make it discoverable.
