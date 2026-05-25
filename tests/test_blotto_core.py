import pytest

from blotto.agent import Agent, GreedyAgent, RandomAgent, UniformAgent
from blotto.engine import BlottoGame


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


def test_initial_state_starts_awaiting_both_players():
    game = BlottoGame(num_battlefields=3, total_resources=9, num_rounds=2)

    state = game.initial_state()

    assert state.round_number == 1
    assert state.phase == "awaiting_action"
    assert state.awaiting == ["A", "B"]
    assert state.pending_actions == {}
    assert state.history == []
    assert state.total_scores == {"A": 0, "B": 0}


def test_apply_first_action_returns_new_waiting_state_without_mutating_original():
    game = BlottoGame(num_battlefields=3, total_resources=9, num_rounds=2)
    state = game.initial_state()

    next_state = game.apply_action(state, "A", [9, 0, 0])

    assert state.awaiting == ["A", "B"]
    assert state.pending_actions == {}
    assert next_state.awaiting == ["B"]
    assert next_state.pending_actions == {"A": [9, 0, 0]}
    assert next_state.history == []
    assert next_state.round_number == 1


def test_apply_second_action_resolves_round_and_advances():
    game = BlottoGame(num_battlefields=3, total_resources=9, num_rounds=2)
    state = game.initial_state()

    state = game.apply_action(state, "A", [9, 0, 0])
    state = game.apply_action(state, "B", [0, 9, 0])

    assert state.round_number == 2
    assert state.phase == "awaiting_action"
    assert state.awaiting == ["A", "B"]
    assert state.pending_actions == {}
    assert state.total_scores == {"A": 1.5, "B": 1.5}
    assert state.history == [
        {
            "round": 1,
            "allocations": {"A": [9, 0, 0], "B": [0, 9, 0]},
            "scores": {"A": 1.5, "B": 1.5},
            "winner": "Tie",
            "total_scores": {"A": 1.5, "B": 1.5},
        }
    ]


def test_apply_final_round_marks_terminal():
    game = BlottoGame(num_battlefields=3, total_resources=9, num_rounds=1)
    state = game.initial_state()

    state = game.apply_action(state, "A", [9, 0, 0])
    state = game.apply_action(state, "B", [0, 9, 0])

    assert game.is_terminal(state)
    assert state.phase == "complete"
    assert state.awaiting == []
    assert state.pending_actions == {}
    assert state.round_number == 1


def test_apply_action_rejects_complete_state_duplicate_player_and_bad_input():
    game = BlottoGame(num_battlefields=3, total_resources=9, num_rounds=1)
    state = game.initial_state()

    with pytest.raises(ValueError, match="unknown player"):
        game.apply_action(state, "C", [9, 0, 0])

    with pytest.raises(ValueError, match="invalid action"):
        game.apply_action(state, "A", [9, 0])

    state = game.apply_action(state, "A", [9, 0, 0])

    with pytest.raises(ValueError, match="already submitted"):
        game.apply_action(state, "A", [0, 9, 0])

    state = game.apply_action(state, "B", [0, 9, 0])

    with pytest.raises(ValueError, match="already complete"):
        game.apply_action(state, "A", [9, 0, 0])


def test_compute_results_requires_terminal_state_and_reports_winner():
    game = BlottoGame(num_battlefields=3, total_resources=9, num_rounds=1)
    state = game.initial_state()

    with pytest.raises(ValueError, match="complete"):
        game.compute_results(state)

    state = game.apply_action(state, "A", [9, 0, 0])
    state = game.apply_action(state, "B", [0, 5, 4])

    assert game.compute_results(state) == {
        "total_scores": {"A": 1, "B": 2},
        "winner": "B",
        "history": [
            {
                "round": 1,
                "allocations": {"A": [9, 0, 0], "B": [0, 5, 4]},
                "scores": {"A": 1, "B": 2},
                "winner": "B",
                "total_scores": {"A": 1, "B": 2},
            }
        ],
        "metrics": {
            "total_payoff": {"A": 1, "B": 2},
            "average_payoff": {"A": 1.0, "B": 2.0},
            "round_win_counts": {"A": 0, "B": 1, "Tie": 0},
            "round_win_rate": {"A": 0.0, "B": 1.0, "Tie": 0.0},
            "allocation_concentration": {"A": 1.0, "B": pytest.approx(5 / 9)},
        },
    }
