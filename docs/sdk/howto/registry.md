# Register your agent in the registry

If you build a custom `BaseAgent` subclass and want `quick_play` to find it by game slug, register it with `@register`.

## Basic registration

```python
from outplayarena_sdk import BaseAgent
from outplayarena_sdk.registry import register


@register("trading-game")
class TradingGameAgent(BaseAgent):
    def action_format_hint(self) -> str:
        return "a single number (your price offer)"

    def parse_action(self, raw_text, state):
        from outplayarena_sdk.parsers import parse_quantity
        return parse_quantity(raw_text, max_quantity=state.get("max_price", 100.0))
```

After the decorator runs, `quick_play(game="trading-game", ...)` will instantiate `TradingGameAgent` automatically.

## Where to put the registration

The decorator runs at class-creation time. **Import your agent module once at app startup** so the registration is in effect before anyone calls `quick_play`.

### In a single file

If the agent is in `my_agents.py` and you only have one app, just import it at the top of `main.py`:

```python
# main.py
import my_agents  # noqa: F401  - registers MyAgent on import

from outplayarena_sdk import quick_play
results = quick_play(game="my-game", agents={...})
```

### In a package

If you have multiple custom agents in a package, expose them via `__init__.py`:

```python
# my_agents/__init__.py
from .trading import TradingGameAgent     # registers on import
from .auction import AuctionGameAgent     # registers on import
```

Then `import my_agents` once at startup.

## Duplicate registration is an error

Registering the same slug twice raises `ValueError` at class creation:

```python
@register("trading-game")
class TradingGameAgent(BaseAgent):
    ...

@register("trading-game")  # ValueError: game 'trading-game' already registered
class TradingGameAgentV2(BaseAgent):
    ...
```

If you really need to replace a registration (e.g. in a test), remove the old entry first:

```python
from outplayarena_sdk import GAME_AGENTS

@register("trading-game")
class TradingGameAgent(BaseAgent):
    ...

# In a test:
GAME_AGENTS.pop("trading-game", None)

@register("trading-game")
class FakeTradingGameAgent(BaseAgent):
    ...
```

## Looking up agents

```python
from outplayarena_sdk import GAME_AGENTS, get_agent_class, supported_games

# List every registered game
print(supported_games())
# ['battle_of_the_sexes', 'centipede', 'colonelblotto', ..., 'ultimatum', 'trading-game']

# Look up by slug
cls = get_agent_class("trading-game")
# → <class 'TradingGameAgent'>

# Check if a slug is registered
if "trading-game" in GAME_AGENTS:
    cls = GAME_AGENTS["trading-game"]
```

`get_agent_class` raises `ValueError` with a clear message for unknown slugs:

```python
get_agent_class("nonexistent")
# ValueError: no per-game agent registered for 'nonexistent';
# supported: battle_of_the_sexes, centipede, colonelblotto, ..., trading-game, ultimatum
```

## Unregistering

`GAME_AGENTS` is a plain `dict`. To remove an entry (rare):

```python
GAME_AGENTS.pop("trading-game", None)
```

## See also

- [Registry](../registry.md) &mdash; full reference for `GAME_AGENTS`, `register`, `get_agent_class`, `supported_games`.
- [Subclass for a new game](custom-game.md) &mdash; write the agent first.
- [Quick play](../quick-play.md) &mdash; the helper that uses the registry.
