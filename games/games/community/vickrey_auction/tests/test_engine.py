import pytest

from games.community.vickrey_auction.config import config_from_dict
from games.community.vickrey_auction.engine import (
    VickreyAuctionGame,
    VickreyAuctionState,
)


def make_game(**kw) -> VickreyAuctionGame:
    kw.setdefault("num_players", 3)
    kw.setdefault("num_rounds", 5)
    return VickreyAuctionGame(**kw)


def play_round(game: VickreyAuctionGame, state: VickreyAuctionState, bids: dict[str, float]) -> VickreyAuctionState:
    for player, bid in bids.items():
        state = game.apply_action(state, player, bid)
    return state


# ─── Config ──────────────────────────────────────────────────────────────────

class TestConfig:
    def test_defaults(self):
        cfg = config_from_dict({"game": "vickrey_auction", "players": 3, "rounds": 10})
        assert cfg.value_min == 0.0
        assert cfg.value_max == 100.0
        assert cfg.max_bid == 200.0
        assert cfg.truthful_tolerance == 1.0
        assert cfg.seed is None

    def test_rejects_players_out_of_range(self):
        with pytest.raises(ValueError, match="2-8 players"):
            config_from_dict({"game": "vickrey_auction", "players": 1, "rounds": 5})
        with pytest.raises(ValueError, match="2-8 players"):
            config_from_dict({"game": "vickrey_auction", "players": 9, "rounds": 5})

    def test_rejects_value_max_leq_value_min(self):
        with pytest.raises(ValueError, match="value_max must be > value_min"):
            config_from_dict({"game": "vickrey_auction", "players": 3, "rounds": 5,
                               "value_min": 50.0, "value_max": 50.0})

    def test_rejects_max_bid_below_value_max(self):
        with pytest.raises(ValueError, match="max_bid must be >= value_max"):
            config_from_dict({"game": "vickrey_auction", "players": 3, "rounds": 5,
                               "value_max": 100.0, "max_bid": 50.0})

    def test_rejects_negative_truthful_tolerance(self):
        with pytest.raises(ValueError, match="truthful_tolerance"):
            config_from_dict({"game": "vickrey_auction", "players": 3, "rounds": 5,
                               "truthful_tolerance": -1.0})

    def test_rejects_negative_value_min(self):
        with pytest.raises(ValueError, match="value_min"):
            config_from_dict({"game": "vickrey_auction", "players": 3, "rounds": 5, "value_min": -5.0})

    def test_player_ids_scale_with_players(self):
        cfg = config_from_dict({"game": "vickrey_auction", "players": 5, "rounds": 5})
        assert cfg.player_ids() == ["A", "B", "C", "D", "E"]

    def test_config_hash_stable(self):
        cfg1 = config_from_dict({"game": "vickrey_auction", "players": 3, "rounds": 5, "seed": 7})
        cfg2 = config_from_dict({"game": "vickrey_auction", "players": 3, "rounds": 5, "seed": 7})
        assert cfg1.config_hash() == cfg2.config_hash()


# ─── Initial state ────────────────────────────────────────────────────────────

class TestInitialState:
    def test_fields(self):
        game = make_game(num_players=3)
        s = game.initial_state()
        assert s.round_number == 1
        assert s.phase == "awaiting_action"
        assert sorted(s.awaiting) == ["A", "B", "C"]
        assert s.pending_bids == {}
        assert s.history == []
        assert s.total_scores == {"A": 0.0, "B": 0.0, "C": 0.0}
        assert set(s.private_values.keys()) == {"A", "B", "C"}

    def test_values_within_bounds(self):
        game = make_game(num_players=4, value_min=10.0, value_max=20.0, seed=1)
        s = game.initial_state()
        for v in s.private_values.values():
            assert 10.0 <= v <= 20.0


# ─── Round resolution ──────────────────────────────────────────────────────────

