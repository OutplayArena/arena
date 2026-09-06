import pytest

from games.community.chicken_game.config import config_from_dict
from games.community.chicken_game.engine import ChickenGameGame, ChickenGameState


def make_game(**kw) -> ChickenGameGame:
    return ChickenGameGame(num_rounds=kw.get("num_rounds", 5), **{k: v for k, v in kw.items() if k != "num_rounds"})


def play_round(game: ChickenGameGame, state: ChickenGameState, a: str, b: str) -> ChickenGameState:
    state = game.apply_action(state, "A", a)
    state = game.apply_action(state, "B", b)
    return state


# ─── Config ──────────────────────────────────────────────────────────────────

class TestConfig:
    def test_defaults(self):
        cfg = config_from_dict({"game": "chicken_game", "variant": "classic", "players": 2, "rounds": 10})
        assert cfg.payoff_win == 1.0
        assert cfg.payoff_tie == 0.0
        assert cfg.payoff_lose == -1.0
        assert cfg.payoff_crash == -10.0
        assert cfg.noise == 0.0
        assert cfg.seed is None

    def test_custom_payoffs(self):
        cfg = config_from_dict({"game": "chicken_game", "variant": "classic", "players": 2, "rounds": 5,
                                 "payoff_win": 2.0, "payoff_tie": 1.0, "payoff_lose": -2.0, "payoff_crash": -20.0})
        assert cfg.payoff_win == 2.0
        assert cfg.payoff_crash == -20.0

    def test_rejects_invalid_payoff_order(self):
        with pytest.raises(ValueError, match="payoff_win > payoff_tie > payoff_lose > payoff_crash"):
            config_from_dict({"game": "chicken_game", "variant": "classic", "players": 2, "rounds": 5,
                               "payoff_win": 1.0, "payoff_tie": 2.0, "payoff_lose": -1.0, "payoff_crash": -10.0})

    def test_rejects_high_noise(self):
        with pytest.raises(ValueError, match="noise"):
            config_from_dict({"game": "chicken_game", "variant": "noisy", "players": 2, "rounds": 5, "noise": 0.6})

    def test_rejects_invalid_variant(self):
        with pytest.raises(ValueError, match="unknown variant"):
            config_from_dict({"game": "chicken_game", "variant": "weird", "players": 2, "rounds": 5})

    def test_rejects_invalid_player_count(self):
        with pytest.raises(ValueError, match="2 players"):
            config_from_dict({"game": "chicken_game", "variant": "classic", "players": 3, "rounds": 5})

    def test_player_ids(self):
        cfg = config_from_dict({"game": "chicken_game", "variant": "classic", "players": 2, "rounds": 5})
        assert cfg.player_ids() == ["A", "B"]

    def test_to_dict_roundtrip(self):
        cfg = config_from_dict({"game": "chicken_game", "variant": "classic", "players": 2, "rounds": 5, "seed": 42})
        d = cfg.to_dict()
        assert d["rounds"] == 5
        assert d["seed"] == 42

    def test_config_hash_stable(self):
        cfg = config_from_dict({"game": "chicken_game", "variant": "classic", "players": 2, "rounds": 5, "seed": 7})
        assert cfg.config_hash() == cfg.config_hash()


# ─── Initial state ────────────────────────────────────────────────────────────

class TestInitialState:
    def test_fields(self):
        game = make_game()
        s = game.initial_state()
        assert s.round_number == 1
        assert s.phase == "awaiting_action"
        assert sorted(s.awaiting) == ["A", "B"]
        assert s.pending_actions == {}
        assert s.history == []
        assert s.total_scores == {"A": 0.0, "B": 0.0}


# ─── Round outcomes ───────────────────────────────────────────────────────────

class TestRoundOutcomes:
    @pytest.mark.parametrize("a,b,outcome,pa,pb", [
        ("dare", "dare", "DD", -10.0, -10.0),
        ("dare", "swerve", "DS", 1.0, -1.0),
        ("swerve", "dare", "SD", -1.0, 1.0),
        ("swerve", "swerve", "SS", 0.0, 0.0),
    ])
    def test_outcome(self, a, b, outcome, pa, pb):
        game = make_game(num_rounds=2)
        s = play_round(game, game.initial_state(), a, b)
        entry = s.history[0]
        assert entry["outcome"] == outcome
        assert entry["payoffs"]["A"] == pytest.approx(pa)
        assert entry["payoffs"]["B"] == pytest.approx(pb)
        assert s.total_scores["A"] == pytest.approx(pa)
        assert s.total_scores["B"] == pytest.approx(pb)


# ─── Multi-round ──────────────────────────────────────────────────────────────

class TestMultiRound:
    def test_cumulative_scores(self):
        game = make_game(num_rounds=3)
        s = game.initial_state()
        s = play_round(game, s, "swerve", "swerve")  # SS: 0,0
        s = play_round(game, s, "dare", "swerve")    # DS: 1,-1
        s = play_round(game, s, "dare", "dare")      # DD: -10,-10
        assert s.total_scores["A"] == pytest.approx(-9.0)
        assert s.total_scores["B"] == pytest.approx(-11.0)
        assert len(s.history) == 3

    def test_terminal_on_last_round(self):
        game = make_game(num_rounds=2)
        s = game.initial_state()
        s = play_round(game, s, "swerve", "swerve")
        assert not game.is_terminal(s)
        s = play_round(game, s, "swerve", "swerve")
        assert game.is_terminal(s)
        assert s.phase == "complete"

    def test_round_counter_increments(self):
        game = make_game(num_rounds=3)
        s = game.initial_state()
        assert s.round_number == 1
        s = play_round(game, s, "swerve", "dare")
        assert s.round_number == 2

    def test_awaiting_resets_each_round(self):
        game = make_game(num_rounds=2)
        s = game.initial_state()
        s = play_round(game, s, "swerve", "swerve")
        assert sorted(s.awaiting) == ["A", "B"]

    def test_pending_actions_cleared_after_round(self):
        game = make_game(num_rounds=2)
        s = game.initial_state()
        s = play_round(game, s, "swerve", "swerve")
        assert s.pending_actions == {}


