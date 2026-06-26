"""Stag Hunt agent."""
from __future__ import annotations

from typing import Any

from outplayarena_sdk.base import BaseAgent
from outplayarena_sdk.parsers import parse_choice
from outplayarena_sdk.registry import register


@register("stag_hunt")
class StagHuntAgent(BaseAgent):
    """Agent that plays Stag Hunt."""

    OPTIONS = ("stag", "hare")

    def action_format_hint(self) -> str:
        return 'either "stag" or "hare" (lowercase, plain text).'

    def parse_action(self, raw_text: str, state: dict[str, Any]) -> str:
        return parse_choice(raw_text, list(self.OPTIONS), default=self.OPTIONS[0])
