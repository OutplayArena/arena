"""Hand-checked signed external regret for finite payoff callbacks."""

import json
import math

import pytest
from arena.metrics.external_regret import FiniteActionGame, external_regret

MATCHING = FiniteActionGame(("x", "y"), ("x", "y"), lambda a, b: 2 if a == b else 0)


@pytest.mark.parametrize(
    ("own", "opponents", "actual", "regret"),
    [
        (["y", "x"], ["x", "y"], 0, 2),
        (["x", "x"], ["x", "y"], 2, 0),
        (["x", "y"], ["x", "y"], 4, -2),
        (["y"], ["x"], 0, 2),
    ],
)
def test_manual_matrix(
    own: list[str], opponents: list[str], actual: float, regret: float
) -> None:
    result = external_regret(MATCHING, own, opponents)
    assert result["actual_total_payoff"] == actual
    assert result["cumulative"] == regret
    assert result["average"] == regret / len(own)
    assert result["normalized_average"] == regret / len(own) / 2
    assert result["best_fixed_action"] == "x"
    assert result["best_fixed_total_payoff"] == 2
    assert result["fixed_action_total_payoffs"]["x"] == 2
    assert len(result["series"]) == result["num_rounds"] == len(own)
    assert result["series"][-1]["cumulative"] == result["cumulative"]
    assert json.loads(json.dumps(result, allow_nan=False)) == result


def test_negative_regret_for_causal_adaptive_agent() -> None:
    # A knows the opponent cycles x,y. It uses only the round index.
    opponents = ["x", "y"] * 3
    actions = ["x" if t % 2 == 0 else "y" for t in range(6)]
    result = external_regret(MATCHING, actions, opponents)
    assert result["actual_total_payoff"] == 12
    assert result["best_fixed_total_payoff"] == 6
    assert result["cumulative"] == -6


def test_empty_and_constant_range() -> None:
    assert external_regret(MATCHING, [], []) == {
        "status": "unavailable",
        "reason": "empty trajectory",
    }
    game = FiniteActionGame(("x", "y"), ("z",), lambda a, b: -7)
    result = external_regret(game, ["y"], ["z"])
    assert result["cumulative"] == result["average"] == 0
    assert result["normalized_average"] is None
    assert result["series"][0]["normalized_average"] is None
    assert result["best_fixed_action"] == "x"


@pytest.mark.parametrize(
    ("actions", "opponents", "payoffs"),
    [
        (["x"], [], None),
        (["bad"], ["x"], None),
        ([None], ["x"], None),
        ([{}], ["x"], None),
        (["x"], ["bad"], None),
        (["x"], [None], None),
        (["x"], ["x"], []),
        (["x"], ["x"], [1]),
        (["x"], ["x"], [math.nan]),
        (["x"], ["x"], [math.inf]),
        (["x"], ["x"], [True]),
        (["x"], ["x"], [None]),
    ],
)
def test_invalid_core_inputs(
    actions: list, opponents: list, payoffs: list | None
) -> None:
    with pytest.raises(ValueError):
        external_regret(MATCHING, actions, opponents, payoffs)


@pytest.mark.parametrize(
    "game",
    [
        FiniteActionGame((), ("x",), lambda a, b: 0),
        FiniteActionGame(("x", "x"), ("x",), lambda a, b: 0),
        FiniteActionGame(("x",), (), lambda a, b: 0),
        FiniteActionGame(("x",), ("x",), lambda a, b: math.nan),
        FiniteActionGame(
            ("x", "y"), ("x",), lambda a, b: 1e308 if a == "x" else -1e308
        ),
    ],
)
def test_invalid_game(game: FiniteActionGame) -> None:
    with pytest.raises(ValueError):
        external_regret(game, [], [])


def test_non_symmetric_finite_core_has_separate_opponent_action_set() -> None:
    matrix = {"safe": {"low": 1, "high": 1}, "risky": {"low": -2, "high": 4}}
    game = FiniteActionGame(
        ("safe", "risky"), ("low", "high"), lambda a, b: matrix[a][b]
    )
    result = external_regret(game, ["safe", "risky"], ["low", "high"])
    assert result["actual_total_payoff"] == 5
    assert result["fixed_action_total_payoffs"] == {"safe": 2, "risky": 2}
    assert result["cumulative"] == -3
    assert result["normalized_average"] == -0.25
