"""Texas Hold 'Em agent.

Action: a single move name string (e.g. ``"fold"``, ``"check"``,
``"call"``, ``"raise"``). The backend's poker engine accepts only the
move name — the bet/raise amount is determined by the engine's fixed
bet size, not by the client. ``parse_action`` extracts the move name
from the LLM's text (case-insensitive, whole-word match) and falls
back to ``"fold"`` if no legal move is detected.

Legal moves are read from ``state.get("legal_moves", ...)`` when
present; otherwise defaults to a conservative set.
"""
from __future__ import annotations

from typing import Any

from outplaylabs_arena_sdk.base import BaseAgent
from outplaylabs_arena_sdk.parsers import parse_poker_action
from outplaylabs_arena_sdk.registry import register


@register("texas_hold_em")
class TexasHoldEmAgent(BaseAgent):
    """Agent that plays Texas Hold 'Em poker."""

    DEFAULT_MOVES = ("check", "call", "fold", "raise", "bet", "all_in")

    def action_format_hint(self) -> str:
        return (
            'a poker move: one of "check", "call", "fold", "raise", '
            '"bet", or "all_in" (lowercase, plain text). The engine '
            "uses a fixed bet size; you don't specify an amount."
        )

    def parse_action(self, raw_text: str, state: dict[str, Any]) -> str:
        legal = state.get("legal_moves") or list(self.DEFAULT_MOVES)
        # Make sure "fold" is always a legal fallback even if it's not
        # in the current set; agents can still choose to fold.
        if "fold" not in legal:
            legal = [*legal, "fold"]
        move, _amount = parse_poker_action(
            raw_text, legal_moves=list(legal), default_move="fold"
        )
        return move
