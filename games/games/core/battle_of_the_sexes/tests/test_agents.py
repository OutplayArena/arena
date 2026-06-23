from unittest.mock import patch

from games.core.battle_of_the_sexes.agent import (
    AlwaysA,
    AlwaysB,
    MixedNashAgent,
    RandomAgent,
    TitForTat,
)


class TestAlwaysA:
    def test_returns_option_a(self):
        agent = AlwaysA(option_a="opera")
        assert agent.act([]) == "opera"
        assert agent.act([{"actions": {"A": "football", "B": "football"}}]) == "opera"

    def test_custom_option(self):
        agent = AlwaysA(option_a="ballet")
        assert agent.act([]) == "ballet"


class TestAlwaysB:
    def test_returns_option_b(self):
        agent = AlwaysB(option_b="football")
        assert agent.act([]) == "football"
        assert agent.act([{"actions": {"A": "opera", "B": "opera"}}]) == "football"

    def test_custom_option(self):
        agent = AlwaysB(option_b="hockey")
        assert agent.act([]) == "hockey"


class TestTitForTat:
    def test_first_round_player_a_prefers_a(self):
        agent = TitForTat(player="A", option_a="opera", option_b="football")
        assert agent.act([]) == "opera"

    def test_first_round_player_b_prefers_b(self):
        agent = TitForTat(player="B", option_a="opera", option_b="football")
        assert agent.act([]) == "football"

    def test_mirrors_opponents_last_action(self):
        agent = TitForTat(player="A", option_a="opera", option_b="football")
        history = [{"actions": {"A": "opera", "B": "football"}}]
        assert agent.act(history) == "football"

    def test_player_b_mirrors_a(self):
        agent = TitForTat(player="B", option_a="opera", option_b="football")
        history = [{"actions": {"A": "football", "B": "opera"}}]
        assert agent.act(history) == "football"

    def test_falls_back_to_preferred_when_opponent_missing(self):
        agent = TitForTat(player="A", option_a="opera", option_b="football")
        history = [{"actions": {"A": "opera"}}]
        assert agent.act(history) == "opera"


class TestMixedNashAgent:
    def test_player_a_plays_a_above_threshold(self):
        agent = MixedNashAgent(player="A", prob_a=0.6)
        with patch("random.random", return_value=0.5):
            assert agent.act([]) == "opera"

    def test_player_a_plays_b_below_threshold(self):
        agent = MixedNashAgent(player="A", prob_a=0.6)
        with patch("random.random", return_value=0.7):
            assert agent.act([]) == "football"

    def test_player_b_inverts_probability(self):
        agent = MixedNashAgent(player="B", prob_a=0.6)
        assert agent.prob_a == 0.4
        with patch("random.random", return_value=0.3):
            assert agent.act([]) == "opera"
        with patch("random.random", return_value=0.5):
            assert agent.act([]) == "football"

    def test_custom_options(self):
        agent = MixedNashAgent(player="A", option_a="ballet", option_b="hockey", prob_a=1.0)
        with patch("random.random", return_value=0.5):
            assert agent.act([]) == "ballet"


class TestRandomAgent:
    def test_returns_one_of_two_options(self):
        agent = RandomAgent(option_a="opera", option_b="football")
        with patch("random.choice", return_value="opera") as mock_choice:
            assert agent.act([]) == "opera"
            mock_choice.assert_called_once_with(["opera", "football"])
        with patch("random.choice", return_value="football"):
            assert agent.act([]) == "football"
