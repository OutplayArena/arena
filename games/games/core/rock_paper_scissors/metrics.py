from __future__ import annotations

import numpy as np

from arena.game_components.game_metrics import GameMetrics
from arena.metrics.extension import GameMetricsExtension

MOVES = ("rock", "paper", "scissors")


def _move_frequencies(actions: list[str]) -> dict[str, float]:
    n = len(actions)
    if n == 0:
        return {m: 0.0 for m in MOVES}
    return {m: actions.count(m) / n for m in MOVES}


def _nash_distance(freqs: dict[str, float]) -> float:
    """Total variation distance from the uniform 1/3-1/3-1/3 Nash equilibrium."""
    uniform = 1.0 / 3.0
    return 0.5 * sum(abs(freqs.get(m, 0.0) - uniform) for m in MOVES)


def _pattern_exploitability(actions: list[str]) -> float:
    """Mean lag-1 autocorrelation of encoded move sequence (0=random, 1=predictable)."""
    if len(actions) < 3:
        return 0.0
    encode = {m: float(i) for i, m in enumerate(MOVES)}
    arr = np.array([encode[a] for a in actions if a in encode])
    if len(arr) < 3:
        return 0.0
    if np.std(arr) < 1e-8:
        return 1.0
    n = (arr - np.mean(arr)) / np.std(arr)
    with np.errstate(invalid="ignore", divide="ignore"):
        corr = float(abs(np.corrcoef(n[:-1], n[1:])[0, 1]))
    return 0.0 if np.isnan(corr) else corr


class RPSMetrics(GameMetrics, GameMetricsExtension):

    # ── GameMetrics (legacy, used by compute_results) ────────────────────────

    def compute(self, history: list[dict], total_scores: dict) -> dict:
        n = len(history)
        win_counts: dict[str, int] = {"A": 0, "B": 0, "Tie": 0}
        all_actions: dict[str, list[str]] = {"A": [], "B": []}
        for entry in history:
            winner = entry.get("winner", "Tie")
            if winner in win_counts:
                win_counts[winner] += 1
            for player in ("A", "B"):
                act = entry.get("actions", {}).get(player)
                if act:
                    all_actions[player].append(act)
        return {
            "total_payoff":     dict(total_scores),
            "average_payoff":   {p: (total_scores[p] / n if n else 0.0) for p in total_scores},
            "round_win_counts": win_counts,
            "round_win_rate":   {k: (v / n if n else 0.0) for k, v in win_counts.items()},
            "move_frequencies": {p: _move_frequencies(all_actions[p]) for p in ("A", "B")},
        }

    # ── GameMetricsExtension (rich, used by MatchEvaluator) ─────────────────

    def compute_joint(self, match, config: dict) -> dict:
        collision = 0
        total = 0
        for r in range(match.num_rounds()):
            moves = match.moves_by_round(r)
            acts = {m.agent_id: m.action for m in moves if isinstance(m.action, str)}
            if len(acts) == 2:
                total += 1
                vals = list(acts.values())
                if vals[0] == vals[1]:
                    collision += 1
        return {"rps_collision_rate": collision / total if total else 0.0}

    def compute_agent(self, match, agent_id: str, config: dict, joint: dict) -> dict:
        actions = [a for a in match.actions(agent_id) if isinstance(a, str) and a in MOVES]
        freqs = _move_frequencies(actions)
        return {
            "rps": {
                "move_frequencies":       freqs,
                "nash_distance":          _nash_distance(freqs),
                "pattern_exploitability": _pattern_exploitability(actions),
            }
        }
