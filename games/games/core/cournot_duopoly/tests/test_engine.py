import pytest
from games.core.cournot_duopoly.config import config_from_dict
from games.core.cournot_duopoly.engine import CournotGame, CournotState


def make_game(**kw) -> CournotGame:
    return CournotGame(num_rounds=kw.get("num_rounds", 5), **{k: v for k, v in kw.items() if k != "num_rounds"})


def play_round(game: CournotGame, state: CournotState, qa: float, qb: float) -> CournotState:
    state = game.apply_action(state, "A", qa)
    state = game.apply_action(state, "B", qb)
    return state


# ─── Config ──────────────────────────────────────────────────────────────────

class TestConfig:
    def test_defaults(self):
        cfg = config_from_dict({"game": "cournot_duopoly", "players": 2, "rounds": 10})
        assert cfg.demand_a == 120.0
        assert cfg.demand_b == 1.0
        assert cfg.cost_per_unit == 0.0
        assert cfg.max_quantity == 120.0

    def test_custom_params(self):
        cfg = config_from_dict({"game": "cournot_duopoly", "players": 2, "rounds": 5,
                                 "demand_a": 100.0, "demand_b": 2.0, "cost_per_unit": 10.0})
        assert cfg.demand_a == 100.0
        assert cfg.demand_b == 2.0

    def test_nash_quantity_property(self):
        cfg = config_from_dict({"game": "cournot_duopoly", "players": 2, "rounds": 5})
        # (120 - 0) / (3 * 1) = 40
        assert cfg.nash_quantity == pytest.approx(40.0)

    def test_collusive_quantity_property(self):
        cfg = config_from_dict({"game": "cournot_duopoly", "players": 2, "rounds": 5})
        # (120 - 0) / (4 * 1) = 30
        assert cfg.collusive_quantity == pytest.approx(30.0)

    def test_rejects_zero_demand(self):
        with pytest.raises(ValueError, match="demand_a and demand_b must be positive"):
            config_from_dict({"game": "cournot_duopoly", "players": 2, "rounds": 5,
                               "demand_a": 0.0, "demand_b": 1.0})

    def test_rejects_invalid_player_count(self):
        with pytest.raises(ValueError, match="2 players"):
            config_from_dict({"game": "cournot_duopoly", "players": 3, "rounds": 5})

    def test_player_ids(self):
        cfg = config_from_dict({"game": "cournot_duopoly", "players": 2, "rounds": 5})
        assert cfg.player_ids() == ["A", "B"]

    def test_config_hash_stable(self):
        cfg = config_from_dict({"game": "cournot_duopoly", "players": 2, "rounds": 5, "seed": 7})
        assert cfg.config_hash() == cfg.config_hash()


# ─── Initial state ────────────────────────────────────────────────────────────

class TestInitialState:
    def test_fields(self):
        game = make_game()
        s = game.initial_state()
        assert s.round_number == 1
        assert s.phase == "awaiting_action"
        assert sorted(s.awaiting) == ["A", "B"]
        assert s.pending_quantities == {}
        assert s.history == []
        assert s.total_scores == {"A": 0.0, "B": 0.0}


# ─── Round outcomes ───────────────────────────────────────────────────────────

class TestRoundOutcomes:
    def test_nash_equilibrium_quantities(self):
        # q=40 each: total=80, price=120-80=40, profit=40*40=1600 each
        game = make_game(num_rounds=2)
        s = play_round(game, game.initial_state(), 40.0, 40.0)
        entry = s.history[0]
        assert entry["quantities"]["A"] == pytest.approx(40.0)
        assert entry["quantities"]["B"] == pytest.approx(40.0)
        assert entry["price"] == pytest.approx(40.0)
        assert entry["payoffs"]["A"] == pytest.approx(1600.0)
        assert entry["payoffs"]["B"] == pytest.approx(1600.0)

    def test_asymmetric_quantities(self):
        # A=60, B=20: total=80, price=40, profit_A=60*40=2400, profit_B=20*40=800
        game = make_game(num_rounds=2)
        s = play_round(game, game.initial_state(), 60.0, 20.0)
        entry = s.history[0]
        assert entry["payoffs"]["A"] == pytest.approx(2400.0)
        assert entry["payoffs"]["B"] == pytest.approx(800.0)

    def test_price_floor_zero(self):
        # Both max quantity: total=240, price=max(0, 120-240)=0
        game = make_game(num_rounds=2)
        s = play_round(game, game.initial_state(), 120.0, 120.0)
        entry = s.history[0]
        assert entry["price"] == pytest.approx(0.0)
        assert entry["payoffs"]["A"] == pytest.approx(0.0)
        assert entry["payoffs"]["B"] == pytest.approx(0.0)

    def test_zero_quantities(self):
        # q=0 each: total=0, price=120, profit=0 each
        game = make_game(num_rounds=2)
        s = play_round(game, game.initial_state(), 0.0, 0.0)
        entry = s.history[0]
        assert entry["price"] == pytest.approx(120.0)
        assert entry["payoffs"]["A"] == pytest.approx(0.0)


