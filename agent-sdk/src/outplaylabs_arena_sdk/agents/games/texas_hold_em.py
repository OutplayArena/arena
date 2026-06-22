"""Texas Hold 'Em agent.

Action: a ``(move, amount)`` tuple.  ``amount`` is ``0.0`` for
non-betting moves (``check``, ``call``, ``fold``, ``all_in``) and
parsed from the LLM text for ``bet`` / ``raise``.

Legal moves are read from ``state.get("legal_moves", ...)`` when
present; otherwise defaults to a conservative set. The agent
falls back to ``fold`` if the LLM response is unparseable.
"""
from __future__ import annotations

from typing import Any

from outplaylabs_arena_sdk.base import BaseAgent
from outplaylabs_arena_sdk.parsers import parse_poker_action
from outplaylabs_arena_sdk.registry import register


@register("texas_hold_em")
class TexasHoldEmAgent(BaseAgent):
    """Agent that plays Texas Hold 'Em poker."""

    DEFAULT_MOVES = ("check", "call", "fold", "bet", "raise", "all_in")

    def action_format_hint(self) -> str:
        return (
            'a poker move: one of "check", "call", "fold", "bet N", '
            '"raise N", or "all_in". For "bet" and "raise", follow the '
            "word with a space and the amount."
        )

    def parse_action(self, raw_text: str, state: dict[str, Any]) -> tuple[str, float]:
        legal = state.get("legal_moves") or list(self.DEFAULT_MOVES)
        # Make sure "fold" is always a legal fallback even if it's not
        # in the current set; agents can still choose to fold.
        if "fold" not in legal:
            legal = [*legal, "fold"]
        return parse_poker_action(raw_text, legal_moves=list(legal), default_move="fold")
