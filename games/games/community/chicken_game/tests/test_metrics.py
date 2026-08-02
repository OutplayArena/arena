import pytest
from arena.metrics.contracts import Match, Move

from games.community.chicken_game.metrics import (
    ChickenGameMetrics,
    _alternation_index,
    _mixed_ne_dare_probability,
    _outcome_counts,
)


def make_history(*outcomes: str,
                  win=1.0, tie=0.0, lose=-1.0, crash=-10.0) -> tuple[list[dict], dict[str, float]]:
    PAYOFFS = {"DD": (crash, crash), "DS": (win, lose), "SD": (lose, win), "SS": (tie, tie)}
    history = []
    totals: dict[str, float] = {"A": 0.0, "B": 0.0}
    for i, outcome in enumerate(outcomes, start=1):
        pa, pb = PAYOFFS[outcome]
        totals["A"] += pa
        totals["B"] += pb
        a_action = "dare" if outcome[0] == "D" else "swerve"
        b_action = "dare" if outcome[1] == "D" else "swerve"
        history.append({
            "round":   i,
            "actions": {"A": a_action, "B": b_action},
            "outcome": outcome,
            "payoffs": {"A": pa, "B": pb},
        })
    return history, totals


def _cg_match(*outcomes: str) -> Match:
    PAYOFFS = {"DD": (-10.0, -10.0), "DS": (1.0, -1.0), "SD": (-1.0, 1.0), "SS": (0.0, 0.0)}
    moves = []
    for i, outcome in enumerate(outcomes):
        pa, pb = PAYOFFS[outcome]
        a_act = "dare" if outcome[0] == "D" else "swerve"
        b_act = "dare" if outcome[1] == "D" else "swerve"
        moves.append(Move(agent_id="A", round_number=i, action=a_act, payoff=pa))
        moves.append(Move(agent_id="B", round_number=i, action=b_act, payoff=pb))
    return Match(match_id="test", game_type="chicken_game", agent_ids=["A", "B"], moves=moves)


# ─── _outcome_counts ─────────────────────────────────────────────────────────

class TestOutcomeCounts:
    def test_counts(self):
        history, _ = make_history("DD", "DS", "SD", "SS", "DD")
        counts = _outcome_counts(history)
        assert counts == {"DD": 2, "DS": 1, "SD": 1, "SS": 1}

    def test_empty(self):
        counts = _outcome_counts([])
        assert all(v == 0 for v in counts.values())


# ─── _mixed_ne_dare_probability ───────────────────────────────────────────────

class TestMixedNeDareProbability:
    def test_default_payoffs(self):
        q = _mixed_ne_dare_probability(1.0, 0.0, -1.0, -10.0)
        assert q == pytest.approx(0.1)

    def test_symmetric_payoffs_give_half(self):
        q = _mixed_ne_dare_probability(1.0, 0.0, -1.0, -2.0)
        assert q == pytest.approx(0.5)

    def test_zero_denominator_defaults_to_half(self):
        q = _mixed_ne_dare_probability(1.0, 1.0, -1.0, -1.0)
        assert q == pytest.approx(0.5)


# ─── _alternation_index ────────────────────────────────────────────────────────

class TestAlternationIndex:
    def test_perfect_alternation(self):
        history, _ = make_history("DS", "SD", "DS", "SD")
        assert _alternation_index(history) == pytest.approx(1.0)

    def test_no_alternation(self):
        history, _ = make_history("DS", "DS", "DS")
        assert _alternation_index(history) == pytest.approx(0.0)

    def test_ignores_symmetric_outcomes(self):
        history, _ = make_history("SS", "DD", "DS", "SD")
        assert _alternation_index(history) == pytest.approx(1.0)

    def test_insufficient_data_returns_zero(self):
        history, _ = make_history("DS")
        assert _alternation_index(history) == pytest.approx(0.0)
        assert _alternation_index([]) == pytest.approx(0.0)


# ─── compute ─────────────────────────────────────────────────────────────────

