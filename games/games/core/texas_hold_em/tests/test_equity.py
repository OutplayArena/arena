import pytest

from games.core.texas_hold_em.equity import hand_equity, preflop_equity_for_hand


def test_single_live_player_has_certain_equity():
    assert hand_equity({"A": ["Ah", "Kh"]}, [], ["A"]) == {"A": 1.0}


def test_no_live_players_returns_empty():
    assert hand_equity({}, [], []) == {}


def test_river_equity_is_exact_and_deterministic():
    """With all 5 community cards known, there's no completion to enumerate:
    equity must be exactly 1.0 for the actual winner, 0.0 for the loser."""
    hole = {"A": ["Ah", "Ad"], "B": ["2h", "3d"]}
    community = ["Ac", "Ks", "Qs", "7d", "2c"]  # A has trip aces, B has a pair of 2s
    eq = hand_equity(hole, community, ["A", "B"])
    assert eq["A"] == pytest.approx(1.0)
    assert eq["B"] == pytest.approx(0.0)


def test_river_tie_splits_equity():
    # Both play the same board (no better hand from either hole card pair):
    # board is a straight A-2-3-4-5 and both hole cards are irrelevant low cards.
    hole = {"A": ["2c", "3c"], "B": ["2d", "3d"]}
    community = ["Ah", "Kh", "Qh", "Jh", "Th"]  # royal flush on board, plays for both
    eq = hand_equity(hole, community, ["A", "B"])
    assert eq["A"] == pytest.approx(0.5)
    assert eq["B"] == pytest.approx(0.5)


def test_turn_equity_sums_to_one_across_players():
    hole = {"A": ["Ah", "Ad"], "B": ["Kc", "Kd"], "C": ["7h", "2d"]}
    community = ["As", "2h", "9c", "3d"]  # turn: 1 card left (exact enumeration)
    eq = hand_equity(hole, community, ["A", "B", "C"])
    assert set(eq.keys()) == {"A", "B", "C"}
    assert sum(eq.values()) == pytest.approx(1.0)
    # A already has trip aces on the turn -- should be a big favorite over
    # both B (one pair, kings) and C (one pair, deuces).
    assert eq["A"] > eq["B"]
    assert eq["A"] > eq["C"]


def test_flop_equity_sums_to_one():
    hole = {"A": ["Ah", "Ad"], "B": ["7c", "2d"]}
    community = ["As", "Kh", "9c"]  # flop: 2 cards left (exact enumeration, 990 combos)
    eq = hand_equity(hole, community, ["A", "B"])
    assert sum(eq.values()) == pytest.approx(1.0)
    assert eq["A"] > 0.9  # already flopped trips, hard to catch


def test_preflop_equity_is_approximately_correct_for_a_coinflip():
    """AK vs QQ preflop heads-up is a well-known near-coinflip (roughly
    43-57%); Monte Carlo with enough trials should land in a wide but sane
    band around that, confirming the sampler isn't systematically biased."""
    hole = {"A": ["Ah", "Kh"], "B": ["Qc", "Qd"]}
    eq = hand_equity(hole, [], ["A", "B"], mc_trials=1500, seed=42)
    assert sum(eq.values()) == pytest.approx(1.0, abs=1e-6)
    assert 0.30 < eq["A"] < 0.65
    assert 0.35 < eq["B"] < 0.70


def test_preflop_equity_favors_pocket_aces_heavily_over_random_hand():
    hole = {"A": ["Ah", "As"], "B": ["7c", "2d"]}
    eq = hand_equity(hole, [], ["A", "B"], mc_trials=1500, seed=7)
    assert eq["A"] > 0.75


def test_preflop_equity_for_hand_covers_all_dealt_players():
    hole = {"A": ["Ah", "As"], "B": ["7c", "2d"], "C": ["Kd", "Kc"]}
    eq = preflop_equity_for_hand(hole, ["A", "B", "C"], mc_trials=300, seed=1)
    assert set(eq.keys()) == {"A", "B", "C"}
    assert sum(eq.values()) == pytest.approx(1.0)
