import pytest
from games.core.stag_hunt.metrics import StagHuntMetrics, _outcome_counts
from arena.metrics.contracts import Match, Move


def make_history(*outcomes: str,
                 ss=4.0, hh=2.0, sh=0.0) -> tuple[list[dict], dict[str, float]]:
    PAYOFFS = {"SS": (ss, ss), "SH": (sh, hh), "HS": (hh, sh), "HH": (hh, hh)}
    history = []
    totals: dict[str, float] = {"A": 0.0, "B": 0.0}
    for i, outcome in enumerate(outcomes, start=1):
        pa, pb = PAYOFFS[outcome]
        totals["A"] += pa
        totals["B"] += pb
        a_action = "stag" if outcome[0] == "S" else "hare"
        b_action = "stag" if outcome[1] == "S" else "hare"
        history.append({
            "round":   i,
            "actions": {"A": a_action, "B": b_action},
            "outcome": outcome,
            "payoffs": {"A": pa, "B": pb},
        })
    return history, totals


def _sh_match(*outcomes: str) -> Match:
    PAYOFFS = {"SS": (4.0, 4.0), "SH": (0.0, 2.0), "HS": (2.0, 0.0), "HH": (2.0, 2.0)}
    moves = []
    for i, outcome in enumerate(outcomes):
        pa, pb = PAYOFFS[outcome]
        a_act = "stag" if outcome[0] == "S" else "hare"
        b_act = "stag" if outcome[1] == "S" else "hare"
        moves.append(Move(agent_id="A", round_number=i, action=a_act, payoff=pa))
        moves.append(Move(agent_id="B", round_number=i, action=b_act, payoff=pb))
    return Match(match_id="test", game_type="stag_hunt", agent_ids=["A", "B"], moves=moves)


# ─── _outcome_counts ─────────────────────────────────────────────────────────

class TestOutcomeCounts:
    def test_counts(self):
        history, _ = make_history("SS", "SH", "HS", "HH", "SS")
        counts = _outcome_counts(history)
        assert counts == {"SS": 2, "SH": 1, "HS": 1, "HH": 1}

    def test_empty(self):
        counts = _outcome_counts([])
        assert all(v == 0 for v in counts.values())


# ─── compute ─────────────────────────────────────────────────────────────────

class TestCompute:
    def test_all_ss(self):
        history, totals = make_history("SS", "SS", "SS")
        m = StagHuntMetrics().compute(history, totals)
        assert m["stag_rate"]["A"] == pytest.approx(1.0)
        assert m["stag_rate"]["B"] == pytest.approx(1.0)
        assert m["mutual_stag_rate"] == pytest.approx(1.0)
        assert m["mutual_hare_rate"] == pytest.approx(0.0)
        assert m["total_payoff"]["A"] == pytest.approx(12.0)
        assert m["average_payoff"]["A"] == pytest.approx(4.0)

    def test_all_hh(self):
        history, totals = make_history("HH", "HH")
        m = StagHuntMetrics().compute(history, totals)
        assert m["stag_rate"]["A"] == pytest.approx(0.0)
        assert m["mutual_hare_rate"] == pytest.approx(1.0)
        assert m["total_payoff"]["A"] == pytest.approx(4.0)

    def test_mixed(self):
        history, totals = make_history("SS", "SH", "HS", "HH")
        m = StagHuntMetrics().compute(history, totals)
        assert m["stag_rate"]["A"] == pytest.approx(0.5)
        assert m["stag_rate"]["B"] == pytest.approx(0.5)
        assert m["mutual_stag_rate"] == pytest.approx(0.25)
        assert m["mutual_hare_rate"] == pytest.approx(0.25)

    def test_empty_history(self):
        m = StagHuntMetrics().compute([], {"A": 0.0, "B": 0.0})
        assert m["stag_rate"]["A"] == pytest.approx(0.0)
        assert m["mutual_stag_rate"] == pytest.approx(0.0)

    def test_outcome_counts_in_metrics(self):
        history, totals = make_history("SS", "HH", "SH")
        m = StagHuntMetrics().compute(history, totals)
        assert "outcome_counts" in m
        assert m["outcome_counts"]["SS"] == 1
        assert m["outcome_counts"]["HH"] == 1
        assert m["outcome_counts"]["SH"] == 1


# ─── compute_joint ────────────────────────────────────────────────────────────

class TestComputeJoint:
    def test_all_ss(self):
        match = _sh_match("SS", "SS", "SS")
        j = StagHuntMetrics().compute_joint(match, {"payoff_stag_stag": 4.0, "payoff_hare_hare": 2.0})
        assert j["sh_mutual_stag_rate"] == pytest.approx(1.0)
        assert j["sh_mutual_hare_rate"] == pytest.approx(0.0)
        assert j["equilibrium_selection_rate"] == pytest.approx(1.0)

    def test_all_hh(self):
        match = _sh_match("HH", "HH", "HH")
        j = StagHuntMetrics().compute_joint(match, {})
        assert j["sh_mutual_stag_rate"] == pytest.approx(0.0)
        assert j["sh_mutual_hare_rate"] == pytest.approx(1.0)

    def test_price_of_risk(self):
        # hare_welfare / pareto_welfare = (2*2) / (4*2) = 0.5
        j = StagHuntMetrics().compute_joint(
            _sh_match("SS"),
            {"payoff_stag_stag": 4.0, "payoff_hare_hare": 2.0}
        )
        assert j["sh_price_of_risk"] == pytest.approx(0.5)


# ─── compute_agent ────────────────────────────────────────────────────────────

class TestComputeAgent:
    def test_always_stag(self):
        match = _sh_match("SS", "SS", "SS")
        r = StagHuntMetrics().compute_agent(match, "A", {}, {})
        assert r["sh"]["stag_rate"] == pytest.approx(1.0)
        assert r["sh"]["first_move"] == "stag"

    def test_always_hare(self):
        match = _sh_match("HH", "HH")
        r = StagHuntMetrics().compute_agent(match, "A", {}, {})
        assert r["sh"]["stag_rate"] == pytest.approx(0.0)

    def test_empty_actions(self):
        match = Match(match_id="t", game_type="stag_hunt", agent_ids=["A", "B"], moves=[])
        r = StagHuntMetrics().compute_agent(match, "A", {}, {})
        assert r == {}
