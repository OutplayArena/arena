from unittest.mock import patch

from games.core.cournot_duopoly.agent import (
    CollussiveAgent,
    GreedyAgent,
    NashEquilibriumAgent,
    RandomAgent,
)


class TestNashEquilibriumAgent:
    def test_returns_nash_quantity(self):
        agent = NashEquilibriumAgent(nash_quantity=40.0)
        assert agent.act([]) == 40.0

    def test_custom_quantity(self):
        agent = NashEquilibriumAgent(nash_quantity=25.0)
        assert agent.act([]) == 25.0


class TestCollussiveAgent:
    def test_returns_collusive_quantity(self):
        agent = CollussiveAgent(collusive_quantity=30.0)
        assert agent.act([]) == 30.0

    def test_custom_quantity(self):
        agent = CollussiveAgent(collusive_quantity=20.0)
        assert agent.act([]) == 20.0


class TestGreedyAgent:
    def test_empty_history_returns_nash_q(self):
        agent = GreedyAgent(nash_q=40.0)
        assert agent.act([]) == 40.0

    def test_responds_to_opponents_low_quantity(self):
        agent = GreedyAgent(demand_a=120.0, demand_b=1.0, cost=0.0, max_q=120.0, nash_q=40.0)
        history = [{"quantities": {"A": 10.0, "B": 20.0}}]
        result = agent.act(history)
        assert result > 40.0

    def test_responds_to_opponents_high_quantity(self):
        agent = GreedyAgent(demand_a=120.0, demand_b=1.0, cost=0.0, max_q=120.0, nash_q=40.0)
        history = [{"quantities": {"A": 100.0, "B": 80.0}}]
        result = agent.act(history)
        assert result < 40.0

    def test_best_response_clamped_to_max(self):
        agent = GreedyAgent(demand_a=120.0, demand_b=1.0, cost=0.0, max_q=50.0, nash_q=40.0)
        history = [{"quantities": {"A": 0.0, "B": 0.0}}]
        result = agent.act(history)
        assert result == 50.0

    def test_best_response_clamped_to_zero(self):
        agent = GreedyAgent(demand_a=120.0, demand_b=1.0, cost=200.0, max_q=120.0, nash_q=40.0)
        history = [{"quantities": {"A": 0.0, "B": 0.0}}]
        result = agent.act(history)
        assert result == 0.0

    def test_no_quantities_in_history_returns_nash(self):
        agent = GreedyAgent(nash_q=40.0)
        history = [{"round": 1}]
        assert agent.act(history) == 40.0

    def test_quantities_value_is_none_returns_nash(self):
        agent = GreedyAgent(nash_q=40.0)
        history = [{"quantities": {}}]
        assert agent.act(history) == 40.0

    def test_takes_any_value_from_quantities(self):
        agent = GreedyAgent(demand_a=120.0, demand_b=1.0, cost=0.0, max_q=120.0, nash_q=40.0)
        history = [{"quantities": {"A": 10.0, "B": 100.0}}]
        result = agent.act(history)
        assert result < 40.0


class TestRandomAgent:
    def test_returns_float_in_range(self):
        agent = RandomAgent(max_quantity=120.0)
        with patch("random.uniform", return_value=50.0):
            assert agent.act([]) == 50.0

    def test_uniform_called_with_zero_and_max(self):
        agent = RandomAgent(max_quantity=80.0)
        with patch("random.uniform", return_value=10.0) as mock_uniform:
            agent.act([])
            mock_uniform.assert_called_once_with(0.0, 80.0)
