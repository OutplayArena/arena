import pytest
from games.core.texas_hold_em.config import config_from_dict
from games.core.texas_hold_em.engine import (
    TexasHoldEmGame, _evaluate_5, _best_hand, _to_call, STARTING_CHIPS, ANTE, BET_SIZE,
)


def make_game(rounds: int = 3) -> TexasHoldEmGame:
    cfg = config_from_dict({"game": "texas_hold_em", "variant": "classic", "players": 2, "rounds": rounds})
    return TexasHoldEmGame.from_config(cfg)


def make_n_player_game(players: int, rounds: int = 1, seed: int | None = 1) -> TexasHoldEmGame:
    cfg = config_from_dict({
        "game": "texas_hold_em", "variant": "classic",
        "players": players, "rounds": rounds, "seed": seed,
    })
    return TexasHoldEmGame.from_config(cfg)


def play_actions(game, state, actions: list[tuple[str, str]]):
    for player, action in actions:
        state = game.apply_action(state, player, action)
    return state


def test_config_from_dict():
    cfg = config_from_dict({"game": "texas_hold_em", "variant": "classic", "players": 2, "rounds": 5})
    assert cfg.rounds == 5
    assert cfg.player_ids() == ["A", "B"]


def test_config_hash_is_deterministic():
    cfg1 = config_from_dict({"game": "texas_hold_em", "rounds": 10})
    cfg2 = config_from_dict({"game": "texas_hold_em", "rounds": 10})
    assert cfg1.config_hash() == cfg2.config_hash()


def test_config_rejects_unknown_variant():
    with pytest.raises(ValueError, match="variant"):
        config_from_dict({"game": "texas_hold_em", "variant": "omaha", "rounds": 5})


def test_evaluate_royal_flush():
    s, _ = _evaluate_5(["Ah", "Kh", "Qh", "Jh", "Th"])
    assert s == 9


def test_evaluate_straight_flush():
    s, _ = _evaluate_5(["9s", "8s", "7s", "6s", "5s"])
    assert s == 8


def test_evaluate_four_of_a_kind():
    s, _ = _evaluate_5(["Ah", "Ad", "Ac", "As", "Kh"])
    assert s == 7


def test_evaluate_full_house():
    s, _ = _evaluate_5(["Kh", "Kd", "Kc", "Qs", "Qh"])
    assert s == 6


def test_evaluate_flush():
    s, _ = _evaluate_5(["Ah", "Th", "7h", "4h", "2h"])
    assert s == 5


def test_evaluate_straight():
    s, _ = _evaluate_5(["9h", "8d", "7c", "6s", "5h"])
    assert s == 4


def test_evaluate_three_of_a_kind():
    s, _ = _evaluate_5(["7h", "7d", "7c", "Ks", "Qh"])
    assert s == 3


def test_evaluate_two_pair():
    s, _ = _evaluate_5(["Jh", "Jd", "4c", "4s", "Ks"])
    assert s == 2


def test_evaluate_one_pair():
    s, _ = _evaluate_5(["9h", "9d", "Kc", "Qs", "2h"])
    assert s == 1


def test_evaluate_high_card():
    s, _ = _evaluate_5(["Ah", "Kd", "Qc", "Js", "9h"])
    assert s == 0


def test_evaluate_ace_low_straight():
    s, k = _evaluate_5(["Ah", "2d", "3c", "4s", "5h"])
    assert s == 4
    assert k == [3]


def test_best_hand_royal_flush():
    r, _, _ = _best_hand(["Ah", "Kh"], ["Qh", "Jh", "Th", "9d", "2c"])
    assert r == 9


def test_best_hand_prefers_flush_over_pair():
    r, _, _ = _best_hand(["2h", "7h"], ["Ah", "Kh", "Qh", "Jh", "9s"])
    assert r == 5
    

def test_initial_state():
    game = make_game()
    state = game.initial_state()
    assert state.hand_number == 1
    assert state.street == "preflop"
    assert state.phase == "awaiting_action"
    assert state.awaiting == ["A"]
    assert game.is_terminal(state) is False
    assert len(state.hole_cards["A"]) == 2
    assert len(state.hole_cards["B"]) == 2
    assert state.chips == {"A": STARTING_CHIPS - ANTE, "B": STARTING_CHIPS - ANTE}
    assert state.pot == ANTE * 2


