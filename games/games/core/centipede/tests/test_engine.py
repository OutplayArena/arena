import pytest
from games.core.centipede.config import config_from_dict
from games.core.centipede.engine import CentipedeGame


def make_game(**kw) -> CentipedeGame:
    return CentipedeGame(
        max_steps=kw.get("max_steps", 6),
        initial_pot_a=kw.get("initial_pot_a", 4.0),
        initial_pot_b=kw.get("initial_pot_b", 1.0),
        growth_factor=kw.get("growth_factor", 2.0),
    )


# ─── Config ──────────────────────────────────────────────────────────────────

class TestConfig:
    def test_defaults(self):
        cfg = config_from_dict({"game": "centipede", "players": 2})
        assert cfg.max_steps == 6
        assert cfg.initial_pot_a == 4.0
        assert cfg.initial_pot_b == 1.0
        assert cfg.growth_factor == 2.0

    def test_custom_params(self):
        cfg = config_from_dict({"game": "centipede", "players": 2,
                                 "max_steps": 8, "initial_pot_a": 2.0, "growth_factor": 3.0})
        assert cfg.max_steps == 8
        assert cfg.growth_factor == 3.0

    def test_rejects_too_few_steps(self):
        with pytest.raises(ValueError, match="max_steps must be >= 2"):
            config_from_dict({"game": "centipede", "players": 2, "max_steps": 1})

    def test_rejects_growth_factor_lte_one(self):
        with pytest.raises(ValueError, match="growth_factor must be > 1.0"):
            config_from_dict({"game": "centipede", "players": 2, "growth_factor": 1.0})

    def test_rejects_invalid_player_count(self):
        with pytest.raises(ValueError, match="2 players"):
            config_from_dict({"game": "centipede", "players": 3})

    def test_player_ids(self):
        cfg = config_from_dict({"game": "centipede", "players": 2})
        assert cfg.player_ids() == ["A", "B"]

    def test_config_hash_stable(self):
        cfg = config_from_dict({"game": "centipede", "players": 2, "seed": 7})
        assert cfg.config_hash() == cfg.config_hash()


# ─── Initial state ────────────────────────────────────────────────────────────

class TestInitialState:
    def test_fields(self):
        game = make_game()
        s = game.initial_state()
        assert s.step == 1
        assert s.current_player == "A"
        assert s.phase == "awaiting_action"
        assert s.pot_a == pytest.approx(4.0)
        assert s.pot_b == pytest.approx(1.0)
        assert s.history == []
        assert s.total_scores == {"A": 0.0, "B": 0.0}
        assert s.game_ended_by is None


# ─── Take action ──────────────────────────────────────────────────────────────

class TestTakeAction:
    def test_a_takes_step_1(self):
        # A takes at step 1: A gets pot_a=4, B gets pot_b=1
        game = make_game()
        s = game.apply_action(game.initial_state(), "A", "take")
        assert game.is_terminal(s)
        assert s.total_scores["A"] == pytest.approx(4.0)
        assert s.total_scores["B"] == pytest.approx(1.0)
        assert s.game_ended_by == "A"
        assert s.history[-1]["action"] == "take"

    def test_b_takes_step_2(self):
        # A passes → pots double (8, 2) → B takes: B gets 8, A gets 2
        game = make_game()
        s = game.apply_action(game.initial_state(), "A", "pass")
        s = game.apply_action(s, "B", "take")
        assert game.is_terminal(s)
        assert s.total_scores["B"] == pytest.approx(8.0)
        assert s.total_scores["A"] == pytest.approx(2.0)
        assert s.game_ended_by == "B"

    def test_take_ends_game_immediately(self):
        game = make_game()
        s = game.apply_action(game.initial_state(), "A", "take")
        assert s.phase == "complete"
        assert game.is_terminal(s)


# ─── Pass action ──────────────────────────────────────────────────────────────

class TestPassAction:
    def test_pass_doubles_pots(self):
        game = make_game()
        s = game.apply_action(game.initial_state(), "A", "pass")
        assert s.pot_a == pytest.approx(8.0)
        assert s.pot_b == pytest.approx(2.0)

    def test_pass_switches_player(self):
        game = make_game()
        s = game.apply_action(game.initial_state(), "A", "pass")
        assert s.current_player == "B"
        assert s.step == 2

    def test_pass_switches_back(self):
        game = make_game()
        s = game.apply_action(game.initial_state(), "A", "pass")
        s = game.apply_action(s, "B", "pass")
        assert s.current_player == "A"
        assert s.step == 3

    def test_forced_payout_at_max_steps(self):
        # Pass all 6 steps → forced payout at current pots
        # After 6 passes: pot_a = 4 × 2^6 = 256, pot_b = 1 × 2^6 = 64
        game = make_game(max_steps=6)
        s = game.initial_state()
        players = ["A", "B", "A", "B", "A", "B"]  # alternating
        for p in players:
            s = game.apply_action(s, p, "pass")
        assert game.is_terminal(s)
        assert s.game_ended_by == "forced"
        assert s.total_scores["A"] == pytest.approx(4.0 * (2 ** 6))
        assert s.total_scores["B"] == pytest.approx(1.0 * (2 ** 6))

    def test_growth_factor_3x(self):
        game = make_game(growth_factor=3.0)
        s = game.apply_action(game.initial_state(), "A", "pass")
        assert s.pot_a == pytest.approx(12.0)
        assert s.pot_b == pytest.approx(3.0)


