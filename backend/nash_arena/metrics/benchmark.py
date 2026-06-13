"""
Aggregates tournament results across games into a structured benchmark report.
The four benchmark dimensions:
  - competitive_rationality: Elo vs NashAgent, α-Rank, nash_gap
  - cooperative_reasoning:   social_welfare, cooperation_rate, equilibrium_selection_rate
  - strategic_adaptation:    cumulative_regret, behavioral_consistency, strategy_entropy
  - cognitive_depth:         backward_induction_adherence, offer_fairness_index
"""
from __future__ import annotations

from collections import defaultdict
from typing import Any

import numpy as np

from nash_arena.metrics.registry import AgentRegistry

_COMPETITIVE_GAMES = frozenset({
    "rock_paper_scissors", "colonelblotto", "centipede", "ultimatum"
})
_COOPERATIVE_GAMES = frozenset({
    "prisonersdilemma", "stag_hunt", "public_goods", "battle_of_the_sexes"
})
_SEQUENTIAL_GAMES = frozenset({
    "ultimatum", "centipede", "texas_hold_em"
})
_RATIONALITY_GAMES = frozenset({
    "centipede", "ultimatum", "texas_hold_em"
})


def _safe_mean(vals: list[float]) -> float | None:
    if not vals:
        return None
    return float(np.mean(vals))


class BenchmarkReport:
    """
    Accumulates per-match metric snapshots and produces an aggregated report.
    Instantiate once per tournament; call record_match() after each match.
    """

    def __init__(self):
        self._per_agent: dict[str, dict[str, list[float]]] = defaultdict(lambda: defaultdict(list))
        self._match_count: dict[str, int] = defaultdict(int)
        self._game_results: list[dict] = []

    def record_match(self, game_type: str, rich_metrics: dict) -> None:
        """Record the rich_metrics blob from a single match."""
        self._game_results.append({"game_type": game_type, **rich_metrics})
        agents_data = rich_metrics.get("agents", {})
        joint_data = rich_metrics.get("joint", {})

        for agent_id, ar in agents_data.items():
            self._match_count[agent_id] += 1
            store = self._per_agent[agent_id]

            for key in ("avg_payoff", "cumulative_regret", "strategy_entropy",
                        "behavioral_consistency", "nash_gap", "cooperation_rate"):
                val = ar.get(key)
                if isinstance(val, (int, float)):
                    store[key].append(float(val))

            for key in ("backward_induction_adherence",):
                val = ar.get(key)
                if isinstance(val, (int, float)):
                    store[key].append(float(val))

            for key in ("social_welfare", "pareto_efficiency", "gini_coefficient",
                        "equilibrium_selection_rate"):
                val = joint_data.get(key)
                if isinstance(val, (int, float)):
                    store[f"joint_{key}"].append(float(val))

    def generate(self, registry: AgentRegistry, agent_ids: list[str]) -> dict:
        """Return the full benchmark report dict."""
        if len(agent_ids) >= 2:
            alpha_scores = registry.compute_alpha_rank_scores(agent_ids)
            pop = {
                "elo_ratings": {a: registry.elo_ratings[a] for a in agent_ids},
                "alpha_rank_scores": alpha_scores,
                "alpha_rank_ranking": sorted(alpha_scores, key=alpha_scores.get, reverse=True),
                "population_diversity": registry.population_diversity(agent_ids),
                "matches_played": len(registry.match_history),
            }
        else:
            pop = {}

        per_agent_summary: dict[str, dict[str, Any]] = {}
        for agent_id in agent_ids:
            store = self._per_agent[agent_id]
            summary: dict[str, Any] = {
                "matches_played": self._match_count.get(agent_id, 0),
                "elo": pop.get("elo_ratings", {}).get(agent_id),
                "alpha_rank": pop.get("alpha_rank_scores", {}).get(agent_id),
            }

            # Aggregate scalar metrics
            for key in ("avg_payoff", "cumulative_regret", "strategy_entropy",
                        "behavioral_consistency", "nash_gap", "cooperation_rate",
                        "backward_induction_adherence",
                        "joint_social_welfare", "joint_pareto_efficiency",
                        "joint_gini_coefficient", "joint_equilibrium_selection_rate"):
                vals = store.get(key, [])
                summary[key] = _safe_mean(vals)

            # Dimension scores (0–1 normalized)
            summary["competitive_rationality"] = self._competitive_score(agent_id, pop)
            summary["cooperative_reasoning"] = self._cooperative_score(agent_id)
            summary["strategic_adaptation"] = self._adaptation_score(agent_id)
            summary["cognitive_depth"] = self._cognitive_score(agent_id)

            per_agent_summary[agent_id] = summary

        ranking = sorted(
            agent_ids,
            key=lambda a: sum(
                v for k, v in per_agent_summary[a].items()
                if k in ("competitive_rationality", "cooperative_reasoning",
                         "strategic_adaptation", "cognitive_depth")
                and v is not None
            ),
            reverse=True,
        )

        return {
            "agents": per_agent_summary,
            "ranking": ranking,
            "population": pop,
            "total_matches": sum(self._match_count.values()) // 2,
        }

    def _competitive_score(self, agent_id: str, pop: dict) -> float | None:
        elo = pop.get("elo_ratings", {}).get(agent_id)
        alpha = pop.get("alpha_rank_scores", {}).get(agent_id)
        nash_gap_vals = self._per_agent[agent_id].get("nash_gap", [])
        nash_gap_mean = _safe_mean(nash_gap_vals)

        components = []
        if elo is not None:
            # Normalize Elo: 1200 = 0.5, each 400 points = 0.25
            components.append(min(1.0, max(0.0, (elo - 800) / 800)))
        if alpha is not None:
            components.append(min(1.0, alpha * 10))  # rough normalization
        if nash_gap_mean is not None:
            components.append(max(0.0, 1.0 - min(1.0, nash_gap_mean)))

        return _safe_mean(components) if components else None

    def _cooperative_score(self, agent_id: str) -> float | None:
        store = self._per_agent[agent_id]
        components = []
        for key in ("cooperation_rate", "joint_social_welfare", "joint_pareto_efficiency",
                    "joint_equilibrium_selection_rate"):
            val = _safe_mean(store.get(key, []))
            if val is not None:
                components.append(min(1.0, max(0.0, val)))
        return _safe_mean(components) if components else None

    def _adaptation_score(self, agent_id: str) -> float | None:
        store = self._per_agent[agent_id]
        components = []
        regret = _safe_mean(store.get("cumulative_regret", []))
        if regret is not None:
            components.append(max(0.0, 1.0 - min(1.0, regret / 100.0)))
        consistency = _safe_mean(store.get("behavioral_consistency", []))
        if consistency is not None:
            components.append(consistency)
        entropy = _safe_mean(store.get("strategy_entropy", []))
        if entropy is not None:
            components.append(min(1.0, entropy / 2.0))
        return _safe_mean(components) if components else None

    def _cognitive_score(self, agent_id: str) -> float | None:
        store = self._per_agent[agent_id]
        components = []
        bi = _safe_mean(store.get("backward_induction_adherence", []))
        if bi is not None:
            components.append(bi)
        return _safe_mean(components) if components else None