def test_a_folds_b_wins_pot():
    game = make_game(rounds=1)
    state = game.initial_state()
    state = game.apply_action(state, "A", "fold")
    assert game.is_terminal(state)
    h = state.history[0]
    assert h["result"]["outcome"] == "fold"
    assert h["result"]["winner"] == "B"
    assert h["chips_after"]["B"] == STARTING_CHIPS - ANTE + ANTE * 2
    assert h["chips_after"]["A"] == STARTING_CHIPS - ANTE


def test_b_folds_a_wins_pot():
    game = make_game(rounds=1)
    state = game.initial_state()
    state = play_actions(game, state, [("A", "check")])
    state = play_actions(game, state, [("B", "fold")])
    assert game.is_terminal(state)
    h = state.history[0]
    assert h["result"]["winner"] == "A"


def test_sequential_check_check_all_streets():
    game = make_game(rounds=1)
    state = game.initial_state()
    # preflop: A checks, B checks → flop
    state = play_actions(game, state, [("A", "check"), ("B", "check")])
    assert state.street == "flop"
    assert len(state.community_cards) == 3
    assert state.current_player == "B"
    # flop: B checks, A checks → turn
    state = play_actions(game, state, [("B", "check"), ("A", "check")])
    assert state.street == "turn"
    assert len(state.community_cards) == 4
    # turn: B checks, A checks → river
    state = play_actions(game, state, [("B", "check"), ("A", "check")])
    assert state.street == "river"
    assert len(state.community_cards) == 5
    # river: B checks, A checks → showdown
    state = play_actions(game, state, [("B", "check"), ("A", "check")])
    assert game.is_terminal(state)
    h = state.history[0]
    assert h["result"]["outcome"] == "showdown"


def test_raise_call_preflop():
    game = make_game(rounds=1)
    state = game.initial_state()
    # A raises (cost = BET_SIZE + 0 = 2), B calls (cost = to_call)
    chips_before = dict(state.chips)
    pot_before = state.pot
    state = play_actions(game, state, [("A", "raise")])
    assert state.chips["A"] == chips_before["A"] - BET_SIZE
    assert state.pot == pot_before + BET_SIZE
    state = play_actions(game, state, [("B", "call")])
    # After call, B matches the difference
    assert state.street == "flop"
    assert len(state.community_cards) == 3


# Multi hand tests
def test_two_hands_accumulate():
    game = make_game(rounds=2)
    state = game.initial_state()
    state = play_actions(game, state, [("A", "fold")])  # hand 1
    assert state.hand_number == 2
    assert len(state.history) == 1
    state = play_actions(game, state, [("A", "fold")])  # hand 2
    assert game.is_terminal(state)
    assert len(state.history) == 2


def test_total_scores_track_chip_profit():
    game = make_game(rounds=1)
    state = game.initial_state()
    state = play_actions(game, state, [("A", "fold")])
    results = game.compute_results(state)
    # A lost 1 ante, B won 2 pot - 1 ante = 1 profit
    assert results["total_scores"]["A"] == -ANTE
    assert results["total_scores"]["B"] == ANTE


def test_tie_showdown():
    game = make_game(rounds=1)
    state = game.initial_state()
    state = play_actions(game, state, [
        ("A", "check"), ("B", "check"),
        ("B", "check"), ("A", "check"),
        ("B", "check"), ("A", "check"),
        ("B", "check"), ("A", "check"),
    ])
    assert game.is_terminal(state)


# ── Results ───────────────────────────────────────────────────────────────────

def test_compute_results_has_metrics():
    game = make_game(rounds=1)
    state = game.initial_state()
    state = play_actions(game, state, [("A", "fold")])
    results = game.compute_results(state)
    assert "metrics" in results
    assert "total_payoff" in results["metrics"]


def test_compute_results_raises_if_not_terminal():
    game = make_game()
    state = game.initial_state()
    with pytest.raises(ValueError, match="not complete"):
        game.compute_results(state)


# ── Validation ────────────────────────────────────────────────────────────────

def test_invalid_action_raises():
    game = make_game()
    state = game.initial_state()
    with pytest.raises(ValueError):
        game.apply_action(state, "A", "bluff")


def test_invalid_player_raises():
    game = make_game()
    state = game.initial_state()
    with pytest.raises(ValueError):
        game.apply_action(state, "C", "fold")


def test_wrong_turn_raises():
    game = make_game()
    state = game.initial_state()
    with pytest.raises(ValueError, match="not on turn"):
        game.apply_action(state, "B", "fold")


