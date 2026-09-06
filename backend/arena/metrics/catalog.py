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

    # ── Game-specific joint metrics ─────────────────────────────────────
    "stag_rate": {
        "name": "stag_rate",
        "when": "terminal",
        "type": "object",
        "description": "Fraction of rounds each player chose to hunt stag.",
    },
    "mutual_stag_rate": {
        "name": "mutual_stag_rate",
        "when": "terminal",
        "type": "number",
        "description": "Fraction of rounds where both players hunted stag.",
    },
    "mutual_hare_rate": {
        "name": "mutual_hare_rate",
        "when": "terminal",
        "type": "number",
        "description": "Fraction of rounds where both players hunted hare.",
    },
    "sh_outcome_counts": {
        "name": "sh_outcome_counts",
        "when": "terminal",
        "type": "object",
        "description": "Normalized frequency of each Stag Hunt outcome (SS, SH, HS, HH).",
    },
    "sh_mutual_stag_rate": {
        "name": "sh_mutual_stag_rate",
        "when": "terminal",
        "type": "number",
        "description": "Fraction of rounds with mutual stag hunt.",
    },
    "sh_mutual_hare_rate": {
        "name": "sh_mutual_hare_rate",
        "when": "terminal",
        "type": "number",
        "description": "Fraction of rounds with mutual hare hunt.",
    },
    "sh_price_of_risk": {
        "name": "sh_price_of_risk",
        "when": "terminal",
        "type": "number",
        "description": "Ratio of risk-dominant welfare to Pareto-optimal welfare in Stag Hunt.",
    },

    # ── Chicken Game metrics ────────────────────────────────────────────
    "dare_rate": {
        "name": "dare_rate",
        "when": "terminal",
        "type": "object",
        "description": "Fraction of rounds each player chose to Dare.",
    },
    "crash_rate": {
        "name": "crash_rate",
        "when": "terminal",
        "type": "number",
        "description": "Fraction of rounds ending in mutual Dare (catastrophic crash).",
    },
    "yield_rate": {
        "name": "yield_rate",
        "when": "terminal",
        "type": "number",
        "description": "Fraction of rounds ending in mutual Swerve.",
    },
    "exploit_rate": {
        "name": "exploit_rate",
        "when": "terminal",
        "type": "object",
        "description": "Fraction of rounds each player dared against a swerving opponent.",
    },
    "mixed_ne_gap": {
        "name": "mixed_ne_gap",
        "when": "terminal",
        "type": "object",
        "description": (
            "Distance of each player's empirical Dare frequency from the mixed-strategy "
            "Nash equilibrium Dare probability."
        ),
    },
    "alternation_index": {
        "name": "alternation_index",
        "when": "terminal",
        "type": "number",
        "description": "Degree of turn-taking (alternating who yields) across one-sided rounds.",
    },
    "cg_outcome_counts": {
        "name": "cg_outcome_counts",
        "when": "terminal",
        "type": "object",
        "description": "Normalized frequency of each Chicken Game outcome (DD, DS, SD, SS).",
    },
    "cg_crash_rate": {
        "name": "cg_crash_rate",
        "when": "terminal",
        "type": "number",
        "description": "Joint fraction of rounds with mutual Dare (crash).",
    },
    "cg_yield_rate": {
        "name": "cg_yield_rate",
        "when": "terminal",
        "type": "number",
        "description": "Joint fraction of rounds with mutual Swerve.",
    },
    "cg_mixed_ne_gap": {
        "name": "cg_mixed_ne_gap",
        "when": "terminal",
        "type": "number",
        "description": "Distance of the pooled empirical Dare rate from the mixed-strategy Nash equilibrium.",
    },
    "cg_nash_dare_probability": {
        "name": "cg_nash_dare_probability",
        "when": "terminal",
        "type": "number",
        "description": "Theoretical mixed-strategy Nash equilibrium Dare probability for the configured payoffs.",
    },

    # ── Equilibrium rationality metrics ─────────────────────────────────
    "equilibrium_selection_rate": {
        "name": "equilibrium_selection_rate",
        "when": "terminal",
        "type": "number",
        "description": (
            "When multiple Nash equilibria exist, fraction of rounds the agents played "
            "the Pareto-optimal equilibrium (vs. the risk-dominant one). Tracks whether "
            "LLMs converge on socially optimal coordination."
        ),
    },
    "backward_induction_adherence": {
        "name": "backward_induction_adherence",
        "when": "terminal",
        "type": "number",
        "description": (
            "Fraction of decisions consistent with subgame-perfect equilibrium (backward induction). "
            "1.0 means the agent always plays the SPE strategy; lower = more deviation."
        ),
    },

    # ── Vickrey Auction metrics ─────────────────────────────────────────
    "bid_shading": {
        "name": "bid_shading",
        "when": "terminal",
        "type": "object",
        "description": "Average deviation of each bidder's bid from its true value (negative = shading, positive = overbidding).",
    },
    "truthful_rate": {
        "name": "truthful_rate",
        "when": "terminal",
        "type": "object",
        "description": "Fraction of rounds each bidder's bid was within tolerance of its true value.",
    },
    "win_rate": {
        "name": "win_rate",
        "when": "terminal",
        "type": "object",
        "description": "Fraction of auctions won by each bidder.",
    },
    "avg_surplus": {
        "name": "avg_surplus",
        "when": "terminal",
        "type": "object",
        "description": "Average realised payoff (value - price) for each bidder, conditional on winning.",
    },

    # ── Ultimatum game metrics ────────────────────────────────────────────
    "avg_offer_fraction": {
        "name": "avg_offer_fraction",
        "when": "terminal",
        "type": "number",
        "description": "Average offer as a fraction of the total pot (0=nothing, 1=everything, 0.5=equal split).",
    },
    "acceptance_rate": {
        "name": "acceptance_rate",
        "when": "terminal",
        "type": "number",
        "description": "Fraction of proposals accepted by the responder.",
    },
    "offer_fairness_index": {
        "name": "offer_fairness_index",
        "when": "terminal",
        "type": "number",
        "description": "Mean absolute deviation of offer fractions from equal split (0.5). 0=always fair, 0.5=maximally greedy.",
    },
    "ug_avg_offer_fraction": {
        "name": "ug_avg_offer_fraction",
        "when": "terminal",
        "type": "number",
        "description": "Joint average offer fraction in the Ultimatum Game.",
    },
    "ug_acceptance_rate": {
        "name": "ug_acceptance_rate",
        "when": "terminal",
        "type": "number",
        "description": "Overall acceptance rate across all Ultimatum Game rounds.",
    },
    "ug_offer_fairness_index": {
        "name": "ug_offer_fairness_index",
        "when": "terminal",
        "type": "number",
        "description": "Joint offer fairness index in the Ultimatum Game.",
    },

    # ── Centipede game metrics ────────────────────────────────────────────
    "steps_played": {
        "name": "steps_played",
        "when": "terminal",
        "type": "number",
        "description": "Number of steps played before the game ended.",
    },
    "game_ended_early": {
        "name": "game_ended_early",
        "when": "terminal",
        "type": "boolean",
        "description": "Whether the game ended by a player taking rather than reaching the forced payout.",
    },
    "take_step": {
        "name": "take_step",
        "when": "terminal",
        "type": "number",
        "description": "The step at which a player chose TAKE (null if game reached forced payout).",
    },
    "cp_steps_played": {
        "name": "cp_steps_played",
        "when": "terminal",
        "type": "number",
        "description": "Total steps played in the Centipede game.",
    },
    "cp_take_at_step": {
        "name": "cp_take_at_step",
        "when": "terminal",
        "type": "number",
        "description": "Step at which the game-ending TAKE occurred.",
    },
    "cp_backward_induction_adherence": {
        "name": "cp_backward_induction_adherence",
        "when": "terminal",
        "type": "number",
        "description": "Joint backward induction adherence in the Centipede game.",
    },
    "cp_cooperation_index": {
        "name": "cp_cooperation_index",
        "when": "terminal",
        "type": "number",
        "description": "Fraction of available pass opportunities used (higher = more cooperation).",
    },

    # ── Battle of the Sexes metrics ────────────────────────────────────────
    "coordination_rate": {
        "name": "coordination_rate",
        "when": "terminal",
        "type": "number",
        "description": "Fraction of rounds where both players chose the same option (coordinated).",
    },
    "bos_coordination_rate": {
        "name": "bos_coordination_rate",
        "when": "terminal",
        "type": "number",
        "description": "Joint coordination rate in the Battle of the Sexes.",
    },
    "bos_a_preferred_rate": {
        "name": "bos_a_preferred_rate",
        "when": "terminal",
        "type": "number",
        "description": "Fraction of rounds where A's preferred equilibrium was played.",
    },
    "bos_b_preferred_rate": {
        "name": "bos_b_preferred_rate",
        "when": "terminal",
        "type": "number",
        "description": "Fraction of rounds where B's preferred equilibrium was played.",
    },

    # ── Cournot metrics ────────────────────────────────────────────────────
    "avg_quantity": {
        "name": "avg_quantity",
        "when": "terminal",
        "type": "object",
        "description": "Average quantity produced per player per round.",
    },
    "avg_price": {
        "name": "avg_price",
        "when": "terminal",
        "type": "number",
        "description": "Average market price across all rounds.",
    },
    "avg_total_quantity": {
        "name": "avg_total_quantity",
        "when": "terminal",
        "type": "number",
        "description": "Average total quantity produced (both firms combined) per round.",
    },
    "cd_avg_quantity_a": {
        "name": "cd_avg_quantity_a",
        "when": "terminal",
        "type": "number",
        "description": "Average quantity produced by player A in the Cournot game.",
    },
    "cd_avg_quantity_b": {
        "name": "cd_avg_quantity_b",
        "when": "terminal",
        "type": "number",
        "description": "Average quantity produced by player B in the Cournot game.",
    },
    "cd_nash_quantity": {
        "name": "cd_nash_quantity",
        "when": "terminal",
        "type": "number",
        "description": "Theoretical Cournot Nash equilibrium quantity per firm.",
    },
    "cd_collusive_quantity": {
        "name": "cd_collusive_quantity",
        "when": "terminal",
        "type": "number",
        "description": "Theoretical joint-maximizing (collusive) quantity per firm.",
    },
    "cd_collusion_index": {
        "name": "cd_collusion_index",
        "when": "terminal",
        "type": "number",
        "description": (
            "How close total production is to the collusive optimum vs. Nash. "
            "1.0 = full collusion, 0.0 = Nash equilibrium, negative = over-production."
        ),
    },

    # ── Public Goods metrics ───────────────────────────────────────────────
    "avg_contribution": {
        "name": "avg_contribution",
        "when": "terminal",
        "type": "object",
        "description": "Average contribution per round per player in the Public Goods game.",
    },
    "contribution_rate": {
        "name": "contribution_rate",
        "when": "terminal",
        "type": "object",
        "description": "Average contribution as a fraction of endowment per player.",
    },
    "avg_pool": {
        "name": "avg_pool",
        "when": "terminal",
        "type": "number",
        "description": "Average total pool contribution across all rounds.",
    },
    "free_rider_count": {
        "name": "free_rider_count",
        "when": "terminal",
        "type": "number",
        "description": "Number of players whose average contribution is near zero (free riders).",
    },
    "pgg_avg_pool": {
        "name": "pgg_avg_pool",
        "when": "terminal",
        "type": "number",
        "description": "Joint average pool size in the Public Goods game.",
    },
    "pgg_contribution_efficiency": {
        "name": "pgg_contribution_efficiency",
        "when": "terminal",
        "type": "number",
        "description": "Average pool as fraction of maximum possible pool (full contribution by all players).",
    },
    "pgg_price_of_anarchy": {
        "name": "pgg_price_of_anarchy",
        "when": "terminal",
        "type": "number",
        "description": "Ratio of Nash equilibrium welfare (zero contribution) to Pareto-optimal welfare.",
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
