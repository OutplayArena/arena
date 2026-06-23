from unittest.mock import patch

from games.core.public_goods.agent import (
    AlwaysContributeMax,
    AlwaysContributeZero,
    ConditionalCooperator,
    LinearDecayAgent,
    NashEquilibriumAgent,
    PunishLowContributors,
    RandomAgent,
)


class TestAlwaysContributeMax:
    def test_contributes_full_endowment(self):
        agent = AlwaysContributeMax(endowment=10.0)
        assert agent.act([]) == 10.0
        assert agent.act([
            {"phase": "contribution", "contributions": {"A": 2.0, "B": 2.0}}
        ]) == 10.0

    def test_custom_endowment(self):
        agent = AlwaysContributeMax(endowment=20.0)
        assert agent.act([]) == 20.0


class TestAlwaysContributeZero:
    def test_contributes_zero(self):
        agent = AlwaysContributeZero()
        assert agent.act([]) == 0.0
        assert agent.act([
            {"phase": "contribution", "contributions": {"A": 10.0, "B": 10.0}}
        ]) == 0.0


class TestNashEquilibriumAgent:
    def test_contributes_zero(self):
        agent = NashEquilibriumAgent()
        assert agent.act([]) == 0.0


class TestLinearDecayAgent:
    def test_first_round_full_contribution(self):
        agent = LinearDecayAgent(endowment=10.0, rounds=10)
        assert agent.act([]) == 10.0

    def test_last_round_zero_contribution(self):
        agent = LinearDecayAgent(endowment=10.0, rounds=10)
        history = [{"phase": "contribution"}] * 9
        result = agent.act(history)
        assert result < 0.1

    def test_decay_arithmetic(self):
        agent = LinearDecayAgent(endowment=10.0, rounds=5)
        history = [{"phase": "contribution"}] * 1
        result = agent.act(history)
        assert abs(result - 7.5) < 1e-9

    def test_single_round_returns_endowment(self):
        agent = LinearDecayAgent(endowment=10.0, rounds=1)
        result = agent.act([])
        assert result == 10.0


class TestConditionalCooperator:
    def test_empty_history_returns_endowment(self):
        agent = ConditionalCooperator(endowment=10.0, player_id="A")
        assert agent.act([]) == 10.0

    def test_no_contribution_rounds_returns_endowment(self):
        agent = ConditionalCooperator(endowment=10.0, player_id="A")
        history = [{"phase": "punishment", "contributions": {"A": 5.0, "B": 5.0}}]
        assert agent.act(history) == 10.0

    def test_matches_others_average(self):
        agent = ConditionalCooperator(endowment=10.0, player_id="A")
        history = [{"phase": "contribution", "contributions": {"A": 2.0, "B": 6.0}}]
        assert agent.act(history) == 6.0

    def test_excludes_own_contribution(self):
        agent = ConditionalCooperator(endowment=10.0, player_id="A")
        history = [{"phase": "contribution", "contributions": {"A": 0.0, "B": 4.0, "C": 8.0}}]
        assert agent.act(history) == 6.0

    def test_clamped_to_endowment(self):
        agent = ConditionalCooperator(endowment=5.0, player_id="A")
        history = [{"phase": "contribution", "contributions": {"A": 2.0, "B": 20.0}}]
        assert agent.act(history) == 5.0

    def test_clamped_to_zero(self):
        agent = ConditionalCooperator(endowment=5.0, player_id="A")
        history = [{"phase": "contribution", "contributions": {"A": 2.0, "B": -10.0}}]
        assert agent.act(history) == 0.0

    def test_no_others_returns_endowment(self):
        agent = ConditionalCooperator(endowment=10.0, player_id="A")
        history = [{"phase": "contribution", "contributions": {"A": 5.0}}]
        assert agent.act(history) == 10.0


class TestRandomAgent:
    def test_returns_float_in_range(self):
        agent = RandomAgent(endowment=10.0)
        with patch("random.uniform", return_value=3.5):
            assert agent.act([]) == 3.5


class TestPunishLowContributors:
    def test_contribution_phase_returns_endowment(self):
        agent = PunishLowContributors(endowment=10.0, player_id="A")
        assert agent.act([]) == 10.0

    def test_punishment_phase_punishes_below_average(self):
        agent = PunishLowContributors(endowment=10.0, player_id="A")
        history = [
            {"phase": "contribution", "contributions": {"A": 10.0, "B": 8.0, "C": 2.0}, "punishment_costs": {"A": 0.0, "B": 0.0, "C": 0.0}}
        ]
        result = agent.act(history)
        assert isinstance(result, dict)
        assert "B" in result
        assert "C" in result
        assert result["C"] == 3.0

    def test_punishment_phase_no_others_returns_empty(self):
        agent = PunishLowContributors(endowment=10.0, player_id="A")
        history = [
            {"phase": "contribution", "contributions": {"A": 10.0}, "punishment_costs": {"A": 0.0}}
        ]
        result = agent.act(history)
        assert result == {}

    def test_punishment_clamped_to_zero(self):
        agent = PunishLowContributors(endowment=10.0, player_id="A")
        history = [
            {"phase": "contribution", "contributions": {"A": 10.0, "B": 8.0, "C": 20.0}, "punishment_costs": {"A": 0.0, "B": 0.0, "C": 0.0}}
        ]
        result = agent.act(history)
        assert result["C"] == 0.0
