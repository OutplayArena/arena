"""Hand-checked regret, adapter validation, and preservation of legacy metrics."""

import json
import math
from copy import deepcopy
from itertools import product

import pytest
from arena.game_registry import GameRegistry
from arena.metrics.behavioral import BehavioralMetrics
from arena.metrics.contracts import Match, Move
from arena.metrics.evaluator import MatchEvaluator
from arena.metrics.external_regret import FiniteActionGame, external_regret
from arena.metrics.matrix_regret import matrix_history_match
from arena.metrics.registry import AgentRegistry
from arena.session import GameSession
from games.core.prisonersdilemma.engine import PDGame
from games.core.rock_paper_scissors.engine import RPSGame
from games.core.rock_paper_scissors.metrics import RPSMetrics
from games.core.stag_hunt.engine import StagHuntGame

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


def test_prefixes_reselect_best_and_are_not_per_round_oracle() -> None:
    game = RPSGame().metrics_engine.regret_game({})
    result = external_regret(
        game, ["paper", "scissors", "rock"], ["rock", "paper", "scissors"]
    )
    assert result["fixed_action_total_payoffs"] == {
        "rock": 0,
        "paper": 0,
        "scissors": 0,
    }
    assert result["actual_total_payoff"] == 3
    assert result["cumulative"] == -3
    assert result["best_fixed_action"] == "rock"
    assert [p["round"] for p in result["series"]] == [1, 2, 3]
    assert [p["cumulative"] for p in result["series"]] == [0, -1, -3]
    assert [p["average"] for p in result["series"]] == [0, -0.5, -1]
    assert [p["best_fixed_action"] for p in result["series"]] == [
        "paper",
        "paper",
        "rock",
    ]
    per_round_oracle_gap = 3 - result["actual_total_payoff"]
    assert per_round_oracle_gap == 0 != result["cumulative"]


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


CASES = [
    (
        "rock_paper_scissors",
        {},
        ("rock", "paper", "scissors"),
        [[0, -1, 1], [1, 0, -1], [-1, 1, 0]],
    ),
    ("prisonersdilemma", {}, ("cooperate", "defect"), [[3, 0], [5, 1]]),
    (
        "prisonersdilemma",
        {"payoff_T": 9, "payoff_R": 6, "payoff_P": 2, "payoff_S": -2},
        ("cooperate", "defect"),
        [[6, -2], [9, 2]],
    ),
    ("stag_hunt", {}, ("stag", "hare"), [[4, 0], [2, 2]]),
    (
        "stag_hunt",
        {"payoff_stag_stag": 8, "payoff_hare_hare": 3, "payoff_stag_hare": -2},
        ("stag", "hare"),
        [[8, -2], [3, 3]],
    ),
]


def completed_session(
    slug: str, config: dict, pairs: list[tuple[str, str]]
) -> GameSession:
    """Create a local completed session with explicit distinct agent identifiers."""
    cfg = GameRegistry().config_from_request(
        {"game": slug, "rounds": len(pairs), **config}
    )
    session = GameSession.create(cfg, agents={"A": "agent_a", "B": "agent_b"})
    for a, b in pairs:
        session.submit_action("A", a)
        session.submit_action("B", b)
    return session


@pytest.mark.parametrize(("slug", "config", "actions", "payoffs"), CASES)
def test_all_payoff_cells_and_perspectives(
    slug: str, config: dict, actions: tuple[str, ...], payoffs: list[list[float]]
) -> None:
    pairs = list(product(actions, repeat=2))
    session = completed_session(slug, config, pairs)
    adapter = session.game.metrics_engine.regret_game(session.config.to_dict())
    for (i, a), (j, b) in product(enumerate(actions), repeat=2):
        assert adapter.payoff(a, b) == payoffs[i][j]
    engine_results = session.game.compute_results(session.state)
    result = session.results(MatchEvaluator(AgentRegistry()))
    for role, agent, index in (("A", "agent_a", 0), ("B", "agent_b", 1)):
        actual = sum(
            payoffs[actions.index(pair[index])][actions.index(pair[1 - index])]
            for pair in pairs
        )
        totals = {
            fixed: sum(payoffs[j][actions.index(pair[1 - index])] for pair in pairs)
            for j, fixed in enumerate(actions)
        }
        metric = result["rich_metrics"]["agents"][agent]["external_regret"]
        assert metric == result["metrics"]["external_regret"][role]
        assert metric == engine_results["metrics"]["external_regret"][role]
        assert metric["status"] == "available"
        assert metric["actual_total_payoff"] == actual
        assert metric["fixed_action_total_payoffs"] == totals
        assert metric["best_fixed_total_payoff"] == max(totals.values())
        assert metric["cumulative"] == max(totals.values()) - actual
        assert metric["payoff_range"] == {
            "min": min(map(min, payoffs)),
            "max": max(map(max, payoffs)),
        }
    assert "cumulative_regret" in result["rich_metrics"]["agents"]["agent_a"]
    assert "external_regret" in GameRegistry().get_metric_names(slug)
    assert json.loads(json.dumps(result, allow_nan=False)) == result


