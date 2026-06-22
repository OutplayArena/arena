"""Tests for :mod:`outplaylabs_arena_sdk.registry`."""
from __future__ import annotations

import pytest

from outplaylabs_arena_sdk.base import BaseAgent
from outplaylabs_arena_sdk.registry import (
    GAME_AGENTS,
    get_agent_class,
    register,
    supported_games,
)


def test_supported_games_lists_all_registered():
    games = supported_games()
    assert "ultimatum" in games
    assert "colonelblotto" in games
    assert len(games) == 10


def test_get_agent_class_returns_subclass():
    cls = get_agent_class("ultimatum")
    assert issubclass(cls, BaseAgent)


def test_get_agent_class_unknown_raises():
    with pytest.raises(ValueError, match="no per-game agent registered"):
        get_agent_class("nonexistent-game")


def test_register_duplicate_raises():
    """Re-registering the same game slug raises a clear error."""
    with pytest.raises(ValueError, match="already registered"):

        @register("ultimatum")
        class _Dupe(BaseAgent):
            pass


def test_register_new_game_succeeds():
    """The decorator is the supported extension point."""
    initial = len(GAME_AGENTS)

    @register("custom-test-game")
    class _CustomAgent(BaseAgent):
        pass

    try:
        assert "custom-test-game" in GAME_AGENTS
        assert get_agent_class("custom-test-game") is _CustomAgent
    finally:
        # Clean up so other tests aren't affected.
        del GAME_AGENTS["custom-test-game"]
    assert len(GAME_AGENTS) == initial
