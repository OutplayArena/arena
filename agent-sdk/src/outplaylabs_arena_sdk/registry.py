"""Registry mapping game slugs to their :class:`BaseAgent` subclasses.

Used by :func:`quick_play` to auto-pick the right per-game agent class
when the user does not specify one explicitly. Also useful for callers
who want to enumerate the supported games.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from outplaylabs_arena_sdk.base import BaseAgent


GAME_AGENTS: dict[str, type["BaseAgent"]] = {}


def register(game: str):
    """Class decorator that registers a :class:`BaseAgent` subclass for a game."""

    def _wrap(cls: type["BaseAgent"]) -> type["BaseAgent"]:
        if game in GAME_AGENTS:
            raise ValueError(
                f"game {game!r} already registered to {GAME_AGENTS[game].__name__}"
            )
        GAME_AGENTS[game] = cls
        return cls

    return _wrap


def get_agent_class(game: str) -> type["BaseAgent"]:
    """Return the registered :class:`BaseAgent` subclass for *game*."""
    try:
        return GAME_AGENTS[game]
    except KeyError as exc:
        supported = ", ".join(sorted(GAME_AGENTS)) or "(none registered yet)"
        raise ValueError(
            f"no per-game agent registered for {game!r}; supported: {supported}"
        ) from exc


def supported_games() -> list[str]:
    """List the game slugs with a registered :class:`BaseAgent` subclass."""
    return sorted(GAME_AGENTS)


__all__ = ["GAME_AGENTS", "register", "get_agent_class", "supported_games"]
