from __future__ import annotations

import math
from itertools import combinations


class RankingMetrics:
    """
    Multi-player Elo and α-Rank fixation probability.

    Multi-player Elo strategy: decompose an N-player match into C(N,2) virtual
    pairwise contests, each weighted by 1/(N-1). Standard approach used in
    multiplayer gaming and endorsed by Glicko authors.
    """

    @staticmethod
    def expected_score(rating_a: float, rating_b: float) -> float:
        return 1.0 / (1.0 + 10 ** ((rating_b - rating_a) / 400))

    @staticmethod
    def update_elo_multiplayer(
        ratings: dict[str, float],
        results: dict[str, float],   # agent_id → avg_payoff this match
        k: float = 32,
    ) -> dict[str, float]:
        """
        N-player Elo update via virtual pairwise decomposition.

        For each ordered pair (i, j):
          score_i = 1 if payoff_i > payoff_j, 0.5 if tied, 0 otherwise
          Weight each update by 1/(N-1) so total update magnitude is K.

        Returns updated ratings dict (does not mutate input).
        """
        new_ratings = dict(ratings)
        agents = list(results)
        n = len(agents)
        if n < 2:
            return new_ratings

        weight = 1.0 / (n - 1)

        for a, b in combinations(agents, 2):
            pa, pb = results[a], results[b]
            score_a = 1.0 if pa > pb else (0.5 if pa == pb else 0.0)
            score_b = 1.0 - score_a

            ea = RankingMetrics.expected_score(new_ratings.get(a, 1200.0), new_ratings.get(b, 1200.0))
            eb = 1.0 - ea

            new_ratings[a] = new_ratings.get(a, 1200.0) + k * weight * (score_a - ea)
            new_ratings[b] = new_ratings.get(b, 1200.0) + k * weight * (score_b - eb)

        return new_ratings

    @staticmethod
    def alpha_rank_fixation_probability(
        payoff_a_vs_b: float,
        payoff_b_vs_a: float,
        alpha: float = 50.0,
        population_size: int = 100,
    ) -> float:
        """Fermi fixation probability of A invading B's population."""
        delta = payoff_a_vs_b - payoff_b_vs_a
        if abs(delta) < 1e-10:
            return 1.0 / population_size

        exp_num = -alpha * delta
        exp_den = -alpha * population_size * delta

        num_val = 0.0 if exp_num < -700 else (float("inf") if exp_num > 700 else math.exp(exp_num))
        den_val = 0.0 if exp_den < -700 else (float("inf") if exp_den > 700 else math.exp(exp_den))

        if math.isinf(num_val) or math.isinf(den_val):
            return 1.0 / population_size

        numerator   = 1.0 - num_val
        denominator = 1.0 - den_val
        if abs(denominator) < 1e-10:
            return 1.0 / population_size

        return numerator / denominator
