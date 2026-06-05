import pytest
from games.core.prisonersdilemma.metrics import PDMetrics, _outcome_counts


def make_history(*outcomes: str, R=3.0, T=5.0, P=1.0, S=0.0) -> tuple[list[dict], dict[str, float]]:
    PAYOFFS = {"CC": (R, R), "CD": (S, T), "DC": (T, S), "DD": (P, P)}
    history = []
    totals: dict[str, float] = {"A": 0.0, "B": 0.0}
    for i, outcome in enumerate(outcomes, start=1):
        pa, pb = PAYOFFS[outcome]
        totals["A"] += pa
        totals["B"] += pb
        a_action = "cooperate" if outcome[0] == "C" else "defect"
        b_action = "cooperate" if outcome[1] == "C" else "defect"
        history.append({
            "round":        i,
            "actions":      {"A": a_action, "B": b_action},
            "outcome":      outcome,
            "payoffs":      {"A": pa, "B": pb},
            "total_scores": dict(totals),
        })
    return history, totals


class TestOutcomeCounts:
    def test_counts(self):
        history, _ = make_history("CC", "CD", "DC", "DD", "CC")
        counts = _outcome_counts(history)
        assert counts == {"CC": 2, "CD": 1, "DC": 1, "DD": 1}

    def test_empty(self):
        counts = _outcome_counts([])
        assert all(v == 0 for v in counts.values())


class TestComputeBasics:
    def test_all_cc(self):
        history, totals = make_history("CC", "CC", "CC")
        m = PDMetrics().compute(history, totals)
        assert m["cooperation_rate"]["A"] == pytest.approx(1.0)
        assert m["cooperation_rate"]["B"] == pytest.approx(1.0)
        assert m["mutual_cooperation_rate"] == pytest.approx(1.0)
        assert m["mutual_defection_rate"] == pytest.approx(0.0)
        assert m["total_payoff"]["A"] == pytest.approx(9.0)
        assert m["average_payoff"]["A"] == pytest.approx(3.0)

    def test_all_dd(self):
        history, totals = make_history("DD", "DD")
        m = PDMetrics().compute(history, totals)
        assert m["cooperation_rate"]["A"] == pytest.approx(0.0)
        assert m["mutual_defection_rate"] == pytest.approx(1.0)
        assert m["total_payoff"]["A"] == pytest.approx(2.0)

    def test_mixed(self):
        history, totals = make_history("CC", "CD", "DC", "DD")
        m = PDMetrics().compute(history, totals)
        assert m["cooperation_rate"]["A"] == pytest.approx(0.5)
        assert m["cooperation_rate"]["B"] == pytest.approx(0.5)
        assert m["mutual_cooperation_rate"] == pytest.approx(0.25)
        assert m["mutual_defection_rate"] == pytest.approx(0.25)

    def test_empty_history(self):
        m = PDMetrics().compute([], {"A": 0.0, "B": 0.0})
        assert m["cooperation_rate"]["A"] == pytest.approx(0.0)
        assert m["mutual_cooperation_rate"] == pytest.approx(0.0)

    def test_outcome_counts_present(self):
        history, totals = make_history("CC", "DD", "CD")
        m = PDMetrics().compute(history, totals)
        assert "outcome_counts" in m
        assert m["outcome_counts"]["CC"] == 1
        assert m["outcome_counts"]["DD"] == 1
        assert m["outcome_counts"]["CD"] == 1

    def test_average_payoff_cd(self):
        history, totals = make_history("CD")
        m = PDMetrics().compute(history, totals)
        assert m["average_payoff"]["A"] == pytest.approx(0.0)
        assert m["average_payoff"]["B"] == pytest.approx(5.0)