# ─── Validation ───────────────────────────────────────────────────────────────

class TestValidation:
    def test_rejects_invalid_action(self):
        game = make_game()
        s = game.initial_state()
        with pytest.raises(ValueError, match="invalid action"):
            game.apply_action(s, "A", "cooperate")

    def test_rejects_wrong_player(self):
        game = make_game()
        s = game.initial_state()
        with pytest.raises(ValueError, match="turn"):
            game.apply_action(s, "B", "take")

    def test_rejects_unknown_player(self):
        game = make_game()
        s = game.initial_state()
        with pytest.raises(ValueError, match="unknown player"):
            game.apply_action(s, "C", "take")

    def test_rejects_action_on_complete_game(self):
        game = make_game()
        s = game.apply_action(game.initial_state(), "A", "take")
        with pytest.raises(ValueError, match="complete"):
            game.apply_action(s, "A", "take")

    def test_case_insensitive_action(self):
        game = make_game()
        s = game.apply_action(game.initial_state(), "A", "TAKE")
        assert game.is_terminal(s)


# ─── Backward induction scenario ─────────────────────────────────────────────

class TestBackwardInduction:
    def test_take_at_step_1_is_spe(self):
        # SPE: A should take immediately at step 1
        game = make_game()
        s = game.apply_action(game.initial_state(), "A", "take")
        r = game.compute_results(s)
        assert r["game_ended_by"] == "A"
        assert r["total_scores"]["A"] == pytest.approx(4.0)

    def test_full_cooperation_to_max_gives_both_more(self):
        # Both always passing gives better outcome than taking at step 1
        game = make_game(max_steps=6)
        # Backward induction payoff: A=4, B=1
        # Full cooperation payoff: A=256, B=64
        s = game.initial_state()
        players = ["A", "B", "A", "B", "A", "B"]
        for p in players:
            s = game.apply_action(s, p, "pass")
        assert s.total_scores["A"] > 4.0
        assert s.total_scores["B"] > 1.0


# ─── Results ──────────────────────────────────────────────────────────────────

class TestResults:
    def test_winner_when_a_takes(self):
        game = make_game()
        s = game.apply_action(game.initial_state(), "A", "take")
        r = game.compute_results(s)
        assert r["winner"] == "A"   # A=4 > B=1

    def test_raises_if_incomplete(self):
        game = make_game()
        s = game.apply_action(game.initial_state(), "A", "pass")
        with pytest.raises(ValueError, match="not complete"):
            game.compute_results(s)

    def test_includes_metrics(self):
        game = make_game()
        s = game.apply_action(game.initial_state(), "A", "take")
        r = game.compute_results(s)
        assert "metrics" in r
        assert "steps_played" in r["metrics"]
        assert "game_ended_early" in r["metrics"]


# ─── State serialization ──────────────────────────────────────────────────────

class TestStateSerialization:
    def test_roundtrip(self):
        game = make_game()
        s = game.apply_action(game.initial_state(), "A", "pass")
        s2 = game.state_from_dict(s.__dict__)
        assert s2.step == s.step
        assert s2.current_player == s.current_player
        assert s2.pot_a == s.pot_a
        assert s2.history == s.history


# ─── Public state ─────────────────────────────────────────────────────────────

class TestPublicState:
    def test_initial_public_state(self):
        cfg = config_from_dict({"game": "centipede", "players": 2, "max_steps": 6})
        game = CentipedeGame.from_config(cfg)
        s = game.initial_state()
        ps = game.public_state(s, cfg, "sess-1", cfg.config_hash())
        assert ps["step"] == 1
        assert ps["max_steps"] == 6
        assert ps["current_player"] == "A"
        assert ps["awaiting"] == ["A"]
        assert ps["pot_a"] == pytest.approx(4.0)
        assert ps["pot_b"] == pytest.approx(1.0)

    def test_public_state_after_take_empty_awaiting(self):
        cfg = config_from_dict({"game": "centipede", "players": 2})
        game = CentipedeGame.from_config(cfg)
        s = game.apply_action(game.initial_state(), "A", "take")
        ps = game.public_state(s, cfg, "sess-1", cfg.config_hash())
        assert ps["awaiting"] == []
        assert ps["game_ended_by"] == "A"
