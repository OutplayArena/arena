import pytest
from arena.metrics.contracts import Match, Move

from games.community.vickrey_auction.metrics import VickreyAuctionMetrics


def make_history(*rounds: dict) -> tuple[list[dict], dict[str, float]]:
    """rounds: each dict is {"values": {...}, "bids": {...}}."""
    history = []
    players = sorted(rounds[0]["values"].keys()) if rounds else []
    totals: dict[str, float] = {p: 0.0 for p in players}
    for i, r in enumerate(rounds, start=1):
        values, bids = r["values"], r["bids"]
        ranked = sorted(players, key=lambda p: bids[p], reverse=True)
        top_bid = bids[ranked[0]]
        winner = next(p for p in ranked if bids[p] == top_bid)
        price = bids[ranked[1]]
        payoffs = {p: (round(values[p] - price, 2) if p == winner else 0.0) for p in players}
        for p in players:
            totals[p] = round(totals[p] + payoffs[p], 2)
        history.append({
            "round":        i,
            "values":       dict(values),
            "actions":      dict(bids),
            "winner":       winner,
            "price":        price,
            "payoffs":      dict(payoffs),
            "total_scores": dict(totals),
        })
    return history, totals


def _va_match(*rounds: dict) -> Match:
    history, _ = make_history(*rounds)
    moves = []
    for entry in history:
        for p, bid in entry["actions"].items():
            moves.append(Move(agent_id=p, round_number=entry["round"] - 1, action=bid, payoff=entry["payoffs"][p]))
    agent_ids = sorted(rounds[0]["values"].keys()) if rounds else []
    return Match(match_id="test", game_type="vickrey_auction", agent_ids=agent_ids, moves=moves)


# ─── compute ─────────────────────────────────────────────────────────────────

class TestCompute:
    def test_truthful_bidder_has_zero_shading_and_full_truthful_rate(self):
        history, totals = make_history(
            {"values": {"A": 50.0, "B": 30.0}, "bids": {"A": 50.0, "B": 30.0}},
            {"values": {"A": 20.0, "B": 90.0}, "bids": {"A": 20.0, "B": 90.0}},
        )
        m = VickreyAuctionMetrics().compute(history, totals)
        assert m["bid_shading"]["A"] == pytest.approx(0.0)
        assert m["bid_shading"]["B"] == pytest.approx(0.0)
        assert m["truthful_rate"]["A"] == pytest.approx(1.0)
        assert m["truthful_rate"]["B"] == pytest.approx(1.0)

    def test_shading_and_overbidding_signs(self):
        history, totals = make_history(
            {"values": {"A": 100.0, "B": 50.0}, "bids": {"A": 80.0, "B": 70.0}},
        )
        m = VickreyAuctionMetrics().compute(history, totals)
        assert m["bid_shading"]["A"] == pytest.approx(-20.0)  # underbid
        assert m["bid_shading"]["B"] == pytest.approx(20.0)   # overbid

    def test_win_rate(self):
        history, totals = make_history(
            {"values": {"A": 90.0, "B": 10.0}, "bids": {"A": 90.0, "B": 10.0}},
            {"values": {"A": 10.0, "B": 90.0}, "bids": {"A": 10.0, "B": 90.0}},
        )
        m = VickreyAuctionMetrics().compute(history, totals)
        assert m["win_rate"]["A"] == pytest.approx(0.5)
        assert m["win_rate"]["B"] == pytest.approx(0.5)

    def test_avg_surplus_conditional_on_winning(self):
        history, totals = make_history(
            {"values": {"A": 90.0, "B": 10.0}, "bids": {"A": 90.0, "B": 10.0}},
        )
        m = VickreyAuctionMetrics().compute(history, totals)
        assert m["avg_surplus"]["A"] == pytest.approx(80.0)  # 90 - 10
        assert m["avg_surplus"]["B"] == pytest.approx(0.0)   # never won

    def test_truthful_tolerance_respected(self):
        history, totals = make_history(
            {"values": {"A": 50.0, "B": 10.0}, "bids": {"A": 50.4, "B": 10.0}},
        )
        m = VickreyAuctionMetrics(truthful_tolerance=0.5).compute(history, totals)
        assert m["truthful_rate"]["A"] == pytest.approx(1.0)
        m_strict = VickreyAuctionMetrics(truthful_tolerance=0.1).compute(history, totals)
        assert m_strict["truthful_rate"]["A"] == pytest.approx(0.0)

    def test_empty_history(self):
        m = VickreyAuctionMetrics().compute([], {"A": 0.0, "B": 0.0})
        assert m["bid_shading"]["A"] == pytest.approx(0.0)
        assert m["win_rate"]["A"] == pytest.approx(0.0)
        assert m["avg_surplus"]["A"] == pytest.approx(0.0)


# ─── compute_joint ────────────────────────────────────────────────────────────

class TestComputeJoint:
    def test_returns_empty(self):
        match = _va_match({"values": {"A": 50.0, "B": 30.0}, "bids": {"A": 50.0, "B": 30.0}})
        assert VickreyAuctionMetrics().compute_joint(match, {}) == {}


# ─── compute_agent ────────────────────────────────────────────────────────────

class TestComputeAgent:
    def test_avg_bid_and_win_rate(self):
        match = _va_match(
            {"values": {"A": 90.0, "B": 10.0}, "bids": {"A": 90.0, "B": 10.0}},
            {"values": {"A": 10.0, "B": 90.0}, "bids": {"A": 10.0, "B": 90.0}},
        )
        r = VickreyAuctionMetrics().compute_agent(match, "A", {}, {})
        assert r["va"]["avg_bid"] == pytest.approx(50.0)
        assert r["va"]["win_rate"] == pytest.approx(0.5)
        assert r["va"]["first_bid"] == pytest.approx(90.0)

    def test_empty_actions(self):
        match = Match(match_id="t", game_type="vickrey_auction", agent_ids=["A", "B"], moves=[])
        r = VickreyAuctionMetrics().compute_agent(match, "A", {}, {})
        assert r == {}
