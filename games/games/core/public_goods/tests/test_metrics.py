import pytest
from games.core.public_goods.metrics import PublicGoodsMetrics
from arena.metrics.contracts import Match, Move


def make_history(*rounds: dict[str, float],
                 endowment=10.0, multiplier=2.0, n_players=4) -> tuple[list[dict], dict[str, float]]:
    players = [chr(ord("A") + i) for i in range(n_players)]
    history = []
    totals: dict[str, float] = {p: 0.0 for p in players}
    for i, contribs in enumerate(rounds, start=1):
        pool = sum(contribs.values())
        total_pool = pool * multiplier
        share = total_pool / n_players
        round_payoffs = {p: (endowment - contribs.get(p, 0.0)) + share for p in players}
        for p in players:
            totals[p] += round_payoffs[p]
        history.append({
            "round":         i,
            "phase":         "contribution",
            "contributions": dict(contribs),
            "pool":          pool,
            "total_pool":    total_pool,
            "share":         share,
            "round_payoffs": round_payoffs,
            "total_scores":  dict(totals),
        })
    return history, totals


def _pgg_match(*rounds: dict[str, float]) -> Match:
    moves = []
    r_idx = 0
    for contribs in rounds:
        for player, amount in contribs.items():
            moves.append(Move(agent_id=player, round_number=r_idx, action=float(amount), payoff=0.0))
        r_idx += 1
    return Match(match_id="test", game_type="public_goods",
                 agent_ids=list(rounds[0].keys()) if rounds else ["A", "B", "C", "D"],
                 moves=moves)


# ─── compute ─────────────────────────────────────────────────────────────────

class TestCompute:
    def test_all_contribute_max(self):
        history, totals = make_history(
            {"A": 10.0, "B": 10.0, "C": 10.0, "D": 10.0},
            {"A": 10.0, "B": 10.0, "C": 10.0, "D": 10.0},
        )
        m = PublicGoodsMetrics().compute(history, totals)
        assert m["avg_contribution"]["A"] == pytest.approx(10.0)
        assert m["avg_contribution"]["B"] == pytest.approx(10.0)
        assert m["free_rider_count"] == 0
        assert m["avg_pool"] == pytest.approx(40.0)

    def test_all_free_ride(self):
        history, totals = make_history(
            {"A": 0.0, "B": 0.0, "C": 0.0, "D": 0.0},
        )
        m = PublicGoodsMetrics().compute(history, totals)
        assert m["avg_contribution"]["A"] == pytest.approx(0.0)
        assert m["free_rider_count"] == 4  # all free ride
        assert m["avg_pool"] == pytest.approx(0.0)

    def test_asymmetric_contributions(self):
        history, totals = make_history(
            {"A": 10.0, "B": 0.0, "C": 0.0, "D": 0.0},
        )
        m = PublicGoodsMetrics().compute(history, totals)
        assert m["avg_contribution"]["A"] == pytest.approx(10.0)
        assert m["avg_contribution"]["B"] == pytest.approx(0.0)
        # B, C, D free ride
        assert m["free_rider_count"] >= 3

    def test_empty_history(self):
        m = PublicGoodsMetrics().compute([], {"A": 0.0, "B": 0.0, "C": 0.0, "D": 0.0})
        assert "total_payoff" in m

    def test_contribution_rate(self):
        history, totals = make_history(
            {"A": 5.0, "B": 10.0, "C": 0.0, "D": 5.0},
        )
        m = PublicGoodsMetrics().compute(history, totals)
        # max_contrib = 10
        assert m["contribution_rate"]["B"] == pytest.approx(1.0)
        assert m["contribution_rate"]["C"] == pytest.approx(0.0)
        assert m["contribution_rate"]["A"] == pytest.approx(0.5)

    def test_average_payoff(self):
        history, totals = make_history(
            {"A": 10.0, "B": 10.0, "C": 10.0, "D": 10.0},
            {"A": 10.0, "B": 10.0, "C": 10.0, "D": 10.0},
        )
        m = PublicGoodsMetrics().compute(history, totals)
        # 2 rounds, each round payoff = 20, so avg = 20
        assert m["average_payoff"]["A"] == pytest.approx(20.0)


# ─── compute_joint ────────────────────────────────────────────────────────────

class TestComputeJoint:
    def test_full_contribution_efficiency(self):
        match = _pgg_match(
            {"A": 10.0, "B": 10.0, "C": 10.0, "D": 10.0},
            {"A": 10.0, "B": 10.0, "C": 10.0, "D": 10.0},
        )
        j = PublicGoodsMetrics().compute_joint(match, {"endowment": 10.0, "multiplier": 2.0})
        # total per round = 40, max = 40 → efficiency = 1.0
        assert j["pgg_contribution_efficiency"] == pytest.approx(1.0)

    def test_zero_contribution_efficiency(self):
        match = _pgg_match(
            {"A": 0.0, "B": 0.0, "C": 0.0, "D": 0.0},
        )
        j = PublicGoodsMetrics().compute_joint(match, {"endowment": 10.0, "multiplier": 2.0})
        assert j["pgg_contribution_efficiency"] == pytest.approx(0.0)

    def test_price_of_anarchy(self):
        match = _pgg_match({"A": 5.0, "B": 5.0, "C": 5.0, "D": 5.0})
        # pga = nash_welfare / pareto_welfare = (10*4) / (10*2*4) = 40/80 = 0.5
        j = PublicGoodsMetrics().compute_joint(match, {"endowment": 10.0, "multiplier": 2.0})
        assert j["pgg_price_of_anarchy"] == pytest.approx(0.5)


# ─── compute_agent ────────────────────────────────────────────────────────────

class TestComputeAgent:
    def test_full_contributor(self):
        match = _pgg_match(
            {"A": 10.0, "B": 5.0},
            {"A": 10.0, "B": 5.0},
        )
        r = PublicGoodsMetrics().compute_agent(match, "A", {"endowment": 10.0}, {})
        assert r["pgg"]["avg_contribution"] == pytest.approx(10.0)
        assert r["pgg"]["contribution_rate"] == pytest.approx(1.0)
        assert r["pgg"]["free_rider"] is False

    def test_free_rider(self):
        match = _pgg_match(
            {"A": 0.0, "B": 5.0},
            {"A": 0.0, "B": 5.0},
        )
        r = PublicGoodsMetrics().compute_agent(match, "A", {"endowment": 10.0}, {})
        assert r["pgg"]["contribution_rate"] == pytest.approx(0.0)
        assert r["pgg"]["free_rider"] is True

    def test_empty_actions(self):
        match = Match(match_id="t", game_type="public_goods", agent_ids=["A", "B"], moves=[])
        r = PublicGoodsMetrics().compute_agent(match, "A", {}, {})
        assert r == {}

    def test_contribution_decay(self):
        # First half contributes more than second half
        match = _pgg_match(
            {"A": 10.0, "B": 5.0},
            {"A": 10.0, "B": 5.0},
            {"A": 0.0, "B": 5.0},
            {"A": 0.0, "B": 5.0},
        )
        r = PublicGoodsMetrics().compute_agent(match, "A", {"endowment": 10.0}, {})
        assert r["pgg"]["contribution_decay"] > 0
