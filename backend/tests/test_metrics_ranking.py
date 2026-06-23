"""Tests for the Elo and α-Rank ranking metrics."""
import math

import pytest

from arena.metrics.ranking import RankingMetrics


class TestExpectedScore:
    def test_equal_ratings_returns_half(self):
        assert RankingMetrics.expected_score(1500, 1500) == 0.5

    def test_higher_rating_returns_higher_expected(self):
        higher = RankingMetrics.expected_score(1600, 1400)
        lower = RankingMetrics.expected_score(1400, 1600)
        assert higher > 0.5
        assert lower < 0.5
        assert math.isclose(higher + lower, 1.0, rel_tol=1e-9)

    def test_400_point_difference(self):
        score = RankingMetrics.expected_score(1900, 1500)
        assert math.isclose(score, 0.9090909090, rel_tol=1e-4)

    def test_symmetry(self):
        a, b = 1700, 1300
        assert math.isclose(
            RankingMetrics.expected_score(a, b),
            1 - RankingMetrics.expected_score(b, a),
            rel_tol=1e-9,
        )


class TestUpdateEloMultiplayer:
    def test_empty_ratings_returns_empty(self):
        result = RankingMetrics.update_elo_multiplayer({}, {})
        assert result == {}

    def test_single_agent_returns_unchanged(self):
        result = RankingMetrics.update_elo_multiplayer({"A": 1500.0}, {"A": 10.0})
        assert result == {"A": 1500.0}

    def test_two_agents_winner_gains_loser_loses(self):
        ratings = {"A": 1500.0, "B": 1500.0}
        results = {"A": 10.0, "B": 0.0}
        new = RankingMetrics.update_elo_multiplayer(ratings, results)
        assert new["A"] > 1500.0
        assert new["B"] < 1500.0
        # Total magnitude is bounded by K=32 (weight=1.0 for 2-player)
        assert abs(new["A"] - 1500.0) <= 32

    def test_three_player_weighted(self):
        """With 3 players, each pairwise update is weighted 1/(N-1) = 1/2."""
        ratings = {"A": 1500.0, "B": 1500.0, "C": 1500.0}
        results = {"A": 10.0, "B": 5.0, "C": 0.0}
        new = RankingMetrics.update_elo_multiplayer(ratings, results)
        assert new["A"] > 1500.0
        assert new["C"] < 1500.0

    def test_does_not_mutate_input(self):
        ratings = {"A": 1500.0, "B": 1500.0}
        original_a = ratings["A"]
        RankingMetrics.update_elo_multiplayer(ratings, {"A": 10.0, "B": 0.0})
        assert ratings["A"] == original_a

    def test_tie_keeps_ratings_unchanged(self):
        ratings = {"A": 1500.0, "B": 1500.0}
        new = RankingMetrics.update_elo_multiplayer(ratings, {"A": 5.0, "B": 5.0})
        assert new == ratings

    def test_unknown_agent_uses_default_rating(self):
        ratings = {"A": 1500.0}
        new = RankingMetrics.update_elo_multiplayer(
            ratings, {"A": 10.0, "B": 0.0}
        )
        assert "B" in new
        assert new["B"] < 1200.0  # default 1200, lost, so below 1200


class TestAlphaRankFixationProbability:
    def test_equal_payoffs_returns_uniform(self):
        prob = RankingMetrics.alpha_rank_fixation_probability(5.0, 5.0)
        assert prob == pytest.approx(0.01)  # 1/population_size

    def test_dominant_strategy_higher_probability(self):
        prob = RankingMetrics.alpha_rank_fixation_probability(10.0, 0.0)
        assert prob > 0.01

    def test_dominated_strategy_at_most_uniform(self):
        prob = RankingMetrics.alpha_rank_fixation_probability(0.0, 10.0)
        assert prob <= 0.01

    def test_positive_probability(self):
        prob = RankingMetrics.alpha_rank_fixation_probability(8.0, 2.0)
        assert 0 < prob <= 1

    def test_extreme_difference_handled(self):
        """Large delta should not crash and should return sane value."""
        prob = RankingMetrics.alpha_rank_fixation_probability(100.0, 0.0)
        assert 0 < prob <= 1

    def test_higher_alpha_pushes_probability_toward_extremes(self):
        # With strong selection, A's advantage over B should manifest as
        # a fixation probability that deviates from the uniform baseline.
        prob = RankingMetrics.alpha_rank_fixation_probability(8.0, 2.0, alpha=200.0)
        assert prob > 0.01  # higher than the uniform 1/population_size

    def test_custom_population_size(self):
        prob = RankingMetrics.alpha_rank_fixation_probability(5.0, 5.0, population_size=50)
        assert prob == pytest.approx(0.02)