def test_cannot_check_facing_bet():
    game = make_game()
    state = game.initial_state()
    state = play_actions(game, state, [("A", "raise")])
    with pytest.raises(ValueError, match="cannot check"):
        game.apply_action(state, "B", "check")


def test_cannot_call_when_no_bet():
    game = make_game()
    state = game.initial_state()
    with pytest.raises(ValueError, match="cannot call"):
        game.apply_action(state, "A", "call")


def test_cannot_raise_twice():
    game = make_game()
    state = game.initial_state()
    state = play_actions(game, state, [("A", "raise")])
    state = play_actions(game, state, [("B", "raise")])
    with pytest.raises(ValueError, match="cannot raise twice"):
        game.apply_action(state, "A", "raise")


def test_cannot_act_after_game_complete():
    game = make_game(rounds=1)
    state = game.initial_state()
    state = play_actions(game, state, [("A", "fold")])
    with pytest.raises(ValueError, match="already complete"):
        game.apply_action(state, "A", "fold")


# ── Public state ──────────────────────────────────────────────────────────────

def test_public_state_keys():
    cfg = config_from_dict({"game": "texas_hold_em", "rounds": 5, "seed": 1})
    game = TexasHoldEmGame.from_config(cfg)
    state = game.initial_state()
    ps = game.public_state(state, cfg, "sess-1", "hash-1")
    for key in ("street", "chips", "pot", "current_player", "hole_cards",
                "community_cards", "street_actions", "hand_number"):
        assert key in ps


# ── Forfeit ───────────────────────────────────────────────────────────────────

def test_forfeit_hand():
    game = make_game(rounds=2)
    state = game.initial_state()
    state = game.forfeit_round(state, "A")
    assert len(state.history) == 1
    assert state.history[0]["result"]["outcome"] == "forfeit"
    assert state.history[0]["result"]["winner"] == "B"
    assert state.hand_number == 2


def test_forfeit_ends_game():
    game = make_game(rounds=1)
    state = game.initial_state()
    state = game.forfeit_round(state, "A")
    assert game.is_terminal(state)


# ── State serialisation ───────────────────────────────────────────────────────

def test_state_from_dict_round_trip():
    game = make_game(rounds=3)
    state = game.initial_state()
    state = play_actions(game, state, [("A", "fold")])
    d = {
        "round_number": state.round_number,
        "phase": state.phase,
        "awaiting": state.awaiting,
        "pending_actions": state.pending_actions,
        "history": state.history,
        "total_scores": state.total_scores,
        "hand_number": state.hand_number,
        "street": state.street,
        "deck": state.deck,
        "hole_cards": state.hole_cards,
        "community_cards": state.community_cards,
        "chips": state.chips,
        "pot": state.pot,
        "current_player": state.current_player,
        "street_actions": state.street_actions,
        "last_raise": state.last_raise,
        "raised_this_street": state.raised_this_street,
        "hand_over": state.hand_over,
        "hand_result": state.hand_result,
    }
    restored = game.state_from_dict(d)
    assert restored.hand_number == state.hand_number
    assert restored.chips == state.chips
    assert restored.hole_cards == state.hole_cards
    assert restored.street == state.street


# ── Betting flow ──────────────────────────────────────────────────────────────

def test_to_call_helper():
    hs = {"A": 99.0, "B": 99.0}
    live = ["A", "B"]
    assert _to_call(hs, {"A": 97.0, "B": 99.0}, "B", live) == 2.0
    assert _to_call(hs, {"A": 99.0, "B": 97.0}, "A", live) == 2.0
    assert _to_call(hs, {"A": 99.0, "B": 99.0}, "A", live) == 0.0
    assert _to_call(hs, {"A": 99.0, "B": 99.0}, "B", live) == 0.0


def test_to_call_ignores_prior_winnings():
    hs = {"A": 101.0, "B": 97.0}
    live = ["A", "B"]
    assert _to_call(hs, {"A": 101.0, "B": 97.0}, "A", live) == 0.0
    assert _to_call(hs, {"A": 101.0, "B": 97.0}, "B", live) == 0.0
    assert _to_call(hs, {"A": 99.0, "B": 97.0}, "B", live) == 2.0


def test_to_call_ignores_folded_players_earlier_bet():
    """A folded player's earlier commitment shouldn't set the bar for
    remaining live players (N-player generalization)."""
    hs = {"A": 99.0, "B": 99.0, "C": 99.0}
    # C folded after committing more than A or B; only live players matter.
    assert _to_call(hs, {"A": 97.0, "B": 97.0, "C": 90.0}, "A", ["A", "B"]) == 0.0


