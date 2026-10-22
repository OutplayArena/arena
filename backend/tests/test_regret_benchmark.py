"""Matched experiments, operational failures, budgets, and auditability."""

import json
from copy import deepcopy
from dataclasses import asdict
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest.mock import patch

import pytest
from arena.benchmarks.regret import (
    BenchmarkConfig,
    ModelSpec,
    benchmark_plan,
    run_benchmark,
)
from arena.benchmarks.report import summarize, write_plots, write_report

MODEL = ModelSpec(
    "candidate_llm", "test-model", "TEST_REGRET_KEY", "http://localhost:8001/v1"
)


def completion_response(text: str) -> SimpleNamespace:
    """Return a provider-compatible response with no network access."""
    return SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content=text))],
        model="test-version",
        id="test-response",
        usage=None,
    )


def fake_model(sdk: Any, observation: dict, state: dict, choices: tuple) -> dict:
    """Exercise the real SDK decision path through an injected text completion."""
    return sdk.decide_once(
        observation,
        state,
        choices,
        completion=lambda messages: completion_response(choices[0]),
    )


@pytest.mark.parametrize(
    "game,custom",
    [
        ("rock_paper_scissors", {}),
        (
            "prisonersdilemma",
            {"payoff_T": 9, "payoff_R": 6, "payoff_P": 2, "payoff_S": -2},
        ),
        (
            "stag_hunt",
            {"payoff_stag_stag": 8, "payoff_hare_hare": 3, "payoff_stag_hare": -2},
        ),
    ],
)
def test_free_study_matches_traces_and_existing_evaluation(
    game: str, custom: dict
) -> None:
    cfg = BenchmarkConfig(game=game, rounds=4, seeds=(1, 2), game_config=custom)
    with patch(
        "outplayarena_sdk.base.OpenAI", side_effect=AssertionError("no model access")
    ):
        report = run_benchmark(cfg)
        repeated = run_benchmark(cfg)
    assert report == repeated
    assert report["model_calls_used"] == 0
    assert len(report["trials"]) == 2 * 4 * 5
    for trial in report["trials"]:
        assert trial["status"] == "completed"
        metric = trial["external_regret"]
        assert (
            metric
            == trial["result"]["rich_metrics"]["agents"][trial["candidate"]][
                "external_regret"
            ]
        )
        assert metric["num_rounds"] == 4
        assert metric["series"][-1]["cumulative"] == metric["cumulative"]
        trace = report["traces"][str(trial["seed"])][trial["trace"]]
        assert trial["opponent_actions"] == trace
        assert [row["actions"]["B"] for row in trial["history"]] == trace
        for key, value in custom.items():
            assert trial["resolved_game_config"][key] == value
        assert "player_tokens" not in json.dumps(trial)
    groups = report["summary"]["groups"]
    assert all(g["completed_runs"] == 2 and g["failed_runs"] == 0 for g in groups)
    assert all(p["paired_runs"] == 2 for p in report["summary"]["paired_comparisons"])
    assert all(
        t["candidate_kind"] == "mock"
        for t in report["trials"]
        if t["candidate"] == "mock_llm"
    )


@pytest.mark.parametrize(
    "changes",
    [
        {"game": "texas_hold_em"},
        {"rounds": 0},
        {"rounds": True},
        {"seeds": ()},
        {"seeds": (1, 1)},
        {"seeds": (True,)},
        {"max_attempts": 0},
        {"include_mock_llm": "yes"},
        {"traces": ("unknown",)},
        {"baselines": ("bad",)},
        {"traces": (), "recorded_traces": {}},
        {"game_config": {"seed": 7}},
        {"game_config": {"unknown": 4}},
        {"game": "stag_hunt", "game_config": {"noise": 0.1}},
        {"models": (ModelSpec("ftpl", "model", "KEY", "http://localhost/v1"),)},
    ],
)
def test_invalid_configs_rejected(changes: dict) -> None:
    with pytest.raises((ValueError, TypeError)):
        BenchmarkConfig(**changes)


def test_bad_models_and_unknown_config_fields() -> None:
    with pytest.raises(TypeError):
        BenchmarkConfig.from_dict({"typo": 1})
    for changes in (
        {"base_url": "https://user:password@host/v1"},
        {"base_url": "https://host/v1?key=secret"},
        {"temperature": float("nan")},
        {"max_tokens": 0},
        {"timeout": 0},
    ):
        with pytest.raises(ValueError):
            ModelSpec(**{**asdict(MODEL), **changes})


