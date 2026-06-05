from __future__ import annotations

from typing import Any

MetricDef = dict[str, Any]

_METRICS: dict[str, MetricDef] = {
    # ── Common outcome metrics ──────────────────────────────────────────
    "total_payoff": {
        "name": "total_payoff",
        "when": "terminal",
        "type": "object",
        "description": "Cumulative payoff for each player at the end of the match.",
    },
    "average_payoff": {
        "name": "average_payoff",
        "when": "terminal",
        "type": "object",
        "description": "Average payoff per round for each player.",
    },
    "round_win_counts": {
        "name": "round_win_counts",
        "when": "terminal",
        "type": "object",
        "description": "Number of rounds won by each player, plus ties.",
    },
    "round_win_rate": {
        "name": "round_win_rate",
        "when": "terminal",
        "type": "object",
        "description": "Fraction of rounds won by each player, plus ties.",
    },

    # ── RPS-specific metrics ────────────────────────────────────────────
    "move_frequencies": {
        "name": "move_frequencies",
        "when": "terminal",
        "type": "object",
        "description": "Empirical frequency of each action per player.",
    },
    "rps_collision_rate": {
        "name": "rps_collision_rate",
        "when": "terminal",
        "type": "number",
        "description": "Fraction of rounds where both players chose the same move.",
    },
    "nash_distance": {
        "name": "nash_distance",
        "when": "terminal",
        "type": "number",
        "description": "Total variation distance from the uniform Nash equilibrium mixed strategy.",
    },
    "pattern_exploitability": {
        "name": "pattern_exploitability",
        "when": "terminal",
        "type": "number",
        "description": "Lag-1 autocorrelation of the agent's action sequence. 0 = random, 1 = perfectly predictable.",
    },

    # ── PD-specific metrics ─────────────────────────────────────────────
    "cooperation_rate": {
        "name": "cooperation_rate",
        "when": "terminal",
        "type": "object",
        "description": "Fraction of rounds each player chose to cooperate.",
    },
    "mutual_cooperation_rate": {
        "name": "mutual_cooperation_rate",
        "when": "terminal",
        "type": "number",
        "description": "Fraction of rounds where both players cooperated (CC).",
    },
    "mutual_defection_rate": {
        "name": "mutual_defection_rate",
        "when": "terminal",
        "type": "number",
        "description": "Fraction of rounds where both players defected (DD).",
    },
    "outcome_counts": {
        "name": "outcome_counts",
        "when": "terminal",
        "type": "object",
        "description": "Raw count of each outcome type: CC, CD, DC, DD.",
    },
    "pd_outcome_counts": {
        "name": "pd_outcome_counts",
        "when": "terminal",
        "type": "object",
        "description": "Normalized frequency of each outcome type (CC, CD, DC, DD).",
    },
    "pd_mutual_cooperation_rate": {
        "name": "pd_mutual_cooperation_rate",
        "when": "terminal",
        "type": "number",
        "description": "Fraction of rounds with mutual cooperation (CC).",
    },
    "pd_price_of_anarchy": {
        "name": "pd_price_of_anarchy",
        "when": "terminal",
        "type": "number",
        "description": "Ratio of mutual defection payoff (P) to mutual cooperation payoff (R).",
    },
    "exploitation_rate": {
        "name": "exploitation_rate",
        "when": "terminal",
        "type": "number",
        "description": "Fraction of rounds where the agent defected after the opponent cooperated.",
    },
    "forgiveness_rate": {
        "name": "forgiveness_rate",
        "when": "terminal",
        "type": "number",
        "description": "Fraction of opponent defection rounds where the agent cooperated in response.",
    },
    "first_move": {
        "name": "first_move",
        "when": "terminal",
        "type": "string",
        "description": "The agent's action in the first round. Indicates opening strategy.",
    },
    "tit_for_tat_adherence": {
        "name": "tit_for_tat_adherence",
        "when": "terminal",
        "type": "number",
        "description": "How closely the agent follows Tit-for-Tat: copying the opponent's previous move.",
    },
    "forgiveness_index": {
        "name": "forgiveness_index",
        "when": "terminal",
        "type": "number",
        "description": "Average rounds waited before resuming cooperation after an opponent defection.",
    },
    "conditional_cooperation": {
        "name": "conditional_cooperation",
        "when": "terminal",
        "type": "object",
        "description": "Cooperation rate conditioned on the opponent's previous action (after_cooperate vs after_defect).",
    },
    "multilateral_cooperation_index": {
        "name": "multilateral_cooperation_index",
        "when": "terminal",
        "type": "object",
        "description": "Time series of per-round fraction of cooperating agents.",
    },

    # ── Colonel Blotto metrics ──────────────────────────────────────────
    "allocation_concentration": {
        "name": "allocation_concentration",
        "when": "terminal",
        "type": "object",
        "description": "Average concentration of each player's allocations across battlefields.",
    },
    "blotto_fronts_won": {
        "name": "blotto_fronts_won",
        "when": "terminal",
        "type": "object",
        "description": "Fraction of battlefields won by each player.",
    },
    "blotto_targeting_overlap": {
        "name": "blotto_targeting_overlap",
        "when": "terminal",
        "type": "object",
        "description": "Cosine similarity of allocation vectors between player pairs.",
    },

    # ── Behavioral metrics ──────────────────────────────────────────────
    "strategy_entropy": {
        "name": "strategy_entropy",
        "when": "terminal",
        "type": "number",
        "description": "Shannon entropy of the agent's action distribution. Higher = more unpredictable.",
    },
    "behavioral_consistency": {
        "name": "behavioral_consistency",
        "when": "terminal",
        "type": "number",
        "description": "How consistently the agent repeats the same action. 1.0 = always identical, lower = more varied.",
    },
    "cumulative_regret": {
        "name": "cumulative_regret",
        "when": "terminal",
        "type": "number",
        "description": "Gap between achieved payoff and the best achievable fixed-action payoff.",
    },
    "adaptive_regret_series": {
        "name": "adaptive_regret_series",
        "when": "terminal",
        "type": "object",
        "description": "Windowed regret over the course of the match — tracks learning/drift.",
    },

    # ── Equilibrium metrics ─────────────────────────────────────────────
    "nash_gap": {
        "name": "nash_gap",
        "when": "terminal",
        "type": "number",
        "description": "Per-agent deviation from the Nash equilibrium payoff.",
    },
    "total_nash_gap": {
        "name": "total_nash_gap",
        "when": "terminal",
        "type": "number",
        "description": "Sum of all per-agent Nash gaps across the match.",
    },
    "nash_gap_per_agent": {
        "name": "nash_gap_per_agent",
        "when": "terminal",
        "type": "object",
        "description": "Per-agent Nash gap breakdown.",
    },
    "social_welfare": {
        "name": "social_welfare",
        "when": "terminal",
        "type": "number",
        "description": "Sum of average payoffs across all agents. Higher = better collective outcome.",
    },
    "pareto_efficiency": {
        "name": "pareto_efficiency",
        "when": "terminal",
        "type": "number",
        "description": "How close the achieved joint payoff is to the Pareto-optimal frontier. 1.0 = Pareto optimal.",
    },
    "social_efficiency_ratio": {
        "name": "social_efficiency_ratio",
        "when": "terminal",
        "type": "number",
        "description": "Achieved social welfare as a fraction of Pareto-optimal welfare.",
    },
    "gini_coefficient": {
        "name": "gini_coefficient",
        "when": "terminal",
        "type": "number",
        "description": "Inequality measure across agent payoffs. 0 = perfectly equal, 1 = extreme inequality.",
    },

    # ── Rating / ranking metrics ────────────────────────────────────────
    "elo_ratings": {
        "name": "elo_ratings",
        "when": "population",
        "type": "object",
        "description": "Elo ratings for each agent across all matches played.",
    },
    "alpha_rank_scores": {
        "name": "alpha_rank_scores",
        "when": "population",
        "type": "object",
        "description": "α-Rank stationary distribution scores for each agent.",
    },
    "population_diversity": {
        "name": "population_diversity",
        "when": "population",
        "type": "number",
        "description": "Shannon entropy of the population strategy distribution across agents.",
    },
}


def get_metric(name: str) -> MetricDef | None:
    """Return the central definition for a metric, or None if unknown."""
    return _METRICS.get(name)


def get_all_metrics() -> dict[str, MetricDef]:
    return dict(_METRICS)


def build_metrics_list(names: list[str], overrides: dict[str, str] | None = None) -> list[MetricDef]:
    """
    Build a resolved metrics list for a game by looking up each name in the
    central catalog, applying optional per-game description overrides.
    """
    overrides = overrides or {}
    result = []
    for name in names:
        metric = get_metric(name)
        if metric is None:
            continue
        entry = dict(metric)
        if name in overrides:
            entry["description"] = overrides[name]
        result.append(entry)
    return result
