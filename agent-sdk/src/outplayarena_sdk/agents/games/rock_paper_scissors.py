"""Rock Paper Scissors agent."""
from __future__ import annotations

from typing import Any

from outplayarena_sdk.base import BaseAgent
from outplayarena_sdk.parsers import parse_choice
from outplayarena_sdk.registry import register


@register("rock_paper_scissors")
class RockPaperScissorsAgent(BaseAgent):
    """Agent that plays RPS."""

    OPTIONS = ("rock", "paper", "scissors")

    def action_format_hint(self) -> str:
        return 'one of "rock", "paper", or "scissors" (lowercase, plain text).'

    def parse_action(self, raw_text: str, state: dict[str, Any]) -> str:
        return parse_choice(raw_text, list(self.OPTIONS), default=self.OPTIONS[0])