def test_recorded_trace_validation_and_no_future_observation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("TEST_REGRET_KEY", "never-write-this-secret")
    trace = ["scissors", "paper", "rock"]
    cfg = BenchmarkConfig(
        rounds=3,
        seeds=(7,),
        traces=(),
        baselines=(),
        include_mock_llm=False,
        models=(MODEL,),
        recorded_traces={"recording": trace},
    )
    seen = []

    def decide(sdk: Any, observation: dict, state: dict, choices: tuple) -> dict:
        index = len(seen)
        assert len(state["history"]) == index
        assert [row["actions"]["B"] for row in state["history"]] == trace[:index]
        assert "recording" not in str(observation)
        assert "Payoff" in observation["system"] or "payoff" in observation["system"]
        assert "never-write-this-secret" not in str(observation)
        seen.append(deepcopy(state))
        return fake_model(sdk, observation, state, choices)

    result = run_benchmark(
        cfg, allow_model_calls=True, max_model_calls=3, model_decision=decide
    )
    assert len(seen) == result["model_calls_used"] == 3
    assert "never-write-this-secret" not in json.dumps(result)
    assert result["trials"][0]["candidate_kind"] == "llm"
    for bad in (["rock"], ["rock", "invalid", "paper"]):
        with pytest.raises(ValueError):
            benchmark_plan(
                BenchmarkConfig(rounds=3, recorded_traces={"recording": bad})
            )


