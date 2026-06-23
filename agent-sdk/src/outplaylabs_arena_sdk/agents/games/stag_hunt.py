"""Stag Hunt agent."""
from __future__ import annotations

from typing import Any

from outplaylabs_arena_sdk.base import BaseAgent
from outplaylabs_arena_sdk.parsers import parse_choice
from outplaylabs_arena_sdk.registry import register


@register("stag_hunt")
class StagHuntAgent(BaseAgent):
    """Agent that plays Stag Hunt."""

    OPTIONS = ("stag", "hare")

    def action_format_hint(self) -> str:
        return 'either "stag" or "hare" (lowercase, plain text).'

    def parse_action(self, raw_text: str, state: dict[str, Any]) -> str:
        return parse_choice(raw_text, list(self.OPTIONS), default=self.OPTIONS[0])
