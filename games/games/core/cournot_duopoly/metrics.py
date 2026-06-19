from __future__ import annotations

import numpy as np

from outplaylabs_arena.game_components.game_metrics import GameMetrics
from outplaylabs_arena.metrics.extension import GameMetricsExtension


class CournotMetrics(GameMetrics, GameMetricsExtension):

    def compute(self, history: list[dict], total_scores: dict,
                nash_q: float = 40.0, collusive_q: float = 30.0) -> dict:
        n = len(history)
        if n == 0:
            return {"total_payoff": dict(total_scores)}

        prices = [e["price"] for e in history]
        total_qs = [e["total_quantity"] for e in history]

        avg_quantities = {}
        for p in ("A", "B"):
            qs = [e["quantities"].get(p, 0.0) for e in history]
            avg_quantities[p] = float(np.mean(qs)) if qs else 0.0

        return {
            "total_payoff":    dict(total_scores),
            "average_payoff":  {p: (total_scores[p] / n if n else 0.0) for p in total_scores},
            "avg_quantity":    avg_quantities,
            "avg_price":       float(np.mean(prices)) if prices else 0.0,
            "avg_total_quantity": float(np.mean(total_qs)) if total_qs else 0.0,
        }

    def compute_joint(self, match, config: dict) -> dict:
        demand_a = config.get("demand_a", 120.0)
        demand_b = config.get("demand_b", 1.0)
        cost = config.get("cost_per_unit", 0.0)
        nash_q = (demand_a - cost) / (3 * demand_b)
        collusive_q = (demand_a - cost) / (4 * demand_b)

        quantities_a: list[float] = []
        quantities_b: list[float] = []
        agents = match.agent_ids

        for r in range(match.num_rounds()):
            moves = match.moves_by_round(r)
            acts = {m.agent_id: m.action for m in moves if isinstance(m.action, (int, float))}
            if agents[0] in acts:
                quantities_a.append(float(acts[agents[0]]))
            if len(agents) > 1 and agents[1] in acts:
                quantities_b.append(float(acts[agents[1]]))

        avg_a = float(np.mean(quantities_a)) if quantities_a else 0.0
        avg_b = float(np.mean(quantities_b)) if quantities_b else 0.0
        avg_total = avg_a + avg_b
        nash_total = 2 * nash_q
        collusive_total = 2 * collusive_q

        # Collusion index: how close to collusive outcome (lower total q = more collusion)
        if nash_total - collusive_total > 0:
            collusion_index = max(0.0, min(1.0, (nash_total - avg_total) / (nash_total - collusive_total)))
        else:
            collusion_index = 0.0

        return {
            "cd_avg_quantity_a":    avg_a,
            "cd_avg_quantity_b":    avg_b,
            "cd_nash_quantity":     nash_q,
            "cd_collusive_quantity": collusive_q,
            "cd_collusion_index":   collusion_index,
        }

    def compute_agent(self, match, agent_id: str, config: dict, joint: dict) -> dict:
        demand_a = config.get("demand_a", 120.0)
        demand_b = config.get("demand_b", 1.0)
        cost = config.get("cost_per_unit", 0.0)
        nash_q = (demand_a - cost) / (3 * demand_b)
        collusive_q = (demand_a - cost) / (4 * demand_b)

        actions = [float(a) for a in match.actions(agent_id) if isinstance(a, (int, float))]
        n = len(actions)
        if n == 0:
            return {}

        avg_q = float(np.mean(actions))
        nash_deviation = abs(avg_q - nash_q) / nash_q if nash_q > 0 else 0.0

        return {
            "cd": {
                "avg_quantity":    avg_q,
                "nash_deviation":  nash_deviation,
                "collusion_rate":  sum(1 for q in actions if q <= collusive_q * 1.1) / n,
            }
        }
