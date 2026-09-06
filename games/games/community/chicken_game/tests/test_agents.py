from unittest.mock import patch

from games.community.chicken_game.agent import (
    AlternatingAgent,
    AlwaysDare,
    AlwaysSwerve,
    GrimTrigger,
    RandomAgent,
    TitForTat,
)


class TestAlwaysSwerve:
    def test_always_swerve(self):
        agent = AlwaysSwerve()
        assert agent.act([]) == "swerve"
        assert agent.act([{"actions": {"A": "dare", "B": "dare"}}]) == "swerve"


class TestAlwaysDare:
    def test_always_dare(self):
        agent = AlwaysDare()
        assert agent.act([]) == "dare"
        assert agent.act([{"actions": {"A": "swerve", "B": "swerve"}}]) == "dare"


class TestTitForTat:
    def test_first_round_swerve(self):
        agent = TitForTat(player="A")
        assert agent.act([]) == "swerve"

    def test_mirrors_opponent_swerve(self):
        agent = TitForTat(player="A")
        history = [{"actions": {"A": "dare", "B": "swerve"}}]
        assert agent.act(history) == "swerve"

    def test_mirrors_opponent_dare(self):
        agent = TitForTat(player="A")
        history = [{"actions": {"A": "swerve", "B": "dare"}}]
        assert agent.act(history) == "dare"

    def test_player_b_tracks_a(self):
        agent = TitForTat(player="B")
        history = [{"actions": {"A": "dare", "B": "swerve"}}]
        assert agent.act(history) == "dare"

    def test_default_to_swerve_when_opponent_action_missing(self):
        agent = TitForTat(player="A")
        history = [{"actions": {"A": "swerve"}}]
        assert agent.act(history) == "swerve"


class TestGrimTrigger:
    def test_first_round_swerve(self):
        agent = GrimTrigger(player="A")
        assert agent.act([]) == "swerve"

    def test_stays_swerve_through_mutual_swerve(self):
        agent = GrimTrigger(player="A")
        history = [
            {"actions": {"A": "swerve", "B": "swerve"}},
            {"actions": {"A": "swerve", "B": "swerve"}},
        ]
        assert agent.act(history) == "swerve"

    def test_triggers_after_opponent_dares(self):
        agent = GrimTrigger(player="A")
        history = [{"actions": {"A": "swerve", "B": "dare"}}]
        assert agent.act(history) == "dare"

    def test_stays_dare_forever_after_trigger(self):
        agent = GrimTrigger(player="A")
        history = [
            {"actions": {"A": "swerve", "B": "dare"}},
            {"actions": {"A": "dare", "B": "swerve"}},
        ]
        assert agent.act(history) == "dare"

    def test_player_b_tracks_a(self):
        agent = GrimTrigger(player="B")
        history = [{"actions": {"A": "dare", "B": "swerve"}}]
        assert agent.act(history) == "dare"


class TestAlternatingAgent:
    def test_starts_with_dare(self):
        agent = AlternatingAgent()
        assert agent.act([]) == "dare"

    def test_alternates_each_round(self):
        agent = AlternatingAgent()
        assert agent.act([{}]) == "swerve"
        assert agent.act([{}, {}]) == "dare"
        assert agent.act([{}, {}, {}]) == "swerve"


class TestRandomAgent:
    def test_returns_swerve_or_dare(self):
        agent = RandomAgent()
        with patch("random.choice", return_value="swerve"):
            assert agent.act([]) == "swerve"
        with patch("random.choice", return_value="dare"):
            assert agent.act([]) == "dare"
