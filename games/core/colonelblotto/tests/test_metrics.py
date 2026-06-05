from games.core.colonelblotto.metrics import compute_colonel_blotto_metrics


def test_blotto_metrics_include_declared_keys():
    metrics = compute_colonel_blotto_metrics(
        history=[
            {
                "winner": "A",
                "allocations": {"A": [10, 0, 0], "B": [0, 5, 5]},
            }
        ],
        total_scores={"A": 1, "B": 2},
    )

    assert set(metrics) == {
        "total_payoff",
        "average_payoff",
        "round_win_counts",
        "round_win_rate",
        "allocation_concentration",
    }