def test_raise_then_fold():
    game = make_game(rounds=1)
    state = game.initial_state()
    state = play_actions(game, state, [("A", "raise"), ("B", "fold")])
    assert game.is_terminal(state)
    assert state.history[0]["result"]["winner"] == "A"


def test_flop_b_acts_first():
    game = make_game(rounds=1)
    state = game.initial_state()
    state = play_actions(game, state, [("A", "check"), ("B", "check")])
    # After flop: B acts first
    assert state.awaiting == ["B"]
    assert state.current_player == "B"


def test_street_advance_with_community_cards():
    game = make_game(rounds=1)
    state = game.initial_state()
    state = play_actions(game, state, [("A", "check"), ("B", "check")])
    assert state.street == "flop"
    assert len(state.community_cards) == 3
    state = play_actions(game, state, [("B", "check"), ("A", "check")])
    assert state.street == "turn"
    assert len(state.community_cards) == 4
    state = play_actions(game, state, [("B", "check"), ("A", "check")])
    assert state.street == "river"
    assert len(state.community_cards) == 5


# ── Bug fix: _to_call with prior winnings ──────────────────────────────────────

def test_multi_hand_betting_not_inflated():
    game = make_game(rounds=3)
    state = game.initial_state()
    state = play_actions(game, state, [
        ("A", "check"), ("B", "check"),
        ("B", "check"), ("A", "check"),
        ("B", "check"), ("A", "check"),
        ("B", "check"), ("A", "check"),
    ])
    assert state.hand_number == 2
    start = dict(state.hand_start_chips)
    assert start["A"] > 0 and start["B"] > 0
    state = play_actions(game, state, [("A", "raise")])
    tc_b = _to_call(state.hand_start_chips, state.chips, "B", ["A", "B"])
    assert tc_b == BET_SIZE


# ── Bug fix: chip exhaustion ──────────────────────────────────────────────────

def test_cannot_call_with_insufficient_chips():
    game = make_game(rounds=10)
    state = game.initial_state()
    state = play_actions(game, state, [("A", "raise"), ("B", "raise")])
    state.chips["A"] = 0.5
    state.hand_start_chips["A"] = state.chips["A"] + 3.0
    with pytest.raises(ValueError, match="not enough chips to call"):
        game.apply_action(state, "A", "call")


# ── Bug fix: ante affordability ───────────────────────────────────────────────

def test_ante_at_low_chips():
    game = make_game(rounds=2)
    state = game.initial_state()
    state.chips["A"] = 0.0
    state = play_actions(game, state, [("A", "fold")])
    assert state.hand_number == 2
    assert state.chips["A"] == 0.0
    assert state.chips["B"] >= STARTING_CHIPS - ANTE - ANTE


# ── State compat ───────────────────────────────────────────────────────────────

def test_state_from_dict_without_hand_start():
    game = make_game()
    d = {
        "round_number": 1, "phase": "awaiting_action",
        "awaiting": ["A"], "pending_actions": {}, "history": [],
        "total_scores": {"A": 0.0, "B": 0.0},
        "hand_number": 1, "street": "preflop",
        "deck": [], "hole_cards": {"A": [], "B": []}, "community_cards": [],
        "chips": {"A": 99.0, "B": 99.0},
        "pot": 2.0, "current_player": "A",
        "street_actions": [], "last_raise": 0.0,
        "raised_this_street": [], "hand_over": False,
        "hand_result": None,
    }
    restored = game.state_from_dict(d)
    assert restored.hand_start_chips == {"A": 99.0, "B": 99.0}


# ── N-player support (#41) ────────────────────────────────────────────────────

def test_config_supports_2_to_6_players():
    for n in (2, 3, 4, 5, 6):
        cfg = config_from_dict({"game": "texas_hold_em", "players": n, "rounds": 1})
        assert cfg.player_ids() == [chr(ord("A") + i) for i in range(n)]


def test_config_rejects_out_of_range_player_counts():
    with pytest.raises(ValueError, match="2-6 players"):
        config_from_dict({"game": "texas_hold_em", "players": 1, "rounds": 1})
    with pytest.raises(ValueError, match="2-6 players"):
        config_from_dict({"game": "texas_hold_em", "players": 7, "rounds": 1})


