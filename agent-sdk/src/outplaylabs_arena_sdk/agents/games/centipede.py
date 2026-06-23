"""Centipede agent.

Each turn a player chooses to ``"take"`` (the running pot) or ``"pass"``
(continue to the next node).  The game is sequential: only the
``state["current_player"]`` is in ``state["awaiting"]`` at any time.
"""
from __future__ import annotations

from typing import Any

from outplaylabs_arena_sdk.base import BaseAgent
from outplaylabs_arena_sdk.parsers import parse_choice
from outplaylabs_arena_sdk.registry import register


@register("centipede")
class CentipedeAgent(BaseAgent):
    """Agent that plays Centipede."""

    OPTIONS = ("take", "pass")

    def action_format_hint(self) -> str:
        return 'either "take" (end the game and take the pot) or "pass" (continue).'

    def parse_action(self, raw_text: str, state: dict[str, Any]) -> str:
        return parse_choice(raw_text, list(self.OPTIONS), default=self.OPTIONS[1])
