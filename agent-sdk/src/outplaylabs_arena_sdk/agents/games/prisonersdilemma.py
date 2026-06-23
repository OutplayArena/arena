"""Prisoner's Dilemma agent.

Action: one of the canonical names ``"cooperate"`` or ``"defect"``. The
backend's PD engine accepts only the canonical names regardless of
``state["scenario"]``'s human-readable labels (e.g. "Stay silent" /
"Betray"). The LLM is told the canonical names; ``parse_action`` looks
for them in the LLM's text (case-insensitive, whole-word match) and
falls back to ``"defect"`` if neither is present.
"""
from __future__ import annotations

from typing import Any

from outplaylabs_arena_sdk.base import BaseAgent
from outplaylabs_arena_sdk.parsers import parse_choice
from outplaylabs_arena_sdk.registry import register


@register("prisonersdilemma")
class PrisonersDilemmaAgent(BaseAgent):
    """Agent that plays iterated or one-shot Prisoner's Dilemma."""

    ACTIONS = ("cooperate", "defect")

    def action_format_hint(self) -> str:
        return f'either "{self.ACTIONS[0]}" or "{self.ACTIONS[1]}" (lowercase, plain text).'

    def parse_action(self, raw_text: str, state: dict[str, Any]) -> str:
        return parse_choice(raw_text, list(self.ACTIONS), default=self.ACTIONS[1])
