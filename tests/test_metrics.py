import pytest

from games.core.blotto.engine import BlottoGame
from games.core.blotto.metrics import (
    BlottoMetrics,
    allocation_concentration,
    average_payoff,
    compute_blotto_metrics,
    round_win_counts,
    round_win_rate,
)


def sample_history():
    return [
        {
            "round": 1,
            "allocations": {"A": [10, 0, 0], "B": [4, 3, 3]},
            "scores": {"A": 2, "B": 1},
            "winner": "A",
            "total_scores": {"A": 2, "B": 1},
        },
        {
            "round": 2,
            "allocations": {"A": [3, 3, 4], "B": [0, 10, 0]},
            "scores": {"A": 1, "B": 2},
            "winner": "B",
            "total_scores": {"A": 3, "B": 3},
        },
        {
            "round": 3,
            "allocations": {"A": [4, 3, 3], "B": [4, 3, 3]},
            "scores": {"A": 1.5, "B": 1.5},
            "winner": "Tie",
            "total_scores": {"A": 4.5, "B": 4.5},
        },
    ]


def test_compute_metrics_handles_empty_history():
    assert compute_blotto_metrics([], {"A": 0, "B": 0}) == {
        "total_payoff": {"A": 0, "B": 0},
        "average_payoff": {"A": 0, "B": 0},
        "round_win_counts": {"A": 0, "B": 0, "Tie": 0},
        "round_win_rate": {"A": 0, "B": 0, "Tie": 0},
        "allocation_concentration": {"A": 0, "B": 0},
    }


def test_average_payoff_divides_total_score_by_rounds():
    assert average_payoff(sample_history(), {"A": 6, "B": 3}) == {
        "A": 2.0,
        "B": 1.0,
    }


def test_round_win_counts_and_rates():
    counts = round_win_counts(sample_history())

    assert counts == {"A": 1, "B": 1, "Tie": 1}
    assert round_win_rate(sample_history(), counts) == {
        "A": pytest.approx(1 / 3),
        "B": pytest.approx(1 / 3),
        "Tie": pytest.approx(1 / 3),
    }


def test_round_win_counts_rejects_unknown_winner():
    with pytest.raises(ValueError, match="unknown round winner"):
        round_win_counts([{"winner": "C"}])


def test_allocation_concentration_averages_max_share_per_round():
    assert allocation_concentration(sample_history()) == {
        "A": pytest.approx(0.6),
        "B": pytest.approx(0.6),
    }


def test_compute_blotto_metrics_combines_all_metrics():
    assert compute_blotto_metrics(sample_history(), {"A": 4.5, "B": 4.5}) == {
        "total_payoff": {"A": 4.5, "B": 4.5},
        "average_payoff": {"A": 1.5, "B": 1.5},
        "round_win_counts": {"A": 1, "B": 1, "Tie": 1},
        "round_win_rate": {
            "A": pytest.approx(1 / 3),
            "B": pytest.approx(1 / 3),
            "Tie": pytest.approx(1 / 3),
        },
        "allocation_concentration": {
            "A": pytest.approx(0.6),
            "B": pytest.approx(0.6),
        },
    }


def test_blotto_metrics_class_matches_function_wrapper():
    assert BlottoMetrics().compute(sample_history(), {"A": 4.5, "B": 4.5}) == (
        compute_blotto_metrics(sample_history(), {"A": 4.5, "B": 4.5})
    )


def test_compute_results_includes_metrics():
    game = BlottoGame(num_battlefields=3, total_resources=9, num_rounds=1)
    state = game.initial_state()

    state = game.apply_action(state, "A", [9, 0, 0])
    state = game.apply_action(state, "B", [0, 5, 4])

    results = game.compute_results(state)

    assert results["metrics"] == {
        "total_payoff": {"A": 1, "B": 2},
        "average_payoff": {"A": 1.0, "B": 2.0},
        "round_win_counts": {"A": 0, "B": 1, "Tie": 0},
        "round_win_rate": {"A": 0.0, "B": 1.0, "Tie": 0.0},
        "allocation_concentration": {"A": 1.0, "B": pytest.approx(5 / 9)},
    }
