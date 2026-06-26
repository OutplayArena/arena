"""Cournot Duopoly agent.

Action: a non-negative float quantity, clamped to
``[0, state["max_quantity"]]``.  Reads the max from state when
available.
"""
from __future__ import annotations

from typing import Any

from outplayarena_sdk.base import BaseAgent
from outplayarena_sdk.parsers import parse_quantity
from outplayarena_sdk.registry import register


@register("cournot_duopoly")
class CournotDuopolyAgent(BaseAgent):
    """Agent that plays Cournot Duopoly (production quantity)."""

    def action_format_hint(self) -> str:
        state = self._last_state or {}
        max_q = state.get("max_quantity")
        if isinstance(max_q, (int, float)):
            return f"a single non-negative number up to {max_q} (your production quantity)."
        return "a single non-negative number (your production quantity)."

    def parse_action(self, raw_text: str, state: dict[str, Any]) -> float:
        max_q = state.get("max_quantity")
        if not isinstance(max_q, (int, float)) or max_q <= 0:
            max_q = 100.0
        return parse_quantity(raw_text, max_quantity=float(max_q))
