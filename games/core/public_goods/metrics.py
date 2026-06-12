from __future__ import annotations

import numpy as np

from nash_arena.game_components.game_metrics import GameMetrics
from nash_arena.metrics.extension import GameMetricsExtension


class PublicGoodsMetrics(GameMetrics, GameMetricsExtension):

    def compute(self, history: list[dict], total_scores: dict) -> dict:
        contrib_rounds = [e for e in history if e.get("phase") == "contribution"]
        n = len(contrib_rounds)
        if n == 0:
            return {"total_payoff": dict(total_scores)}

        players = list(total_scores.keys())
        per_player: dict[str, list[float]] = {p: [] for p in players}
        pools: list[float] = []
        for entry in contrib_rounds:
            contribs = entry.get("contributions", {})
            pools.append(entry.get("pool", 0.0))
            for p in players:
                per_player[p].append(contribs.get(p, 0.0))

        avg_contribution = {p: float(np.mean(per_player[p])) if per_player[p] else 0.0 for p in players}
        all_contribs = [c for vals in per_player.values() for c in vals]
        max_contrib = max(all_contribs) if all_contribs else 10.0

        contribution_rate = {
            p: (avg_contribution[p] / max_contrib if max_contrib > 0 else 0.0)
            for p in players
        }
        avg_pool = float(np.mean(pools)) if pools else 0.0

        return {
            "total_payoff":       dict(total_scores),
            "average_payoff":     {p: (total_scores[p] / n if n else 0.0) for p in players},
            "avg_contribution":   avg_contribution,
            "contribution_rate":  contribution_rate,
            "avg_pool":           avg_pool,
            "free_rider_count":   sum(1 for p in players if avg_contribution[p] < 0.01 * (max_contrib or 10.0)),
        }

    def compute_joint(self, match, config: dict) -> dict:
        # Build from match.moves_by_round
        agents = match.agent_ids
        n_rounds = match.num_rounds()
        endowment = config.get("endowment", 10.0)
        multiplier = config.get("multiplier", 2.0)

        total_contributions: list[float] = []
        for r in range(n_rounds):
            moves = match.moves_by_round(r)
            round_contribs = []
            for m in moves:
                if isinstance(m.action, (int, float)):
                    round_contribs.append(float(m.action))
            if round_contribs:
                total_contributions.append(sum(round_contribs))

        n = len(total_contributions)
        avg_pool = float(np.mean(total_contributions)) if n else 0.0
        n_players = len(agents)
        max_pool = endowment * n_players
        contribution_efficiency = avg_pool / max_pool if max_pool > 0 else 0.0

        # Price of anarchy: ratio of Nash (0 contrib) welfare to Pareto welfare
        pareto_welfare = endowment * multiplier * n_players
        nash_welfare = endowment * n_players
        pgg_price_of_anarchy = nash_welfare / pareto_welfare if pareto_welfare > 0 else 1.0

        return {
            "pgg_avg_pool":             avg_pool,
            "pgg_contribution_efficiency": contribution_efficiency,
            "pgg_price_of_anarchy":     pgg_price_of_anarchy,
        }

    def compute_agent(self, match, agent_id: str, config: dict, joint: dict) -> dict:
        actions = [a for a in match.actions(agent_id) if isinstance(a, (int, float))]
        n = len(actions)
        if n == 0:
            return {}

        endowment = config.get("endowment", 10.0)
        avg_contrib = float(np.mean(actions)) if actions else 0.0
        contribution_rate = avg_contrib / endowment if endowment > 0 else 0.0

        # Decay: is the contribution declining over time?
        if n >= 4:
            first_half = float(np.mean(actions[:n // 2]))
            second_half = float(np.mean(actions[n // 2:]))
            contribution_decay = first_half - second_half
        else:
            contribution_decay = 0.0

        return {
            "pgg": {
                "avg_contribution":    avg_contrib,
                "contribution_rate":   contribution_rate,
                "contribution_decay":  contribution_decay,
                "free_rider":          contribution_rate < 0.1,
            }
        }
