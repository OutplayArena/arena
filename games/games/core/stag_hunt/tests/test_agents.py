from unittest.mock import patch

from games.core.stag_hunt.agent import (
    AlwaysHare,
    AlwaysStag,
    NashEquilibriumAgent,
    OptimisticAgent,
    ParetoOptimalAgent,
    RandomAgent,
    TitForTat,
)


class TestAlwaysStag:
    def test_always_stag(self):
        agent = AlwaysStag()
        assert agent.act([]) == "stag"
        assert agent.act([{"actions": {"A": "hare", "B": "hare"}}]) == "stag"


class TestAlwaysHare:
    def test_always_hare(self):
        agent = AlwaysHare()
        assert agent.act([]) == "hare"
        assert agent.act([{"actions": {"A": "stag", "B": "stag"}}]) == "hare"


class TestNashEquilibriumAgent:
    def test_always_hare(self):
        agent = NashEquilibriumAgent()
        assert agent.act([]) == "hare"
        assert agent.act([{"actions": {"A": "stag", "B": "stag"}}]) == "hare"


class TestParetoOptimalAgent:
    def test_always_stag(self):
        agent = ParetoOptimalAgent()
        assert agent.act([]) == "stag"
        assert agent.act([{"actions": {"A": "hare", "B": "hare"}}]) == "stag"


class TestTitForTat:
    def test_first_round_stag(self):
        agent = TitForTat(player="A")
        assert agent.act([]) == "stag"

    def test_mirrors_opponent_stag(self):
        agent = TitForTat(player="A")
        history = [{"actions": {"A": "stag", "B": "stag"}}]
        assert agent.act(history) == "stag"

    def test_mirrors_opponent_hare(self):
        agent = TitForTat(player="A")
        history = [{"actions": {"A": "stag", "B": "hare"}}]
        assert agent.act(history) == "hare"

    def test_player_b_tracks_a(self):
        agent = TitForTat(player="B")
        history = [{"actions": {"A": "hare", "B": "stag"}}]
        assert agent.act(history) == "hare"

    def test_default_to_stag_when_opponent_action_missing(self):
        agent = TitForTat(player="A")
        history = [{"actions": {"A": "stag"}}]
        assert agent.act(history) == "stag"


class TestOptimisticAgent:
    def test_first_round_stag(self):
        agent = OptimisticAgent(player="A")
        assert agent.act([]) == "stag"

    def test_stays_stag_through_cooperation(self):
        agent = OptimisticAgent(player="A")
        history = [
            {"actions": {"A": "stag", "B": "stag"}},
            {"actions": {"A": "stag", "B": "stag"}},
        ]
        assert agent.act(history) == "stag"

    def test_switches_to_hare_after_betrayal(self):
        agent = OptimisticAgent(player="A")
        history = [{"actions": {"A": "stag", "B": "hare"}}]
        assert agent.act(history) == "hare"

    def test_stays_hare_forever_after_betrayal(self):
        agent = OptimisticAgent(player="A")
        history = [
            {"actions": {"A": "stag", "B": "hare"}},
            {"actions": {"A": "hare", "B": "stag"}},
        ]
        assert agent.act(history) == "hare"

    def test_player_b_tracks_a(self):
        agent = OptimisticAgent(player="B")
        history = [{"actions": {"A": "hare", "B": "stag"}}]
        assert agent.act(history) == "hare"


class TestRandomAgent:
    def test_returns_stag_or_hare(self):
        agent = RandomAgent()
        with patch("random.choice", return_value="stag"):
            assert agent.act([]) == "stag"
        with patch("random.choice", return_value="hare"):
            assert agent.act([]) == "hare"
