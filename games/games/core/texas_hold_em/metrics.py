from __future__ import annotations

from arena.game_components.game_metrics import GameMetrics
from arena.metrics.extension import GameMetricsExtension


def _rate(actions: list[str], target: str) -> float:
    if not actions:
        return 0.0
    return actions.count(target) / len(actions)


def _actual_pot_share(entry: dict, player: str) -> float:
    """Fraction of a hand's total pot `player` actually won (0.0-1.0),
    correctly handling side pots at showdown."""
    pot = entry.get("pot") or 0.0
    if pot <= 0:
        return 0.0
    result = entry.get("result") or {}
    outcome = result.get("outcome")
    if outcome in ("fold", "forfeit"):
        return 1.0 if result.get("winner") == player else 0.0
    if outcome == "showdown":
        share = 0.0
        for p in result.get("pots", []):
            winners = p.get("winners", [])
            if player in winners:
                share += p.get("amount", 0.0) / len(winners)
        return share / pot
    return 0.0


class TexasHoldEmMetrics(GameMetrics, GameMetricsExtension):

    def compute(self, history: list[dict], total_scores: dict) -> dict:
        players = list(total_scores.keys())
        n = len(history)
        win_ct: dict[str, int] = {p: 0 for p in players}
        win_ct["Tie"] = 0
        showdowns = 0
        folds: dict[str, int] = {p: 0 for p in players}
        raises: dict[str, int] = {p: 0 for p in players}
        all_acts: dict[str, list[str]] = {p: [] for p in players}
        for entry in history:
            r = entry.get("result") or {}
            w = r.get("winner", "Tie")
            if w not in win_ct:
                win_ct[w] = 0
            win_ct[w] += 1
            if r.get("outcome") == "showdown":
                showdowns += 1
            for act in entry.get("street_actions", []):
                p = act.get("player", "")
                a = act.get("action", "")
                if p not in all_acts:
                    continue
                all_acts[p].append(a)
                if a == "fold":
                    folds[p] = folds.get(p, 0) + 1
                elif a == "raise":
                    raises[p] = raises.get(p, 0) + 1

        result = {
            "total_payoff": dict(total_scores),
            "average_payoff": {p: (total_scores[p] / n if n else 0.0) for p in players},
            "hand_win_counts": win_ct,
            "hand_win_rate": {k: (v / n if n else 0.0) for k, v in win_ct.items()},
            "fold_rate": {p: _rate(all_acts[p], "fold") for p in players},
            "raise_rate": {p: _rate(all_acts[p], "raise") for p in players},
            "showdown_count": showdowns,
            "fold_count": folds,
            "raise_count": raises,
        }

        # Equity-based metrics (#24): only present when `compute_hand_equity`
        # was enabled, since each entry then carries a `preflop_equity` dict.
        equity_hands = [e for e in history if e.get("preflop_equity")]
        if equity_hands:
            fold_equities: dict[str, list[float]] = {p: [] for p in players}
            equity_deltas: dict[str, list[float]] = {p: [] for p in players}
            for e in equity_hands:
                pe = e["preflop_equity"]
                folded_this_hand = {
                    a.get("player") for a in e.get("street_actions", []) if a.get("action") == "fold"
                }
                for p in players:
                    if p not in pe:
                        continue
                    if p in folded_this_hand:
                        fold_equities[p].append(pe[p])
                    equity_deltas[p].append(_actual_pot_share(e, p) - pe[p])
            result["conservativeness_index"] = {
                # Average preflop equity of hands this player folded: low =
                # only folds genuinely bad hands (loose), high = folds even
                # decent hands (tight/conservative). None = never folded.
                p: (sum(v) / len(v) if v else None) for p, v in fold_equities.items()
            }
            result["equity_realization"] = {
                # Actual pot share won minus preflop equity, averaged across
                # hands: positive = outperforming preflop equity (e.g. via
                # postflop play or opponents folding), negative = underneath.
                p: (sum(v) / len(v) if v else 0.0) for p, v in equity_deltas.items()
            }

        return result

    def compute_joint(self, match, config: dict) -> dict:
        agents = match.agent_ids
        n = len(agents)
        showdowns = 0
        total = 0
        for r in range(match.num_rounds()):
            moves = match.moves_by_round(r)
            acts = {m.agent_id: m.action for m in moves if isinstance(m.action, str)}
            if len(acts) >= n:
                total += 1
                if all(v != "fold" for v in acts.values()):
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
