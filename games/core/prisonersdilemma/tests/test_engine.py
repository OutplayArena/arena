import pytest
from games.core.prisonersdilemma.config import PDExperimentConfig, config_from_dict
from games.core.prisonersdilemma.engine import PDGame, PDState


def make_game(**kw) -> PDGame:
    return PDGame(num_rounds=kw.get("num_rounds", 5), **{k: v for k, v in kw.items() if k != "num_rounds"})


def play_round(game: PDGame, state: PDState, a: str, b: str) -> PDState:
    state = game.apply_action(state, "A", a)
    state = game.apply_action(state, "B", b)
    return state


# ─── Config ─────────────────────────────────────────────────────────────────

class TestConfig:
    def test_defaults(self):
        cfg = config_from_dict({"variant": "classic", "players": 2, "rounds": 10})
        assert cfg.payoff_T == 5.0
        assert cfg.payoff_R == 3.0
        assert cfg.payoff_P == 1.0
        assert cfg.payoff_S == 0.0
        assert cfg.noise == 0.0
        assert cfg.seed is None

    def test_custom_payoffs(self):
        cfg = config_from_dict({"variant": "classic", "players": 2, "rounds": 5,
                                 "payoff_T": 6, "payoff_R": 4, "payoff_P": 2, "payoff_S": 1})
        assert cfg.payoff_T == 6.0
        assert cfg.payoff_R == 4.0

    def test_rejects_invalid_constraint_TgR(self):
        with pytest.raises(ValueError, match="T > R"):
            config_from_dict({"variant": "classic", "players": 2, "rounds": 5,
                               "payoff_T": 3.0, "payoff_R": 3.0, "payoff_P": 1.0, "payoff_S": 0.0})

    def test_rejects_invalid_constraint_2RgTplusS(self):
        with pytest.raises(ValueError, match="2R > T"):
            config_from_dict({"variant": "classic", "players": 2, "rounds": 5,
                               "payoff_T": 7.0, "payoff_R": 3.0, "payoff_P": 1.0, "payoff_S": 0.0})

    def test_rejects_high_noise(self):
        with pytest.raises(ValueError, match="noise"):
            config_from_dict({"variant": "noisy", "players": 2, "rounds": 5, "noise": 0.6})

    def test_player_ids(self):
        cfg = config_from_dict({"variant": "classic", "players": 2, "rounds": 5})
        assert cfg.player_ids() == ["A", "B"]

    def test_to_dict_roundtrip(self):
        cfg = config_from_dict({"variant": "classic", "players": 2, "rounds": 5, "seed": 42})
        d = cfg.to_dict()
        assert d["rounds"] == 5
        assert d["seed"] == 42

    def test_config_hash_stable(self):
        cfg = config_from_dict({"variant": "classic", "players": 2, "rounds": 5, "seed": 7})
        assert cfg.config_hash() == cfg.config_hash()


# ─── Initial state ───────────────────────────────────────────────────────────

class TestInitialState:
    def test_initial_state(self):
        game = make_game()
        s = game.initial_state()
        assert s.round_number == 1
        assert s.phase == "awaiting_action"
        assert sorted(s.awaiting) == ["A", "B"]
        assert s.pending_actions == {}
        assert s.history == []
        assert s.total_scores == {"A": 0.0, "B": 0.0}


# ─── Round outcomes ──────────────────────────────────────────────────────────

class TestRoundOutcomes:
    @pytest.mark.parametrize("a,b,expected_outcome,pa,pb", [
        ("cooperate", "cooperate", "CC", 3.0, 3.0),
        ("cooperate", "defect",    "CD", 0.0, 5.0),
        ("defect",    "cooperate", "DC", 5.0, 0.0),
        ("defect",    "defect",    "DD", 1.0, 1.0),
    ])
    def test_outcome(self, a, b, expected_outcome, pa, pb):
        game = make_game(num_rounds=2)
        s = game.initial_state()
        s = play_round(game, s, a, b)
        entry = s.history[0]
        assert entry["outcome"] == expected_outcome
        assert entry["payoffs"]["A"] == pytest.approx(pa)
        assert entry["payoffs"]["B"] == pytest.approx(pb)
        assert s.total_scores["A"] == pytest.approx(pa)
        assert s.total_scores["B"] == pytest.approx(pb)


# ─── Multi-round ─────────────────────────────────────────────────────────────

class TestMultiRound:
    def test_cumulative_scores(self):
        game = make_game(num_rounds=3)
        s = game.initial_state()
        s = play_round(game, s, "cooperate", "cooperate")  # CC: 3+3
        s = play_round(game, s, "defect",    "cooperate")  # DC: 5+0
        s = play_round(game, s, "defect",    "defect")     # DD: 1+1
        assert s.total_scores["A"] == pytest.approx(9.0)
        assert s.total_scores["B"] == pytest.approx(4.0)
        assert len(s.history) == 3

    def test_terminal_on_last_round(self):
        game = make_game(num_rounds=2)
        s = game.initial_state()
        s = play_round(game, s, "cooperate", "cooperate")
        assert not game.is_terminal(s)
        s = play_round(game, s, "cooperate", "cooperate")
        assert game.is_terminal(s)
        assert s.phase == "complete"

    def test_round_counter_increments(self):
        game = make_game(num_rounds=3)
        s = game.initial_state()
        assert s.round_number == 1
        s = play_round(game, s, "cooperate", "defect")
        assert s.round_number == 2


