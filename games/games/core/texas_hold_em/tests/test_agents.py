from unittest.mock import patch

from games.core.texas_hold_em.agent import (
    AggressiveAgent,
    CallStationAgent,
    ConservativeAgent,
    MOVES,
    RandomAgent,
)


class TestRandomAgent:
    def test_returns_valid_move(self):
        agent = RandomAgent()
        for move in MOVES:
            with patch("random.choice", return_value=move):
                assert agent.act([]) == move

    def test_random_choice_called_with_moves(self):
        agent = RandomAgent()
        with patch("random.choice", return_value="fold") as mock_choice:
            agent.act([])
            mock_choice.assert_called_once_with(list(MOVES))


class TestConservativeAgent:
    def test_uses_weighted_distribution(self):
        agent = ConservativeAgent()
        with patch("random.choices", return_value=["fold"]) as mock_choices:
            assert agent.act([]) == "fold"
            call_args = mock_choices.call_args
            assert call_args.args[0] == MOVES
            weights = call_args.kwargs.get("weights")
            assert weights == [0.4, 0.3, 0.2, 0.1]


class TestAggressiveAgent:
    def test_uses_weighted_distribution(self):
        agent = AggressiveAgent()
        with patch("random.choices", return_value=["raise"]) as mock_choices:
            assert agent.act([]) == "raise"
            call_args = mock_choices.call_args
            assert call_args.args[0] == MOVES
            weights = call_args.kwargs.get("weights")
            assert weights == [0.05, 0.15, 0.3, 0.5]


class TestCallStationAgent:
    def test_uses_weighted_distribution(self):
        agent = CallStationAgent()
        with patch("random.choices", return_value=["call"]) as mock_choices:
            assert agent.act([]) == "call"
            call_args = mock_choices.call_args
            assert call_args.args[0] == MOVES
            weights = call_args.kwargs.get("weights")
            assert weights == [0.0, 0.2, 0.6, 0.2]
