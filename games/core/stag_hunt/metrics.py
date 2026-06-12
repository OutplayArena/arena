from __future__ import annotations

from nash_arena.game_components.game_metrics import GameMetrics
from nash_arena.metrics.extension import GameMetricsExtension


def _outcome_counts(history: list[dict]) -> dict[str, int]:
    counts: dict[str, int] = {"SS": 0, "SH": 0, "HS": 0, "HH": 0}
    for entry in history:
        outcome = entry.get("outcome")
        if outcome in counts:
            counts[outcome] += 1
    return counts


class StagHuntMetrics(GameMetrics, GameMetricsExtension):

    def compute(self, history: list[dict], total_scores: dict) -> dict:
        n = len(history)
        counts = _outcome_counts(history)
        stag_counts: dict[str, int] = {"A": 0, "B": 0}
        for entry in history:
            for player in ("A", "B"):
                if entry.get("actions", {}).get(player) == "stag":
                    stag_counts[player] += 1
        return {
            "total_payoff":          dict(total_scores),
            "average_payoff":        {p: (total_scores[p] / n if n else 0.0) for p in total_scores},
            "stag_rate":             {p: (stag_counts[p] / n if n else 0.0) for p in ("A", "B")},
            "mutual_stag_rate":      counts["SS"] / n if n else 0.0,
            "mutual_hare_rate":      counts["HH"] / n if n else 0.0,
            "outcome_counts":        counts,
        }

    def compute_joint(self, match, config: dict) -> dict:
        counts: dict[str, int] = {"SS": 0, "SH": 0, "HS": 0, "HH": 0}
        total = 0
        agents = match.agent_ids
        for r in range(match.num_rounds()):
            moves = match.moves_by_round(r)
            acts = {m.agent_id: m.action for m in moves if isinstance(m.action, str)}
            if len(acts) == 2 and len(agents) >= 2:
                a_code = "S" if acts.get(agents[0]) == "stag" else "H"
                b_code = "S" if acts.get(agents[1]) == "stag" else "H"
                key = a_code + b_code
                if key in counts:
                    counts[key] += 1
                    total += 1

        pareto_welfare = config.get("payoff_stag_stag", 4.0) * 2
        hare_welfare = config.get("payoff_hare_hare", 2.0) * 2
        price_of_risk = hare_welfare / pareto_welfare if pareto_welfare > 0 else 0.0

        pareto_selection_rate = counts["SS"] / total if total else 0.0

        return {
            "sh_outcome_counts":        {k: (v / total if total else 0.0) for k, v in counts.items()},
            "sh_mutual_stag_rate":      counts["SS"] / total if total else 0.0,
            "sh_mutual_hare_rate":      counts["HH"] / total if total else 0.0,
            "sh_price_of_risk":         price_of_risk,
            "equilibrium_selection_rate": pareto_selection_rate,
        }

    def compute_agent(self, match, agent_id: str, config: dict, joint: dict) -> dict:
        actions = [a for a in match.actions(agent_id) if isinstance(a, str)]
        n = len(actions)
        if n == 0:
            return {}

        agents = match.agent_ids
        opponent_id = next((a for a in agents if a != agent_id), None)
        opp_actions = [a for a in match.actions(opponent_id) if isinstance(a, str)] if opponent_id else []

        stag_after_stag = 0
        stag_after_hare = 0
        opp_stag_count = 0
        opp_hare_count = 0
        for i in range(1, min(len(actions), len(opp_actions))):
            if opp_actions[i - 1] == "stag":
                opp_stag_count += 1
                if actions[i] == "stag":
                    stag_after_stag += 1
            else:
                opp_hare_count += 1
                if actions[i] == "stag":
                    stag_after_hare += 1

        return {
            "sh": {
                "stag_rate":          actions.count("stag") / n,
                "first_move":         actions[0] if actions else None,
                "stag_after_stag":    stag_after_stag / opp_stag_count if opp_stag_count else 0.0,
                "stag_after_hare":    stag_after_hare / opp_hare_count if opp_hare_count else 0.0,
            }
        }
