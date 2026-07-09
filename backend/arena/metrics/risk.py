from __future__ import annotations

from typing import Any

import numpy as np


def hhi(allocation: list[int | float]) -> float:
    """Herfindahl-Hirschman Index: 0 = perfectly spread, 1 = all-in on one item."""
    total = sum(allocation)
    if total == 0:
        return 0.0
    return float(sum((x / total) ** 2 for x in allocation))


class RiskMetrics:
    """Volatility and concentration signals describing an agent's risk profile."""

    hhi = staticmethod(hhi)

    @staticmethod
    def payoff_volatility(payoffs: list[float]) -> float:
        """Standard deviation of round-by-round payoffs."""
        if not payoffs or len(payoffs) < 2:
            return 0.0
        return float(np.std(payoffs))

    @staticmethod
    def action_concentration(actions: list[Any]) -> float | None:
        """
        Mean Herfindahl-Hirschman Index across numeric-vector actions
        (e.g. Blotto allocations, Cournot quantities).

        Returns None if no actions are vector-shaped (e.g. scalar/string
        actions like Prisoner's Dilemma cooperate/defect).
        """
        vectors = [
            a for a in actions
            if isinstance(a, list) and a and all(isinstance(x, (int, float)) for x in a)
        ]
        if not vectors:
            return None
        return float(np.mean([hhi(v) for v in vectors]))
