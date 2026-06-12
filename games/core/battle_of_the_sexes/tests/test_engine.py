import pytest
from games.core.battle_of_the_sexes.config import config_from_dict
from games.core.battle_of_the_sexes.engine import BoSGame, BoSState


def make_game(**kw) -> BoSGame:
    return BoSGame(num_rounds=kw.get("num_rounds", 5), **{k: v for k, v in kw.items() if k != "num_rounds"})


def play_round(game: BoSGame, state: BoSState, a: str, b: str) -> BoSState:
    state = game.apply_action(state, "A", a)
    state = game.apply_action(state, "B", b)
    return state


# ─── Config ──────────────────────────────────────────────────────────────────

class TestConfig:
    def test_defaults(self):
        cfg = config_from_dict({"game": "battle_of_the_sexes", "players": 2, "rounds": 10})
        assert cfg.payoff_preferred_a == 3.0
        assert cfg.payoff_preferred_b == 3.0
        assert cfg.payoff_nonpreferred == 2.0
        assert cfg.payoff_mismatch == 0.0
        assert cfg.option_a_label == "opera"
        assert cfg.option_b_label == "football"

    def test_custom_labels(self):
        cfg = config_from_dict({"game": "battle_of_the_sexes", "players": 2, "rounds": 5,
                                 "option_a_label": "beach", "option_b_label": "mountains"})
        assert cfg.option_a_label == "beach"
        assert cfg.option_b_label == "mountains"

    def test_rejects_invalid_player_count(self):
        with pytest.raises(ValueError, match="2 players"):
            config_from_dict({"game": "battle_of_the_sexes", "players": 3, "rounds": 5})

    def test_player_ids(self):
        cfg = config_from_dict({"game": "battle_of_the_sexes", "players": 2, "rounds": 5})
        assert cfg.player_ids() == ["A", "B"]

    def test_to_dict_roundtrip(self):
        cfg = config_from_dict({"game": "battle_of_the_sexes", "players": 2, "rounds": 5, "seed": 7})
        d = cfg.to_dict()
        assert d["rounds"] == 5
        assert d["seed"] == 7
        assert d["option_a_label"] == "opera"

    def test_config_hash_stable(self):
        cfg = config_from_dict({"game": "battle_of_the_sexes", "players": 2, "rounds": 5, "seed": 7})
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
    def test_both_opera_a_preferred(self):
        game = make_game(num_rounds=2)
        s = play_round(game, game.initial_state(), "opera", "opera")
        entry = s.history[0]
        assert entry["outcome"] == "AA"
        assert entry["coordinated"] is True
        assert entry["payoffs"]["A"] == pytest.approx(3.0)   # preferred_a
        assert entry["payoffs"]["B"] == pytest.approx(2.0)   # nonpreferred

    def test_both_football_b_preferred(self):
        game = make_game(num_rounds=2)
        s = play_round(game, game.initial_state(), "football", "football")
        entry = s.history[0]
        assert entry["outcome"] == "BB"
        assert entry["coordinated"] is True
        assert entry["payoffs"]["A"] == pytest.approx(2.0)   # nonpreferred
        assert entry["payoffs"]["B"] == pytest.approx(3.0)   # preferred_b

    def test_mismatch_a_opera_b_football(self):
        game = make_game(num_rounds=2)
        s = play_round(game, game.initial_state(), "opera", "football")
        entry = s.history[0]
        assert entry["outcome"] == "AB"
        assert entry["coordinated"] is False
        assert entry["payoffs"]["A"] == pytest.approx(0.0)
        assert entry["payoffs"]["B"] == pytest.approx(0.0)

    def test_mismatch_a_football_b_opera(self):
        game = make_game(num_rounds=2)
        s = play_round(game, game.initial_state(), "football", "opera")
        entry = s.history[0]
        assert entry["outcome"] == "BA"
        assert entry["coordinated"] is False
        assert entry["payoffs"]["A"] == pytest.approx(0.0)
        assert entry["payoffs"]["B"] == pytest.approx(0.0)


# ─── Multi-round ──────────────────────────────────────────────────────────────

