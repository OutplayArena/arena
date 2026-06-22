from unittest.mock import patch

from games.core.rock_paper_scissors.agent import (
    BEATEN_BY,
    BiasedAgent,
    CopycatAgent,
    CounterAgent,
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
        with patch("random.choice", return_value="rock") as mock_choice:
            agent.act([])
            mock_choice.assert_called_once_with(MOVES)


class TestBiasedAgent:
    def test_returns_valid_move(self):
        agent = BiasedAgent(rock_weight=0.5)
        for move in MOVES:
            with patch("random.choices", return_value=[move]) as mock_choices:
                assert agent.act([]) == move
                weights_arg = mock_choices.call_args.kwargs.get("weights") or mock_choices.call_args.args[1]
                assert len(weights_arg) == 3
                assert abs(sum(weights_arg) - 1.0) < 1e-9

    def test_default_rock_weight_is_50_percent(self):
        agent = BiasedAgent()
        assert agent._weights[0] == 0.5
        assert abs(agent._weights[1] - 0.25) < 1e-9
        assert abs(agent._weights[2] - 0.25) < 1e-9

    def test_high_rock_weight(self):
        agent = BiasedAgent(rock_weight=0.9)
        assert agent._weights[0] == 0.9
        assert abs(agent._weights[1] - 0.05) < 1e-9
        assert abs(agent._weights[2] - 0.05) < 1e-9


class TestCopycatAgent:
    def test_first_round_returns_random_move(self):
        agent = CopycatAgent(player="A")
        for move in MOVES:
            with patch("random.choice", return_value=move):
                assert agent.act([]) == move

    def test_copies_opponents_last_move(self):
        agent = CopycatAgent(player="A")
        history = [{"actions": {"A": "rock", "B": "paper"}}]
        assert agent.act(history) == "paper"

    def test_player_b_copies_a(self):
        agent = CopycatAgent(player="B")
        history = [{"actions": {"A": "scissors", "B": "rock"}}]
        assert agent.act(history) == "scissors"

    def test_falls_back_to_random_when_opponent_missing(self):
        agent = CopycatAgent(player="A")
        history = [{"actions": {"A": "rock"}}]
        with patch("random.choice", return_value="scissors") as mock_choice:
            assert agent.act(history) == "scissors"
            mock_choice.assert_called_once_with(MOVES)


class TestCounterAgent:
    def test_first_round_returns_random_move(self):
        agent = CounterAgent(player="A")
        for move in MOVES:
            with patch("random.choice", return_value=move):
                assert agent.act([]) == move

    def test_beats_opponents_rock(self):
        agent = CounterAgent(player="A")
        history = [{"actions": {"A": "scissors", "B": "rock"}}]
        assert agent.act(history) == "paper"

    def test_beats_opponents_paper(self):
        agent = CounterAgent(player="A")
        history = [{"actions": {"A": "rock", "B": "paper"}}]
        assert agent.act(history) == "scissors"

    def test_beats_opponents_scissors(self):
        agent = CounterAgent(player="A")
        history = [{"actions": {"A": "paper", "B": "scissors"}}]
        assert agent.act(history) == "rock"

    def test_player_b_counter_works(self):
        agent = CounterAgent(player="B")
        history = [{"actions": {"A": "paper", "B": "scissors"}}]
        assert agent.act(history) == "scissors"

    def test_falls_back_to_random_when_opponent_missing(self):
        agent = CounterAgent(player="A")
        history = [{"actions": {"A": "rock"}}]
        with patch("random.choice", return_value="scissors"):
            assert agent.act(history) == "scissors"

    def test_falls_back_to_random_when_opponent_move_invalid(self):
        agent = CounterAgent(player="A")
        history = [{"actions": {"A": "rock", "B": "invalid"}}]
        with patch("random.choice", return_value="scissors") as mock_choice:
            assert agent.act(history) == "scissors"
            mock_choice.assert_called_once_with(MOVES)

    def test_beats_table_is_consistent(self):
        for move in MOVES:
            assert CounterAgent(player="A").act(
                [{"actions": {"A": "rock", "B": move}}]
            ) == BEATEN_BY[move]
