import pytest
from games.core.public_goods.config import config_from_dict
from games.core.public_goods.engine import PublicGoodsGame, PGGState


def make_game(**kw) -> PublicGoodsGame:
    return PublicGoodsGame(
        num_players=kw.get("num_players", 4),
        num_rounds=kw.get("num_rounds", 3),
        endowment=kw.get("endowment", 10.0),
        multiplier=kw.get("multiplier", 2.0),
        punishment=kw.get("punishment", False),
    )


def play_round(game: PublicGoodsGame, state: PGGState, contributions: dict) -> PGGState:
    for player, amount in contributions.items():
        state = game.apply_action(state, player, amount)
    return state


_ALL_PLAYERS = ["A", "B", "C", "D"]


# ─── Config ──────────────────────────────────────────────────────────────────

class TestConfig:
    def test_defaults(self):
        cfg = config_from_dict({"game": "public_goods", "variant": "classic", "players": 4, "rounds": 10})
        assert cfg.endowment == 10.0
        assert cfg.multiplier == 2.0
        assert cfg.punishment_cost == 1.0
        assert cfg.punishment_effect == 3.0

    def test_player_ids_4(self):
        cfg = config_from_dict({"game": "public_goods", "variant": "classic", "players": 4, "rounds": 5})
        assert cfg.player_ids() == ["A", "B", "C", "D"]

    def test_player_ids_3(self):
        cfg = config_from_dict({"game": "public_goods", "variant": "classic", "players": 3, "rounds": 5})
        assert cfg.player_ids() == ["A", "B", "C"]

    def test_rejects_too_few_players(self):
        with pytest.raises(ValueError, match="3–6 players"):
            config_from_dict({"game": "public_goods", "variant": "classic", "players": 2, "rounds": 5})

    def test_rejects_too_many_players(self):
        with pytest.raises(ValueError, match="3–6 players"):
            config_from_dict({"game": "public_goods", "variant": "classic", "players": 7, "rounds": 5})

    def test_rejects_invalid_variant(self):
        with pytest.raises(ValueError, match="unknown variant"):
            config_from_dict({"game": "public_goods", "variant": "weird", "players": 4, "rounds": 5})

    def test_rejects_non_positive_endowment(self):
        with pytest.raises(ValueError, match="endowment must be positive"):
            config_from_dict({"game": "public_goods", "variant": "classic", "players": 4, "rounds": 5,
                               "endowment": 0.0})

    def test_rejects_multiplier_below_1(self):
        with pytest.raises(ValueError, match="multiplier must be >= 1.0"):
            config_from_dict({"game": "public_goods", "variant": "classic", "players": 4, "rounds": 5,
                               "multiplier": 0.5})

    def test_config_hash_stable(self):
        cfg = config_from_dict({"game": "public_goods", "variant": "classic", "players": 4, "rounds": 5})
        assert cfg.config_hash() == cfg.config_hash()


# ─── Initial state ────────────────────────────────────────────────────────────

class TestInitialState:
    def test_fields(self):
        game = make_game()
        s = game.initial_state()
        assert s.round_number == 1
        assert s.phase == "awaiting_contribution"
        assert sorted(s.awaiting) == ["A", "B", "C", "D"]
        assert s.pending_contributions == {}
        assert s.history == []
        assert s.total_scores == {"A": 0.0, "B": 0.0, "C": 0.0, "D": 0.0}


# ─── Round payoffs ────────────────────────────────────────────────────────────