# ─── Validation ───────────────────────────────────────────────────────────────

class TestValidation:
    def test_rejects_invalid_action(self):
        game = make_game()
        s = game.initial_state()
        with pytest.raises(ValueError, match="invalid action"):
            game.apply_action(s, "A", "cooperate")

    def test_rejects_duplicate_submission(self):
        game = make_game()
        s = game.initial_state()
        s = game.apply_action(s, "A", "swerve")
        with pytest.raises(ValueError, match="already submitted"):
            game.apply_action(s, "A", "swerve")

    def test_rejects_unknown_player(self):
        game = make_game()
        s = game.initial_state()
        with pytest.raises(ValueError, match="unknown player"):
            game.apply_action(s, "C", "swerve")

    def test_rejects_action_on_complete_game(self):
        game = make_game(num_rounds=1)
        s = play_round(game, game.initial_state(), "swerve", "swerve")
        assert game.is_terminal(s)
        with pytest.raises(ValueError, match="complete"):
            game.apply_action(s, "A", "swerve")


# ─── Results ──────────────────────────────────────────────────────────────────

class TestResults:
    def test_winner_a(self):
        game = make_game(num_rounds=1)
        s = play_round(game, game.initial_state(), "dare", "swerve")  # DS: A=1, B=-1
        r = game.compute_results(s)
        assert r["winner"] == "A"

    def test_winner_b(self):
        game = make_game(num_rounds=1)
        s = play_round(game, game.initial_state(), "swerve", "dare")  # SD: A=-1, B=1
        r = game.compute_results(s)
        assert r["winner"] == "B"

    def test_tie(self):
        game = make_game(num_rounds=1)
        s = play_round(game, game.initial_state(), "swerve", "swerve")  # SS: 0,0
        r = game.compute_results(s)
        assert r["winner"] == "Tie"

    def test_raises_if_incomplete(self):
        game = make_game(num_rounds=2)
        s = play_round(game, game.initial_state(), "swerve", "swerve")
        with pytest.raises(ValueError, match="not complete"):
            game.compute_results(s)

    def test_includes_metrics(self):
        game = make_game(num_rounds=2)
        s = game.initial_state()
        s = play_round(game, s, "dare", "swerve")
        s = play_round(game, s, "swerve", "swerve")
        r = game.compute_results(s)
        assert "metrics" in r
        assert "dare_rate" in r["metrics"]


# ─── State serialization ──────────────────────────────────────────────────────

class TestStateSerialization:
    def test_roundtrip(self):
        game = make_game(num_rounds=3)
        s = play_round(game, game.initial_state(), "swerve", "dare")
        s2 = game.state_from_dict(s.__dict__)
        assert s2.round_number == s.round_number
        assert s2.total_scores == s.total_scores
        assert s2.history == s.history


# ─── Noise ────────────────────────────────────────────────────────────────────

class TestNoise:
    def test_noisy_game_stores_intended_actions(self):
        game = ChickenGameGame(num_rounds=20, noise=0.5, seed=0)
        s = game.initial_state()
        for _ in range(20):
            if not game.is_terminal(s):
                s = play_round(game, s, "swerve", "swerve")
        flipped = [e for e in s.history if "intended_actions" in e
                   and e["intended_actions"] != e["actions"]]
        assert len(flipped) > 0

    def test_noise_zero_never_flips(self):
        game = ChickenGameGame(num_rounds=5, noise=0.0, seed=99)
        s = game.initial_state()
        for _ in range(5):
            if not game.is_terminal(s):
                s = play_round(game, s, "swerve", "swerve")
        for entry in s.history:
            assert entry["actions"] == {"A": "swerve", "B": "swerve"}


# ─── Forfeit ──────────────────────────────────────────────────────────────────

class TestForfeit:
    def test_forfeit_a_is_swerve_vs_opponent_dare(self):
        game = make_game(num_rounds=2)
        s = game.initial_state()
        s = game.forfeit_round(s, "A")
        entry = s.history[0]
        assert entry["outcome"] == "SD"
        assert entry["forfeit_by"] == "A"
        assert entry["payoffs"]["A"] == pytest.approx(-1.0)
        assert entry["payoffs"]["B"] == pytest.approx(1.0)

    def test_forfeit_b_is_swerve_vs_opponent_dare(self):
        game = make_game(num_rounds=2)
        s = game.initial_state()
        s = game.forfeit_round(s, "B")
        entry = s.history[0]
        assert entry["outcome"] == "DS"
        assert entry["forfeit_by"] == "B"
        assert entry["payoffs"]["A"] == pytest.approx(1.0)
        assert entry["payoffs"]["B"] == pytest.approx(-1.0)


# ─── Public state ─────────────────────────────────────────────────────────────

class TestPublicState:
    def test_fields(self):
        cfg = config_from_dict({"game": "chicken_game", "variant": "classic", "players": 2, "rounds": 5})
        game = ChickenGameGame.from_config(cfg)
        s = game.initial_state()
        ps = game.public_state(s, cfg, "sess-1", cfg.config_hash())
        assert ps["round"] == 1
        assert ps["round_total"] == 5
        assert sorted(ps["awaiting"]) == ["A", "B"]
        assert "total_scores" in ps
        assert "payoffs" in ps
        assert ps["payoffs"]["win"] == 1.0
        assert ps["payoffs"]["crash"] == -10.0
