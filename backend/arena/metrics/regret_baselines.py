"""Seeded full-information baselines on losses normalized to [0, 1]."""

import math
import random
from collections.abc import Sequence
from typing import Literal

from arena.metrics.external_regret import FiniteActionGame, external_regret


class FullInformationLearner:
    """Common payoff scaling and feedback for the two offline baselines.

    Loss(a, b) = (max_payoff - payoff(a, b)) / payoff_range. A constant
    payoff matrix gives zero losses. Learning rates therefore do not depend on
    the game's payoff units. Call choose_action before observing each round.
    """

    def __init__(
        self, game: FiniteActionGame, learning_rate: float, seed: int = 0
    ) -> None:
        if not math.isfinite(learning_rate) or learning_rate <= 0:
            raise ValueError("learning_rate must be finite and positive")
        self.learning_rate = learning_rate
        self.actions = game.actions
        self.matrix = game.matrix()
        values = [v for row in self.matrix.values() for v in row.values()]
        self.high = max(values)
        self.span = self.high - min(values)
        if not math.isfinite(self.span):
            raise ValueError("payoff range must be finite")
        self.cumulative_losses = dict.fromkeys(game.actions, 0.0)
        self.rng = random.Random(seed)

    def observe(self, opponent_action: str) -> None:
        """Update every action's historical loss after observing the round."""
        if (
            not isinstance(opponent_action, str)
            or opponent_action not in self.matrix[self.actions[0]]
        ):
            raise ValueError("invalid opponent action")
        for action in self.actions:
            loss = (
                (self.high - self.matrix[action][opponent_action]) / self.span
                if self.span
                else 0
            )
            self.cumulative_losses[action] += loss


class FTPL(FullInformationLearner):
    """Follow the perturbed leader with fresh exponential reward perturbations.

    Choose argmin_a [L_{t-1}(a) - Z_t(a)/eta], with independent Exp(1)
    perturbations Z_t(a). This is a full-information finite-experts baseline;
    eta acts on normalized losses and perturbation scale is 1/eta.
    """

    def choose_action(self) -> str:
        """Sample perturbations and select using only past cumulative losses."""
        smallest = min(self.cumulative_losses.values())
        return min(
            self.actions,
            key=lambda a: (
                self.learning_rate * (self.cumulative_losses[a] - smallest)
                - self.rng.expovariate(1)
            ),
        )


class FTRL(FullInformationLearner):
    """Entropy-regularized FTRL (Hedge), sampling p_t ∝ exp(-eta L_{t-1}).

    The objective over the probability simplex is <L_{t-1}, p> +
    sum_a p(a) log p(a) / eta. Reported regret uses the sampled actions'
    realized payoffs, rather than expected payoffs under p_t.
    """

    def probabilities(self) -> list[float]:
        """Return stable Hedge probabilities in the adapter's action order."""
        smallest = min(self.cumulative_losses.values())
        weights = [
            math.exp(-self.learning_rate * (self.cumulative_losses[a] - smallest))
            for a in self.actions
        ]
        total = sum(weights)
        return [w / total for w in weights]

    def choose_action(self) -> str:
        """Sample a fixed action using feedback available before this round."""
        return self.rng.choices(self.actions, weights=self.probabilities(), k=1)[0]


def replay_baseline(
    game: FiniteActionGame,
    opponent_actions: Sequence[str],
    algorithm: Literal["ftpl", "ftrl"],
    *,
    seed: int = 0,
    learning_rate: float | None = None,
) -> dict:
    """Run a baseline against a fixed trace, choosing before current feedback.

    The horizon is assumed known. The default constant eta is
    sqrt(2 log(K) / T) (eta=1 for K=1 or an empty trace). This convention
    is shared for reproducible comparisons, not a claim of an optimal FTPL
    constant. Offline replay does not simulate an adaptive opponent's response.
    """
    if algorithm not in {"ftpl", "ftrl"}:
        raise ValueError("algorithm must be 'ftpl' or 'ftrl'")
    if learning_rate is None:
        learning_rate = (
            math.sqrt(2 * math.log(len(game.actions)) / len(opponent_actions))
            if len(game.actions) > 1 and opponent_actions
            else 1.0
        )
    learner = (FTPL if algorithm == "ftpl" else FTRL)(game, learning_rate, seed)
    actions = []
    for opponent in opponent_actions:
        actions.append(learner.choose_action())
        learner.observe(opponent)
    return {
        "algorithm": algorithm,
        "seed": seed,
        "learning_rate": learning_rate,
        "actions": actions,
        "opponent_actions": list(opponent_actions),
        "external_regret": external_regret(game, actions, opponent_actions),
    }
