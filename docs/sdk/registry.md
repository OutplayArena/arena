# Registry

`outplaylabs_arena_sdk.registry` provides the `GAME_AGENTS` map and the `@register` decorator that power `quick_play` and other slug-based lookups.

## The map

```python
from outplaylabs_arena_sdk import GAME_AGENTS, supported_games, get_agent_class

# All 10 built-in per-game agents are registered automatically when
# their modules are imported (which happens via the top-level __init__).
print(supported_games())
# ['battle_of_the_sexes', 'centipede', 'colonelblotto',
#  'cournot_duopoly', 'prisonersdilemma', 'public_goods',
#  'rock_paper_scissors', 'stag_hunt', 'texas_hold_em', 'ultimatum']

# Look up by slug.
cls = get_agent_class("colonelblotto")  # → ColonelBlottoAgent
```

`get_agent_class` raises `ValueError` with a clear message if the slug is unknown:

```python
get_agent_class("nonexistent")
# ValueError: no per-game agent registered for 'nonexistent';
# supported: battle_of_the_sexes, centipede, colonelblotto, ...
```

## `@register` for your own game

If you build a custom `BaseAgent` subclass for a new game, register it so `quick_play` and `get_agent_class` can find it:

```python
from outplaylabs_arena_sdk import BaseAgent
from outplaylabs_arena_sdk.registry import register


@register("my-custom-game")
class MyCustomGameAgent(BaseAgent):
    def action_format_hint(self) -> str:
        return "the action format for my custom game"

    def parse_action(self, raw_text, state):
        return raw_text.strip()  # placeholder
```

After this decorator runs, `get_agent_class("my-custom-game")` returns `MyCustomGameAgent`, and `quick_play(game="my-custom-game", ...)` will use it automatically.

## Duplicate registration raises

Registering the same slug twice is an error &mdash; the second `@register` call raises a `ValueError` at class-creation time:

```python
@register("ultimatum")  # already taken by UltimatumAgent
class UltimatumClone(BaseAgent):
    ...
# ValueError: game 'ultimatum' already registered to UltimatumAgent
```

## When to import custom agents

The `agents/games/__init__.py` is imported by the top-level `outplaylabs_arena_sdk/__init__.py`, so the 10 built-in per-game agents are registered automatically.

For custom subclasses, **import them once at app startup** so the `@register` decorator runs before anyone calls `quick_play` or `get_agent_class`:

```python
# my_app/agents.py
from outplaylabs_arena_sdk.registry import register
from outplaylabs_arena_sdk import BaseAgent


@register("my-game")
class MyGameAgent(BaseAgent):
    ...

# main.py
import my_app.agents  # registers MyGameAgent on import
from outplaylabs_arena_sdk import quick_play

results = quick_play(game="my-game", agents={...})  # uses MyGameAgent
```

## Removing a registration (rare)

`GAME_AGENTS` is a plain `dict`, so you can remove entries in tests or when unloading a plugin:

```python
from outplaylabs_arena_sdk import GAME_AGENTS

def _unregister(slug: str) -> None:
    GAME_AGENTS.pop(slug, None)
```

This is rarely needed in practice; the registry is meant to be a one-shot setup at app startup.

## See also

- [Per-game agents](per-game-agents.md) &mdash; the 10 built-in subclasses.
- [Quick play](quick-play.md) &mdash; the high-level helper that uses the registry.
- [How-to: subclass for a new game](howto/custom-game.md) &mdash; a worked example.
