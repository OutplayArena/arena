from __future__ import annotations

import math
from collections import defaultdict
from typing import Any



class BehavioralMetrics:
    """Strategy entropy, consistency, regret, and opponent prediction accuracy."""

    @staticmethod
    def strategy_entropy(actions: list[Any]) -> float:
        if not actions:
            return 0.0
        counts: dict = defaultdict(int)
        for a in actions:
            counts[tuple(a) if isinstance(a, list) else a] += 1
        n     = len(actions)
        probs = [c / n for c in counts.values()]
        return float(-sum(p * math.log2(p) for p in probs if p > 0))

    @staticmethod
    def behavioral_consistency(actions: list[Any]) -> float:
        unique = len({tuple(a) if isinstance(a, list) else a for a in actions})
        if unique <= 1:
            return 1.0
        max_e = math.log2(unique)
        return 0.0 if max_e == 0 else 1.0 - (BehavioralMetrics.strategy_entropy(actions) / max_e)

    @staticmethod
    def regret(realized_payoffs: list[float], best_fixed_payoff: float) -> float:
        return max(0.0, best_fixed_payoff * len(realized_payoffs) - sum(realized_payoffs))

    @staticmethod
    def adaptive_regret(realized_payoffs: list[float], window: int = 10) -> list[float]:
        regrets = []
        for i in range(0, len(realized_payoffs), window):
            w = realized_payoffs[i:i+window]
            if w:
                regrets.append(max(w) * len(w) - sum(w))
        return regrets

    @staticmethod
    def opponent_prediction_accuracy(
        predicted: list[Any],
        actual: list[Any],
    ) -> float:
        if not predicted or len(predicted) != len(actual):
            return 0.0
        def norm(x):
            return tuple(x) if isinstance(x, list) else x
        return sum(1 for p, a in zip(predicted, actual) if norm(p) == norm(a)) / len(predicted)

    @staticmethod
    def per_opponent_prediction_accuracy(
        predicted_per_opp: dict[str, list[Any]],
        actual_per_opp: dict[str, list[Any]],
    ) -> dict[str, float]:
        """Theory-of-Mind score against each opponent."""
        return {
            opp: BehavioralMetrics.opponent_prediction_accuracy(
                predicted_per_opp.get(opp, []),
                actual_per_opp.get(opp, []),
            )
            for opp in actual_per_opp
        }