def test_three_player_initial_deal():
    game = make_n_player_game(3)
    state = game.initial_state()
    assert state.player_ids == ["A", "B", "C"]
    assert len(state.hole_cards["A"]) == 2
    assert len(state.hole_cards["B"]) == 2
    assert len(state.hole_cards["C"]) == 2
    # Hole cards must be disjoint.
    all_hole = state.hole_cards["A"] + state.hole_cards["B"] + state.hole_cards["C"]
    assert len(set(all_hole)) == 6
    assert state.chips == {"A": STARTING_CHIPS - ANTE, "B": STARTING_CHIPS - ANTE, "C": STARTING_CHIPS - ANTE}
    assert state.pot == ANTE * 3


def test_three_player_preflop_first_actor_is_left_of_button():
    """With 3+ players (no blinds), action starts left of the button on every
    street including preflop -- unlike heads-up, where the button acts first
    preflop as a special case."""
    game = make_n_player_game(3)
    state = game.initial_state()
    assert state.awaiting == ["B"]


def test_three_player_postflop_first_actor_is_left_of_button():
    game = make_n_player_game(3)
    state = game.initial_state()
    state = play_actions(game, state, [("B", "check"), ("C", "check"), ("A", "check")])
    assert state.street == "flop"
    assert state.awaiting == ["B"]


def test_three_player_turn_order_skips_folded_player():
    game = make_n_player_game(3)
    state = game.initial_state()
    state = play_actions(game, state, [("B", "fold")])
    assert state.awaiting == ["C"]
    assert "B" in state.folded
    assert not game.is_terminal(state)


def test_fold_down_to_last_live_player_ends_hand():
    game = make_n_player_game(3, rounds=1)
    state = game.initial_state()
    state = play_actions(game, state, [("B", "fold"), ("C", "fold")])
    assert game.is_terminal(state)
    result = state.history[0]["result"]
    assert result["outcome"] == "fold"
    assert result["winner"] == "A"


def test_raise_reopens_action_for_players_who_already_acted():
    """A raise must reopen action for players who already checked/called this
    street, not just move to the immediate next seat."""
    game = make_n_player_game(3, rounds=1)
    state = game.initial_state()
    # Preflop, n=3: B acts first.
    state = play_actions(game, state, [("B", "check")])
    assert state.awaiting == ["C"]
    state = play_actions(game, state, [("C", "raise")])
    # A hasn't acted yet, but B (who already checked) must also get a chance
    # to respond to C's raise before the street can close.
    assert state.awaiting == ["A"]
    state = play_actions(game, state, [("A", "call")])
    assert state.awaiting == ["B"]
    assert state.street == "preflop"
    state = play_actions(game, state, [("B", "call")])
    assert state.street == "flop"


def test_forfeit_with_three_players_continues_game():
    game = make_n_player_game(3, rounds=1)
    state = game.initial_state()
    state = game.forfeit_round(state, "B")
    assert "B" in state.folded
    assert not game.is_terminal(state)
    assert state.awaiting == ["C"]


def test_forfeit_down_to_last_player_ends_hand():
    game = make_n_player_game(3, rounds=1)
    state = game.initial_state()
    state = game.forfeit_round(state, "B")
    state = game.forfeit_round(state, "C")
    assert game.is_terminal(state)
    assert state.history[0]["result"]["outcome"] == "forfeit"
    assert state.history[0]["result"]["winner"] == "A"


def test_side_pot_short_stack_only_wins_eligible_layer():
    """C is short-stacked and all-in for less than A/B's later flop bet. C has
    the best hand, so C must win the (smaller) pot they're eligible for, but
    NOT the side pot built from A/B's extra flop betting, which they never
    covered."""
    game = make_n_player_game(3, rounds=1, seed=7)
    state = game.initial_state()

    # C had 3 chips before ante (1 -> 2 after ante), everyone else starts full.
    state.hand_start_chips_pre_ante["C"] = 3.0
    state.chips["C"] = 2.0
    state.hand_start_chips["C"] = 2.0

    state = play_actions(game, state, [("B", "raise"), ("C", "call"), ("A", "call")])
    assert "C" in state.all_in
    assert state.street == "flop"
    pot_at_allin = state.pot

    state = play_actions(game, state, [("B", "raise"), ("A", "call")])
    assert state.street == "turn"
    state = play_actions(game, state, [("B", "check"), ("A", "check")])
    state = play_actions(game, state, [("B", "check"), ("A", "check")])
    assert game.is_terminal(state)

    result = state.history[0]["result"]
    assert result["outcome"] == "showdown"
    pots = result["pots"]
    # Two layers: the pot C could contest, and a side pot only A/B covered.
    assert len(pots) == 2
    main_pot, side_pot = pots
    assert main_pot["amount"] == pytest.approx(pot_at_allin)
    assert set(main_pot["eligible"]) == {"A", "B", "C"}
    assert set(side_pot["eligible"]) == {"A", "B"}
    assert "C" not in side_pot["winners"]
    # Whole-hand pot is fully distributed: no chips vanish or get double-paid.
    total_awarded = sum(p["amount"] for p in pots)
    assert total_awarded == pytest.approx(state.history[0]["pot"])


