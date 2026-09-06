from __future__ import annotations

from arena.game_components.game_metrics import GameMetrics
from arena.metrics.extension import GameMetricsExtension


def _outcome_counts(history: list[dict]) -> dict[str, int]:
    counts: dict[str, int] = {"DD": 0, "DS": 0, "SD": 0, "SS": 0}
    for entry in history:
        outcome = entry.get("outcome")
        if outcome in counts:
            counts[outcome] += 1
    return counts


def _mixed_ne_dare_probability(payoff_win: float, payoff_tie: float, payoff_lose: float, payoff_crash: float) -> float:
    """Equilibrium dare probability q* for the symmetric mixed-strategy Nash
    equilibrium of Chicken, where the opponent's dare probability makes a
    player indifferent between Swerve and Dare.

    q* = (T - R) / ((T - R) + (S - P))
    with T=payoff_win, R=payoff_tie, S=payoff_lose, P=payoff_crash.
    """
    numerator = payoff_win - payoff_tie
    denominator = numerator + (payoff_lose - payoff_crash)
    if denominator == 0:
        return 0.5
    return numerator / denominator


def _alternation_index(history: list[dict]) -> float:
    """Degree of turn-taking (alternating who yields) across asymmetric rounds.

    Considers only rounds with a one-sided outcome (DS or SD) and measures
    the fraction of consecutive such rounds where the yielding player switched.
    """
    yielders: list[str] = []
    for entry in history:
        outcome = entry.get("outcome")
        if outcome == "DS":
            yielders.append("B")
        elif outcome == "SD":
            yielders.append("A")
    if len(yielders) < 2:
        return 0.0
    switches = sum(1 for i in range(1, len(yielders)) if yielders[i] != yielders[i - 1])
    return switches / (len(yielders) - 1)


class ChickenGameMetrics(GameMetrics, GameMetricsExtension):
    def __init__(
        self,
        payoff_win: float = 1.0,
        payoff_tie: float = 0.0,
        payoff_lose: float = -1.0,
        payoff_crash: float = -10.0,
    ):
        self.payoff_win = payoff_win
        self.payoff_tie = payoff_tie
        self.payoff_lose = payoff_lose
        self.payoff_crash = payoff_crash

    def compute(self, history: list[dict], total_scores: dict) -> dict:
        n = len(history)
        counts = _outcome_counts(history)
        dare_counts: dict[str, int] = {"A": 0, "B": 0}
        exploit_counts: dict[str, int] = {"A": 0, "B": 0}
        for entry in history:
            actions = entry.get("actions", {})
            for player in ("A", "B"):
                if actions.get(player) == "dare":
                    dare_counts[player] += 1
            if entry.get("outcome") == "DS":
                exploit_counts["A"] += 1
            elif entry.get("outcome") == "SD":
                exploit_counts["B"] += 1

        dare_rate = {p: (dare_counts[p] / n if n else 0.0) for p in ("A", "B")}
        q_star = _mixed_ne_dare_probability(
            self.payoff_win, self.payoff_tie, self.payoff_lose, self.payoff_crash
        )

        return {
            "total_payoff":   dict(total_scores),
            "average_payoff": {p: (total_scores[p] / n if n else 0.0) for p in total_scores},
            "dare_rate":      dare_rate,
            "crash_rate":     counts["DD"] / n if n else 0.0,
            "yield_rate":     counts["SS"] / n if n else 0.0,
            "exploit_rate":   {p: (exploit_counts[p] / n if n else 0.0) for p in ("A", "B")},
            "mixed_ne_gap": {
                "A": abs(dare_rate["A"] - q_star),
                "B": abs(dare_rate["B"] - q_star),
                "nash_dare_probability": q_star,
            },
            "alternation_index": _alternation_index(history),
            "outcome_counts":    counts,
        }

    def compute_joint(self, match, config: dict) -> dict:
        counts: dict[str, int] = {"DD": 0, "DS": 0, "SD": 0, "SS": 0}
        total = 0
        agents = match.agent_ids
        for r in range(match.num_rounds()):
            moves = match.moves_by_round(r)
            acts = {m.agent_id: m.action for m in moves if isinstance(m.action, str)}
            if len(acts) == 2 and len(agents) >= 2:
                a_code = "D" if acts.get(agents[0]) == "dare" else "S"
                b_code = "D" if acts.get(agents[1]) == "dare" else "S"
                key = a_code + b_code
                if key in counts:
                    counts[key] += 1
                    total += 1

        payoff_win = config.get("payoff_win", 1.0)
        payoff_tie = config.get("payoff_tie", 0.0)
        payoff_lose = config.get("payoff_lose", -1.0)
        payoff_crash = config.get("payoff_crash", -10.0)
        q_star = _mixed_ne_dare_probability(payoff_win, payoff_tie, payoff_lose, payoff_crash)

        pooled_dare_rate = (2 * counts["DD"] + counts["DS"] + counts["SD"]) / (2 * total) if total else 0.0

        return {
            "cg_outcome_counts":         {k: (v / total if total else 0.0) for k, v in counts.items()},
            "cg_crash_rate":             counts["DD"] / total if total else 0.0,
            "cg_yield_rate":             counts["SS"] / total if total else 0.0,
            "cg_mixed_ne_gap":           abs(pooled_dare_rate - q_star),
            "cg_nash_dare_probability":  q_star,
        }

    def compute_agent(self, match, agent_id: str, config: dict, joint: dict) -> dict:
        actions = [a for a in match.actions(agent_id) if isinstance(a, str)]
        n = len(actions)
        if n == 0:
            return {}

        agents = match.agent_ids
        opponent_id = next((a for a in agents if a != agent_id), None)
        opp_actions = [a for a in match.actions(opponent_id) if isinstance(a, str)] if opponent_id else []

        dare_after_swerve = 0
        dare_after_dare = 0
        opp_swerve_count = 0
        opp_dare_count = 0
        exploit_count = 0
        for i in range(1, min(len(actions), len(opp_actions))):
            if opp_actions[i - 1] == "swerve":
                opp_swerve_count += 1
                if actions[i] == "dare":
                    dare_after_swerve += 1
            else:
                opp_dare_count += 1
                if actions[i] == "dare":
                    dare_after_dare += 1
        for i in range(min(len(actions), len(opp_actions))):
            if actions[i] == "dare" and opp_actions[i] == "swerve":
                exploit_count += 1

        return {
            "cg": {
                "dare_rate":          actions.count("dare") / n,
                "first_move":         actions[0] if actions else None,
                "dare_after_swerve":  dare_after_swerve / opp_swerve_count if opp_swerve_count else 0.0,
                "dare_after_dare":    dare_after_dare / opp_dare_count if opp_dare_count else 0.0,
                "exploit_rate":       exploit_count / n,
            }
        }
