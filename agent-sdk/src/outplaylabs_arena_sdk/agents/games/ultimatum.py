"""Ultimatum agent.

Dispatches on the game phase:

  - ``awaiting_proposal`` (or when the player is the proposer) &mdash; parse
    a numeric offer clamped to ``[min_offer, total]``.
  - otherwise &mdash; parse ``"accept"`` or ``"reject"``.

Both branches also read ``state["total"]`` and ``state["min_offer"]``
when present (set by the engine's ``public_state``).
"""
from __future__ import annotations

from typing import Any

from outplaylabs_arena_sdk.base import BaseAgent
from outplaylabs_arena_sdk.parsers import parse_accept_reject, parse_offer
from outplaylabs_arena_sdk.registry import register


@register("ultimatum")
class UltimatumAgent(BaseAgent):
    """Agent that plays Ultimatum, dispatching on the game phase."""

    def action_format_hint(self) -> str:
        if self._is_proposer():
            return (
                "a numeric offer as a plain number (no symbols). "
                "Example: 40 (for 40 out of 100)."
            )
        return 'either "accept" or "reject" (lowercase, plain text).'

    def parse_action(self, raw_text: str, state: dict[str, Any]) -> Any:
        if self._is_proposer():
            total = float(state.get("total") or 100.0)
            min_offer = float(state.get("min_offer") or 0.0)
            return parse_offer(raw_text, total=total, min_offer=min_offer)
        return parse_accept_reject(raw_text)

    def _is_proposer(self) -> bool:
        state = self._last_state or {}
        proposer = state.get("proposer")
        if proposer and proposer == self.player:
            return True
        if state.get("phase") == "awaiting_proposal":
            # If phase is awaiting_proposal and our player is the one
            # whose turn it is, we are the proposer.
            return self.player in (state.get("awaiting") or [])
        return False
