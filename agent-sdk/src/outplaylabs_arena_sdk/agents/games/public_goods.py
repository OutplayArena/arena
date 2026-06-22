"""Public Goods agent.

Action: a non-negative float contribution, clamped to
``[0, state["endowment"]]``.
"""
from __future__ import annotations

from typing import Any

from outplaylabs_arena_sdk.base import BaseAgent
from outplaylabs_arena_sdk.parsers import parse_quantity
from outplaylabs_arena_sdk.registry import register


@register("public_goods")
class PublicGoodsAgent(BaseAgent):
    """Agent that plays Public Goods (contribution to a shared pool)."""

    def action_format_hint(self) -> str:
        state = self._last_state or {}
        endowment = state.get("endowment")
        if isinstance(endowment, (int, float)):
            return (
                f"a single non-negative number up to {endowment} (your "
                "contribution to the public pool)."
            )
        return "a single non-negative number (your contribution to the public pool)."

    def parse_action(self, raw_text: str, state: dict[str, Any]) -> float:
        endowment = state.get("endowment")
        if not isinstance(endowment, (int, float)) or endowment <= 0:
            endowment = 20.0
        return parse_quantity(raw_text, max_quantity=float(endowment))
