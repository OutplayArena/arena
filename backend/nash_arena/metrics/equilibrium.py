from __future__ import annotations

import numpy as np


class EquilibriumMetrics:
    """Nash gap, Pareto efficiency, social welfare, and related equilibrium signals."""

    @staticmethod
    def nash_gap_nplayer(
        payoffs_per_agent: dict[str, list[float]],
        best_responses: dict[str, float] | None = None,
    ) -> dict[str, float]:
        """
        Per-agent Nash deviation gain for N players.

        Nash Gap_i = max(0, BR_i - avg_payoff_i)

        If best_responses not supplied, uses observed maximum as a conservative
        proxy (always an overestimate — gap may be 0 in reality).
        """
        gaps = {}
        for agent_id, payoffs in payoffs_per_agent.items():
            avg = float(np.mean(payoffs)) if payoffs else 0.0
            br  = (best_responses or {}).get(agent_id, max(payoffs) if payoffs else 0.0)
            gaps[agent_id] = max(0.0, br - avg)
        return gaps

    @staticmethod
    def total_nash_gap(gaps: dict[str, float]) -> float:
        """Sum of all per-agent gaps — single scalar for the whole match."""
        return sum(gaps.values())

    @staticmethod
    def pareto_efficiency(
        joint_payoffs: list[tuple[float, ...]],
        pareto_optimal_value: float | None = None,
    ) -> float:
        if not joint_payoffs:
            return 0.0
        joint_sums = [sum(p) for p in joint_payoffs]
        reference  = pareto_optimal_value or max(joint_sums)
        if reference == 0:
            return 0.0
        return float(np.mean(joint_sums) / reference)

    @staticmethod
    def social_welfare(payoffs_per_agent: dict[str, list[float]]) -> float:
        return sum(float(np.mean(v)) for v in payoffs_per_agent.values() if v)

    @staticmethod
    def social_efficiency_ratio(achieved: float, pareto_optimal: float) -> float:
        return 0.0 if pareto_optimal == 0 else min(1.0, achieved / pareto_optimal)