class TestRoundPayoffs:
    def test_all_contribute_max(self):
        # 4 players × 10 contribution × 2 multiplier = 80 pool → 20 each
        # each player kept 0, payoff = 0 + 20 = 20
        game = make_game()
        s = play_round(game, game.initial_state(), {"A": 10.0, "B": 10.0, "C": 10.0, "D": 10.0})
        entry = s.history[0]
        assert entry["pool"] == pytest.approx(40.0)           # raw sum before multiplier
        assert entry["total_pool"] == pytest.approx(80.0)     # multiplied
        assert entry["share"] == pytest.approx(20.0)
        for p in _ALL_PLAYERS:
            assert entry["round_payoffs"][p] == pytest.approx(20.0)

    def test_all_free_ride(self):
        # All contribute 0: pool=0, share=0, payoff=endowment=10 each
        game = make_game()
        s = play_round(game, game.initial_state(), {"A": 0.0, "B": 0.0, "C": 0.0, "D": 0.0})
        entry = s.history[0]
        assert entry["pool"] == pytest.approx(0.0)
        assert entry["share"] == pytest.approx(0.0)
        for p in _ALL_PLAYERS:
            assert entry["round_payoffs"][p] == pytest.approx(10.0)  # kept all endowment

    def test_asymmetric_contributions(self):
        # A contributes 10, others 0: pool=10×2=20, share=5 each
        # A payoff = 0 + 5 = 5, others = 10 + 5 = 15
        game = make_game()
        s = play_round(game, game.initial_state(), {"A": 10.0, "B": 0.0, "C": 0.0, "D": 0.0})
        entry = s.history[0]
        assert entry["share"] == pytest.approx(5.0)
        assert entry["round_payoffs"]["A"] == pytest.approx(5.0)
        assert entry["round_payoffs"]["B"] == pytest.approx(15.0)


# ─── Multi-round ──────────────────────────────────────────────────────────────

class TestMultiRound:
    def test_cumulative_scores(self):
        game = make_game(num_rounds=2)
        s = game.initial_state()
        s = play_round(game, s, {"A": 10.0, "B": 10.0, "C": 10.0, "D": 10.0})  # each gets 20
        s = play_round(game, s, {"A": 0.0, "B": 0.0, "C": 0.0, "D": 0.0})     # each gets 10
        assert s.total_scores["A"] == pytest.approx(30.0)
        assert s.total_scores["B"] == pytest.approx(30.0)

    def test_terminal_on_last_round(self):
        game = make_game(num_rounds=2)
        s = game.initial_state()
        s = play_round(game, s, {"A": 5.0, "B": 5.0, "C": 5.0, "D": 5.0})
        assert not game.is_terminal(s)
        s = play_round(game, s, {"A": 5.0, "B": 5.0, "C": 5.0, "D": 5.0})
        assert game.is_terminal(s)
        assert s.phase == "complete"

    def test_round_counter_increments(self):
        game = make_game(num_rounds=3)
        s = game.initial_state()
        assert s.round_number == 1
        s = play_round(game, s, {"A": 5.0, "B": 5.0, "C": 5.0, "D": 5.0})
        assert s.round_number == 2

    def test_awaiting_resets_each_round(self):
        game = make_game(num_rounds=2)
        s = play_round(game, game.initial_state(), {"A": 5.0, "B": 5.0, "C": 5.0, "D": 5.0})
        assert sorted(s.awaiting) == ["A", "B", "C", "D"]


# ─── Validation ───────────────────────────────────────────────────────────────

class TestValidation:
    def test_rejects_contribution_above_endowment(self):
        game = make_game()
        s = game.initial_state()
        with pytest.raises(ValueError, match="out of range"):
            game.apply_action(s, "A", 11.0)

    def test_rejects_negative_contribution(self):
        game = make_game()
        s = game.initial_state()
        with pytest.raises(ValueError, match="out of range"):
            game.apply_action(s, "A", -1.0)

    def test_rejects_non_numeric_contribution(self):
        game = make_game()
        s = game.initial_state()
        with pytest.raises(ValueError, match="number"):
            game.apply_action(s, "A", "all")

    def test_rejects_duplicate_submission(self):
        game = make_game()
        s = game.apply_action(game.initial_state(), "A", 5.0)
        with pytest.raises(ValueError, match="already submitted"):
            game.apply_action(s, "A", 5.0)

    def test_rejects_unknown_player(self):
        game = make_game()
        s = game.initial_state()
        with pytest.raises(ValueError, match="unknown player"):
            game.apply_action(s, "Z", 5.0)

    def test_rejects_action_on_complete_game(self):
        game = make_game(num_rounds=1)
        s = play_round(game, game.initial_state(), {"A": 5.0, "B": 5.0, "C": 5.0, "D": 5.0})
        with pytest.raises(ValueError, match="complete"):
            game.apply_action(s, "A", 5.0)


