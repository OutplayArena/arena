from games.core.colonelblotto.metrics import compute_colonel_blotto_metrics


def test_blotto_metrics_handle_forfeited_round():
    """A forfeited round stores `None` as the forfeiting opponent's allocation
    (see engine.forfeit_round); compute must not crash on it (issue #134)."""
    metrics = compute_colonel_blotto_metrics(
        history=[
            {
                "winner": "A",
                "allocations": {"A": [10, 0, 0], "B": [0, 5, 5]},
            },
            {
                "winner": "B",
                "allocations": {"A": [0, 0, 0], "B": None},
                "forfeit": True,
                "forfeit_by": "A",
            },
        ],
        total_scores={"A": 1, "B": 5},
    )

    # A: round 1 ratio 10/10=1.0, round 2 (all-zero allocation) ratio 0.0 -> avg 0.5
    assert metrics["allocation_concentration"]["A"] == 0.5
    # B: only round 1 counts (round 2 is None, skipped) -> ratio 5/10=0.5
    assert metrics["allocation_concentration"]["B"] == 0.5


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
