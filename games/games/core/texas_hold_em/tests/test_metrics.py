import pytest
from outplaylabs_arena.metrics.contracts import Match, Move

from games.core.texas_hold_em.metrics import TexasHoldEmMetrics, _rate
from games.core.texas_hold_em.engine import TexasHoldEmGame
from games.core.texas_hold_em.config import config_from_dict


def _run_game(action_sets: list[list[tuple[str, str]]], rounds: int | None = None) -> tuple[list[dict], dict]:
    n = rounds or len(action_sets)
    cfg = config_from_dict({"game": "texas_hold_em", "rounds": n, "seed": 1})
    game = TexasHoldEmGame.from_config(cfg)
    state = game.initial_state()
    for actions in action_sets:
        for player, action in actions:
            state = game.apply_action(state, player, action)
        if game.is_terminal(state):
            break
    return state.history, state.total_scores


def test_rate_all_fold():
    assert _rate(["fold", "fold", "fold"], "fold") == 1.0


def test_rate_mixed():
    assert _rate(["check", "call", "raise"], "check") == pytest.approx(1 / 3)


def test_rate_empty():
    assert _rate([], "fold") == 0.0


def test_rate_no_matches():
    assert _rate(["check", "call"], "fold") == 0.0


def test_compute_required_keys():
    history, scores = _run_game([
        [("A", "fold")],           # hand 1
        [("A", "check"), ("B", "fold")],  # hand 2
        [("A", "fold")],            # hand 3
    ])
    result = TexasHoldEmMetrics().compute(history, scores)
    for key in ("total_payoff", "average_payoff", "hand_win_counts", "hand_win_rate",
                "fold_rate", "raise_rate", "showdown_count", "fold_count", "raise_count"):
        assert key in result, f"missing key: {key}"


def test_compute_win_counts():
    history, scores = _run_game([
        [("A", "fold")],
        [("A", "check"), ("B", "fold")],
    ])
    result = TexasHoldEmMetrics().compute(history, scores)
    assert result["hand_win_counts"]["B"] == 1
    assert result["hand_win_counts"]["A"] == 1


def test_compute_fold_count():
    history, scores = _run_game([
        [("A", "fold")],
        [("A", "check"), ("B", "fold")],
    ])
    result = TexasHoldEmMetrics().compute(history, scores)
    assert result["fold_count"]["A"] >= 1
    assert result["fold_count"]["B"] >= 1


def test_compute_showdown_count():
    history, scores = _run_game([
        [("A", "check"), ("B", "check"),
         ("B", "check"), ("A", "check"),
         ("B", "check"), ("A", "check"),
         ("B", "check"), ("A", "check")],
    ])
    result = TexasHoldEmMetrics().compute(history, scores)
    assert result["showdown_count"] == 1
    
    

class TestTexasHoldEmMetricsExtension:
    @staticmethod
    def _make_match(action_pairs: list[list[str]]) -> Match:
        moves = []
        for i, pair in enumerate(action_pairs):
            moves.append(Move(agent_id="A", round_number=i, action=pair[0], payoff=0.0))
            moves.append(Move(agent_id="B", round_number=i, action=pair[1], payoff=0.0))
        return Match(match_id="test", game_type="texas_hold_em",
                     agent_ids=["A", "B"], moves=moves)

    def test_compute_joint_showdown_rate_all_play(self):
        match = self._make_match([["check", "check"]] * 3)
        joint = TexasHoldEmMetrics().compute_joint(match, {})
        assert joint["the_showdown_rate"] == 1.0

    def test_compute_joint_showdown_rate_none(self):
        match = self._make_match([["fold", "check"], ["check", "fold"], ["fold", "fold"]])
        joint = TexasHoldEmMetrics().compute_joint(match, {})
        assert joint["the_showdown_rate"] == 0.0

    def test_compute_joint_showdown_rate_mixed(self):
        match = self._make_match([["check", "check"], ["fold", "check"], ["check", "fold"]])
        joint = TexasHoldEmMetrics().compute_joint(match, {})
        assert joint["the_showdown_rate"] == pytest.approx(1 / 3)

    def test_compute_agent_action_rates(self):
        match = self._make_match([
            ["check", "check"], ["raise", "call"],
            ["fold", "check"], ["call", "raise"],
        ])
        result = TexasHoldEmMetrics().compute_agent(match, "A", {}, {})
        the = result["the"]
        assert the["fold_rate"] == pytest.approx(0.25)
        assert the["check_rate"] == 0.25
        assert the["call_rate"] == 0.25
        assert the["raise_rate"] == 0.25

    def test_compute_agent_all_fold(self):
        match = self._make_match([["fold", "check"], ["fold", "check"]])
        result = TexasHoldEmMetrics().compute_agent(match, "A", {}, {})
        the = result["the"]
        assert the["fold_rate"] == 1.0
        assert the["check_rate"] == 0.0
