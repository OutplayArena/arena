from games.core.colonelblotto.metrics import ColonelBlottoMetrics, compute_colonel_blotto_metrics


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


def test_convergence_rate_detects_shrinking_deltas():
    """Allocations that settle toward a fixed strategy over rounds should score
    a positive convergence_rate (issue #135)."""
    from arena.metrics.contracts import Match, Move

    allocs = [[10, 0, 0], [7, 2, 1], [6, 3, 1], [5, 4, 1], [5, 5, 0]]
    match = Match(
        match_id="m1",
        game_type="colonelblotto",
        agent_ids=["A", "B"],
        moves=[
            Move(agent_id="A", round_number=r, action=a, payoff=0.0)
            for r, a in enumerate(allocs)
        ],
    )
    result = ColonelBlottoMetrics().compute_agent(match, "A", config={}, joint={})
    assert result["blotto"]["convergence_rate"] > 0


def test_exploitability_warning_fires_on_predictable_opponent():
    history = [
        {"allocations": {"A": [10, 0, 0], "B": [3, 3, 4]}},
        {"allocations": {"A": [0, 10, 0], "B": [3, 3, 4]}},
        {"allocations": {"A": [0, 0, 10], "B": [3, 3, 4]}},
    ]
    warning = ColonelBlottoMetrics.exploitability_warning(
        {"history": history, "total_scores": {"A": 0, "B": 0}}, player_id="A"
    )
    assert warning is not None
    assert "B" in warning


def test_exploitability_warning_none_with_too_little_history():
    history = [{"allocations": {"A": [10, 0, 0], "B": [3, 3, 4]}}]
    assert ColonelBlottoMetrics.exploitability_warning(
        {"history": history, "total_scores": {"A": 0, "B": 0}}, player_id="A"
    ) is None
