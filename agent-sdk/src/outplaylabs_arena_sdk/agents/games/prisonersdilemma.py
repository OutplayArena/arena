"""Prisoner's Dilemma agent.

Action: one of the scenario's two action labels (typically
``"cooperate"`` / ``"defect"``).  Reads the exact labels from
``state["scenario"]`` when present.
"""
from __future__ import annotations

from typing import Any

from outplaylabs_arena_sdk.base import BaseAgent
from outplaylabs_arena_sdk.parsers import parse_choice
from outplaylabs_arena_sdk.registry import register


@register("prisonersdilemma")
class PrisonersDilemmaAgent(BaseAgent):
    """Agent that plays iterated or one-shot Prisoner's Dilemma."""

    def action_format_hint(self) -> str:
        scenario = (self._last_state or {}).get("scenario") or {}
        a = scenario.get("cooperate_label", "cooperate")
        b = scenario.get("defect_label", "defect")
        return f'either "{a}" or "{b}" (lowercase, plain text).'

    def parse_action(self, raw_text: str, state: dict[str, Any]) -> str:
        scenario = state.get("scenario") or {}
        a = scenario.get("cooperate_label", "cooperate")
        b = scenario.get("defect_label", "defect")
        return parse_choice(raw_text, [a, b], default=b)