class TestRoundResolution:
    def test_highest_bidder_wins_and_pays_second_price(self):
        game = make_game(num_players=3, num_rounds=2)
        state = game.initial_state()
        state.private_values = {"A": 50.0, "B": 30.0, "C": 80.0}
        state = play_round(game, state, {"A": 50.0, "B": 30.0, "C": 100.0})
        entry = state.history[0]
        assert entry["winner"] == "C"
        assert entry["price"] == pytest.approx(50.0)
        assert entry["payoffs"]["C"] == pytest.approx(30.0)  # value 80 - price 50
        assert entry["payoffs"]["A"] == pytest.approx(0.0)
        assert entry["payoffs"]["B"] == pytest.approx(0.0)

    def test_winners_curse_from_overbidding(self):
        game = make_game(num_players=3, num_rounds=2)
        state = game.initial_state()
        state.private_values = {"A": 60.0, "B": 70.0, "C": 40.0}
        state = play_round(game, state, {"A": 60.0, "B": 70.0, "C": 100.0})
        entry = state.history[0]
        assert entry["winner"] == "C"
        assert entry["price"] == pytest.approx(70.0)
        assert entry["payoffs"]["C"] == pytest.approx(-30.0)  # value 40 - price 70

    def test_truthful_bidding_never_produces_negative_payoff_for_winner(self):
        game = make_game(num_players=3, num_rounds=2)
        state = game.initial_state()
        state.private_values = {"A": 50.0, "B": 30.0, "C": 80.0}
        state = play_round(game, state, {"A": 50.0, "B": 30.0, "C": 80.0})
        entry = state.history[0]
        assert entry["winner"] == "C"
        assert entry["payoffs"]["C"] >= 0.0

    def test_tied_top_bids_price_equals_the_tied_bid(self):
        game = make_game(num_players=3, num_rounds=2, seed=3)
        state = game.initial_state()
        state.private_values = {"A": 50.0, "B": 50.0, "C": 30.0}
        state = play_round(game, state, {"A": 50.0, "B": 50.0, "C": 30.0})
        entry = state.history[0]
        assert entry["winner"] in ("A", "B")
        assert entry["price"] == pytest.approx(50.0)

    def test_cumulative_scores(self):
        game = make_game(num_players=2, num_rounds=2)
        state = game.initial_state()
        state.private_values = {"A": 50.0, "B": 30.0}
        state = play_round(game, state, {"A": 50.0, "B": 30.0})
        state.private_values = {"A": 20.0, "B": 90.0}
        state = play_round(game, state, {"A": 20.0, "B": 90.0})
        assert state.total_scores["A"] == pytest.approx(20.0)  # won round 1: 50-30
        assert state.total_scores["B"] == pytest.approx(70.0)  # won round 2: 90-20

    def test_terminal_on_last_round(self):
        game = make_game(num_players=2, num_rounds=2)
        state = game.initial_state()
        state = play_round(game, state, {"A": 10.0, "B": 5.0})
        assert not game.is_terminal(state)
        state = play_round(game, state, {"A": 10.0, "B": 5.0})
        assert game.is_terminal(state)
        assert state.phase == "complete"

    def test_values_redrawn_each_round(self):
        game = make_game(num_players=2, num_rounds=2, seed=5)
        state = game.initial_state()
        first_values = dict(state.private_values)
        state = play_round(game, state, {"A": 10.0, "B": 5.0})
        assert state.round_number == 2
        assert set(state.private_values.keys()) == set(first_values.keys())
        assert state.private_values != first_values

    def test_pending_bids_cleared_after_round(self):
        game = make_game(num_players=2, num_rounds=2)
        state = game.initial_state()
        state = play_round(game, state, {"A": 10.0, "B": 5.0})
        assert state.pending_bids == {}

    def test_awaiting_resets_each_round(self):
        game = make_game(num_players=3, num_rounds=2)
        state = game.initial_state()
        state = play_round(game, state, {"A": 10.0, "B": 5.0, "C": 1.0})
        assert sorted(state.awaiting) == ["A", "B", "C"]


# ─── Validation ───────────────────────────────────────────────────────────────

