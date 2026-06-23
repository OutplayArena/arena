from unittest.mock import patch

from games.core.ultimatum.agent import (
    FairAgent,
    GreedyProposer,
    RandomAgent,
    SPEAgent,
)


class TestSPEAgent:
    def test_empty_history_proposes_minimum(self):
        agent = SPEAgent(player="A", total=100.0, min_offer=1.0)
        assert agent.act([]) == 1.0

    def test_responder_accepts_above_minimum(self):
        agent = SPEAgent(player="B", total=100.0, min_offer=1.0)
        history = [{"proposer": "A", "responder": "B", "offer": 50.0, "response": None}]
        assert agent.act(history) == "accept"

    def test_responder_accepts_exact_minimum(self):
        agent = SPEAgent(player="B", total=100.0, min_offer=1.0)
        history = [{"proposer": "A", "responder": "B", "offer": 1.0, "response": None}]
        assert agent.act(history) == "accept"

    def test_responder_rejects_below_minimum(self):
        agent = SPEAgent(player="B", total=100.0, min_offer=5.0)
        history = [{"proposer": "A", "responder": "B", "offer": 1.0, "response": None}]
        assert agent.act(history) == "reject"

    def test_proposer_after_own_proposal_proposes_again(self):
        agent = SPEAgent(player="A", total=100.0, min_offer=1.0)
        history = [{"proposer": "A", "responder": "B", "offer": 10.0, "response": "accept"}]
        assert agent.act(history) == 1.0

    def test_proposer_with_no_offer_in_history_returns_minimum(self):
        agent = SPEAgent(player="A", total=100.0, min_offer=2.0)
        history = [{"proposer": "A", "responder": "B", "offer": 0.0, "response": None}]
        assert agent.act(history) == 2.0


class TestFairAgent:
    def test_empty_history_proposes_half(self):
        agent = FairAgent(player="A", total=100.0)
        assert agent.act([]) == 50.0

    def test_responder_accepts_above_40_percent(self):
        agent = FairAgent(player="B", total=100.0)
        history = [{"proposer": "A", "responder": "B", "offer": 50.0, "response": None}]
        assert agent.act(history) == "accept"

    def test_responder_accepts_exact_40_percent(self):
        agent = FairAgent(player="B", total=100.0)
        history = [{"proposer": "A", "responder": "B", "offer": 40.0, "response": None}]
        assert agent.act(history) == "accept"

    def test_responder_rejects_below_40_percent(self):
        agent = FairAgent(player="B", total=100.0)
        history = [{"proposer": "A", "responder": "B", "offer": 30.0, "response": None}]
        assert agent.act(history) == "reject"

    def test_proposer_after_response_proposes_half(self):
        agent = FairAgent(player="A", total=100.0)
        history = [{"proposer": "A", "responder": "B", "offer": 50.0, "response": "accept"}]
        assert agent.act(history) == 50.0

    def test_handles_missing_offer_in_history(self):
        agent = FairAgent(player="B", total=100.0)
        history = [{"proposer": "A", "responder": "B", "response": None}]
        assert agent.act(history) == "reject"


class TestGreedyProposer:
    def test_empty_history_proposes_minimum(self):
        agent = GreedyProposer(player="A", total=100.0, min_offer=1.0)
        assert agent.act([]) == 1.0

    def test_responder_accepts_above_30_percent(self):
        agent = GreedyProposer(player="B", total=100.0, min_offer=1.0)
        history = [{"proposer": "A", "responder": "B", "offer": 40.0, "response": None}]
        assert agent.act(history) == "accept"

    def test_responder_accepts_exact_30_percent(self):
        agent = GreedyProposer(player="B", total=100.0, min_offer=1.0)
        history = [{"proposer": "A", "responder": "B", "offer": 30.0, "response": None}]
        assert agent.act(history) == "accept"

    def test_responder_rejects_below_30_percent(self):
        agent = GreedyProposer(player="B", total=100.0, min_offer=1.0)
        history = [{"proposer": "A", "responder": "B", "offer": 20.0, "response": None}]
        assert agent.act(history) == "reject"

    def test_proposer_after_response_proposes_minimum(self):
        agent = GreedyProposer(player="A", total=100.0, min_offer=1.0)
        history = [{"proposer": "A", "responder": "B", "offer": 5.0, "response": "reject"}]
        assert agent.act(history) == 1.0


class TestRandomAgent:
    def test_empty_history_returns_float_in_range(self):
        agent = RandomAgent(player="A", total=100.0)
        with patch("games.core.ultimatum.agent.random.uniform", return_value=42.5):
            assert agent.act([]) == 42.5

    def test_responder_returns_accept_or_reject(self):
        agent = RandomAgent(player="B", total=100.0)
        history = [{"proposer": "A", "responder": "B", "offer": 50.0, "response": None}]
        with patch("games.core.ultimatum.agent.random.choice", return_value="accept"):
            assert agent.act(history) == "accept"
        with patch("games.core.ultimatum.agent.random.choice", return_value="reject"):
            assert agent.act(history) == "reject"

    def test_proposer_with_response_in_history_proposes_float(self):
        agent = RandomAgent(player="A", total=100.0)
        history = [{"proposer": "A", "responder": "B", "offer": 10.0, "response": "accept"}]
        with patch("games.core.ultimatum.agent.random.uniform", return_value=33.3):
            assert agent.act(history) == 33.3
