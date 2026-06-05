from __future__ import annotations

from itertools import combinations
from typing import Any

import numpy as np


class CooperativeMetrics:
    """
    Pairwise and multilateral cooperation signals for repeated games.

    All pairwise signals are computed against every opponent and returned as
    {opponent_id: value} dicts. A summary scalar (mean across opponents) is
    also provided for convenience.
    """

    # ── binary action helpers ────────────────────────────────────────────────

    @staticmethod
    def _to_binary(actions: list[Any]) -> list[int]:
        _STR_MAP = {"cooperate": 1, "cooperated": 1, "defect": 0, "defected": 0}
        return [
            _STR_MAP[a] if isinstance(a, str) else int(a)
            for a in actions
        ]

    # ── unconditional ────────────────────────────────────────────────────────

    @staticmethod
    def cooperation_rate(actions: list[int]) -> float:
        return float(np.mean(actions)) if actions else 0.0

    # ── pairwise signals ─────────────────────────────────────────────────────

    @staticmethod
    def conditional_cooperation_rates(
        own_actions: list[int],
        opponents_actions: dict[str, list[int]],
    ) -> dict[str, dict[str, float]]:
        """
        Conditional cooperation rate against each opponent.
        Returns {opp_id: {"after_cooperate": float, "after_defect": float}}
        """
        results = {}
        for opp_id, opp_acts in opponents_actions.items():
            if len(own_actions) < 2 or len(opp_acts) < 2:
                results[opp_id] = {"after_cooperate": 0.0, "after_defect": 0.0}
                continue
            after_c = [own_actions[i] for i in range(1, len(own_actions)) if opp_acts[i-1] == 1]
            after_d = [own_actions[i] for i in range(1, len(own_actions)) if opp_acts[i-1] == 0]
            results[opp_id] = {
                "after_cooperate": float(np.mean(after_c)) if after_c else 0.0,
                "after_defect":    float(np.mean(after_d)) if after_d else 0.0,
            }
        return results

    @staticmethod
    def tit_for_tat_adherence(
        own_actions: list[int],
        opponents_actions: dict[str, list[int]],
    ) -> dict[str, float]:
        """
        TfT adherence vs. each opponent. In N-player games, TfT is defined
        against each opponent independently.
        Returns {opp_id: adherence_fraction}.
        """
        results = {}
        for opp_id, opp_acts in opponents_actions.items():
            if not own_actions:
                results[opp_id] = 0.0
                continue
            consistent = int(own_actions[0] == 1)  # TfT opens with cooperation
            for i in range(1, len(own_actions)):
                if i < len(opp_acts) and own_actions[i] == opp_acts[i-1]:
                    consistent += 1
            results[opp_id] = consistent / len(own_actions)
        return results

    @staticmethod
    def forgiveness_index(
        own_actions: list[int],
        opponents_actions: dict[str, list[int]],
    ) -> dict[str, float]:
        """Rounds until resuming cooperation after each opponent defection. Per-opponent."""
        results = {}
        for opp_id, opp_acts in opponents_actions.items():
            waits = []
            i = 1
            while i < len(own_actions):
                if i <= len(opp_acts) and opp_acts[i-1] == 0 and own_actions[i] == 0:
                    j = i + 1
                    while j < len(own_actions) and own_actions[j] == 0:
                        j += 1
                    if j < len(own_actions):
                        waits.append(j - i)
                    i = j
                else:
                    i += 1
            results[opp_id] = float(np.mean(waits)) if waits else 0.0
        return results

    # ── N-player specific ────────────────────────────────────────────────────

    @staticmethod
    def multilateral_cooperation_index(
        all_actions: dict[str, list[int]],
    ) -> list[float]:
        """
        Per-round fraction of agents that cooperated.
        Returns a time-series useful for tracking cooperation dynamics.
        """
        if not all_actions:
            return []
        num_rounds = max(len(v) for v in all_actions.values())
        index = []
        for r in range(num_rounds):
            acts = [v[r] for v in all_actions.values() if r < len(v)]
            index.append(float(np.mean(acts)) if acts else 0.0)
        return index

    @staticmethod
    def pairwise_reciprocity_matrix(
        all_actions: dict[str, list[int]],
        agent_ids: list[str],
    ) -> dict[tuple[str, str], float]:
        """
        Reciprocity(i→j) = lag-1 correlation between i's action and j's previous action.
        Returns {(agent_i, agent_j): score} for all directed pairs.
        """
        matrix = {}
        for i, j in combinations(agent_ids, 2):
            acts_i = all_actions.get(i, [])
            acts_j = all_actions.get(j, [])
            min_len = min(len(acts_i), len(acts_j))
            if min_len < 2:
                matrix[(i, j)] = 0.0
                matrix[(j, i)] = 0.0
                continue
            i_responds = acts_i[1:min_len]
            j_prev     = acts_j[:min_len-1]
            j_responds = acts_j[1:min_len]
            i_prev     = acts_i[:min_len-1]
            if np.std(i_responds) > 1e-8 and np.std(j_prev) > 1e-8:
                matrix[(i, j)] = float(np.corrcoef(i_responds, j_prev)[0, 1])
            else:
                matrix[(i, j)] = 0.0
            if np.std(j_responds) > 1e-8 and np.std(i_prev) > 1e-8:
                matrix[(j, i)] = float(np.corrcoef(j_responds, i_prev)[0, 1])
            else:
                matrix[(j, i)] = 0.0
        return matrix

    # ── social metrics ───────────────────────────────────────────────────────

    @staticmethod
    def gini_coefficient(payoffs: list[float]) -> float:
        if not payoffs or sum(payoffs) == 0:
            return 0.0
        arr = sorted(payoffs)
        n   = len(arr)
        idx = np.arange(1, n + 1)
        return float((2 * np.dot(idx, arr) / (n * sum(arr))) - (n + 1) / n)

    @staticmethod
    def price_of_anarchy(pareto_welfare: float, worst_nash_welfare: float) -> float:
        return float("inf") if worst_nash_welfare == 0 else pareto_welfare / worst_nash_welfare

    # ── coalition helpers ────────────────────────────────────────────────────

    @staticmethod
    def coalition_payoff_improvement(
        solo_payoffs: dict[str, float],
        coalition_payoffs: dict[str, float],
    ) -> dict[str, float]:
        """How much each agent improved by being in a coalition vs. playing solo."""
        result = {}
        for agent_id in coalition_payoffs:
            solo = solo_payoffs.get(agent_id, 0.0)
            coal = coalition_payoffs[agent_id]
            result[agent_id] = (coal - solo) / abs(solo) if solo != 0 else float("inf")
        return result

    @staticmethod
    def shapley_value_deviation(
        actual_payoffs: dict[str, float],
        shapley_values: dict[str, float],
    ) -> dict[str, float]:
        """
        Deviation of actual payoff from Shapley fair-share value.
        Shapley values must be computed externally (game-specific).
        Positive = agent received more than fair share; negative = exploited.
        """
        return {
            a: actual_payoffs.get(a, 0.0) - shapley_values.get(a, 0.0)
            for a in set(actual_payoffs) | set(shapley_values)
        }
