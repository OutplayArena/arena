"""Fixed-trace LLM and classical regret benchmarks using local Arena sessions."""

import json
import math
import os
import random
from collections.abc import Callable
from copy import deepcopy
from dataclasses import asdict, dataclass, field
from types import SimpleNamespace
from typing import Any
from urllib.parse import urlsplit
from uuid import NAMESPACE_URL, uuid5

from outplayarena_sdk.base import LLMConfig
from outplayarena_sdk.decisions import decision_messages
from outplayarena_sdk.registry import get_agent_class

from arena._version import ARENA_VERSION
from arena.game_registry import GameRegistry
from arena.metrics.evaluator import MatchEvaluator
from arena.metrics.external_regret import unavailable
from arena.metrics.registry import AgentRegistry
from arena.metrics.regret_baselines import FTPL, FTRL
from arena.session import GameSession

SUPPORTED_GAMES = ("rock_paper_scissors", "prisonersdilemma", "stag_hunt")
BASELINES = ("ftpl", "ftrl", "uniform", "last_response")
TRACE_NAMES = ("constant", "cyclic", "switching", "uniform")


@dataclass(frozen=True)
class ModelSpec:
    """Public model settings; credentials are read by environment-variable name."""

    name: str
    model: str
    api_key_env: str
    base_url: str
    temperature: float = 0.7
    max_tokens: int = 128
    timeout: float = 60.0

    def __post_init__(self) -> None:
        if any(
            not isinstance(v, str) or not v
            for v in (self.name, self.model, self.api_key_env, self.base_url)
        ):
            raise ValueError(
                "model name, identifier, key environment variable, and URL are required"
            )
        url = urlsplit(self.base_url)
        if (
            url.scheme not in {"http", "https"}
            or not url.netloc
            or url.username
            or url.password
            or url.query
            or url.fragment
        ):
            raise ValueError(
                "base_url must be an HTTP(S) endpoint without credentials or query parameters"
            )
        if not math.isfinite(self.temperature) or not 0 <= self.temperature <= 2:
            raise ValueError("temperature must be finite and in [0, 2]")
        if type(self.max_tokens) is not int or self.max_tokens < 1:
            raise ValueError("max_tokens must be a positive integer")
        if not math.isfinite(self.timeout) or self.timeout <= 0:
            raise ValueError("timeout must be finite and positive")


