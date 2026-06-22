from unittest.mock import patch

from games.core.centipede.agent import (
    AlwaysPassAgent,
    LastStepTakeAgent,
    RandomAgent,
    TakeFirstAgent,
    TitForTatAgent,
)


class TestTakeFirstAgent:
    def test_always_takes(self):
        agent = TakeFirstAgent()
        assert agent.act([]) == "take"
        assert agent.act([{"player": "A", "action": "pass"}]) == "take"
        assert agent.act([
            {"player": "A", "action": "pass"},
            {"player": "B", "action": "pass"},
        ]) == "take"


class TestAlwaysPassAgent:
    def test_always_passes(self):
        agent = AlwaysPassAgent()
        assert agent.act([]) == "pass"
        assert agent.act([{"player": "A", "action": "take"}]) == "pass"


class TestLastStepTakeAgent:
    def test_passes_below_max_steps(self):
        agent = LastStepTakeAgent(max_steps=6, player="A")
        assert agent.act([]) == "pass"
        assert agent.act([
            {"player": "A", "action": "pass"},
            {"player": "B", "action": "pass"},
        ]) == "pass"

    def test_takes_at_max_steps(self):
        agent = LastStepTakeAgent(max_steps=3, player="A")
        history = [
            {"player": "A", "action": "pass"},
            {"player": "B", "action": "pass"},
        ]
        assert agent.act(history) == "take"

    def test_takes_beyond_max_steps(self):
        agent = LastStepTakeAgent(max_steps=2, player="A")
        history = [
            {"player": "A", "action": "pass"},
            {"player": "B", "action": "pass"},
            {"player": "A", "action": "pass"},
        ]
        assert agent.act(history) == "take"


class TestTitForTatAgent:
    def test_first_round_passes(self):
        agent = TitForTatAgent(player="A")
        assert agent.act([]) == "pass"

    def test_passes_when_opponent_passed(self):
        agent = TitForTatAgent(player="A")
        history = [{"player": "B", "action": "pass"}]
        assert agent.act(history) == "pass"

    def test_takes_when_opponent_took(self):
        agent = TitForTatAgent(player="A")
        history = [{"player": "B", "action": "take"}]
        assert agent.act(history) == "take"

    def test_ignores_own_actions(self):
        agent = TitForTatAgent(player="A")
        history = [
            {"player": "A", "action": "take"},
            {"player": "B", "action": "pass"},
        ]
        assert agent.act(history) == "pass"

    def test_player_b_tracks_a(self):
        agent = TitForTatAgent(player="B")
        history = [{"player": "A", "action": "take"}]
        assert agent.act(history) == "take"


class TestRandomAgent:
    def test_returns_take_or_pass(self):
        agent = RandomAgent()
        with patch("random.choice", return_value="take"):
            assert agent.act([]) == "take"
        with patch("random.choice", return_value="pass"):
            assert agent.act([]) == "pass"