class TestCompute:
    def test_all_dd(self):
        history, totals = make_history("DD", "DD")
        m = ChickenGameMetrics().compute(history, totals)
        assert m["dare_rate"]["A"] == pytest.approx(1.0)
        assert m["dare_rate"]["B"] == pytest.approx(1.0)
        assert m["crash_rate"] == pytest.approx(1.0)
        assert m["yield_rate"] == pytest.approx(0.0)
        assert m["total_payoff"]["A"] == pytest.approx(-20.0)

    def test_all_ss(self):
        history, totals = make_history("SS", "SS", "SS")
        m = ChickenGameMetrics().compute(history, totals)
        assert m["dare_rate"]["A"] == pytest.approx(0.0)
        assert m["yield_rate"] == pytest.approx(1.0)
        assert m["crash_rate"] == pytest.approx(0.0)

    def test_exploit_rate(self):
        history, totals = make_history("DS", "DS", "SD")
        m = ChickenGameMetrics().compute(history, totals)
        assert m["exploit_rate"]["A"] == pytest.approx(2 / 3)
        assert m["exploit_rate"]["B"] == pytest.approx(1 / 3)

    def test_mixed_ne_gap_uses_configured_payoffs(self):
        history, totals = make_history("DD", "SS", "SS", "SS", "SS", "SS", "SS", "SS", "SS", "SS")
        m = ChickenGameMetrics(payoff_win=1.0, payoff_tie=0.0, payoff_lose=-1.0, payoff_crash=-10.0).compute(history, totals)
        assert m["mixed_ne_gap"]["nash_dare_probability"] == pytest.approx(0.1)
        assert m["mixed_ne_gap"]["A"] == pytest.approx(abs(0.1 - 0.1))

    def test_empty_history(self):
        m = ChickenGameMetrics().compute([], {"A": 0.0, "B": 0.0})
        assert m["dare_rate"]["A"] == pytest.approx(0.0)
        assert m["crash_rate"] == pytest.approx(0.0)

    def test_outcome_counts_in_metrics(self):
        history, totals = make_history("DD", "SS", "DS")
        m = ChickenGameMetrics().compute(history, totals)
        assert m["outcome_counts"]["DD"] == 1
        assert m["outcome_counts"]["SS"] == 1
        assert m["outcome_counts"]["DS"] == 1


# ─── compute_joint ────────────────────────────────────────────────────────────

class TestComputeJoint:
    def test_all_dd(self):
        match = _cg_match("DD", "DD", "DD")
        j = ChickenGameMetrics().compute_joint(match, {})
        assert j["cg_crash_rate"] == pytest.approx(1.0)
        assert j["cg_yield_rate"] == pytest.approx(0.0)

    def test_all_ss(self):
        match = _cg_match("SS", "SS")
        j = ChickenGameMetrics().compute_joint(match, {})
        assert j["cg_crash_rate"] == pytest.approx(0.0)
        assert j["cg_yield_rate"] == pytest.approx(1.0)

    def test_nash_dare_probability_from_config(self):
        match = _cg_match("SS")
        j = ChickenGameMetrics().compute_joint(
            match, {"payoff_win": 1.0, "payoff_tie": 0.0, "payoff_lose": -1.0, "payoff_crash": -10.0}
        )
        assert j["cg_nash_dare_probability"] == pytest.approx(0.1)


# ─── compute_agent ────────────────────────────────────────────────────────────

class TestComputeAgent:
    def test_always_dare(self):
        match = _cg_match("DD", "DD", "DD")
        r = ChickenGameMetrics().compute_agent(match, "A", {}, {})
        assert r["cg"]["dare_rate"] == pytest.approx(1.0)
        assert r["cg"]["first_move"] == "dare"

    def test_always_swerve(self):
        match = _cg_match("SS", "SS")
        r = ChickenGameMetrics().compute_agent(match, "A", {}, {})
        assert r["cg"]["dare_rate"] == pytest.approx(0.0)

    def test_empty_actions(self):
        match = Match(match_id="t", game_type="chicken_game", agent_ids=["A", "B"], moves=[])
        r = ChickenGameMetrics().compute_agent(match, "A", {}, {})
        assert r == {}
