"""Vickrey Auction agent.

Action: a non-negative float sealed bid, clamped to
``[0, state["max_bid"]]``.  Reads the max from state when available.
"""
from __future__ import annotations

from typing import Any

from outplayarena_sdk.base import BaseAgent
from outplayarena_sdk.parsers import parse_quantity
from outplayarena_sdk.registry import register


@register("vickrey_auction")
class VickreyAuctionAgent(BaseAgent):
    """Agent that plays Vickrey Auction (sealed-bid second-price auction)."""

    def action_format_hint(self) -> str:
        state = self._last_state or {}
        max_bid = state.get("max_bid")
        if isinstance(max_bid, (int, float)):
            return f"a single non-negative number up to {max_bid} (your sealed bid)."
        return "a single non-negative number (your sealed bid)."

    def parse_action(self, raw_text: str, state: dict[str, Any]) -> float:
        max_bid = state.get("max_bid")
        if not isinstance(max_bid, (int, float)) or max_bid <= 0:
            max_bid = 200.0
        return parse_quantity(raw_text, max_quantity=float(max_bid))
