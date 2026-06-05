from games.core.rock_paper_scissors.metrics import (
    RPSMetrics,
    _move_frequencies,
    _nash_distance,
    _pattern_exploitability,
)
from games.core.rock_paper_scissors.engine import RPSGame
from games.core.rock_paper_scissors.config import config_from_dict


def _run_game(moves_a: list[str], moves_b: list[str]) -> tuple[list[dict], dict]:
    cfg = config_from_dict({"game": "rock_paper_scissors", "rounds": len(moves_a)})
    game = RPSGame.from_config(cfg)
    state = game.initial_state()
    for a, b in zip(moves_a, moves_b):
        state = game.apply_action(state, "A", a)
        state = game.apply_action(state, "B", b)
    return state.history, state.total_scores


# ── Low-level helpers ─────────────────────────────────────────────────────────

def test_move_frequencies_uniform():
    actions = ["rock", "paper", "scissors", "rock", "paper", "scissors"]
    freqs = _move_frequencies(actions)
    for m in freqs:
        assert abs(freqs[m] - 1 / 3) < 1e-9


def test_move_frequencies_empty():
    freqs = _move_frequencies([])
    assert all(v == 0.0 for v in freqs.values())


def test_nash_distance_uniform():
    freqs = {"rock": 1 / 3, "paper": 1 / 3, "scissors": 1 / 3}
    assert abs(_nash_distance(freqs)) < 1e-9


def test_nash_distance_pure_rock():
    freqs = {"rock": 1.0, "paper": 0.0, "scissors": 0.0}
    assert abs(_nash_distance(freqs) - 2 / 3) < 1e-9


def test_pattern_exploitability_constant():
    assert _pattern_exploitability(["rock"] * 10) == 1.0


def test_pattern_exploitability_too_short():
    assert _pattern_exploitability(["rock", "paper"]) == 0.0


# ── compute() output ──────────────────────────────────────────────────────────

def test_compute_required_keys():
    history, scores = _run_game(
        ["rock", "paper", "scissors"],
        ["scissors", "rock", "paper"],
    )
    result = RPSMetrics().compute(history, scores)
    for key in ("total_payoff", "average_payoff", "round_win_counts", "round_win_rate", "move_frequencies"):
        assert key in result, f"missing key: {key}"


def test_compute_win_counts_all_a():
    history, scores = _run_game(
        ["rock", "paper", "scissors"],
        ["scissors", "rock", "paper"],
    )
    result = RPSMetrics().compute(history, scores)
    assert result["round_win_counts"]["A"] == 3
    assert result["round_win_counts"]["B"] == 0
    assert result["round_win_counts"]["Tie"] == 0


def test_compute_all_ties():
    history, scores = _run_game(
        ["rock", "paper", "scissors"],
        ["rock", "paper", "scissors"],
    )
    result = RPSMetrics().compute(history, scores)
    assert result["round_win_counts"]["Tie"] == 3
    assert result["total_payoff"]["A"] == 0.0
    assert result["total_payoff"]["B"] == 0.0


def test_compute_move_frequencies_rock_only():
    history, scores = _run_game(["rock"] * 5, ["scissors"] * 5)
    result = RPSMetrics().compute(history, scores)
    assert result["move_frequencies"]["A"]["rock"] == 1.0
    assert result["move_frequencies"]["A"]["paper"] == 0.0


def test_compute_average_payoff():
    history, scores = _run_game(["rock", "rock"], ["scissors", "scissors"])
    result = RPSMetrics().compute(history, scores)
    assert result["average_payoff"]["A"] == 1.0
    assert result["average_payoff"]["B"] == -1.0


def test_compute_win_rate_sums_to_one():
    history, scores = _run_game(["rock", "paper", "scissors"], ["scissors", "paper", "rock"])
    result = RPSMetrics().compute(history, scores)
    total = sum(result["round_win_rate"].values())
    assert abs(total - 1.0) < 1e-9