# ─── Multi-round ──────────────────────────────────────────────────────────────

class TestMultiRound:
    def test_cumulative_scores(self):
        game = make_game(num_rounds=2)
        s = game.initial_state()
        s = play_round(game, s, 40.0, 40.0)   # each: 1600
        s = play_round(game, s, 40.0, 40.0)   # each: 1600
        assert s.total_scores["A"] == pytest.approx(3200.0)
        assert s.total_scores["B"] == pytest.approx(3200.0)

    def test_terminal_on_last_round(self):
        game = make_game(num_rounds=2)
        s = game.initial_state()
        s = play_round(game, s, 40.0, 40.0)
        assert not game.is_terminal(s)
        s = play_round(game, s, 40.0, 40.0)
        assert game.is_terminal(s)

    def test_round_counter_increments(self):
        game = make_game(num_rounds=3)
        s = game.initial_state()
        assert s.round_number == 1
        s = play_round(game, s, 40.0, 40.0)
        assert s.round_number == 2

    def test_pending_quantities_cleared(self):
        game = make_game(num_rounds=2)
        s = play_round(game, game.initial_state(), 40.0, 40.0)
        assert s.pending_quantities == {}


# ─── Validation ───────────────────────────────────────────────────────────────

class TestValidation:
    def test_rejects_non_numeric_action(self):
        game = make_game()
        s = game.initial_state()
        with pytest.raises(ValueError, match="number"):
            game.apply_action(s, "A", "lots")

    def test_rejects_negative_quantity(self):
        game = make_game()
        s = game.initial_state()
        with pytest.raises(ValueError, match="out of range"):
            game.apply_action(s, "A", -1.0)

    def test_rejects_over_max_quantity(self):
        game = make_game()
        s = game.initial_state()
        with pytest.raises(ValueError, match="out of range"):
            game.apply_action(s, "A", 121.0)

    def test_rejects_duplicate_submission(self):
        game = make_game()
        s = game.apply_action(game.initial_state(), "A", 40.0)
        with pytest.raises(ValueError, match="already submitted"):
            game.apply_action(s, "A", 40.0)

    def test_rejects_unknown_player(self):
        game = make_game()
        s = game.initial_state()
        with pytest.raises(ValueError, match="unknown player"):
            game.apply_action(s, "C", 40.0)

    def test_rejects_action_on_complete_game(self):
        game = make_game(num_rounds=1)
        s = play_round(game, game.initial_state(), 40.0, 40.0)
        with pytest.raises(ValueError, match="complete"):
            game.apply_action(s, "A", 40.0)

    def test_accepts_boundary_zero(self):
        game = make_game()
        s = game.apply_action(game.initial_state(), "A", 0.0)
        assert "A" not in s.awaiting

    def test_accepts_boundary_max(self):
        game = make_game()
        s = game.apply_action(game.initial_state(), "A", 120.0)
        assert "A" not in s.awaiting


# ─── Results ──────────────────────────────────────────────────────────────────

class TestResults:
    def test_winner_a(self):
        game = make_game(num_rounds=1)
        # A produces much more than B → higher profit
        s = play_round(game, game.initial_state(), 70.0, 10.0)
        r = game.compute_results(s)
        assert r["winner"] == "A"

    def test_tie(self):
        game = make_game(num_rounds=1)
        s = play_round(game, game.initial_state(), 40.0, 40.0)
        r = game.compute_results(s)
        assert r["winner"] == "Tie"

    def test_raises_if_incomplete(self):
        game = make_game(num_rounds=2)
        s = play_round(game, game.initial_state(), 40.0, 40.0)
        with pytest.raises(ValueError, match="not complete"):
            game.compute_results(s)

    def test_includes_metrics(self):
        game = make_game(num_rounds=1)
        s = play_round(game, game.initial_state(), 40.0, 40.0)
        r = game.compute_results(s)
        assert "metrics" in r
        assert "avg_quantity" in r["metrics"]


# ─── State serialization ──────────────────────────────────────────────────────

class TestStateSerialization:
    def test_roundtrip(self):
        game = make_game(num_rounds=3)
        s = play_round(game, game.initial_state(), 40.0, 50.0)
        s2 = game.state_from_dict(s.__dict__)
        assert s2.round_number == s.round_number
        assert s2.total_scores == s.total_scores
        assert s2.history == s.history


# ─── Public state ─────────────────────────────────────────────────────────────

class TestPublicState:
    def test_fields(self):
        cfg = config_from_dict({"game": "cournot_duopoly", "players": 2, "rounds": 5})
        game = CournotGame.from_config(cfg)
        s = game.initial_state()
        ps = game.public_state(s, cfg, "sess-1", cfg.config_hash())
        assert ps["round"] == 1
        assert ps["round_total"] == 5
        assert sorted(ps["awaiting"]) == ["A", "B"]
        assert ps["nash_quantity"] == pytest.approx(40.0)
        assert ps["collusive_quantity"] == pytest.approx(30.0)
        assert ps["demand_a"] == 120.0
