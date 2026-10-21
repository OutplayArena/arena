"""External regret for finite actions against a fully observed opponent trace."""

import math
from collections.abc import Callable, Sequence
from dataclasses import dataclass


@dataclass(frozen=True)
class FiniteActionGame:
    """Deterministic payoff adapter, from one player's perspective.

    Action order defines deterministic tie-breaking. The payoff range is computed
    over the entire matrix, rather than just the observed trajectory.
    """

    actions: tuple[str, ...]
    opponent_actions: tuple[str, ...]
    payoff: Callable[[str, str], float]

    def matrix(self) -> dict[str, dict[str, float]]:
        """Validate and materialize the finite payoff matrix."""
        for choices in (self.actions, self.opponent_actions):
            if not choices or any(not isinstance(a, str) for a in choices):
                raise ValueError("action sets must be nonempty sequences of strings")
            if len(set(choices)) != len(choices):
                raise ValueError("action sets must contain unique actions")
        matrix = {
            a: {b: float(self.payoff(a, b)) for b in self.opponent_actions}
            for a in self.actions
        }
        if any(not math.isfinite(v) for row in matrix.values() for v in row.values()):
            raise ValueError("payoffs must be finite")
        return matrix


def unavailable(reason: str) -> dict:
    """Return an explicit unavailable metric without fabricated numeric values."""
    return {"status": "unavailable", "reason": reason}


def external_regret(
    game: FiniteActionGame,
    actions: Sequence[str],
    opponent_actions: Sequence[str],
    realized_payoffs: Sequence[float] | None = None,
) -> dict:
    """Compute signed external regret and every 1-based trajectory prefix.

    Args:
        game: Finite deterministic payoff callback and ordered action sets.
        actions: The player's executed actions in chronological order.
        opponent_actions: Observed opponent actions in the same rounds.
        realized_payoffs: Optional logged payoffs, checked against the matrix.

    Returns:
        JSON-compatible totals, all fixed-action payoffs, and a prefix series.
        Empty trajectories return an unavailable status. A constant payoff
        matrix has undefined normalization (null), but valid raw regret.

    Raises:
        ValueError: Actions, lengths, payoffs, or the game matrix are invalid.
    """
    matrix = game.matrix()
    if len(actions) != len(opponent_actions):
        raise ValueError("player and opponent trajectories must have equal lengths")
    if realized_payoffs is not None and len(realized_payoffs) != len(actions):
        raise ValueError("logged payoffs must have one value per round")
    values = [v for row in matrix.values() for v in row.values()]
    low, high = min(values), max(values)
    span = high - low
    if not math.isfinite(span):
        raise ValueError("payoff range must be finite")
    if not actions:
        return unavailable("empty trajectory")
    totals = dict.fromkeys(game.actions, 0.0)
    actual = 0.0
    series = []
    for t, (action, opponent) in enumerate(zip(actions, opponent_actions), start=1):
        if not isinstance(action, str) or action not in matrix:
            raise ValueError(f"invalid player action at round {t}")
        if not isinstance(opponent, str) or opponent not in game.opponent_actions:
            raise ValueError(f"invalid opponent action at round {t}")
        payoff = matrix[action][opponent]
        if realized_payoffs is not None:
            logged = realized_payoffs[t - 1]
            if isinstance(logged, bool) or not isinstance(logged, (int, float)):
                raise ValueError(f"invalid logged payoff at round {t}")
            if not math.isfinite(logged) or not math.isclose(
                logged, payoff, rel_tol=1e-9, abs_tol=1e-9
            ):
                raise ValueError(f"logged payoff disagrees with game at round {t}")
            payoff = float(logged)
        actual += payoff
        for fixed in game.actions:
            totals[fixed] += matrix[fixed][opponent]
        best = max(totals, key=totals.__getitem__)
        regret = totals[best] - actual
        if any(not math.isfinite(v) for v in (*totals.values(), actual, regret)):
            raise ValueError("cumulative payoffs must be finite")
        series.append(
            {
                "round": t,
                "cumulative": regret,
                "average": regret / t,
                "normalized_average": (regret / t) / span if span else None,
                "best_fixed_action": best,
            }
        )
    return {
        "status": "available",
        "cumulative": series[-1]["cumulative"],
        "average": series[-1]["average"],
        "normalized_average": series[-1]["normalized_average"],
        "best_fixed_action": best,
        "best_fixed_total_payoff": totals[best],
        "fixed_action_total_payoffs": totals,
        "actual_total_payoff": actual,
        "num_rounds": len(actions),
        "payoff_range": {"min": low, "max": high},
        "series": series,
    }
