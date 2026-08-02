from unittest.mock import patch

from games.community.vickrey_auction.agent import (
    AlwaysMaxBidder,
    AlwaysZeroBidder,
    Overbidder,
    RandomBidder,
    Shader,
    TruthfulBidder,
)


class TestTruthfulBidder:
    def test_bids_exact_value(self):
        agent = TruthfulBidder()
        agent.set_value(42.0)
        assert agent.act([]) == 42.0

    def test_updates_with_new_value(self):
        agent = TruthfulBidder()
        agent.set_value(10.0)
        assert agent.act([]) == 10.0
        agent.set_value(99.0)
        assert agent.act([]) == 99.0


class TestShader:
    def test_underbids_by_shade_factor(self):
        agent = Shader(shade_factor=0.8)
        agent.set_value(100.0)
        assert agent.act([]) == 80.0

    def test_default_shade_factor(self):
        agent = Shader()
        agent.set_value(50.0)
        assert agent.act([]) == 40.0


class TestOverbidder:
    def test_overbids_by_factor(self):
        agent = Overbidder(overbid_factor=1.2)
        agent.set_value(100.0)
        assert agent.act([]) == 120.0

    def test_default_overbid_factor(self):
        agent = Overbidder()
        agent.set_value(50.0)
        assert agent.act([]) == 60.0


class TestAlwaysMaxBidder:
    def test_always_returns_max_bid_regardless_of_value(self):
        agent = AlwaysMaxBidder(max_bid=200.0)
        agent.set_value(1.0)
        assert agent.act([]) == 200.0


class TestAlwaysZeroBidder:
    def test_always_returns_zero(self):
        agent = AlwaysZeroBidder()
        agent.set_value(75.0)
        assert agent.act([]) == 0.0


class TestRandomBidder:
    def test_returns_value_within_bid_ceiling(self):
        agent = RandomBidder(max_bid=200.0)
        with patch("random.uniform", return_value=123.4):
            assert agent.act([]) == 123.4