# ─── Results ──────────────────────────────────────────────────────────────────

class TestResults:
    def test_winner_is_free_rider(self):
        # A free rides, others contribute all: A gets most
        game = make_game(num_rounds=1)
        s = play_round(game, game.initial_state(), {"A": 0.0, "B": 10.0, "C": 10.0, "D": 10.0})
        r = game.compute_results(s)
        # A keeps 10 + gets share from others' contributions
        assert r["winner"] == "A"

    def test_raises_if_incomplete(self):
        game = make_game(num_rounds=2)
        s = play_round(game, game.initial_state(), {"A": 5.0, "B": 5.0, "C": 5.0, "D": 5.0})
        with pytest.raises(ValueError, match="not complete"):
            game.compute_results(s)

    def test_includes_metrics(self):
        game = make_game(num_rounds=1)
        s = play_round(game, game.initial_state(), {"A": 5.0, "B": 5.0, "C": 5.0, "D": 5.0})
        r = game.compute_results(s)
        assert "metrics" in r
        assert "avg_contribution" in r["metrics"]

    def test_tie_when_all_equal(self):
        # All contribute equally and have same score
        game = make_game(num_rounds=1)
        s = play_round(game, game.initial_state(), {"A": 5.0, "B": 5.0, "C": 5.0, "D": 5.0})
        r = game.compute_results(s)
        # All have same total → Tie (single winner would be first alphabetically or Tie)
        scores = r["total_scores"]
        assert all(scores[p] == pytest.approx(scores["A"]) for p in ["B", "C", "D"])


# ─── Punishment variant ───────────────────────────────────────────────────────

class TestPunishmentVariant:
    def test_punishment_phase_follows_contribution(self):
        game = make_game(punishment=True, num_rounds=2)
        s = game.initial_state()
        # Contribution phase
        s = play_round(game, s, {"A": 5.0, "B": 5.0, "C": 5.0, "D": 5.0})
        assert s.phase == "awaiting_punishment"
        assert sorted(s.awaiting) == ["A", "B", "C", "D"]

    def test_punishment_phase_no_punishment_advances_round(self):
        game = make_game(punishment=True, num_rounds=2)
        s = game.initial_state()
        s = play_round(game, s, {"A": 5.0, "B": 5.0, "C": 5.0, "D": 5.0})
        # All pass empty punishment dict
        for p in _ALL_PLAYERS:
            s = game.apply_action(s, p, {})
        assert s.round_number == 2
        assert s.phase == "awaiting_contribution"

    def test_without_punishment_no_punishment_phase(self):
        game = make_game(punishment=False, num_rounds=2)
        s = game.initial_state()
        s = play_round(game, s, {"A": 5.0, "B": 5.0, "C": 5.0, "D": 5.0})
        # Should jump straight to next contribution round (or complete if last round)
        assert s.phase in ("awaiting_contribution", "complete")


# ─── Public state ─────────────────────────────────────────────────────────────

class TestPublicState:
    def test_fields(self):
        cfg = config_from_dict({"game": "public_goods", "variant": "classic", "players": 4, "rounds": 5})
        game = PublicGoodsGame.from_config(cfg)
        s = game.initial_state()
        ps = game.public_state(s, cfg, "sess-1", cfg.config_hash())
        assert ps["round"] == 1
        assert ps["round_total"] == 5
        assert sorted(ps["awaiting"]) == ["A", "B", "C", "D"]
        assert ps["endowment"] == 10.0
        assert ps["multiplier"] == 2.0