# ─── Validation ──────────────────────────────────────────────────────────────

class TestValidation:
    def test_rejects_invalid_action(self):
        game = make_game()
        s = game.initial_state()
        with pytest.raises(ValueError, match="invalid action"):
            game.apply_action(s, "A", "rock")

    def test_rejects_duplicate_submission(self):
        game = make_game()
        s = game.initial_state()
        s = game.apply_action(s, "A", "cooperate")
        with pytest.raises(ValueError, match="already submitted"):
            game.apply_action(s, "A", "cooperate")

    def test_rejects_unknown_player(self):
        game = make_game()
        s = game.initial_state()
        with pytest.raises(ValueError, match="unknown player"):
            game.apply_action(s, "C", "cooperate")

    def test_rejects_action_on_complete_game(self):
        game = make_game(num_rounds=1)
        s = game.initial_state()
        s = play_round(game, s, "cooperate", "cooperate")
        assert game.is_terminal(s)
        with pytest.raises(ValueError, match="complete"):
            game.apply_action(s, "A", "cooperate")


# ─── Results ─────────────────────────────────────────────────────────────────

class TestResults:
    def test_compute_results_winner_a(self):
        game = make_game(num_rounds=1)
        s = game.initial_state()
        s = play_round(game, s, "defect", "cooperate")
        r = game.compute_results(s)
        assert r["winner"] == "A"
        assert r["total_scores"]["A"] > r["total_scores"]["B"]

    def test_compute_results_tie(self):
        game = make_game(num_rounds=1)
        s = game.initial_state()
        s = play_round(game, s, "cooperate", "cooperate")
        r = game.compute_results(s)
        assert r["winner"] == "Tie"

    def test_compute_results_raises_if_incomplete(self):
        game = make_game(num_rounds=2)
        s = game.initial_state()
        s = play_round(game, s, "cooperate", "cooperate")
        with pytest.raises(ValueError, match="not complete"):
            game.compute_results(s)

    def test_compute_results_includes_metrics(self):
        game = make_game(num_rounds=2)
        s = game.initial_state()
        s = play_round(game, s, "cooperate", "cooperate")
        s = play_round(game, s, "defect",    "defect")
        r = game.compute_results(s)
        assert "metrics" in r
        assert "cooperation_rate" in r["metrics"]


# ─── State serialization ──────────────────────────────────────────────────────

class TestStateSerialization:
    def test_state_roundtrip(self):
        game = make_game(num_rounds=3)
        s = game.initial_state()
        s = play_round(game, s, "cooperate", "defect")
        d = s.__dict__
        s2 = game.state_from_dict(d)
        assert s2.round_number == s.round_number
        assert s2.total_scores == s.total_scores
        assert s2.history == s.history


# ─── Forfeit ─────────────────────────────────────────────────────────────────

class TestForfeit:
    def test_forfeit_a(self):
        game = make_game(num_rounds=2)
        s = game.initial_state()
        s = game.forfeit_round(s, "A")
        # A forfeits = A defects, B cooperates → outcome CD
        entry = s.history[0]
        assert entry["forfeit"] is True
        assert entry["forfeit_by"] == "A"
        # A gets S=0, B gets T=5
        assert s.total_scores["A"] == pytest.approx(0.0)
        assert s.total_scores["B"] == pytest.approx(5.0)

    def test_forfeit_last_round_terminates(self):
        game = make_game(num_rounds=1)
        s = game.initial_state()
        s = game.forfeit_round(s, "B")
        assert game.is_terminal(s)


# ─── Noise ───────────────────────────────────────────────────────────────────

class TestNoise:
    def test_noisy_game_stores_intended_actions(self):
        game = PDGame(num_rounds=20, noise=0.5, seed=0)
        s = game.initial_state()
        for _ in range(20):
            if not game.is_terminal(s):
                s = play_round(game, s, "cooperate", "cooperate")
        flipped = [e for e in s.history if "intended_actions" in e
                   and e["intended_actions"] != e["actions"]]
        assert len(flipped) > 0

    def test_noise_zero_never_flips(self):
        game = PDGame(num_rounds=5, noise=0.0, seed=99)
        s = game.initial_state()
        for _ in range(5):
            if not game.is_terminal(s):
                s = play_round(game, s, "cooperate", "cooperate")
        for entry in s.history:
            assert entry["actions"] == {"A": "cooperate", "B": "cooperate"}


# ─── Public state ─────────────────────────────────────────────────────────────

class TestPublicState:
    def test_public_state_fields(self):
        cfg = config_from_dict({"variant": "classic", "players": 2, "rounds": 5})
        game = PDGame.from_config(cfg)
        s = game.initial_state()
        ps = game.public_state(s, cfg, "sess-1", cfg.config_hash())
        assert ps["round"] == 1
        assert ps["round_total"] == 5
        assert sorted(ps["awaiting"]) == ["A", "B"]
        assert "total_scores" in ps
