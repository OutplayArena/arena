"""Colonel Blotto agent.

Action: a Python list of exactly ``len(state["battlefields"])`` non-negative
integers summing to ``state["budgets"][self.player]``.
"""
from __future__ import annotations

from typing import Any

from outplayarena_sdk.base import BaseAgent
from outplayarena_sdk.parsers import parse_allocation
from outplayarena_sdk.registry import register


@register("colonelblotto")
class ColonelBlottoAgent(BaseAgent):
    """Agent that plays Colonel Blotto.

    Reads ``state["battlefields"]`` and ``state["budgets"][self.player]`` to
    size the allocation list, then falls back to a balanced default if the
    LLM response is unparseable.
    """

    def action_format_hint(self) -> str:
        n = len((self._last_state or {}).get("battlefields", []) or [])
        budget = ((self._last_state or {}).get("budgets") or {}).get(self.player)
        if n and budget is not None:
            return (
                f"a Python list of exactly {n} non-negative integers "
                f"summing to {budget}. Example: [{budget // n}] * {n}."
            )
        return (
            "a Python list of N non-negative integers summing to your total "
            "budget, where N equals the number of battlefields."
        )

    def parse_action(self, raw_text: str, state: dict[str, Any]) -> list[int]:
        battlefields = state.get("battlefields") or []
        budgets = state.get("budgets") or {}
        n_fields = len(battlefields) if isinstance(battlefields, list) else 0
        total = budgets.get(self.player) if isinstance(budgets, dict) else None
        if not n_fields or total is None:
            return []
        return parse_allocation(raw_text, n_fields, total)
