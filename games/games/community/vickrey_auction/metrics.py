from __future__ import annotations

from arena.game_components.game_metrics import GameMetrics
from arena.metrics.extension import GameMetricsExtension


class VickreyAuctionMetrics(GameMetrics, GameMetricsExtension):
    def __init__(self, truthful_tolerance: float = 1.0):
        self.truthful_tolerance = truthful_tolerance

    def compute(self, history: list[dict], total_scores: dict) -> dict:
        n = len(history)
        players = list(total_scores.keys())

        shading_sums: dict[str, float] = {p: 0.0 for p in players}
        truthful_counts: dict[str, int] = {p: 0 for p in players}
        win_counts: dict[str, int] = {p: 0 for p in players}
        surplus_sums: dict[str, float] = {p: 0.0 for p in players}

        for entry in history:
            values = entry.get("values", {})
            bids = entry.get("actions", {})
            winner = entry.get("winner")
            payoffs = entry.get("payoffs", {})
            for p in players:
                if p not in values or p not in bids:
                    continue
                deviation = bids[p] - values[p]
                shading_sums[p] += deviation
                if abs(deviation) <= self.truthful_tolerance:
                    truthful_counts[p] += 1
            if winner in win_counts:
                win_counts[winner] += 1
                surplus_sums[winner] += payoffs.get(winner, 0.0)

        return {
            "total_payoff":   dict(total_scores),
            "average_payoff": {p: (total_scores[p] / n if n else 0.0) for p in players},
            "bid_shading":    {p: (shading_sums[p] / n if n else 0.0) for p in players},
            "truthful_rate":  {p: (truthful_counts[p] / n if n else 0.0) for p in players},
            "win_rate":       {p: (win_counts[p] / n if n else 0.0) for p in players},
            "avg_surplus":    {
                p: (surplus_sums[p] / win_counts[p] if win_counts[p] else 0.0)
                for p in players
            },
        }

    def compute_joint(self, match, config: dict) -> dict:
        """No auction-specific joint metrics — Match/Move records only carry
        each round's bid and payoff (session.py's to_match() drops the
        private value), so the value-aware breakdowns (bid_shading,
        truthful_rate) can only be computed from the raw history in
        compute(), which is what powers get_results()."""
        return {}

    def compute_agent(self, match, agent_id: str, config: dict, joint: dict) -> dict:
        bids = [a for a in match.actions(agent_id) if isinstance(a, (int, float))]
        n = len(bids)
        if n == 0:
            return {}
        payoffs = match.payoffs(agent_id)
        wins = sum(1 for p in payoffs if p != 0.0)
        return {
            "va": {
                "avg_bid":  sum(bids) / n,
                "win_rate": wins / n,
                "first_bid": bids[0],
            }
        }