@dataclass(frozen=True)
class BenchmarkConfig:
    """One game, matched opponent traces, and repeated seeded candidate runs."""

    game: str = "rock_paper_scissors"
    rounds: int = 50
    seeds: tuple[int, ...] = (7, 19, 31)
    traces: tuple[str, ...] = TRACE_NAMES
    baselines: tuple[str, ...] = BASELINES
    models: tuple[ModelSpec, ...] = ()
    include_mock_llm: bool = True
    max_attempts: int = 1
    game_config: dict = field(default_factory=dict)
    recorded_traces: dict[str, list[str]] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict) -> "BenchmarkConfig":
        """Load explicit settings, rejecting unknown keys rather than ignoring typos."""
        values = dict(data)
        for key in ("seeds", "traces", "baselines"):
            if key in values:
                values[key] = tuple(values[key])
        values["models"] = tuple(ModelSpec(**m) for m in values.get("models", []))
        return cls(**values)

    def __post_init__(self) -> None:
        if self.game not in SUPPORTED_GAMES:
            raise ValueError("benchmark requires a supported matrix game")
        if type(self.rounds) is not int or not 1 <= self.rounds <= 10000:
            raise ValueError("rounds must be an integer in [1, 10000]")
        if (
            not self.seeds
            or any(type(s) is not int for s in self.seeds)
            or len(set(self.seeds)) != len(self.seeds)
        ):
            raise ValueError("seeds must be distinct integers")
        if type(self.max_attempts) is not int or not 1 <= self.max_attempts <= 5:
            raise ValueError("max_attempts must be an integer in [1, 5]")
        if type(self.include_mock_llm) is not bool:
            raise ValueError("include_mock_llm must be boolean")
        if len(set(self.traces)) != len(self.traces) or any(
            t not in TRACE_NAMES for t in self.traces
        ):
            raise ValueError("unknown or duplicate generated trace")
        if len(set(self.baselines)) != len(self.baselines) or any(
            b not in BASELINES for b in self.baselines
        ):
            raise ValueError("unknown or duplicate baseline")
        if any(m.name in (*BASELINES, "mock_llm") for m in self.models):
            raise ValueError(
                "model names cannot use reserved baseline or mock identities"
            )
        names = [*self.baselines, *[m.name for m in self.models]]
        if self.include_mock_llm:
            names.append("mock_llm")
        if (
            not names
            or len(set(names)) != len(names)
            or any(n.startswith("trace:") for n in names)
        ):
            raise ValueError(
                "candidate names must be nonempty and distinct from opponent identities"
            )
        if not self.traces and not self.recorded_traces:
            raise ValueError("at least one opponent trace is required")
        if set(self.recorded_traces) & set(TRACE_NAMES):
            raise ValueError(
                "recorded trace names must differ from generated trace names"
            )
        if any(not isinstance(k, str) or not k for k in self.recorded_traces):
            raise ValueError("recorded traces require nonempty names")
        self.resolved_config(self.seeds[0])

    def resolved_config(self, seed: int) -> Any:
        """Resolve actual game defaults while forbidding noise and horizon overrides."""
        data = {
            "game": self.game,
            "rounds": self.rounds,
            "seed": seed,
            **self.game_config,
        }
        if {"game", "rounds", "seed"} & self.game_config.keys():
            raise ValueError("game_config cannot override game, rounds, or seed")
        cfg = GameRegistry().config_from_request(data)
        if set(self.game_config) - cfg.to_dict().keys():
            raise ValueError("game_config contains unknown settings")
        if getattr(cfg, "noise", 0) != 0:
            raise ValueError("exact benchmark requires zero action noise")
        return cfg


def opponent_traces(
    config: BenchmarkConfig, seed: int, actions: tuple[str, ...]
) -> dict[str, list[str]]:
    """Generate shared traces independently of candidate RNGs and decisions."""
    rng = random.Random(seed)
    generated = {
        "constant": [actions[0]] * config.rounds,
        "cyclic": [actions[t % len(actions)] for t in range(config.rounds)],
        "switching": [
            actions[0] if t < config.rounds // 2 else actions[-1]
            for t in range(config.rounds)
        ],
        "uniform": [rng.choice(actions) for _ in range(config.rounds)],
    }
    traces = {name: generated[name] for name in config.traces}
    for name, trace in config.recorded_traces.items():
        if len(trace) != config.rounds or any(
            not isinstance(a, str) or a not in actions for a in trace
        ):
            raise ValueError(
                "recorded traces must contain exactly one valid opponent action per round"
            )
        traces[name] = list(trace)
    return traces


def _last_response(matrix: dict, history: list[dict], rng: random.Random) -> str:
    if not history:
        return rng.choice(list(matrix))
    previous = history[-1]["actions"]["B"]
    return max(matrix, key=lambda a: matrix[a][previous])


