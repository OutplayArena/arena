import pytest
from games.core.cournot_duopoly.metrics import CournotMetrics
from arena.metrics.contracts import Match, Move


def make_history(*rounds: tuple[float, float],
                 demand_a=120.0, demand_b=1.0, cost=0.0) -> tuple[list[dict], dict[str, float]]:
    history = []
    totals: dict[str, float] = {"A": 0.0, "B": 0.0}
    for i, (qa, qb) in enumerate(rounds, start=1):
        total_q = qa + qb
        price = max(0.0, demand_a - demand_b * total_q)
        profit_a = (price - cost) * qa
        profit_b = (price - cost) * qb
        totals["A"] += profit_a
        totals["B"] += profit_b
        history.append({
            "round":           i,
            "quantities":      {"A": qa, "B": qb},
            "total_quantity":  total_q,
            "price":           price,
            "payoffs":         {"A": profit_a, "B": profit_b},
            "total_scores":    dict(totals),
        })
    return history, totals


def _cournot_match(*rounds: tuple[float, float]) -> Match:
    moves = []
    for i, (qa, qb) in enumerate(rounds):
        price = max(0.0, 120.0 - (qa + qb))
        moves.append(Move(agent_id="A", round_number=i, action=qa, payoff=price * qa))
        moves.append(Move(agent_id="B", round_number=i, action=qb, payoff=price * qb))
    return Match(match_id="test", game_type="cournot_duopoly", agent_ids=["A", "B"], moves=moves)


# ─── compute ─────────────────────────────────────────────────────────────────

class TestCompute:
    def test_nash_equilibrium_quantities(self):
        # Both play 40: price=40, profit=1600 each per round
        history, totals = make_history((40.0, 40.0), (40.0, 40.0))
        m = CournotMetrics().compute(history, totals, nash_q=40.0, collusive_q=30.0)
        assert m["avg_quantity"]["A"] == pytest.approx(40.0)
        assert m["avg_quantity"]["B"] == pytest.approx(40.0)
        assert m["avg_price"] == pytest.approx(40.0)
        assert m["average_payoff"]["A"] == pytest.approx(1600.0)

    def test_collusive_quantities(self):
        # Both play 30: price=60, profit=1800 each
        history, totals = make_history((30.0, 30.0))
        m = CournotMetrics().compute(history, totals, nash_q=40.0, collusive_q=30.0)
        assert m["avg_quantity"]["A"] == pytest.approx(30.0)
        assert m["avg_price"] == pytest.approx(60.0)

    def test_empty_history(self):
        m = CournotMetrics().compute([], {"A": 0.0, "B": 0.0}, nash_q=40.0, collusive_q=30.0)
        assert "total_payoff" in m

    def test_avg_total_quantity(self):
        history, totals = make_history((40.0, 40.0), (60.0, 20.0))
        m = CournotMetrics().compute(history, totals, nash_q=40.0, collusive_q=30.0)
        assert m["avg_total_quantity"] == pytest.approx(80.0)

    def test_total_payoff_present(self):
        history, totals = make_history((40.0, 40.0))
        m = CournotMetrics().compute(history, totals, nash_q=40.0, collusive_q=30.0)
        assert "total_payoff" in m
        assert m["total_payoff"]["A"] == pytest.approx(1600.0)


# ─── compute_joint ────────────────────────────────────────────────────────────

class TestComputeJoint:
    def test_collusion_index_at_nash(self):
        # At Nash (40,40): no collusion → collusion_index ≈ 0
        match = _cournot_match((40.0, 40.0), (40.0, 40.0), (40.0, 40.0))
        j = CournotMetrics().compute_joint(match, {"demand_a": 120.0, "demand_b": 1.0, "cost_per_unit": 0.0})
        assert j["cd_collusion_index"] == pytest.approx(0.0)

    def test_collusion_index_at_collusive(self):
        # At collusive (30,30): max collusion → collusion_index ≈ 1
        match = _cournot_match((30.0, 30.0), (30.0, 30.0))
        j = CournotMetrics().compute_joint(match, {"demand_a": 120.0, "demand_b": 1.0, "cost_per_unit": 0.0})
        assert j["cd_collusion_index"] == pytest.approx(1.0)

    def test_nash_and_collusive_q_reported(self):
        match = _cournot_match((40.0, 40.0))
        j = CournotMetrics().compute_joint(match, {"demand_a": 120.0, "demand_b": 1.0, "cost_per_unit": 0.0})
        assert j["cd_nash_quantity"] == pytest.approx(40.0)
        assert j["cd_collusive_quantity"] == pytest.approx(30.0)


# ─── compute_agent ────────────────────────────────────────────────────────────

class TestComputeAgent:
    def test_nash_player(self):
        match = _cournot_match((40.0, 40.0), (40.0, 40.0), (40.0, 40.0))
        r = CournotMetrics().compute_agent(match, "A",
                                           {"demand_a": 120.0, "demand_b": 1.0, "cost_per_unit": 0.0}, {})
        assert r["cd"]["avg_quantity"] == pytest.approx(40.0)
        assert r["cd"]["nash_deviation"] == pytest.approx(0.0)

    def test_collusive_player(self):
        match = _cournot_match((30.0, 30.0), (30.0, 30.0))
        r = CournotMetrics().compute_agent(match, "A",
                                           {"demand_a": 120.0, "demand_b": 1.0, "cost_per_unit": 0.0}, {})
        assert r["cd"]["avg_quantity"] == pytest.approx(30.0)
        assert r["cd"]["collusion_rate"] == pytest.approx(1.0)

    def test_empty_actions(self):
        match = Match(match_id="t", game_type="cournot_duopoly", agent_ids=["A", "B"], moves=[])
        r = CournotMetrics().compute_agent(match, "A", {}, {})
        assert r == {}
