import pytest
from games.core.centipede.metrics import CentipedeMetrics
from nash_arena.metrics.contracts import Match, Move


def make_history(*steps: tuple[str, str]) -> tuple[list[dict], dict[str, float]]:
    """steps: (player, action) pairs. Last step may have payoffs if action == 'take'."""
    history = []
    pot_a, pot_b = 4.0, 1.0
    totals: dict[str, float] = {"A": 0.0, "B": 0.0}
    for i, (player, action) in enumerate(steps, start=1):
        entry: dict = {
            "step":         i,
            "player":       player,
            "action":       action,
            "pot_a_before": pot_a,
            "pot_b_before": pot_b,
        }
        if action == "take":
            if player == "A":
                totals["A"] = pot_a
                totals["B"] = pot_b
            else:
                totals["A"] = pot_b
                totals["B"] = pot_a
            entry["payoffs"] = dict(totals)
            entry["total_scores"] = dict(totals)
        else:
            pot_a *= 2.0
            pot_b *= 2.0
            entry["pot_a_after"] = pot_a
            entry["pot_b_after"] = pot_b
        history.append(entry)
    return history, totals


def _centipede_match(*steps: tuple[str, str]) -> Match:
    moves = []
    for i, (player, action) in enumerate(steps):
        moves.append(Move(agent_id=player, round_number=i, action=action, payoff=0.0))
    return Match(match_id="test", game_type="centipede", agent_ids=["A", "B"], moves=moves)


# ─── compute ─────────────────────────────────────────────────────────────────

class TestCompute:
    def test_take_at_step_1(self):
        history, totals = make_history(("A", "take"))
        m = CentipedeMetrics().compute(history, totals)
        assert m["take_step"] == 1
        assert m["game_ended_early"] is True
        assert m["steps_played"] == 1

    def test_pass_then_take(self):
        history, totals = make_history(("A", "pass"), ("B", "take"))
        m = CentipedeMetrics().compute(history, totals)
        assert m["take_step"] == 2
        assert m["game_ended_early"] is True
        assert m["steps_played"] == 2

    def test_all_pass_forced(self):
        # 6 passes = forced payout (no take)
        steps = [("A", "pass"), ("B", "pass"), ("A", "pass"),
                 ("B", "pass"), ("A", "pass"), ("B", "pass")]
        history, totals = make_history(*steps)
        m = CentipedeMetrics().compute(history, totals)
        assert m["game_ended_early"] is False
        assert m["take_step"] is None
        assert m["steps_played"] == 6

    def test_empty_history(self):
        m = CentipedeMetrics().compute([], {"A": 0.0, "B": 0.0})
        assert m["steps_played"] == 0
        assert m["game_ended_early"] is False
        assert m["take_step"] is None


# ─── compute_joint ────────────────────────────────────────────────────────────

class TestComputeJoint:
    def test_take_at_step_1_low_bi_adherence(self):
        # SPE = take at step 1 → bi_adherence = 1/steps_played
        match = _centipede_match(("A", "take"))
        j = CentipedeMetrics().compute_joint(match, {"max_steps": 6})
        # 1 action played, bi = 1/1 = 1.0
        assert j["cp_backward_induction_adherence"] == pytest.approx(1.0)
        assert j["cp_take_at_step"] == 1

    def test_all_pass_zero_bi_adherence_but_high_cooperation(self):
        match = _centipede_match(
            ("A", "pass"), ("B", "pass"), ("A", "pass"),
            ("B", "pass"), ("A", "pass"), ("B", "pass"),
        )
        j = CentipedeMetrics().compute_joint(match, {"max_steps": 6})
        assert j["cp_cooperation_index"] == pytest.approx(1.0)
        assert j["cp_take_at_step"] is None

    def test_late_take_higher_cooperation(self):
        # Pass 4 times then take
        match = _centipede_match(
            ("A", "pass"), ("B", "pass"), ("A", "pass"), ("B", "pass"), ("A", "take")
        )
        j = CentipedeMetrics().compute_joint(match, {"max_steps": 6})
        assert j["cp_cooperation_index"] == pytest.approx(4 / 6)
        assert j["cp_take_at_step"] == 5


# ─── compute_agent ────────────────────────────────────────────────────────────

class TestComputeAgent:
    def test_take_first_agent(self):
        match = _centipede_match(("A", "take"))
        r = CentipedeMetrics().compute_agent(match, "A", {"max_steps": 6}, {})
        assert r["cp"]["take_rate"] == pytest.approx(1.0)
        assert r["cp"]["cooperation_rate"] == pytest.approx(0.0)
        assert r["cp"]["backward_induction_adherence"] == pytest.approx(1.0)
        assert r["cp"]["first_action"] == "take"

    def test_always_pass_agent(self):
        match = _centipede_match(
            ("A", "pass"), ("B", "pass"), ("A", "pass"), ("B", "pass")
        )
        r = CentipedeMetrics().compute_agent(match, "A", {"max_steps": 6}, {})
        assert r["cp"]["take_rate"] == pytest.approx(0.0)
        assert r["cp"]["cooperation_rate"] == pytest.approx(1.0)
        assert r["cp"]["backward_induction_adherence"] == pytest.approx(0.0)

    def test_empty_actions(self):
        match = Match(match_id="t", game_type="centipede", agent_ids=["A", "B"], moves=[])
        r = CentipedeMetrics().compute_agent(match, "A", {}, {})
        assert r == {}