def test_paid_runs_require_opt_in_budget_and_credentials(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cfg = BenchmarkConfig(rounds=2, seeds=(1, 2), models=(MODEL,), max_attempts=2)
    assert benchmark_plan(cfg)["model_calls_required"] == 32
    with patch("outplayarena_sdk.base.OpenAI") as client:
        for kwargs in (
            {},
            {"allow_model_calls": True, "max_model_calls": 31},
            {"allow_model_calls": False, "max_model_calls": 32},
        ):
            with pytest.raises(ValueError, match="explicit opt-in"):
                run_benchmark(cfg, **kwargs)
        monkeypatch.delenv("TEST_REGRET_KEY", raising=False)
        with pytest.raises(ValueError, match="credential"):
            run_benchmark(cfg, allow_model_calls=True, max_model_calls=32)
    client.assert_not_called()


def test_retries_are_logged_without_feedback_or_fallback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("TEST_REGRET_KEY", "secret")
    cfg = BenchmarkConfig(
        rounds=2,
        seeds=(1,),
        traces=("constant",),
        baselines=("ftpl",),
        include_mock_llm=False,
        models=(MODEL,),
        max_attempts=2,
    )
    calls = []

    def decide(sdk: Any, observation: dict, state: dict, choices: tuple) -> dict:
        calls.append(deepcopy(state["history"]))
        text = "nonsense" if len(calls) % 2 else "paper"
        return sdk.decide_once(
            observation,
            state,
            choices,
            completion=lambda messages: completion_response(text),
        )

    report = run_benchmark(
        cfg, allow_model_calls=True, max_model_calls=4, model_decision=decide
    )
    trial = next(t for t in report["trials"] if t["candidate_kind"] == "llm")
    assert trial["status"] == "completed"
    assert [d["parse_status"] for d in trial["decisions"]] == [
        "invalid",
        "valid",
        "invalid",
        "valid",
    ]
    assert all(not d["fallback_used"] for d in trial["decisions"])
    assert calls[0] == calls[1] and calls[2] == calls[3]
    assert report["model_calls_used"] == 4
    assert [row["actions"]["A"] for row in trial["history"]] == ["paper", "paper"]


def test_failures_are_counted_and_provider_exception_secrets_not_saved(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("TEST_REGRET_KEY", "never-save-secret")
    cfg = BenchmarkConfig(
        rounds=2,
        seeds=(1, 2),
        traces=("constant",),
        models=(MODEL,),
        include_mock_llm=False,
    )

    def broken(*args: Any) -> dict:
        raise RuntimeError("provider URL includes never-save-secret")

    report = run_benchmark(
        cfg, allow_model_calls=True, max_model_calls=4, model_decision=broken
    )
    llms = [t for t in report["trials"] if t["candidate_kind"] == "llm"]
    assert all(
        t["completed_rounds"] == 0 and t["external_regret"]["status"] == "unavailable"
        for t in llms
    )
    assert "never-save-secret" not in json.dumps(report)
    assert all(t["decisions"][0]["messages"] for t in llms)
    group = next(g for g in report["summary"]["groups"] if g["candidate"] == MODEL.name)
    assert group["completed_runs"] == 0 and group["failed_runs"] == 2
    assert group["final"]["average"] is None
    assert group["series"] == []
    assert all(p["paired_runs"] == 0 for p in report["summary"]["paired_comparisons"])


def test_reports_and_optional_plots(tmp_path: Path) -> None:
    report = run_benchmark(
        BenchmarkConfig(rounds=2, seeds=(1, 2), traces=("constant",))
    )
    write_report(report, tmp_path)
    assert (
        json.loads((tmp_path / "report.json").read_text())["mode"]
        == "offline_fixed_trace"
    )
    trials = [
        json.loads(line)
        for line in (tmp_path / "trials.jsonl").read_text().splitlines()
    ]
    assert trials == report["trials"]
    assert len((tmp_path / "curves.csv").read_text().splitlines()) == 1 + 5 * 2 * 3
    plotted = write_plots(report, tmp_path)
    if plotted:
        assert (tmp_path / "comparison.svg").exists()
        assert (tmp_path / "comparison.png").exists()
    altered = deepcopy(report["trials"])
    altered[0]["external_regret"]["num_rounds"] = 3
    with pytest.raises(ValueError, match="unequal horizons"):
        summarize(altered)


def test_descriptive_statistics_and_paired_differences() -> None:
    base = run_benchmark(
        BenchmarkConfig(
            rounds=1, seeds=(1, 2), traces=("constant",), baselines=("ftpl",)
        )
    )
    trials = deepcopy(base["trials"])
    for trial in trials:
        metric = trial["external_regret"]
        value = (
            (2 if trial["seed"] == 1 else 4)
            if trial["candidate"] == "ftpl"
            else (0 if trial["seed"] == 1 else 2)
        )
        metric.update(cumulative=value, average=value, normalized_average=value / 2)
        metric["series"][0].update(
            cumulative=value, average=value, normalized_average=value / 2
        )
    summary = summarize(trials)
    group = next(g for g in summary["groups"] if g["candidate"] == "ftpl")
    stats = group["final"]["average"]
    assert stats["mean"] == 3
    assert stats["stddev"] == pytest.approx(2**0.5)
    assert (stats["min"], stats["max"], stats["n"]) == (2, 4, 2)
    pair = next(p for p in summary["paired_comparisons"] if p["reference"] == "ftpl")
    assert pair["paired_runs"] == 2
    assert pair["normalized_average_difference"]["mean"] == -1
    failed = deepcopy(trials)
    candidate = next(t for t in failed if t["candidate"] == "mock_llm")
    candidate["status"] = "failed"
    candidate["external_regret"] = {
        "status": "unavailable",
        "reason": "invalid response",
    }
    pair = next(
        p for p in summarize(failed)["paired_comparisons"] if p["reference"] == "ftpl"
    )
    assert pair["paired_runs"] == 1 and pair["excluded_runs"] == 1
    mismatched = deepcopy(trials)
    next(t for t in mismatched if t["candidate"] == "mock_llm")["opponent_actions"] = [
        "paper"
    ]
    with pytest.raises(ValueError, match="identical opponent traces"):
        summarize(mismatched)


def test_cli_dry_run_and_free_checkpointed_report(tmp_path: Path) -> None:
    import subprocess
    import sys

    root = Path(__file__).resolve().parents[2]
    script = root / "scripts/regret_benchmark.py"
    config = tmp_path / "config.yaml"
    config.write_text("rounds: 2\nseeds: [7]\ntraces: [constant]\n")
    out = tmp_path / "out"
    command = [
        sys.executable,
        str(script),
        "--config",
        str(config),
        "--output-dir",
        str(out),
    ]
    dry = subprocess.run(
        [*command, "--dry-run"], capture_output=True, text=True, check=True
    )
    assert json.loads(dry.stdout)["trials_planned"] == 5
    assert not out.exists()
    run = subprocess.run(command, capture_output=True, text=True, check=True)
    assert "0 model attempts" in run.stdout
    assert len((out / "trials.jsonl").read_text().splitlines()) == 5
    assert (out / "report.json").exists()
    prior = (out / "trials.jsonl").read_bytes()
    repeat = subprocess.run(command, capture_output=True, text=True, check=False)
    assert repeat.returncode == 2
    assert (out / "trials.jsonl").read_bytes() == prior


def test_invalid_text_exhausts_attempts_and_partial_match_is_not_averaged(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("TEST_REGRET_KEY", "secret")
    cfg = BenchmarkConfig(
        rounds=3,
        seeds=(1,),
        traces=("constant",),
        baselines=("ftpl",),
        include_mock_llm=False,
        models=(MODEL,),
        max_attempts=2,
    )
    calls = 0
    checkpoints = []

    def decide(sdk: Any, observation: dict, state: dict, choices: tuple) -> dict:
        nonlocal calls
        calls += 1
        return sdk.decide_once(
            observation,
            state,
            choices,
            completion=lambda messages: completion_response(
                "paper" if calls == 1 else "ambiguous"
            ),
        )

    report = run_benchmark(
        cfg,
        allow_model_calls=True,
        max_model_calls=6,
        model_decision=decide,
        on_trial=checkpoints.append,
    )
    trial = next(t for t in report["trials"] if t["candidate_kind"] == "llm")
    assert trial["status"] == "failed" and trial["completed_rounds"] == 1
    assert len(trial["history"]) == 1
    assert len(trial["decisions"]) == 3
    assert trial["external_regret"]["status"] == "unavailable"
    assert report["model_calls_used"] == calls == 3
    assert checkpoints == report["trials"]
