import pytest
from games.core.ultimatum.metrics import UltimatumMetrics
from outplaylabs_arena.metrics.contracts import Match, Move


def make_history(*rounds: tuple[float, str],
                 total=100.0) -> tuple[list[dict], dict[str, float]]:
    """rounds: (offer_amount, 'accept'|'reject')"""
    history = []
    totals: dict[str, float] = {"A": 0.0, "B": 0.0}
    for i, (offer, resp) in enumerate(rounds, start=1):
        accepted = resp == "accept"
        fraction = offer / total
        if accepted:
            pa, pb = total - offer, offer
        else:
            pa, pb = 0.0, 0.0
        totals["A"] += pa
        totals["B"] += pb
        # Alternate proposer: odd rounds A proposes, even rounds B proposes
        proposer = "A" if i % 2 == 1 else "B"
        responder = "B" if proposer == "A" else "A"
        history.append({
            "round":          i,
            "proposer":       proposer,
            "responder":      responder,
            "offer":          offer,
            "offer_fraction": fraction,
            "response":       resp,
            "accepted":       accepted,
            "payoffs":        {proposer: pa, responder: pb},
            "total_scores":   dict(totals),
        })
    return history, totals


def _ultimatum_match(*rounds: tuple[float, str]) -> Match:
    moves = []
    for i, (offer, resp) in enumerate(rounds):
        proposer = "A" if i % 2 == 0 else "B"
        responder = "B" if proposer == "A" else "A"
        moves.append(Move(agent_id=proposer, round_number=i, action=offer, payoff=0.0))
        moves.append(Move(agent_id=responder, round_number=i, action=resp, payoff=0.0))
    return Match(match_id="test", game_type="ultimatum", agent_ids=["A", "B"], moves=moves)


# ─── compute ─────────────────────────────────────────────────────────────────

class TestCompute:
    def test_all_accepted_equal_split(self):
        history, totals = make_history((50.0, "accept"), (50.0, "accept"))
        m = UltimatumMetrics().compute(history, totals)
        assert m["acceptance_rate"] == pytest.approx(1.0)
        assert m["avg_offer_fraction"] == pytest.approx(0.5)
        assert m["offer_fairness_index"] == pytest.approx(0.0)  # |0.5-0.5|=0

    def test_all_rejected(self):
        history, totals = make_history((40.0, "reject"), (40.0, "reject"))
        m = UltimatumMetrics().compute(history, totals)
        assert m["acceptance_rate"] == pytest.approx(0.0)
        assert m["total_payoff"]["A"] == pytest.approx(0.0)

    def test_mixed_responses(self):
        history, totals = make_history((50.0, "accept"), (50.0, "reject"))
        m = UltimatumMetrics().compute(history, totals)
        assert m["acceptance_rate"] == pytest.approx(0.5)

    def test_fairness_index_greedy(self):
        # Offer 1/100 → unfairness = |0.01 - 0.5| = 0.49
        history, totals = make_history((1.0, "accept"))
        m = UltimatumMetrics().compute(history, totals)
        assert m["offer_fairness_index"] == pytest.approx(0.49)

    def test_empty_history(self):
        m = UltimatumMetrics().compute([], {"A": 0.0, "B": 0.0})
        assert "total_payoff" in m

    def test_average_payoff(self):
        history, totals = make_history((40.0, "accept"), (40.0, "accept"))
        m = UltimatumMetrics().compute(history, totals)
        # A gets 60+40=100 over 2 rounds... wait A proposes both times alternating
        # Round 1: A proposes 40, B accepts → A=60, B=40
        # Round 2: B proposes 40, A accepts → A=40, B=60
        assert m["average_payoff"]["A"] == pytest.approx(totals["A"] / 2)


# ─── compute_joint ────────────────────────────────────────────────────────────

class TestComputeJoint:
    def test_acceptance_rate(self):
        match = _ultimatum_match((40.0, "accept"), (40.0, "accept"), (40.0, "reject"))
        j = UltimatumMetrics().compute_joint(match, {"total": 100.0})
        assert j["ug_acceptance_rate"] == pytest.approx(2 / 3)

    def test_avg_offer_fraction(self):
        match = _ultimatum_match((50.0, "accept"), (50.0, "accept"))
        j = UltimatumMetrics().compute_joint(match, {"total": 100.0})
        assert j["ug_avg_offer_fraction"] == pytest.approx(0.5)

    def test_fairness_index_equal_split(self):
        match = _ultimatum_match((50.0, "accept"))
        j = UltimatumMetrics().compute_joint(match, {"total": 100.0})
        assert j["ug_offer_fairness_index"] == pytest.approx(0.0)


# ─── compute_agent ────────────────────────────────────────────────────────────

class TestComputeAgent:
    def test_spe_proposer(self):
        # A always proposes minimum (1%), B always accepts
        match = _ultimatum_match((1.0, "accept"), (1.0, "accept"))
        r = UltimatumMetrics().compute_agent(match, "A",
                                             {"total": 100.0, "min_offer": 1.0}, {})
        assert r["ug"]["avg_offer_fraction"] == pytest.approx(0.01)
        assert r["ug"]["backward_induction_proposer"] == pytest.approx(1.0)

    def test_fair_responder(self):
        # B always accepts → high acceptance rate
        match = _ultimatum_match((40.0, "accept"), (40.0, "accept"))
        r = UltimatumMetrics().compute_agent(match, "B",
                                             {"total": 100.0, "min_offer": 1.0}, {})
        assert r["ug"]["avg_acceptance_rate"] == pytest.approx(1.0)

    def test_rejecting_responder(self):
        match = _ultimatum_match((1.0, "reject"), (1.0, "reject"))
        r = UltimatumMetrics().compute_agent(match, "B",
                                             {"total": 100.0, "min_offer": 1.0}, {})
        assert r["ug"]["avg_acceptance_rate"] == pytest.approx(0.0)
        assert r["ug"]["backward_induction_responder"] == pytest.approx(0.0)

    def test_empty_actions(self):
        match = Match(match_id="t", game_type="ultimatum", agent_ids=["A", "B"], moves=[])
        r = UltimatumMetrics().compute_agent(match, "A", {}, {})
        assert r == {} or "ug" in r
