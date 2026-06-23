"""Tests for :mod:`outplaylabs_arena_sdk.parsers`."""
from __future__ import annotations


from outplaylabs_arena_sdk.parsers import (
    _balanced_allocation,
    parse_accept_reject,
    parse_allocation,
    parse_choice,
    parse_offer,
    parse_poker_action,
    parse_quantity,
)


class TestParseAllocation:
    def test_valid(self):
        assert parse_allocation("[10, 20, 30, 40]", 4, 100) == [10, 20, 30, 40]

    def test_with_surrounding_text(self):
        assert parse_allocation("I choose [1, 2, 3]", 3, 6) == [1, 2, 3]

    def test_invalid_text_returns_balanced(self):
        result = parse_allocation("invalid", 3, 100)
        assert len(result) == 3
        assert sum(result) == 100

    def test_wrong_length_returns_balanced(self):
        result = parse_allocation("[10, 20]", 3, 100)
        assert len(result) == 3

    def test_wrong_sum_returns_balanced(self):
        result = parse_allocation("[10, 20, 30]", 3, 100)
        assert len(result) == 3
        assert sum(result) == 100

    def test_negative_values_rejected(self):
        result = parse_allocation("[-10, 50, 60]", 3, 100)
        assert len(result) == 3
        assert sum(result) == 100

    def test_bool_values_rejected(self):
        """bool is a subclass of int in Python; the parser must reject True/False."""
        result = parse_allocation("[True, False, True]", 3, 100)
        assert len(result) == 3
        assert sum(result) == 100

    def test_mixed_types_rejected(self):
        result = parse_allocation("[10, '20', 30]", 3, 60)
        assert len(result) == 3
        assert sum(result) == 60

    def test_empty_list(self):
        result = parse_allocation("[]", 0, 0)
        assert result == []


class TestBalancedAllocation:
    def test_even_split(self):
        assert _balanced_allocation(4, 100) == [25, 25, 25, 25]

    def test_uneven_split(self):
        result = _balanced_allocation(3, 10)
        assert result == [4, 3, 3]
        assert sum(result) == 10

    def test_single_field(self):
        assert _balanced_allocation(1, 50) == [50]

    def test_zero_fields(self):
        assert _balanced_allocation(0, 10) == []


class TestParseOffer:
    def test_valid(self):
        assert parse_offer("I offer 42", 100) == 42.0

    def test_no_number_uses_default(self):
        assert parse_offer("no number here", 100) == 40.0

    def test_clamped_to_total(self):
        assert parse_offer("I offer 200", 100) == 100.0

    def test_clamped_to_min(self):
        assert parse_offer("I offer 0.5", 100, min_offer=1.0) == 1.0

    def test_decimal_offer(self):
        assert parse_offer("I offer 12.5", 100) == 12.5


class TestParseAcceptReject:
    def test_accept(self):
        assert parse_accept_reject("I accept this offer") == "accept"

    def test_reject(self):
        assert parse_accept_reject("I reject this") == "reject"

    def test_case_insensitive(self):
        assert parse_accept_reject("ACCEPT") == "accept"
        assert parse_accept_reject("REJECT") == "reject"

    def test_default_is_reject(self):
        assert parse_accept_reject("nothing useful") == "reject"


class TestParseChoice:
    def test_first_option(self):
        assert parse_choice("I will cooperate", ["cooperate", "defect"]) == "cooperate"

    def test_second_option(self):
        assert parse_choice("I will defect now", ["cooperate", "defect"]) == "defect"

    def test_no_match_returns_default(self):
        assert parse_choice("garbage", ["a", "b"], default="b") == "b"

    def test_no_match_no_default_returns_first(self):
        assert parse_choice("garbage", ["a", "b"]) == "a"

    def test_case_insensitive(self):
        assert parse_choice("ROCK wins", ["rock", "paper", "scissors"]) == "rock"


class TestParseQuantity:
    def test_simple(self):
        assert parse_quantity("I produce 25 units", max_quantity=100) == 25.0

    def test_clamps_to_max(self):
        assert parse_quantity("I produce 200 units", max_quantity=100) == 100.0

    def test_clamps_to_zero(self):
        assert parse_quantity("I produce -5 units", max_quantity=100) == 0.0

    def test_no_number_returns_default(self):
        assert parse_quantity("nothing", max_quantity=100, default=42) == 42

    def test_no_number_no_default(self):
        result = parse_quantity("nothing", max_quantity=100)
        assert result == 50.0  # 100 * 0.5


class TestParsePokerAction:
    def test_check(self):
        move, amount = parse_poker_action("I check", ["check", "call", "bet", "raise"])
        assert move == "check"
        assert amount == 0.0

    def test_fold(self):
        move, amount = parse_poker_action("I fold my hand", ["check", "fold", "bet"])
        assert move == "fold"
        assert amount == 0.0

    def test_bet(self):
        move, amount = parse_poker_action("I bet 50", ["check", "call", "bet", "raise"])
        assert move == "bet"
        assert amount == 50.0

    def test_raise(self):
        move, amount = parse_poker_action("raise 25", ["check", "call", "bet", "raise"])
        assert move == "raise"
        assert amount == 25.0

    def test_unknown_returns_default(self):
        move, amount = parse_poker_action("garbage", ["check", "bet"], default_move="check")
        assert move == "check"
        assert amount == 0.0

    def test_all_in_no_amount(self):
        move, amount = parse_poker_action("all in", ["check", "call", "all_in", "bet"])
        assert move == "all_in"
        assert amount == 0.0
