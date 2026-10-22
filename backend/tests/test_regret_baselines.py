"""Reproducibility, feedback timing, numerical stability, and offline outputs."""

import importlib.util
import json
import math
import random
from pathlib import Path

import pytest
from arena.metrics.external_regret import FiniteActionGame
from arena.metrics.regret_baselines import FTPL, FTRL, replay_baseline

GAME = FiniteActionGame(("x", "y"), ("x", "y"), lambda a, b: 2 if a == b else -2)


@pytest.mark.parametrize("algorithm", ["ftpl", "ftrl"])
def test_seeded_execution_and_scale_invariance(algorithm: str) -> None:
    trace = ["x", "y", "x", "x", "y"] * 10
    result = replay_baseline(GAME, trace, algorithm, seed=41)
    assert result == replay_baseline(GAME, trace, algorithm, seed=41)
    assert result["learning_rate"] == math.sqrt(2 * math.log(2) / len(trace))
    assert (
        result["actions"] != replay_baseline(GAME, trace, algorithm, seed=42)["actions"]
    )
    scaled = FiniteActionGame(
        GAME.actions, GAME.opponent_actions, lambda a, b: 100 * GAME.payoff(a, b) + 17
    )
    assert (
        result["actions"]
        == replay_baseline(scaled, trace, algorithm, seed=41)["actions"]
    )
    metric = result["external_regret"]
    assert metric["num_rounds"] == len(trace)
    assert metric["cumulative"] == metric["series"][-1]["cumulative"]
    json.dumps(result, allow_nan=False)


@pytest.mark.parametrize("algorithm", ["ftpl", "ftrl"])
def test_no_current_or_future_action_leakage(algorithm: str) -> None:
    a = replay_baseline(GAME, ["x", "x", "x", "x"], algorithm, seed=2)
    b = replay_baseline(GAME, ["x", "x", "y", "y"], algorithm, seed=2)
    # Choice at index 2 is made before observing the first differing action.
    assert a["actions"][:3] == b["actions"][:3]


def test_ftrl_entropy_objective_and_stability() -> None:
    learner = FTRL(GAME, learning_rate=1, seed=0)
    assert learner.probabilities() == [0.5, 0.5]
    learner.observe("x")
    assert learner.cumulative_losses == {"x": 0, "y": 1}
    assert learner.probabilities() == pytest.approx(
        [1 / (1 + math.exp(-1)), 1 / (1 + math.exp(1))]
    )
    learner.cumulative_losses = {"x": 1e200, "y": 1e200 + 1e190}
    assert learner.probabilities() == [1, 0]
    assert learner.choose_action() == "x"


def test_ftpl_uses_cumulative_loss_and_scaled_exponential_perturbation() -> None:
    learner = FTPL(GAME, learning_rate=0.25, seed=11)
    learner.observe("x")
    assert learner.cumulative_losses == {"x": 0, "y": 1}
    rng = random.Random(11)
    expected = min(
        GAME.actions,
        key=lambda a: learner.cumulative_losses[a] - rng.expovariate(1) / 0.25,
    )
    assert learner.choose_action() == expected


@pytest.mark.parametrize("learner_type", [FTPL, FTRL])
@pytest.mark.parametrize("rate", [0, -1, math.inf, math.nan])
def test_invalid_rates(learner_type: type, rate: float) -> None:
    with pytest.raises(ValueError):
        learner_type(GAME, rate)


@pytest.mark.parametrize("algorithm", ["ftpl", "ftrl"])
def test_empty_single_action_constant_and_invalid_trace(algorithm: str) -> None:
    assert (
        replay_baseline(GAME, [], algorithm)["external_regret"]["status"]
        == "unavailable"
    )
    constant = FiniteActionGame(("x",), ("z",), lambda a, b: 7)
    result = replay_baseline(constant, ["z"] * 2, algorithm)
    assert result["actions"] == ["x", "x"]
    assert result["external_regret"]["cumulative"] == 0
    assert result["external_regret"]["normalized_average"] is None
    with pytest.raises(ValueError):
        replay_baseline(GAME, ["invalid"], algorithm)
    with pytest.raises(ValueError):
        replay_baseline(GAME, ["x"], "invalid")


def test_example_is_reproducible_and_writes_results(tmp_path: Path) -> None:
    path = (
        Path(__file__).resolve().parents[2] / "scripts" / "external_regret_example.py"
    )
    spec = importlib.util.spec_from_file_location("external_regret_example", path)
    example = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(example)
    prior = random.getstate()
    result = example.experiment(rounds=8, seed=7)
    assert random.getstate() == prior
    assert result == example.experiment(rounds=8, seed=7)
    assert set(result["traces"]) == {"constant", "cyclic", "switching", "uniform"}
    example.write_outputs(result, tmp_path)
    assert json.loads((tmp_path / "results.json").read_text()) == result
    assert len((tmp_path / "curves.csv").read_text().splitlines()) == 1 + 4 * 3 * 8
    if importlib.util.find_spec("matplotlib") is not None:
        for name in ("cumulative", "average"):
            assert "<svg" in (tmp_path / f"{name}.svg").read_text()