class TestMultiRound:
    def test_cumulative_scores(self):
        game = make_game(num_rounds=3)
        s = game.initial_state()
        s = play_round(game, s, "opera", "opera")      # AA: 3,2
        s = play_round(game, s, "football", "football") # BB: 2,3
        s = play_round(game, s, "opera", "football")   # mismatch: 0,0
        assert s.total_scores["A"] == pytest.approx(5.0)
        assert s.total_scores["B"] == pytest.approx(5.0)
        assert len(s.history) == 3

    def test_terminal_on_last_round(self):
        game = make_game(num_rounds=2)
        s = game.initial_state()
        s = play_round(game, s, "opera", "opera")
        assert not game.is_terminal(s)
        s = play_round(game, s, "opera", "opera")
        assert game.is_terminal(s)
        assert s.phase == "complete"

    def test_round_counter_increments(self):
        game = make_game(num_rounds=3)
        s = game.initial_state()
        assert s.round_number == 1
        s = play_round(game, s, "opera", "football")
        assert s.round_number == 2


# ─── Validation ───────────────────────────────────────────────────────────────

class TestValidation:
    def test_rejects_invalid_action(self):
        game = make_game()
        s = game.initial_state()
        with pytest.raises(ValueError, match="invalid action"):
            game.apply_action(s, "A", "cinema")

    def test_rejects_duplicate_submission(self):
        game = make_game()
        s = game.initial_state()
        s = game.apply_action(s, "A", "opera")
        with pytest.raises(ValueError, match="already submitted"):
            game.apply_action(s, "A", "opera")

    def test_rejects_unknown_player(self):
        game = make_game()
        s = game.initial_state()
        with pytest.raises(ValueError, match="unknown player"):
            game.apply_action(s, "C", "opera")

    def test_rejects_action_on_complete_game(self):
        game = make_game(num_rounds=1)
        s = play_round(game, game.initial_state(), "opera", "opera")
        assert game.is_terminal(s)
        with pytest.raises(ValueError, match="complete"):
            game.apply_action(s, "A", "opera")

    def test_custom_labels_are_valid_actions(self):
        game = BoSGame(option_a_label="beach", option_b_label="mountains")
        s = game.initial_state()
        s = game.apply_action(s, "A", "beach")
        assert "A" not in s.awaiting

    def test_default_label_rejected_with_custom_labels(self):
        game = BoSGame(option_a_label="beach", option_b_label="mountains")
        s = game.initial_state()
        with pytest.raises(ValueError, match="invalid action"):
            game.apply_action(s, "A", "opera")


# ─── Results ──────────────────────────────────────────────────────────────────

class TestResults:
    def test_winner_a(self):
        game = make_game(num_rounds=1)
        s = play_round(game, game.initial_state(), "opera", "opera")  # AA: A=3, B=2
        r = game.compute_results(s)
        assert r["winner"] == "A"

    def test_winner_b(self):
        game = make_game(num_rounds=1)
        s = play_round(game, game.initial_state(), "football", "football")  # BB: A=2, B=3
        r = game.compute_results(s)
        assert r["winner"] == "B"

    def test_tie(self):
        # Two rounds: AA then BB → A=5, B=5
        game = make_game(num_rounds=2)
        s = game.initial_state()
        s = play_round(game, s, "opera", "opera")
        s = play_round(game, s, "football", "football")
        r = game.compute_results(s)
        assert r["winner"] == "Tie"

    def test_raises_if_incomplete(self):
        game = make_game(num_rounds=2)
        s = play_round(game, game.initial_state(), "opera", "opera")
        with pytest.raises(ValueError, match="not complete"):
            game.compute_results(s)

    def test_includes_metrics(self):
        game = make_game(num_rounds=2)
        s = game.initial_state()
        s = play_round(game, s, "opera", "opera")
        s = play_round(game, s, "opera", "football")
        r = game.compute_results(s)
        assert "metrics" in r
        assert "coordination_rate" in r["metrics"]


# ─── State serialization ──────────────────────────────────────────────────────

class TestStateSerialization:
    def test_roundtrip(self):
        game = make_game(num_rounds=3)
        s = play_round(game, game.initial_state(), "opera", "football")
        s2 = game.state_from_dict(s.__dict__)
        assert s2.round_number == s.round_number
        assert s2.total_scores == s.total_scores
        assert s2.history == s.history


# ─── Public state ─────────────────────────────────────────────────────────────

class TestPublicState:
    def test_fields(self):
        cfg = config_from_dict({"game": "battle_of_the_sexes", "players": 2, "rounds": 5})
        game = BoSGame.from_config(cfg)
        s = game.initial_state()
        ps = game.public_state(s, cfg, "sess-1", cfg.config_hash())
        assert ps["round"] == 1
        assert ps["round_total"] == 5
        assert sorted(ps["awaiting"]) == ["A", "B"]
        assert ps["option_a"] == "opera"
        assert ps["option_b"] == "football"
