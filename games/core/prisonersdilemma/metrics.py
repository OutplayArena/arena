from __future__ import annotations

from nash_arena.game_components.game_metrics import GameMetrics
from nash_arena.metrics.extension import GameMetricsExtension

OUTCOMES = frozenset({"CC", "CD", "DC", "DD"})


def _outcome_counts(history: list[dict]) -> dict[str, int]:
    counts: dict[str, int] = {"CC": 0, "CD": 0, "DC": 0, "DD": 0}
    for entry in history:
        outcome = entry.get("outcome")
        if outcome in counts:
            counts[outcome] += 1
    return counts


class PDMetrics(GameMetrics, GameMetricsExtension):

    # ── GameMetrics (legacy, used by compute_results) ────────────────────────

    def compute(self, history: list[dict], total_scores: dict) -> dict:
        n = len(history)
        counts = _outcome_counts(history)
        coop_counts: dict[str, int] = {"A": 0, "B": 0}
        for entry in history:
            for player in ("A", "B"):
                if entry.get("actions", {}).get(player) == "cooperate":
                    coop_counts[player] += 1
        return {
            "total_payoff":            dict(total_scores),
            "average_payoff":          {p: (total_scores[p] / n if n else 0.0) for p in total_scores},
            "cooperation_rate":        {p: (coop_counts[p] / n if n else 0.0) for p in ("A", "B")},
            "mutual_cooperation_rate": counts["CC"] / n if n else 0.0,
            "mutual_defection_rate":   counts["DD"] / n if n else 0.0,
            "outcome_counts":          counts,
        }

    # ── GameMetricsExtension (rich, used by MatchEvaluator) ─────────────────

    def compute_joint(self, match, config: dict) -> dict:
        counts: dict[str, int] = {"CC": 0, "CD": 0, "DC": 0, "DD": 0}
        total = 0
        agents = match.agent_ids
        for r in range(match.num_rounds()):
            moves = match.moves_by_round(r)
            acts = {m.agent_id: m.action for m in moves if isinstance(m.action, str)}
            if len(acts) == 2 and len(agents) >= 2:
                a_code = "C" if acts.get(agents[0]) == "cooperate" else "D"
                b_code = "C" if acts.get(agents[1]) == "cooperate" else "D"
                key = a_code + b_code
                if key in counts:
                    counts[key] += 1
                    total += 1

        R = config.get("payoff_R", 3.0)
        P = config.get("payoff_P", 1.0)
        poa = P / R if R > 0 else 0.0

        return {
            "pd_outcome_counts":          {k: (v / total if total else 0.0) for k, v in counts.items()},
            "pd_mutual_cooperation_rate": counts["CC"] / total if total else 0.0,
            "pd_price_of_anarchy":        poa,
        }

    def compute_agent(self, match, agent_id: str, config: dict, joint: dict) -> dict:
        actions = [a for a in match.actions(agent_id) if isinstance(a, str)]
        n = len(actions)
        if n == 0:
            return {}

        agents = match.agent_ids
        opponent_id = next((a for a in agents if a != agent_id), None)
        opp_actions = [a for a in match.actions(opponent_id) if isinstance(a, str)] if opponent_id else []

        exploitation = 0
        forgiveness = 0
        opp_defect_count = 0
        for i in range(1, min(len(actions), len(opp_actions))):
            if opp_actions[i - 1] == "cooperate" and actions[i] == "defect":
                exploitation += 1
            if opp_actions[i - 1] == "defect":
                opp_defect_count += 1
                if actions[i] == "cooperate":
                    forgiveness += 1

        return {
            "pd": {
                "cooperation_rate":  actions.count("cooperate") / n,
                "first_move":        actions[0] if actions else None,
                "exploitation_rate": exploitation / (n - 1) if n > 1 else 0.0,
                "forgiveness_rate":  forgiveness / opp_defect_count if opp_defect_count > 0 else 0.0,
            }
        }
