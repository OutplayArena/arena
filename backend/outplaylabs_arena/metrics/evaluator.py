from __future__ import annotations

import numpy as np

from outplaylabs_arena.metrics.behavioral import BehavioralMetrics
from outplaylabs_arena.metrics.contracts import Match
from outplaylabs_arena.metrics.cooperative import CooperativeMetrics
from outplaylabs_arena.metrics.equilibrium import EquilibriumMetrics
from outplaylabs_arena.metrics.extension import GameMetricsExtension
from outplaylabs_arena.metrics.registry import AgentRegistry


_COOPERATIVE_GAME_TYPES = frozenset({
    "prisoners_dilemma",
    "prisonersdilemma",
    "blotto_coalition",
    "stag_hunt",
    "centipede",
    "public_goods",
})

_ZERO_SUM_GAME_TYPES = frozenset({
    "rock_paper_scissors",
    "colonelblotto",
})


class MatchEvaluator:
    """
    Main entry point. Call evaluate() after every match; population_report()
    after a batch to get α-Rank and Elo standings.

    Pass a GameMetricsExtension to inject game-specific metrics. Use
    GameRegistry.metrics_extension(game_type) to load one automatically.

    Pass declared_metrics (from GameRegistry.get_metric_names()) to filter
    the output to only metrics declared in the game's metrics.yaml.
    """

    @staticmethod
    def _filter_dict(data: dict, declared: set[str]) -> dict:
        """Keep only keys in *declared*, preserving nested dicts when relevant."""
        result = {}
        for key, value in data.items():
            if key in declared:
                result[key] = value
            elif isinstance(value, dict):
                filtered = MatchEvaluator._filter_dict(value, declared)
                if filtered:
                    result[key] = filtered
        return result

    def __init__(self, registry: AgentRegistry):
        self.registry = registry

    def evaluate(
        self,
        match: Match,
        extension: GameMetricsExtension | None = None,
        game_config: dict | None = None,
        declared_metrics: set[str] | None = None,
    ) -> dict:
        config  = game_config or match.config
        agents  = match.agent_ids
        n       = len(agents)
        payoffs_per_agent = {a: match.payoffs(a) for a in agents}
        is_zero_sum = match.game_type in _ZERO_SUM_GAME_TYPES

        report: dict = {
            "match_id":   match.match_id,
            "game_type":  match.game_type,
            "num_agents": n,
            "agents":     {},
            "joint":      {},
            "pairwise":   {},
        }

        # ── Joint metrics ────────────────────────────────────────────────────
        joint_payoffs = match.joint_payoffs()
        pareto_opt    = config.get("pareto_optimal_welfare")
        sw            = EquilibriumMetrics.social_welfare(payoffs_per_agent)

        report["joint"] = {}
        if not is_zero_sum:
            report["joint"]["social_welfare"] = sw
            report["joint"]["pareto_efficiency"] = EquilibriumMetrics.pareto_efficiency(joint_payoffs, pareto_opt)
            report["joint"]["social_efficiency_ratio"] = EquilibriumMetrics.social_efficiency_ratio(sw, pareto_opt or sw)
        report["joint"]["gini_coefficient"] = CooperativeMetrics.gini_coefficient(
            [float(np.mean(v)) for v in payoffs_per_agent.values() if v]
        )

        best_responses = config.get("best_responses")
        if best_responses is None and is_zero_sum:
            best_responses = {a: 0.0 for a in agents}
        nash_gaps = EquilibriumMetrics.nash_gap_nplayer(payoffs_per_agent, best_responses)
        report["joint"]["nash_gap_per_agent"] = nash_gaps
        report["joint"]["total_nash_gap"]     = EquilibriumMetrics.total_nash_gap(nash_gaps)

        # ── Game-specific joint + pairwise metrics (via extension) ───────────
        if extension is not None:
            report["joint"].update(extension.compute_joint(match, config))
            report["pairwise"].update(extension.compute_pairwise(match, config))

        # ── Cooperative joint metrics ─────────────────────────────────────────
        if match.game_type in _COOPERATIVE_GAME_TYPES:
            all_binary = {
                a: CooperativeMetrics._to_binary(match.actions(a))
                for a in agents
            }
            report["joint"]["multilateral_cooperation_index"] = \
                CooperativeMetrics.multilateral_cooperation_index(all_binary)
            report["pairwise"]["reciprocity_matrix"] = {
                f"{a}_{b}": v
                for (a, b), v in CooperativeMetrics.pairwise_reciprocity_matrix(
                    all_binary, agents
                ).items()
            }

        # ── Per-agent metrics ─────────────────────────────────────────────────
        for agent_id in agents:
            actions   = match.actions(agent_id)
            payoffs   = match.payoffs(agent_id)
            opponents = [a for a in agents if a != agent_id]

            best_response_payoff = config.get("best_response_payoff")
            if best_response_payoff is None:
                best_response_payoff = 0.0 if is_zero_sum else (max(payoffs) if payoffs else 0.0)

            ar: dict = {
                "total_payoff":           match.total_payoff(agent_id),
                "avg_payoff":             float(np.mean(payoffs)) if payoffs else 0.0,
                "strategy_entropy":       BehavioralMetrics.strategy_entropy(actions),
                "behavioral_consistency": BehavioralMetrics.behavioral_consistency(actions),
                "cumulative_regret":      BehavioralMetrics.regret(payoffs, best_response_payoff),
                "adaptive_regret_series": BehavioralMetrics.adaptive_regret(payoffs),
                "nash_gap":               nash_gaps.get(agent_id, 0.0),
            }

            # Cooperative signals — vs. every opponent
            if match.game_type in _COOPERATIVE_GAME_TYPES:
                bin_acts = CooperativeMetrics._to_binary(actions)
                ar["cooperation_rate"] = CooperativeMetrics.cooperation_rate(bin_acts)
                opp_bin = {
                    opp: CooperativeMetrics._to_binary(match.actions(opp))
                    for opp in opponents
                }
                ar["conditional_cooperation"] = \
                    CooperativeMetrics.conditional_cooperation_rates(bin_acts, opp_bin)
                ar["tit_for_tat_adherence"] = \
                    CooperativeMetrics.tit_for_tat_adherence(bin_acts, opp_bin)
                ar["forgiveness_index"] = \
                    CooperativeMetrics.forgiveness_index(bin_acts, opp_bin)
                ar["mean_tft_adherence"] = float(np.mean(list(ar["tit_for_tat_adherence"].values()))) \
                                           if ar["tit_for_tat_adherence"] else 0.0
                ar["mean_forgiveness"]   = float(np.mean(list(ar["forgiveness_index"].values()))) \
                                           if ar["forgiveness_index"] else 0.0

            # Game-specific per-agent metrics (via extension)
            if extension is not None:
                ar.update(extension.compute_agent(match, agent_id, config, report["joint"]))

            report["agents"][agent_id] = ar

        # ── Registry update ───────────────────────────────────────────────────
        avg_results = {a: float(np.mean(v)) for a, v in payoffs_per_agent.items() if v}
        self.registry.record_match(match, avg_results)

        # ── Filter to declared metrics ─────────────────────────────────────────
        if declared_metrics is not None:
            report["joint"] = self._filter_dict(report["joint"], declared_metrics)
            report["pairwise"] = self._filter_dict(report["pairwise"], declared_metrics)
            for agent_id in agents:
                report["agents"][agent_id] = self._filter_dict(report["agents"][agent_id], declared_metrics)

        return report

    def population_report(self, agent_ids: list[str]) -> dict:
        alpha_scores = self.registry.compute_alpha_rank_scores(agent_ids)
        return {
            "elo_ratings":          {a: self.registry.elo_ratings[a] for a in agent_ids},
            "alpha_rank_scores":    alpha_scores,
            "alpha_rank_ranking":   sorted(alpha_scores, key=alpha_scores.get, reverse=True),
            "population_diversity": self.registry.population_diversity(agent_ids),
            "matches_played":       len(self.registry.match_history),
        }