@pytest.mark.parametrize(("slug", "config", "actions", "payoffs"), CASES)
def test_single_round(slug: str, config: dict, actions: tuple, payoffs: list) -> None:
    result = completed_session(slug, config, [(actions[0], actions[0])]).results(
        MatchEvaluator(AgentRegistry())
    )
    metric = result["metrics"]["external_regret"]["A"]
    assert metric["num_rounds"] == len(metric["series"]) == 1
    assert metric["cumulative"] == metric["series"][-1]["cumulative"]


@pytest.mark.parametrize(
    "slug,actions",
    [
        ("rock_paper_scissors", ("rock", "scissors")),
        ("prisonersdilemma", ("cooperate", "defect")),
        ("stag_hunt", ("stag", "hare")),
    ],
)
def test_forfeit_rejected_in_both_paths(slug: str, actions: tuple) -> None:
    session = completed_session(slug, {}, [actions, actions])
    # Replace a round by a true engine forfeit, retaining a normal round.
    session.state = session.game.initial_state()
    session.submit_action("A", actions[0])
    session.submit_action("B", actions[1])
    session.state = session.game.forfeit_round(session.state, "A")
    result = session.results(MatchEvaluator(AgentRegistry()))
    for metric in [
        *result["metrics"]["external_regret"].values(),
        *(r["external_regret"] for r in result["rich_metrics"]["agents"].values()),
    ]:
        assert metric["status"] == "unavailable"
        assert "forfeit" in metric["reason"]
        assert "cumulative" not in metric
    assert any(m.metadata["forfeit"] for m in session.to_match().moves)


@pytest.mark.parametrize(
    "slug,action", [("prisonersdilemma", "cooperate"), ("stag_hunt", "stag")]
)
def test_noise_rejected_even_without_observed_flip(slug: str, action: str) -> None:
    session = completed_session(slug, {"noise": 0.5, "seed": 1}, [(action, action)] * 2)
    result = session.results(MatchEvaluator(AgentRegistry()))
    for metric in result["metrics"]["external_regret"].values():
        assert metric["status"] == "unavailable" and "noise" in metric["reason"]
    for report in result["rich_metrics"]["agents"].values():
        assert "noise" in report["external_regret"]["reason"]
    match = session.to_match()
    cfg = {**match.config, "noise": 0}
    assert (
        "noise"
        in session.game.metrics_engine.compute_external_regret(match, "agent_a", cfg)[
            "reason"
        ]
    )


@pytest.mark.parametrize("variant", ["classic", "noisy"])
def test_zero_noise_variant_is_deterministic(variant: str) -> None:
    session = completed_session(
        "stag_hunt", {"variant": variant, "noise": 0}, [("stag", "stag")]
    )
    assert session.results()["metrics"]["external_regret"]["A"]["status"] == "available"


@pytest.mark.parametrize(
    "case,reason",
    [
        ("missing_action", "action"),
        ("missing_payoff", "payoff"),
        ("invalid_action", "action"),
        ("wrong_payoff", "payoff"),
        ("nan_payoff", "payoff"),
        ("incomplete", "length"),
        ("duplicate", "duplicate"),
        ("gap", "contiguous"),
        ("bad_round", "round"),
        ("noise_evidence", "noise"),
        ("not_completed", "incomplete"),
    ],
)
def test_invalid_history_is_explicitly_unavailable(case: str, reason: str) -> None:
    session = completed_session("stag_hunt", {}, [("stag", "hare"), ("hare", "stag")])
    history = deepcopy(session.state.history)
    if case == "missing_action":
        history[0]["actions"].pop("B")
    elif case == "missing_payoff":
        history[0]["payoffs"].pop("A")
    elif case == "invalid_action":
        history[0]["actions"]["A"] = "bad"
    elif case == "wrong_payoff":
        history[0]["payoffs"]["B"] = 99
    elif case == "nan_payoff":
        history[0]["payoffs"]["A"] = math.nan
    elif case == "incomplete":
        history.pop()
    elif case == "duplicate":
        history[1]["round"] = 1
    elif case == "gap":
        history[1]["round"] = 3
    elif case == "bad_round":
        history[0].pop("round")
    elif case == "noise_evidence":
        history[0]["intended_actions"] = history[0]["actions"]
    match = matrix_history_match(
        history,
        "stag_hunt",
        session.config.to_dict(),
        completed=case != "not_completed",
    )
    metric = session.game.metrics_engine.compute_external_regret(
        match, "A", match.config
    )
    assert metric["status"] == "unavailable"
    assert reason in metric["reason"]


