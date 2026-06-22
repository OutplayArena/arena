"""Battle of the Sexes agent.

Reads the two option labels from ``state["option_a"]`` and
``state["option_b"]`` when present; falls back to ``"opera"`` /
``"football"``.
"""
from __future__ import annotations

from typing import Any

from outplaylabs_arena_sdk.base import BaseAgent
from outplaylabs_arena_sdk.parsers import parse_choice
from outplaylabs_arena_sdk.registry import register


@register("battle_of_the_sexes")
class BattleOfTheSexesAgent(BaseAgent):
    """Agent that plays Battle of the Sexes."""

    def action_format_hint(self) -> str:
        state = self._last_state or {}
        a = state.get("option_a", "opera")
        b = state.get("option_b", "football")
        return f'either "{a}" or "{b}" (lowercase, plain text).'

    def parse_action(self, raw_text: str, state: dict[str, Any]) -> str:
        a = state.get("option_a", "opera")
        b = state.get("option_b", "football")
        return parse_choice(raw_text, [a, b], default=a)
