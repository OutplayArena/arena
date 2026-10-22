"""Validation branches and SDK path of the external-regret work not hit elsewhere."""

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from arena.benchmarks.regret import (
    BenchmarkConfig,
    ModelSpec,
    benchmark_plan,
    run_benchmark,
)
from arena.benchmarks.report import write_plots
from arena.metrics.contracts import Match, Move
from arena.metrics.external_regret import FiniteActionGame, external_regret
from arena.metrics.matrix_regret import MatrixRegretExtension, matrix_history_match
from arena.metrics.regret_baselines import FTPL
from games.core.rock_paper_scissors.metrics import RPSMetrics

MODEL = ModelSpec(
    "candidate_llm", "test-model", "TEST_REGRET_KEY", "http://localhost:8001/v1"
)


def _completion(text: str) -> SimpleNamespace:
    return SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content=text))],
        model="test-version",
        id="test-response",
        usage=None,
    )


@pytest.mark.parametrize("field", ["name", "model", "api_key_env", "base_url"])
def test_model_spec_requires_every_identifier(field: str) -> None:
    values = {
        "name": "m",
        "model": "x",
        "api_key_env": "KEY",
        "base_url": "http://localhost/v1",
    }
    values[field] = ""
    with pytest.raises(ValueError, match="required"):
        ModelSpec(**values)


def test_from_dict_converts_sequences_and_models() -> None:
    cfg = BenchmarkConfig.from_dict(
        {
            "rounds": 2,
            "seeds": [1, 2],
            "traces": ["constant"],
            "baselines": ["ftpl"],
            "models": [
                {
                    "name": "m",
                    "model": "x",
                    "api_key_env": "KEY",
                    "base_url": "http://localhost/v1",
                }
            ],
        }
    )
    assert (
        cfg.seeds == (1, 2)
        and cfg.traces == ("constant",)
        and cfg.baselines == ("ftpl",)
    )
    assert [m.name for m in cfg.models] == ["m"]


@pytest.mark.parametrize(
    "changes",
    [
        {"baselines": (), "include_mock_llm": False},
        {
            "baselines": ("ftpl",),
            "models": (ModelSpec("trace:x", "m", "K", "http://localhost/v1"),),
        },
        {"recorded_traces": {"constant": ["rock"]}},
        {"recorded_traces": {"": ["rock"]}},
    ],
)
def test_candidate_and_recorded_trace_names_validated(changes: dict) -> None:
    with pytest.raises(ValueError):
        BenchmarkConfig(**changes)


@pytest.mark.parametrize("budget", [-1, True, 1.5])
def test_budget_must_be_nonnegative_integer(budget: object) -> None:
    with pytest.raises(ValueError, match="nonnegative integer"):
        run_benchmark(BenchmarkConfig(rounds=2, seeds=(1,)), max_model_calls=budget)  # type: ignore[arg-type]


def _model_config() -> BenchmarkConfig:
    return BenchmarkConfig(
        rounds=2,
        seeds=(1,),
        traces=("constant",),
        baselines=("ftpl",),
        include_mock_llm=False,
        models=(MODEL,),
        max_attempts=1,
    )


def test_default_sdk_path_and_http_client_is_closed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("TEST_REGRET_KEY", "secret")
    with patch("outplayarena_sdk.base.OpenAI") as client:
        client.return_value.chat.completions.create.return_value = _completion("rock")
        report = run_benchmark(
            _model_config(), allow_model_calls=True, max_model_calls=2
        )
    trial = next(t for t in report["trials"] if t["candidate_kind"] == "llm")
    assert trial["status"] == "completed"
    assert report["model_calls_used"] == 2
    client.return_value.close.assert_called()


def test_budget_is_enforced_per_attempt(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TEST_REGRET_KEY", "secret")
    cfg = _model_config()
    plan = benchmark_plan(cfg)
    # Understate the worst case so the guard inside the request wrapper is what stops it.
    with patch(
        "arena.benchmarks.regret.benchmark_plan",
        return_value={**plan, "model_calls_required": 0},
    ):
        report = run_benchmark(
            cfg,
            allow_model_calls=True,
            max_model_calls=1,
            model_decision=lambda sdk, obs, state, choices: sdk.decide_once(
                obs, state, choices, completion=lambda messages: _completion("rock")
            ),
        )
    assert report["model_calls_used"] == 1
    trial = next(t for t in report["trials"] if t["candidate_kind"] == "llm")
    assert trial["status"] != "completed"


def test_abstract_adapter_hook_returns_nothing() -> None:
    assert MatrixRegretExtension.regret_game(RPSMetrics(), {}) is None


def test_history_loader_tolerates_malformed_entries() -> None:
    match = matrix_history_match(
        ["junk", {"round": 1, "actions": "bad", "payoffs": "bad"}],
        "rock_paper_scissors",
        {},
    )
    assert len(match.moves) == 4
    assert all(m.metadata["missing_payoff"] for m in match.moves)
    assert all(m.action is None for m in match.moves)


def test_negative_round_in_unflagged_moves_is_unavailable() -> None:
    match = Match(
        match_id="m",
        game_type="rock_paper_scissors",
        agent_ids=["A", "B"],
        moves=[
            Move("A", -1, "rock", 0.0),
            Move("B", -1, "rock", 0.0),
        ],
        metadata={"completed": True},
    )
    result = RPSMetrics().compute_external_regret(match, "A", {})
    assert result["status"] != "available"
    assert "round" in result["reason"]


def test_overflowing_cumulative_payoffs_are_rejected() -> None:
    huge = FiniteActionGame(
        ("x", "y"), ("x", "y"), lambda a, b: 1e308 if a == b else 0.0
    )
    with pytest.raises(ValueError, match="finite"):
        external_regret(huge, ["x", "x"], ["x", "x"])


def test_learner_rejects_infinite_payoff_range() -> None:
    wide = FiniteActionGame(
        ("x", "y"), ("x", "y"), lambda a, b: 1.7e308 if a == b else -1.7e308
    )
    with pytest.raises(ValueError, match="finite"):
        FTPL(wide, 0.1)


def test_plots_unavailable_without_matplotlib(tmp_path: Path) -> None:
    with patch.dict("sys.modules", {"matplotlib": None}):
        assert write_plots({"summary": {"groups": []}}, tmp_path) is False


def test_plots_annotate_candidates_without_completed_trials(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    pytest.importorskip("matplotlib")
    monkeypatch.setenv("TEST_REGRET_KEY", "secret")
    report = run_benchmark(
        _model_config(),
        allow_model_calls=True,
        max_model_calls=2,
        model_decision=lambda sdk, obs, state, choices: sdk.decide_once(
            obs, state, choices, completion=lambda messages: _completion("nonsense")
        ),
    )
    groups = report["summary"]["groups"]
    assert any(not g["series"] for g in groups)
    assert write_plots(report, tmp_path) is True
    assert (tmp_path / "comparison.svg").exists() and (
        tmp_path / "comparison.png"
    ).exists()
