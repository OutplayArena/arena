from __future__ import annotations

from outplaylabs_arena.game_components.game_metrics import GameMetrics
from outplaylabs_arena.metrics.extension import GameMetricsExtension


def _rate(actions: list[str], target: str) -> float:
    if not actions:
        return 0.0
    return actions.count(target) / len(actions)


class TexasHoldEmMetrics(GameMetrics, GameMetricsExtension):

    def compute(self, history: list[dict], total_scores: dict) -> dict:
        n = len(history)
        win_ct: dict[str, int] = {"A": 0, "B": 0, "Tie": 0}
        showdowns = 0
        folds = {"A": 0, "B": 0}
        raises = {"A": 0, "B": 0}
        for entry in history:
            r = entry.get("result", {})
            w = r.get("winner", "Tie")
            if w in win_ct:
                win_ct[w] += 1
            if r.get("outcome") == "showdown":
                showdowns += 1
            for act in entry.get("street_actions", []):
                p = act.get("player", "")
                a = act.get("action", "")
                if a == "fold":
                    folds[p] = folds.get(p, 0) + 1
                elif a == "raise":
                    raises[p] = raises.get(p, 0) + 1

        all_acts: dict[str, list[str]] = {"A": [], "B": []}
        for entry in history:
            for act in entry.get("street_actions", []):
                p = act.get("player", "")
                a = act.get("action", "")
                if p in all_acts:
                    all_acts[p].append(a)

        return {
            "total_payoff": dict(total_scores),
            "average_payoff": {p: (total_scores[p] / n if n else 0.0) for p in total_scores},
            "hand_win_counts": win_ct,
            "hand_win_rate": {k: (v / n if n else 0.0) for k, v in win_ct.items()},
            "fold_rate": {p: _rate(all_acts[p], "fold") for p in ("A", "B")},
            "raise_rate": {p: _rate(all_acts[p], "raise") for p in ("A", "B")},
            "showdown_count": showdowns,
            "fold_count": folds,
            "raise_count": raises,
        }

    def compute_joint(self, match, config: dict) -> dict:
        showdowns = 0
        total = 0
        for r in range(match.num_rounds()):
            moves = match.moves_by_round(r)
            acts = {m.agent_id: m.action for m in moves if isinstance(m.action, str)}
            if len(acts) >= 2:
                total += 1
                vals = list(acts.values())
                if vals[0] != "fold" and vals[1] != "fold":
                    showdowns += 1
        return {"the_showdown_rate": showdowns / total if total else 0.0}

    def compute_agent(self, match, agent_id: str, config: dict, joint: dict) -> dict:
        acts = [a for a in match.actions(agent_id) if isinstance(a, str) and a in ("fold", "check", "call", "raise")]
        return {
            "the": {
                "fold_rate": _rate(acts, "fold"),
                "check_rate": _rate(acts, "check"),
                "call_rate": _rate(acts, "call"),
                "raise_rate": _rate(acts, "raise"),
            }
        }
