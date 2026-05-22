import pytest

from blotto.agent import Agent, GreedyAgent, RandomAgent, UniformAgent
from blotto.api import BlottoGame


class FixedAgent(Agent):
    def __init__(self, name, action):
        super().__init__(name)
        self.action = action

    def act(self, history):
        return self.action


def test_match_winner_can_be_agent_b():
    game = BlottoGame(num_battlefields=5, total_resources=100)
    agent_a = FixedAgent("weak", [0, 0, 0, 0, 100])
    agent_b = FixedAgent("strong", [1, 1, 1, 1, 96])

    result = game.play_match(agent_a, agent_b, num_rounds=1)

    assert result["total_score_a"] == 1
    assert result["total_score_b"] == 4
    assert result["match_winner"] == "strong"


def test_validate_action_accepts_only_exact_integer_allocations():
    game = BlottoGame(num_battlefields=3, total_resources=9)

    assert game.validate_action([3, 3, 3])
    assert not game.validate_action((3, 3, 3))
    assert not game.validate_action([3, 3])
    assert not game.validate_action([3, 3, 2])
    assert not game.validate_action([3, 3, -3])
    assert not game.validate_action([3, 3, 3.0])
    assert not game.validate_action([True, 4, 4])


def test_play_round_scores_wins_losses_and_ties():
    game = BlottoGame(num_battlefields=5, total_resources=10)

    result = game.play_round([5, 2, 1, 1, 1], [1, 2, 2, 3, 2])

    assert result == {
        "action_a": [5, 2, 1, 1, 1],
        "action_b": [1, 2, 2, 3, 2],
        "score_a": 1.5,
        "score_b": 3.5,
        "winner": "B",
    }


def test_play_round_rejects_invalid_actions():
    game = BlottoGame(num_battlefields=3, total_resources=9)

    with pytest.raises(ValueError, match="Invalid action for Agent A"):
        game.play_round([3, 3, 2], [3, 3, 3])

    with pytest.raises(ValueError, match="Invalid action for Agent B"):
        game.play_round([3, 3, 3], [9, 0])


def test_play_match_totals_history_and_tie_winner():
    game = BlottoGame(num_battlefields=3, total_resources=9)
    agent_a = FixedAgent("a", [3, 3, 3])
    agent_b = FixedAgent("b", [3, 3, 3])

    result = game.play_match(agent_a, agent_b, num_rounds=2)

    assert result["total_score_a"] == 3
    assert result["total_score_b"] == 3
    assert result["match_winner"] == "Tie"
    assert len(result["history"]) == 2
    assert result["history"][0]["round"] == 1
    assert result["history"][1]["round"] == 2


def test_play_match_history_contains_opponent_score_key():
    class CapturingAgent(FixedAgent):
        def __init__(self, name, action):
            super().__init__(name, action)
            self.seen_history = None

        def act(self, history):
            self.seen_history = list(history)
            return self.action

    game = BlottoGame(num_battlefields=5, total_resources=100)
    agent_a = CapturingAgent("a", [20, 20, 20, 20, 20])
    agent_b = CapturingAgent("b", [20, 20, 20, 20, 20])

    game.play_match(agent_a, agent_b, num_rounds=2)

    assert agent_a.seen_history[0]["opponent_score"] == 2.5
    assert "oppoenent_score" not in agent_a.seen_history[0]


def test_game_rejects_impossible_parameters():
    with pytest.raises(ValueError, match="num_battlefields"):
        BlottoGame(num_battlefields=0, total_resources=100)

    with pytest.raises(ValueError, match="total_resources"):
        BlottoGame(num_battlefields=5, total_resources=4)


def test_builtin_agents_support_variable_game_parameters():
    uniform = UniformAgent(num_battlefields=3, total_resources=10)
    random_agent = RandomAgent(num_battlefields=3, total_resources=10)
    greedy = GreedyAgent(num_battlefields=3, total_resources=10)

    assert uniform.act([]) == [4, 3, 3]
    assert greedy.act([]) == [4, 3, 3]

    random_action = random_agent.act([])
    assert len(random_action) == 3
    assert sum(random_action) == 10
    assert all(isinstance(value, int) and value >= 0 for value in random_action)