def test_showdown_result_has_generic_per_player_hands():
    game = make_n_player_game(3, rounds=1)
    state = game.initial_state()
    state = play_actions(game, state, [
        ("B", "check"), ("C", "check"), ("A", "check"),
        ("B", "check"), ("C", "check"), ("A", "check"),
        ("B", "check"), ("C", "check"), ("A", "check"),
        ("B", "check"), ("C", "check"), ("A", "check"),
    ])
    assert game.is_terminal(state)
    result = state.history[0]["result"]
    assert result["outcome"] == "showdown"
    assert set(result["hands"].keys()) == {"A", "B", "C"}
    for h in result["hands"].values():
        assert "cards" in h and "hand" in h
    assert result["winner"] in ("A", "B", "C", "Tie")


def test_all_in_preflop_deals_out_remaining_streets_without_further_action():
    """Once everyone remaining is all-in, no more betting is possible: the
    engine must deal straight through to showdown in the same apply_action
    call, rather than leaving `awaiting` empty with nobody able to move the
    game forward."""
    game = make_game(rounds=1)
    state = game.initial_state()
    state.chips = {"A": 2.0, "B": 2.0}
    state.hand_start_chips = {"A": 2.0, "B": 2.0}
    state.hand_start_chips_pre_ante = {"A": 3.0, "B": 3.0}

    state = play_actions(game, state, [("A", "raise")])
    assert "A" in state.all_in
    state = play_actions(game, state, [("B", "call")])

    assert "B" in state.all_in
    assert game.is_terminal(state)
    result = state.history[0]["result"]
    assert result["outcome"] == "showdown"
    assert len(result["community"]) == 5


def test_street_actions_accumulate_across_the_whole_hand():
    """street_actions must record every street's actions, not just the last
    completed street (issue #24: History/metrics under-counted fold/raise
    rates because earlier streets' actions were discarded on each street
    reset)."""
    game = make_game(rounds=1)
    state = game.initial_state()
    state = play_actions(game, state, [
        ("A", "check"), ("B", "check"),   # preflop
        ("B", "check"), ("A", "check"),   # flop
        ("B", "check"), ("A", "check"),   # turn
        ("B", "check"), ("A", "check"),   # river -> showdown
    ])
    assert game.is_terminal(state)
    recorded = state.history[0]["street_actions"]
    assert len(recorded) == 8
    streets_seen = {a["street"] for a in recorded}
    assert streets_seen == {"preflop", "flop", "turn", "river"}


def test_compute_hand_equity_is_off_by_default():
    game = make_game(rounds=1)
    state = game.initial_state()
    state = play_actions(game, state, [("A", "fold")])
    assert "preflop_equity" not in state.history[0]


def test_compute_hand_equity_opt_in_populates_history():
    cfg = config_from_dict({
        "game": "texas_hold_em", "players": 2, "rounds": 1,
        "seed": 1, "compute_hand_equity": True,
    })
    game = TexasHoldEmGame.from_config(cfg)
    state = game.initial_state()
    state = play_actions(game, state, [("A", "fold")])
    equity = state.history[0]["preflop_equity"]
    assert set(equity.keys()) == {"A", "B"}
    assert equity["A"] + equity["B"] == pytest.approx(1.0)


def test_compute_results_generalizes_winner_over_n_players():
    game = make_n_player_game(4, rounds=1)
    state = game.initial_state()
    state = play_actions(game, state, [("B", "fold"), ("C", "fold"), ("D", "fold")])
    results = game.compute_results(state)
    assert results["winner"] == "A"
    assert set(results["total_scores"].keys()) == {"A", "B", "C", "D"}