def test_invalid_match_moves_and_zero_based_rounds() -> None:
    session = completed_session("rock_paper_scissors", {}, [("rock", "paper")])
    match = session.to_match()
    extension = session.game.metrics_engine
    for move in match.moves:
        move.round_number = 0
    assert (
        extension.compute_external_regret(match, "agent_a", match.config)["series"][0][
            "round"
        ]
        == 1
    )
    partial = deepcopy(match)
    partial.moves.pop()
    assert (
        "incomplete round"
        in extension.compute_external_regret(partial, "agent_a", {})["reason"]
    )
    match.moves.append(Move("unknown", 0, "rock", 0))
    assert (
        "unknown" in extension.compute_external_regret(match, "agent_a", {})["reason"]
    )


def test_empty_incomplete_and_duplicate_identities() -> None:
    extension = RPSMetrics()
    match = Match("m", "rock_paper_scissors", ["A", "B"], [])
    assert "empty" in extension.compute_external_regret(match, "A", {})["reason"]
    assert "unknown" in extension.compute_external_regret(match, "C", {})["reason"]
    match.agent_ids = ["same", "same"]
    assert "distinct" in extension.compute_external_regret(match, "same", {})["reason"]


def test_legacy_estimates_unchanged_and_distinct() -> None:
    session = completed_session(
        "rock_paper_scissors",
        {},
        [("paper", "rock"), ("scissors", "paper"), ("rock", "scissors")],
    )
    report = MatchEvaluator(AgentRegistry()).evaluate(
        session.to_match(), session.game.metrics_engine
    )
    metric = report["agents"]["agent_a"]
    assert metric["cumulative_regret"] == BehavioralMetrics.regret([1, 1, 1], 0) == 0
    assert (
        metric["adaptive_regret_series"]
        == BehavioralMetrics.adaptive_regret([1, 1, 1])
        == [0]
    )
    assert metric["external_regret"]["cumulative"] == -3
    assert metric["total_payoff"] == 3


def test_unsupported_extension_omits_metric() -> None:
    from games.core.public_goods.metrics import PublicGoodsMetrics

    match = Match("m", "public_goods", ["A", "B"], [])
    report = MatchEvaluator(AgentRegistry()).evaluate(match, PublicGoodsMetrics())
    assert all("external_regret" not in r for r in report["agents"].values())


def test_direct_engine_custom_configuration_matches_session() -> None:
    for game in [PDGame(1, T=9, R=6, P=2, S=-2), StagHuntGame(1, 8, 3, -2)]:
        actions = (
            ("cooperate", "defect") if isinstance(game, PDGame) else ("stag", "hare")
        )
        state = game.apply_action(game.initial_state(), "A", actions[0])
        state = game.apply_action(state, "B", actions[1])
        metric = game.compute_results(state)["metrics"]["external_regret"]["A"]
        assert metric["status"] == "available"
        assert metric["actual_total_payoff"] == -2
        assert metric["best_fixed_total_payoff"] == (
            2 if isinstance(game, PDGame) else 3
        )


def test_fractional_payoff_precision_is_preserved() -> None:
    session = completed_session(
        "stag_hunt",
        {
            "payoff_stag_stag": 4.123456,
            "payoff_hare_hare": 2.123456,
            "payoff_stag_hare": -0.123456,
        },
        [("stag", "hare")] * 3,
    )
    result = session.results(MatchEvaluator(AgentRegistry()))
    metric = result["rich_metrics"]["agents"]["agent_a"]["external_regret"]
    assert metric == result["metrics"]["external_regret"]["A"]
    assert metric["actual_total_payoff"] == -0.123456 * 3
    assert metric["cumulative"] == metric["series"][-1]["cumulative"]


@pytest.mark.parametrize("field", ["action", "payoff", "round"])
def test_incomplete_record_survives_session_result_evaluation(field: str) -> None:
    session = completed_session("prisonersdilemma", {}, [("cooperate", "defect")] * 3)
    if field == "action":
        session.state.history[1]["actions"].pop("B")
    elif field == "payoff":
        session.state.history[1]["payoffs"].pop("B")
    else:
        session.state.history[1].pop("round")
    result = session.results(MatchEvaluator(AgentRegistry()))
    assert (
        result["rich_metrics"]["agents"]["agent_a"]["external_regret"]["status"]
        == "unavailable"
    )
    assert result["metrics"]["external_regret"]["A"]["status"] == "unavailable"


def test_invalid_configuration_and_duplicate_identity_are_unavailable() -> None:
    session = completed_session("stag_hunt", {}, [("stag", "hare")])
    match = session.to_match()
    metric = session.game.metrics_engine.compute_external_regret(
        match, "agent_a", {"payoff_hare_hare": 10}
    )
    assert metric["status"] == "unavailable"
    session.agents = {"A": "same", "B": "same"}
    result = session.results(MatchEvaluator(AgentRegistry()))
    assert result["metrics"]["external_regret"]["A"]["status"] == "available"
    assert (
        "distinct"
        in result["rich_metrics"]["agents"]["same"]["external_regret"]["reason"]
    )


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
