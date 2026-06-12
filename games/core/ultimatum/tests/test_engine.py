import pytest
from games.core.ultimatum.config import config_from_dict
from games.core.ultimatum.engine import UltimatumGame, UltimatumState


def make_game(**kw) -> UltimatumGame:
    return UltimatumGame(
        num_rounds=kw.get("num_rounds", 4),
        total=kw.get("total", 100.0),
        min_offer=kw.get("min_offer", 1.0),
    )


def play_round(game: UltimatumGame, state: UltimatumState,
               offer: float, response: str) -> UltimatumState:
    proposer = state.proposer
    responder = state.responder
    state = game.apply_action(state, proposer, offer)
    state = game.apply_action(state, responder, response)
    return state


# ─── Config ──────────────────────────────────────────────────────────────────

class TestConfig:
    def test_defaults(self):
        cfg = config_from_dict({"game": "ultimatum", "players": 2, "rounds": 10})
        assert cfg.total == 100.0
        assert cfg.min_offer == 1.0

    def test_custom_total(self):
        cfg = config_from_dict({"game": "ultimatum", "players": 2, "rounds": 5, "total": 50.0})
        assert cfg.total == 50.0

    def test_rejects_zero_total(self):
        with pytest.raises(ValueError, match="total must be positive"):
            config_from_dict({"game": "ultimatum", "players": 2, "rounds": 5, "total": 0.0})

    def test_rejects_zero_min_offer(self):
        with pytest.raises(ValueError, match="min_offer must be positive"):
            config_from_dict({"game": "ultimatum", "players": 2, "rounds": 5, "min_offer": 0.0})

    def test_rejects_invalid_player_count(self):
        with pytest.raises(ValueError, match="2 players"):
            config_from_dict({"game": "ultimatum", "players": 3, "rounds": 5})

    def test_player_ids(self):
        cfg = config_from_dict({"game": "ultimatum", "players": 2, "rounds": 5})
        assert cfg.player_ids() == ["A", "B"]

    def test_config_hash_stable(self):
        cfg = config_from_dict({"game": "ultimatum", "players": 2, "rounds": 5, "seed": 7})
        assert cfg.config_hash() == cfg.config_hash()


# ─── Initial state ────────────────────────────────────────────────────────────

class TestInitialState:
    def test_fields(self):
        game = make_game()
        s = game.initial_state()
        assert s.round_number == 1
        assert s.phase == "awaiting_proposal"
        assert s.proposer == "A"        # odd round → A proposes
        assert s.responder == "B"
        assert s.awaiting == ["A"]
        assert s.pending_offer is None
        assert s.history == []
        assert s.total_scores == {"A": 0.0, "B": 0.0}

    def test_proposer_alternates_round_2(self):
        game = make_game(num_rounds=4)
        s = game.initial_state()
        s = play_round(game, s, 40.0, "accept")
        assert s.proposer == "B"        # even round → B proposes
        assert s.responder == "A"
        assert s.phase == "awaiting_proposal"


# ─── Offer acceptance ─────────────────────────────────────────────────────────

class TestOfferAcceptance:
    def test_accept_splits_correctly(self):
        game = make_game(num_rounds=2)
        s = game.initial_state()  # A proposes
        s = game.apply_action(s, "A", 40.0)   # offer 40 to B
        s = game.apply_action(s, "B", "accept")
        entry = s.history[0]
        assert entry["accepted"] is True
        assert entry["payoffs"]["A"] == pytest.approx(60.0)  # total - offer
        assert entry["payoffs"]["B"] == pytest.approx(40.0)  # offer

    def test_reject_gives_zero(self):
        game = make_game(num_rounds=2)
        s = game.initial_state()
        s = game.apply_action(s, "A", 40.0)
        s = game.apply_action(s, "B", "reject")
        entry = s.history[0]
        assert entry["accepted"] is False
        assert entry["payoffs"]["A"] == pytest.approx(0.0)
        assert entry["payoffs"]["B"] == pytest.approx(0.0)

    def test_offer_fraction_recorded(self):
        game = make_game(num_rounds=2)
        s = game.initial_state()
        s = game.apply_action(s, "A", 25.0)
        s = game.apply_action(s, "B", "accept")
        entry = s.history[0]
        assert entry["offer_fraction"] == pytest.approx(0.25)

    def test_phase_transitions_correctly(self):
        game = make_game(num_rounds=2)
        s = game.initial_state()
        assert s.phase == "awaiting_proposal"
        s = game.apply_action(s, "A", 40.0)
        assert s.phase == "awaiting_response"
        assert s.awaiting == ["B"]
        s = game.apply_action(s, "B", "accept")
        # Round advanced to round 2
        assert s.phase == "awaiting_proposal"
        assert s.round_number == 2

    def test_zero_offer_accepted(self):
        game = make_game(num_rounds=2)
        s = game.initial_state()
        s = game.apply_action(s, "A", 0.0)
        s = game.apply_action(s, "B", "accept")
        assert s.history[0]["payoffs"]["A"] == pytest.approx(100.0)
        assert s.history[0]["payoffs"]["B"] == pytest.approx(0.0)