class TestValidation:
    def test_rejects_negative_bid(self):
        game = make_game()
        state = game.initial_state()
        with pytest.raises(ValueError, match="out of range"):
            game.apply_action(state, "A", -1.0)

    def test_rejects_bid_above_max_bid(self):
        game = make_game(max_bid=200.0)
        state = game.initial_state()
        with pytest.raises(ValueError, match="out of range"):
            game.apply_action(state, "A", 500.0)

    def test_rejects_non_numeric_bid(self):
        game = make_game()
        state = game.initial_state()
        with pytest.raises(ValueError, match="must be a number"):
            game.apply_action(state, "A", "high")

    def test_rejects_duplicate_submission(self):
        game = make_game()
        state = game.initial_state()
        state = game.apply_action(state, "A", 10.0)
        with pytest.raises(ValueError, match="already submitted"):
            game.apply_action(state, "A", 20.0)

    def test_rejects_unknown_player(self):
        game = make_game(num_players=2)
        state = game.initial_state()
        with pytest.raises(ValueError, match="unknown player"):
            game.apply_action(state, "Z", 10.0)

    def test_rejects_action_on_complete_game(self):
        game = make_game(num_players=2, num_rounds=1)
        state = play_round(game, game.initial_state(), {"A": 10.0, "B": 5.0})
        assert game.is_terminal(state)
        with pytest.raises(ValueError, match="complete"):
            game.apply_action(state, "A", 10.0)


# ─── Forfeit ──────────────────────────────────────────────────────────────────

class TestForfeit:
    def test_forfeit_submits_zero_bid(self):
        game = make_game(num_players=3, num_rounds=2)
        state = game.initial_state()
        state.private_values = {"A": 50.0, "B": 30.0, "C": 80.0}
        state = game.forfeit_round(state, "A")
        assert "A" not in state.awaiting
        state = play_round(game, state, {"B": 30.0, "C": 80.0})
        entry = state.history[0]
        assert entry["actions"]["A"] == pytest.approx(0.0)
        assert entry["forfeits"] == ["A"]


# ─── Results ──────────────────────────────────────────────────────────────────

class TestResults:
    def test_winner_is_highest_total_score(self):
        game = make_game(num_players=2, num_rounds=1)
        state = game.initial_state()
        state.private_values = {"A": 80.0, "B": 20.0}
        state = play_round(game, state, {"A": 80.0, "B": 20.0})
        r = game.compute_results(state)
        assert r["winner"] == "A"

    def test_tie(self):
        game = make_game(num_players=2, num_rounds=1)
        state = game.initial_state()
        state.private_values = {"A": 0.0, "B": 0.0}
        state = play_round(game, state, {"A": 0.0, "B": 0.0})
        r = game.compute_results(state)
        assert r["winner"] == "Tie"

    def test_raises_if_incomplete(self):
        game = make_game(num_players=2, num_rounds=2)
        state = play_round(game, game.initial_state(), {"A": 10.0, "B": 5.0})
        with pytest.raises(ValueError, match="not complete"):
            game.compute_results(state)

    def test_includes_metrics(self):
        game = make_game(num_players=2, num_rounds=1)
        state = play_round(game, game.initial_state(), {"A": 10.0, "B": 5.0})
        r = game.compute_results(state)
        assert "metrics" in r
        assert "bid_shading" in r["metrics"]


# ─── State serialization ──────────────────────────────────────────────────────

class TestStateSerialization:
    def test_roundtrip(self):
        game = make_game(num_players=2, num_rounds=3)
        state = play_round(game, game.initial_state(), {"A": 10.0, "B": 5.0})
        state2 = game.state_from_dict(state.__dict__)
        assert state2.round_number == state.round_number
        assert state2.total_scores == state.total_scores
        assert state2.history == state.history


# ─── Public state ─────────────────────────────────────────────────────────────

class TestPublicState:
    def test_fields(self):
        cfg = config_from_dict({"game": "vickrey_auction", "players": 3, "rounds": 5})
        game = VickreyAuctionGame.from_config(cfg)
        state = game.initial_state()
        ps = game.public_state(state, cfg, "sess-1", cfg.config_hash())
        assert ps["round"] == 1
        assert ps["round_total"] == 5
        assert sorted(ps["awaiting"]) == ["A", "B", "C"]
        assert "total_scores" in ps
        assert "private_values" in ps
        assert set(ps["private_values"].keys()) == {"A", "B", "C"}
        assert ps["value_max"] == 100.0
        assert ps["max_bid"] == 200.0
