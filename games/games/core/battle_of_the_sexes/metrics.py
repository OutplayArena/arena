from __future__ import annotations


from outplaylabs_arena.game_components.game_metrics import GameMetrics
from outplaylabs_arena.metrics.extension import GameMetricsExtension


class BoSMetrics(GameMetrics, GameMetricsExtension):

    def compute(self, history: list[dict], total_scores: dict) -> dict:
        n = len(history)
        coordinated = [e["coordinated"] for e in history]
        outcomes = [e["outcome"] for e in history]
        return {
            "total_payoff":       dict(total_scores),
            "average_payoff":     {p: (total_scores[p] / n if n else 0.0) for p in total_scores},
            "coordination_rate":  sum(coordinated) / n if n else 0.0,
            "outcome_counts":     {k: outcomes.count(k) for k in ("AA", "BB", "AB", "BA")},
        }

    def compute_joint(self, match, config: dict) -> dict:
        option_a = config.get("option_a_label", "opera")

        coordinated = 0
        a_wins = 0  # A's preferred outcome (both chose option_a)
        b_wins = 0  # B's preferred outcome (both chose option_b)
        total = 0

        for r in range(match.num_rounds()):
            moves = match.moves_by_round(r)
            acts = {m.agent_id: m.action for m in moves if isinstance(m.action, str)}
            if len(acts) == 2:
                total += 1
                vals = list(acts.values())
                if vals[0] == vals[1]:
                    coordinated += 1
                    if vals[0] == option_a:
                        a_wins += 1
                    else:
                        b_wins += 1

        coordination_rate = coordinated / total if total else 0.0
        equilibrium_selection_rate = (
            max(a_wins, b_wins) / coordinated if coordinated else 0.0
        )

        return {
            "bos_coordination_rate":       coordination_rate,
            "bos_a_preferred_rate":        a_wins / total if total else 0.0,
            "bos_b_preferred_rate":        b_wins / total if total else 0.0,
            "equilibrium_selection_rate":  equilibrium_selection_rate,
        }

    def compute_agent(self, match, agent_id: str, config: dict, joint: dict) -> dict:
        option_a = config.get("option_a_label", "opera")
        option_b = config.get("option_b_label", "football")
        actions = [a for a in match.actions(agent_id) if isinstance(a, str)]
        n = len(actions)
        if n == 0:
            return {}

        preferred = option_a if agent_id == match.agent_ids[0] else option_b
        return {
            "bos": {
                "preferred_rate":   actions.count(preferred) / n,
                "option_a_rate":    actions.count(option_a) / n,
                "option_b_rate":    actions.count(option_b) / n,
                "first_move":       actions[0] if actions else None,
            }
        }