# ─── Multi-round ──────────────────────────────────────────────────────────────

class TestMultiRound:
    def test_cumulative_scores_all_accept(self):
        # Round 1: A proposes 40 → B accepts → A=60, B=40
        # Round 2: B proposes 50 → A accepts → A=50, B=50
        game = make_game(num_rounds=2)
        s = game.initial_state()
        s = play_round(game, s, 40.0, "accept")   # A proposes
        s = play_round(game, s, 50.0, "accept")   # B proposes
        assert s.total_scores["A"] == pytest.approx(110.0)
        assert s.total_scores["B"] == pytest.approx(90.0)

    def test_terminal_on_last_round(self):
        game = make_game(num_rounds=2)
        s = game.initial_state()
        s = play_round(game, s, 40.0, "accept")
        assert not game.is_terminal(s)
        s = play_round(game, s, 40.0, "accept")
        assert game.is_terminal(s)

    def test_round_counter_increments(self):
        game = make_game(num_rounds=4)
        s = game.initial_state()
        assert s.round_number == 1
        s = play_round(game, s, 40.0, "accept")
        assert s.round_number == 2


# ─── Validation ───────────────────────────────────────────────────────────────

class TestValidation:
    def test_rejects_offer_above_total(self):
        game = make_game()
        s = game.initial_state()
        with pytest.raises(ValueError, match="offer must be"):
            game.apply_action(s, "A", 101.0)

    def test_rejects_invalid_response(self):
        game = make_game()
        s = game.initial_state()
        s = game.apply_action(s, "A", 40.0)
        with pytest.raises(ValueError, match="accept"):
            game.apply_action(s, "B", "maybe")

    def test_rejects_wrong_player_in_proposal_phase(self):
        game = make_game()
        s = game.initial_state()
        # B should not propose in round 1
        with pytest.raises(ValueError, match="not expected"):
            game.apply_action(s, "B", 40.0)

    def test_rejects_wrong_player_in_response_phase(self):
        game = make_game()
        s = game.initial_state()
        s = game.apply_action(s, "A", 40.0)
        with pytest.raises(ValueError, match="not expected"):
            game.apply_action(s, "A", "accept")

    def test_rejects_unknown_player(self):
        game = make_game()
        s = game.initial_state()
        with pytest.raises(ValueError, match="unknown player"):
            game.apply_action(s, "C", 40.0)

    def test_rejects_action_on_complete_game(self):
        game = make_game(num_rounds=1)
        s = play_round(game, game.initial_state(), 40.0, "accept")
        with pytest.raises(ValueError, match="complete"):
            game.apply_action(s, "A", 40.0)


# ─── Results ──────────────────────────────────────────────────────────────────

class TestResults:
    def test_winner_a(self):
        # A proposes 1 (minimum), B accepts → A=99, B=1
        game = make_game(num_rounds=1)
        s = play_round(game, game.initial_state(), 1.0, "accept")
        r = game.compute_results(s)
        assert r["winner"] == "A"

    def test_winner_b(self):
        # A proposes 99, B accepts → A=1, B=99
        game = make_game(num_rounds=1)
        s = play_round(game, game.initial_state(), 99.0, "accept")
        r = game.compute_results(s)
        assert r["winner"] == "B"

    def test_raises_if_incomplete(self):
        game = make_game(num_rounds=2)
        s = play_round(game, game.initial_state(), 40.0, "accept")
        with pytest.raises(ValueError, match="not complete"):
            game.compute_results(s)

    def test_includes_metrics(self):
        game = make_game(num_rounds=1)
        s = play_round(game, game.initial_state(), 40.0, "accept")
        r = game.compute_results(s)
        assert "metrics" in r
        assert "avg_offer_fraction" in r["metrics"]
        assert "acceptance_rate" in r["metrics"]


# ─── State serialization ──────────────────────────────────────────────────────

class TestStateSerialization:
    def test_roundtrip(self):
        game = make_game(num_rounds=4)
        s = play_round(game, game.initial_state(), 40.0, "accept")
        s2 = game.state_from_dict(s.__dict__)
        assert s2.round_number == s.round_number
        assert s2.total_scores == s.total_scores
        assert s2.history == s.history
        assert s2.proposer == s.proposer


# ─── Public state ─────────────────────────────────────────────────────────────

class TestPublicState:
    def test_fields(self):
        cfg = config_from_dict({"game": "ultimatum", "players": 2, "rounds": 5})
        game = UltimatumGame.from_config(cfg)
        s = game.initial_state()
        ps = game.public_state(s, cfg, "sess-1", cfg.config_hash())
        assert ps["round"] == 1
        assert ps["round_total"] == 5
        assert ps["phase"] == "awaiting_proposal"
        assert ps["proposer"] == "A"
        assert ps["responder"] == "B"
        assert ps["total"] == 100.0
        assert ps["pending_offer"] is None