def _trial(
    config: BenchmarkConfig,
    seed: int,
    trace_name: str,
    trace: list[str],
    candidate: str,
    model: ModelSpec | None,
    request: Callable,
) -> dict:
    cfg = config.resolved_config(seed)
    trial_id = str(
        uuid5(
            NAMESPACE_URL,
            json.dumps(
                {
                    "config": asdict(config),
                    "seed": seed,
                    "trace": trace_name,
                    "candidate": candidate,
                },
                sort_keys=True,
            ),
        )
    )
    session = GameSession.create(
        cfg, agents={"A": candidate, "B": f"trace:{trace_name}"}, session_id=trial_id
    )
    adapter = session.game.metrics_engine.regret_game(cfg.to_dict())
    matrix = adapter.matrix()
    rng = random.Random(seed)
    learner = None
    if candidate in {"ftpl", "ftrl"}:
        eta = math.sqrt(2 * math.log(len(adapter.actions)) / config.rounds)
        learner = (FTPL if candidate == "ftpl" else FTRL)(adapter, eta, seed)
    sdk = None
    if model or candidate == "mock_llm":
        llm = LLMConfig(
            model=model.model if model else "scripted-mock",
            api_key=os.environ[model.api_key_env] if model else "offline-mock",
            base_url=model.base_url if model else "http://offline.invalid",
            temperature=model.temperature if model else 0,
            max_tokens=model.max_tokens if model else 128,
            max_retries=0,
            timeout=model.timeout if model else 60,
        )
        sdk = get_agent_class(config.game)(
            player="A",
            player_token=session.player_tokens["A"],
            session_id=trial_id,
            arena_url="http://offline.invalid",
            llm_config=llm,
            use_mcp=False,
            seed=seed,
        )
    decisions = []
    failure = None
    try:
        for t, opponent in enumerate(trace, start=1):
            public = session.public_state()
            observation = GameRegistry().render_observation(
                config.game, public, cfg.to_dict(), "A"
            )
            observation["system"] += (
                "\nYour full stage-payoff table (own action -> opponent action -> payoff): "
                + json.dumps(matrix, sort_keys=True)
            )
            action = None
            if sdk:
                for attempt in range(1, config.max_attempts + 1):
                    try:
                        if model:
                            decision = request(
                                sdk, observation, public, adapter.actions
                            )
                        else:
                            raw = _last_response(matrix, public["history"], rng)
                            response = SimpleNamespace(
                                choices=[
                                    SimpleNamespace(
                                        message=SimpleNamespace(content=raw)
                                    )
                                ],
                                id=f"mock-{t}",
                                model="scripted-mock",
                                usage=None,
                            )
                            decision = sdk.decide_once(
                                observation,
                                public,
                                adapter.actions,
                                completion=lambda messages, response=response: response,
                            )
                        decisions.append({"round": t, "attempt": attempt, **decision})
                        action = decision["action"]
                    except Exception as exc:  # noqa: BLE001 - preserve all failed provider attempts without credentials.
                        # Provider exception strings can contain credentials; persist only the type.
                        decisions.append(
                            {
                                "round": t,
                                "attempt": attempt,
                                "parse_status": "error",
                                "error_type": type(exc).__name__,
                                "messages": decision_messages(
                                    observation, adapter.actions
                                ),
                                "raw_response": None,
                                "action": None,
                                "fallback_used": False,
                            }
                        )
                    if action is not None:
                        break
                if action is None:
                    failure = "model decision failed or was invalid; no fallback action executed"
                    break
            else:
                action = (
                    learner.choose_action()
                    if learner
                    else (
                        rng.choice(adapter.actions)
                        if candidate == "uniform"
                        else _last_response(matrix, public["history"], rng)
                    )
                )
                decisions.append(
                    {
                        "round": t,
                        "action": action,
                        "parse_status": "valid",
                        "fallback_used": False,
                    }
                )
            session.submit_action("A", action)
            session.submit_action("B", opponent)
            if learner:
                learner.observe(opponent)
    finally:
        if sdk and sdk._openai is not None:
            sdk._openai.close()
    result = (
        session.results(MatchEvaluator(AgentRegistry())) if failure is None else None
    )
    return {
        "trial_id": trial_id,
        "session_id": session.session_id,
        "game": config.game,
        "trace": trace_name,
        "seed": seed,
        "candidate": candidate,
        "candidate_kind": "llm" if model else ("mock" if sdk else "baseline"),
        "model_config": asdict(model) if model else None,
        "resolved_game_config": cfg.to_dict(),
        "policy_config": {
            "learning_rate": learner.learning_rate if learner else None,
            "seed": seed,
        },
        "status": "failed" if failure else "completed",
        "reason": failure,
        "completed_rounds": len(session.state.history),
        "decisions": decisions,
        "history": deepcopy(session.state.history),
        "opponent_actions": list(trace),
        "external_regret": result["metrics"]["external_regret"]["A"]
        if result
        else unavailable(failure),
        "result": result,
    }


