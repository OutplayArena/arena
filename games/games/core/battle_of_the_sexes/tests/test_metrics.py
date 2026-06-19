import pytest
from games.core.battle_of_the_sexes.metrics import BoSMetrics
from outplaylabs_arena.metrics.contracts import Match, Move


def make_history(*outcomes: str) -> tuple[list[dict], dict[str, float]]:
    # Payoffs: AA=(3,2), BB=(2,3), AB=(0,0), BA=(0,0)
    PAYOFFS = {"AA": (3.0, 2.0), "BB": (2.0, 3.0), "AB": (0.0, 0.0), "BA": (0.0, 0.0)}
    history = []
    totals: dict[str, float] = {"A": 0.0, "B": 0.0}
    for i, outcome in enumerate(outcomes, start=1):
        pa, pb = PAYOFFS[outcome]
        totals["A"] += pa
        totals["B"] += pb
        a_act = "opera" if outcome[0] == "A" else "football"
        b_act = "opera" if outcome[1] == "A" else "football"
        history.append({
            "round":       i,
            "actions":     {"A": a_act, "B": b_act},
            "outcome":     outcome,
            "coordinated": outcome in ("AA", "BB"),
            "payoffs":     {"A": pa, "B": pb},
        })
    return history, totals


def _bos_match(*outcomes: str) -> Match:
    PAYOFFS = {"AA": (3.0, 2.0), "BB": (2.0, 3.0), "AB": (0.0, 0.0), "BA": (0.0, 0.0)}
    moves = []
    for i, outcome in enumerate(outcomes):
        pa, pb = PAYOFFS[outcome]
        a_act = "opera" if outcome[0] == "A" else "football"
        b_act = "opera" if outcome[1] == "A" else "football"
        moves.append(Move(agent_id="A", round_number=i, action=a_act, payoff=pa))
        moves.append(Move(agent_id="B", round_number=i, action=b_act, payoff=pb))
    return Match(match_id="test", game_type="battle_of_the_sexes", agent_ids=["A", "B"], moves=moves)


# ─── compute ─────────────────────────────────────────────────────────────────

class TestCompute:
    def test_all_aa_coordinated(self):
        history, totals = make_history("AA", "AA", "AA")
        m = BoSMetrics().compute(history, totals)
        assert m["coordination_rate"] == pytest.approx(1.0)
        assert m["outcome_counts"]["AA"] == 3
        assert m["outcome_counts"]["BB"] == 0
        assert m["total_payoff"]["A"] == pytest.approx(9.0)
        assert m["average_payoff"]["A"] == pytest.approx(3.0)

    def test_all_bb_coordinated(self):
        history, totals = make_history("BB", "BB")
        m = BoSMetrics().compute(history, totals)
        assert m["coordination_rate"] == pytest.approx(1.0)
        assert m["outcome_counts"]["BB"] == 2
        assert m["average_payoff"]["B"] == pytest.approx(3.0)

    def test_all_miscoordinated(self):
        history, totals = make_history("AB", "AB", "BA")
        m = BoSMetrics().compute(history, totals)
        assert m["coordination_rate"] == pytest.approx(0.0)
        assert m["total_payoff"]["A"] == pytest.approx(0.0)

    def test_mixed(self):
        history, totals = make_history("AA", "BB", "AB", "BA")
        m = BoSMetrics().compute(history, totals)
        assert m["coordination_rate"] == pytest.approx(0.5)
        assert m["outcome_counts"]["AA"] == 1
        assert m["outcome_counts"]["BB"] == 1
        assert m["outcome_counts"]["AB"] == 1
        assert m["outcome_counts"]["BA"] == 1

    def test_empty_history(self):
        m = BoSMetrics().compute([], {"A": 0.0, "B": 0.0})
        assert m["coordination_rate"] == pytest.approx(0.0)


# ─── compute_joint ────────────────────────────────────────────────────────────

class TestComputeJoint:
    def test_all_aa(self):
        match = _bos_match("AA", "AA", "AA")
        j = BoSMetrics().compute_joint(match, {"option_a_label": "opera"})
        assert j["bos_coordination_rate"] == pytest.approx(1.0)
        assert j["bos_a_preferred_rate"] == pytest.approx(1.0)
        assert j["bos_b_preferred_rate"] == pytest.approx(0.0)
        assert j["equilibrium_selection_rate"] == pytest.approx(1.0)

    def test_all_bb(self):
        match = _bos_match("BB", "BB")
        j = BoSMetrics().compute_joint(match, {"option_a_label": "opera"})
        assert j["bos_coordination_rate"] == pytest.approx(1.0)
        assert j["bos_b_preferred_rate"] == pytest.approx(1.0)

    def test_all_miscoordinated(self):
        match = _bos_match("AB", "AB", "AB")
        j = BoSMetrics().compute_joint(match, {"option_a_label": "opera"})
        assert j["bos_coordination_rate"] == pytest.approx(0.0)

    def test_mixed_coordination(self):
        match = _bos_match("AA", "BB", "AB", "AB")
        j = BoSMetrics().compute_joint(match, {"option_a_label": "opera"})
        assert j["bos_coordination_rate"] == pytest.approx(0.5)


# ─── compute_agent ────────────────────────────────────────────────────────────

class TestComputeAgent:
    def test_always_opera_player_a(self):
        match = _bos_match("AA", "AA", "AB")
        r = BoSMetrics().compute_agent(match, "A",
                                       {"option_a_label": "opera", "option_b_label": "football"}, {})
        assert r["bos"]["option_a_rate"] == pytest.approx(1.0)
        assert r["bos"]["option_b_rate"] == pytest.approx(0.0)
        assert r["bos"]["first_move"] == "opera"

    def test_always_football_player_b(self):
        match = _bos_match("BB", "BB")
        r = BoSMetrics().compute_agent(match, "B",
                                       {"option_a_label": "opera", "option_b_label": "football"}, {})
        assert r["bos"]["option_b_rate"] == pytest.approx(1.0)

    def test_empty_actions(self):
        match = Match(match_id="t", game_type="battle_of_the_sexes", agent_ids=["A", "B"], moves=[])
        r = BoSMetrics().compute_agent(match, "A", {}, {})
        assert r == {}
