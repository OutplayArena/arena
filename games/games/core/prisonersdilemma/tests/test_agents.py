from unittest.mock import patch

from games.core.prisonersdilemma.agent import (
    AlwaysCooperate,
    AlwaysDefect,
    ForgivingTFT,
    GrimTrigger,
    Pavlov,
    RandomAgent,
    TitForTat,
)


class TestAlwaysCooperate:
    def test_empty_history_cooperates(self):
        assert AlwaysCooperate().act([]) == "cooperate"

    def test_with_history_still_cooperates(self):
        agent = AlwaysCooperate()
        history = [{"actions": {"A": "defect", "B": "defect"}, "outcome": "DD"}]
        assert agent.act(history) == "cooperate"


class TestAlwaysDefect:
    def test_empty_history_defects(self):
        assert AlwaysDefect().act([]) == "defect"

    def test_with_history_still_defects(self):
        agent = AlwaysDefect()
        history = [{"actions": {"A": "cooperate", "B": "cooperate"}, "outcome": "CC"}]
        assert agent.act(history) == "defect"


class TestTitForTat:
    def test_empty_history_cooperates(self):
        agent = TitForTat(player="A")
        assert agent.act([]) == "cooperate"

    def test_copies_opponents_last_defect(self):
        agent = TitForTat(player="A")
        history = [{"actions": {"A": "cooperate", "B": "defect"}, "outcome": "CD"}]
        assert agent.act(history) == "defect"

    def test_copies_opponents_last_cooperate(self):
        agent = TitForTat(player="A")
        history = [{"actions": {"A": "defect", "B": "cooperate"}, "outcome": "DC"}]
        assert agent.act(history) == "cooperate"

    def test_player_b_tracks_a(self):
        agent = TitForTat(player="B")
        history = [{"actions": {"A": "defect", "B": "cooperate"}, "outcome": "DC"}]
        assert agent.act(history) == "defect"

    def test_default_to_cooperate_when_opponent_action_missing(self):
        agent = TitForTat(player="A")
        history = [{"actions": {"A": "cooperate"}, "outcome": "C?"}]
        assert agent.act(history) == "cooperate"


class TestGrimTrigger:
    def test_empty_history_cooperates(self):
        agent = GrimTrigger(player="A")
        assert agent.act([]) == "cooperate"

    def test_cooperates_through_cooperation(self):
        agent = GrimTrigger(player="A")
        history = [
            {"actions": {"A": "cooperate", "B": "cooperate"}, "outcome": "CC"},
            {"actions": {"A": "cooperate", "B": "cooperate"}, "outcome": "CC"},
        ]
        assert agent.act(history) == "cooperate"

    def test_triggers_on_opponent_defect(self):
        agent = GrimTrigger(player="A")
        history = [{"actions": {"A": "cooperate", "B": "defect"}, "outcome": "CD"}]
        assert agent.act(history) == "defect"

    def test_defects_forever_after_trigger(self):
        agent = GrimTrigger(player="A")
        history = [
            {"actions": {"A": "cooperate", "B": "cooperate"}, "outcome": "CC"},
            {"actions": {"A": "cooperate", "B": "defect"}, "outcome": "CD"},
            {"actions": {"A": "defect", "B": "cooperate"}, "outcome": "DC"},
        ]
        assert agent.act(history) == "defect"

    def test_player_b_tracks_a(self):
        agent = GrimTrigger(player="B")
        history = [{"actions": {"A": "defect", "B": "cooperate"}, "outcome": "DC"}]
        assert agent.act(history) == "defect"


class TestForgivingTFT:
    def test_empty_history_cooperates(self):
        agent = ForgivingTFT(player="A")
        assert agent.act([]) == "cooperate"

    def test_copies_opponent_cooperate(self):
        agent = ForgivingTFT(player="A")
        history = [{"actions": {"A": "defect", "B": "cooperate"}, "outcome": "DC"}]
        assert agent.act(history) == "cooperate"

    def test_mirrors_opponent_defect_when_no_forgiveness(self):
        agent = ForgivingTFT(player="A", forgiveness_prob=0.0)
        history = [{"actions": {"A": "cooperate", "B": "defect"}, "outcome": "CD"}]
        with patch("random.random", return_value=0.5):
            assert agent.act(history) == "defect"

    def test_forgives_opponent_defect(self):
        agent = ForgivingTFT(player="A", forgiveness_prob=0.5)
        history = [{"actions": {"A": "cooperate", "B": "defect"}, "outcome": "CD"}]
        with patch("random.random", return_value=0.1):
            assert agent.act(history) == "cooperate"

    def test_default_to_cooperate_when_opponent_action_missing(self):
        agent = ForgivingTFT(player="A")
        history = [{"actions": {"A": "defect"}, "outcome": "D?"}]
        assert agent.act(history) == "cooperate"

    def test_player_b_tracks_a(self):
        agent = ForgivingTFT(player="B", forgiveness_prob=0.0)
        history = [{"actions": {"A": "defect", "B": "cooperate"}, "outcome": "DC"}]
        with patch("random.random", return_value=0.5):
            assert agent.act(history) == "defect"


class TestPavlov:
    def test_empty_history_cooperates(self):
        agent = Pavlov(player="A")
        assert agent.act([]) == "cooperate"

    def test_player_a_cooperates_after_cc(self):
        agent = Pavlov(player="A")
        history = [{"actions": {"A": "cooperate", "B": "cooperate"}, "outcome": "CC"}]
        assert agent.act(history) == "cooperate"

    def test_player_a_cooperates_after_dc(self):
        agent = Pavlov(player="A")
        history = [{"actions": {"A": "defect", "B": "cooperate"}, "outcome": "DC"}]
        assert agent.act(history) == "cooperate"

    def test_player_a_defects_after_cd(self):
        agent = Pavlov(player="A")
        history = [{"actions": {"A": "cooperate", "B": "defect"}, "outcome": "CD"}]
        assert agent.act(history) == "defect"

    def test_player_a_defects_after_dd(self):
        agent = Pavlov(player="A")
        history = [{"actions": {"A": "defect", "B": "defect"}, "outcome": "DD"}]
        assert agent.act(history) == "defect"

    def test_player_b_cooperates_after_cc(self):
        agent = Pavlov(player="B")
        history = [{"actions": {"A": "cooperate", "B": "cooperate"}, "outcome": "CC"}]
        assert agent.act(history) == "cooperate"

    def test_player_b_cooperates_after_cd(self):
        agent = Pavlov(player="B")
        history = [{"actions": {"A": "cooperate", "B": "defect"}, "outcome": "CD"}]
        assert agent.act(history) == "cooperate"

    def test_player_b_defects_after_dc(self):
        agent = Pavlov(player="B")
        history = [{"actions": {"A": "defect", "B": "cooperate"}, "outcome": "DC"}]
        assert agent.act(history) == "defect"

    def test_player_b_defects_after_dd(self):
        agent = Pavlov(player="B")
        history = [{"actions": {"A": "defect", "B": "defect"}, "outcome": "DD"}]
        assert agent.act(history) == "defect"


class TestRandomAgent:
    def test_returns_cooperate_or_defect(self):
        agent = RandomAgent()
        with patch("random.choice", return_value="cooperate"):
            assert agent.act([]) == "cooperate"
        with patch("random.choice", return_value="defect"):
            assert agent.act([]) == "defect"