def benchmark_plan(config: BenchmarkConfig) -> dict:
    """Validate every trace and resolve a worst-case request count without model access."""
    initial = config.resolved_config(config.seeds[0])
    engine = GameRegistry().game_from_config(initial)
    actions = engine.metrics_engine.regret_game(initial.to_dict()).actions
    traces = {seed: opponent_traces(config, seed, actions) for seed in config.seeds}
    candidates = (
        len(config.baselines) + len(config.models) + int(config.include_mock_llm)
    )
    return {
        "game": config.game,
        "rounds": config.rounds,
        "trials_planned": sum(len(t) for t in traces.values()) * candidates,
        "model_calls_required": len(config.models)
        * sum(len(t) for rows in traces.values() for t in rows.values())
        * config.max_attempts,
        "traces_by_seed": traces,
    }


def run_benchmark(
    config: BenchmarkConfig,
    *,
    allow_model_calls: bool = False,
    max_model_calls: int = 0,
    on_trial: Callable[[dict], None] | None = None,
    model_decision: Callable | None = None,
) -> dict:
    """Run matched offline comparisons, with explicit opt-in and bounded model calls.

    Each model attempt consumes one budget unit before invocation. SDK HTTP
    retries are disabled. Worst-case capacity is checked before any model call.
    Injected model decisions are for tests; they obey the same budget protocol.
    """
    if type(max_model_calls) is not int or max_model_calls < 0:
        raise ValueError("max_model_calls must be a nonnegative integer")
    plan = benchmark_plan(config)
    traces_by_seed = plan["traces_by_seed"]
    required = plan["model_calls_required"]
    if config.models and (
        not allow_model_calls
        or type(max_model_calls) is not int
        or max_model_calls < required
    ):
        raise ValueError(
            f"model runs require explicit opt-in and max_model_calls >= {required}"
        )
    for model in config.models:
        if not os.environ.get(model.api_key_env):
            raise ValueError(
                f"missing credential environment variable: {model.api_key_env}"
            )
    used = 0

    def request(sdk: Any, observation: dict, state: dict, choices: tuple) -> dict:
        nonlocal used
        if used >= max_model_calls:
            raise RuntimeError("model call budget exhausted")
        used += 1
        if model_decision:
            return model_decision(sdk, deepcopy(observation), deepcopy(state), choices)
        return sdk.decide_once(observation, state, choices)

    candidates = [(name, None) for name in config.baselines]
    if config.include_mock_llm:
        candidates.append(("mock_llm", None))
    candidates.extend((model.name, model) for model in config.models)
    trials = []
    for seed, traces in traces_by_seed.items():
        for name, trace in traces.items():
            for candidate, model in candidates:
                trial = _trial(config, seed, name, trace, candidate, model, request)
                trials.append(trial)
                if on_trial:
                    on_trial(deepcopy(trial))
    from arena.benchmarks.report import summarize

    return {
        "schema_version": 1,
        "arena_version": ARENA_VERSION,
        "mode": "offline_fixed_trace",
        "config": asdict(config),
        "protocol": {
            "feedback": "full_information",
            "history": "all_completed_rounds",
            "tools": False,
            "invalid_actions": "retry_then_fail_without_fallback",
            "model_http_retries": 0,
        },
        "traces": {str(seed): traces for seed, traces in traces_by_seed.items()},
        "model_calls_used": used,
        "model_call_budget": max_model_calls,
        "trials": trials,
        "summary": summarize(trials),
    }
