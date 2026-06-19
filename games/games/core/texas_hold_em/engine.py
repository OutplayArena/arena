from __future__ import annotations

import random
from copy import deepcopy
from dataclasses import dataclass, field
from itertools import combinations

from nash_arena.game_engine import GameEngine
from games.core.texas_hold_em.metrics import TexasHoldEmMetrics

RANKS = "23456789TJQKA"
SUITS = "hdcs"
DECK = [r + s for r in RANKS for s in SUITS]
RANK_VALUES = {r: i for i, r in enumerate(RANKS)}

ANTE = 1
BET_SIZE = 2
STARTING_CHIPS = 100.0

_HAND_NAMES = [
    "high_card", "one_pair", "two_pair", "three_of_a_kind",
    "straight", "flush", "full_house", "four_of_a_kind",
    "straight_flush", "royal_flush",
]
_STREET_ORDER = ["preflop", "flop", "turn", "river"]
VALID_ACTIONS = frozenset({"fold", "check", "call", "raise"})


def _rank_val(card: str) -> int:
    return RANK_VALUES[card[0]]


def _suit(card: str) -> str:
    return card[1]


def _evaluate_5(cards: list[str]) -> tuple[int, list[int]]:
    ranks = sorted((_rank_val(c) for c in cards), reverse=True)
    suits = [_suit(c) for c in cards]
    rank_counts = {}
    for r in ranks:
        rank_counts[r] = rank_counts.get(r, 0) + 1
    counts = sorted(rank_counts.values(), reverse=True)
    is_flush = len(set(suits)) == 1
    is_straight = False
    straight_high = 0
    unique_ranks = sorted(set(ranks), reverse=True)
    if len(unique_ranks) == 5 and unique_ranks[0] - unique_ranks[4] == 4:
        is_straight = True
        straight_high = unique_ranks[0]
    if set(ranks) == {12, 3, 2, 1, 0}:
        is_straight = True
        straight_high = 3
    if is_flush and is_straight:
        return (9, []) if straight_high == 12 else (8, [straight_high])
    if counts == [4, 1]:
        q = next(r for r, c in rank_counts.items() if c == 4)
        k = next(r for r, c in rank_counts.items() if c == 1)
        return (7, [q, k])
    if counts == [3, 2]:
        t = next(r for r, c in rank_counts.items() if c == 3)
        p = next(r for r, c in rank_counts.items() if c == 2)
        return (6, [t, p])
    if is_flush:
        return (5, ranks)
    if is_straight:
        return (4, [straight_high])
    if counts == [3, 1, 1]:
        t = next(r for r, c in rank_counts.items() if c == 3)
        ks = sorted((r for r in ranks if r != t), reverse=True)
        return (3, [t] + ks)
    if counts == [2, 2, 1]:
        ps = sorted((r for r, c in rank_counts.items() if c == 2), reverse=True)
        k = next(r for r, c in rank_counts.items() if c == 1)
        return (2, ps + [k])
    if counts == [2, 1, 1, 1]:
        p = next(r for r, c in rank_counts.items() if c == 2)
        ks = sorted((r for r in ranks if r != p), reverse=True)
        return (1, [p] + ks)
    return (0, ranks)


def _best_hand(hole: list[str], community: list[str]) -> tuple[int, list[int], list[str]]:
    all_cards = hole + community
    if len(all_cards) < 5:
        return (0, [], [])
    best_score = (-1, [])
    best_5 = []
    for combo in combinations(all_cards, 5):
        score = _evaluate_5(list(combo))
        if score > best_score:
            best_score = score
            best_5 = list(combo)
    return (best_score[0], best_score[1], best_5)


def _hand_name(score: int) -> str:
    return _HAND_NAMES[score]


def _make_deck(seed: int | None) -> list[str]:
    deck = list(DECK)
    random.Random(seed).shuffle(deck)
    return deck


def _next_street(current: str) -> str | None:
    idx = _STREET_ORDER.index(current)
    return _STREET_ORDER[idx + 1] if idx + 1 < len(_STREET_ORDER) else None


def _community_count(street: str) -> int:
    return {"preflop": 0, "flop": 3, "turn": 4, "river": 5}[street]


def _to_call(hand_start: dict, chips: dict, player: str) -> float:
    opp = "B" if player == "A" else "A"
    player_committed = hand_start[player] - chips[player]
    opp_committed = hand_start[opp] - chips[opp]
    return max(0.0, opp_committed - player_committed)


@dataclass
class TexasHoldEmState:
    round_number: int
    phase: str
    awaiting: list[str]
    pending_actions: dict[str, str]
    history: list[dict]
    total_scores: dict[str, float]
    hand_number: int
    street: str
    deck: list[str]
    hole_cards: dict[str, list[str]]
    community_cards: list[str]
    chips: dict[str, float]
    hand_start_chips: dict[str, float]
    pot: float
    current_player: str
    street_actions: list[dict]
    last_raise: float
    raised_this_street: list[str]
    hand_over: bool
    hand_result: dict | None = None
    final_hand_pot: float = 0.0
    messages: list = field(default_factory=list)


class TexasHoldEmGame(GameEngine):
    def __init__(self, num_rounds: int = 10, seed: int | None = None):
        self.num_rounds = num_rounds
        self.seed = seed
        self.metrics_engine = TexasHoldEmMetrics()

    @classmethod
    def from_config(cls, config) -> TexasHoldEmGame:
        return cls(num_rounds=config.rounds, seed=config.seed)

    def _deal_new_hand(self, hand_number: int) -> tuple[list[str], dict, list[str]]:
        s = (self.seed or 0) + hand_number
        deck = _make_deck(s)
        return deck[4:], {"A": deck[0:2], "B": deck[2:4]}, []

    def initial_state(self) -> TexasHoldEmState:
        deck, hole, _ = self._deal_new_hand(1)
        start_chips = {"A": STARTING_CHIPS, "B": STARTING_CHIPS}
        state = TexasHoldEmState(
            round_number=1, phase="awaiting_action",
            awaiting=["A"], pending_actions={}, history=[],
            total_scores={"A": 0.0, "B": 0.0},
            hand_number=1, street="preflop",
            deck=deck, hole_cards=hole, community_cards=[],
            chips=dict(start_chips), hand_start_chips={},
            pot=0.0, current_player="A",
            street_actions=[], last_raise=0.0,
            raised_this_street=[], hand_over=False,
        )
        for p in ("A", "B"):
            state.chips[p] -= ANTE
        state.pot = ANTE * 2
        state.hand_start_chips = dict(state.chips)
        return state

    def state_from_dict(self, d: dict) -> TexasHoldEmState:
        if "hand_start_chips" not in d:
            d["hand_start_chips"] = dict(d.get("chips", {"A": STARTING_CHIPS, "B": STARTING_CHIPS}))
        if "final_hand_pot" not in d:
            d["final_hand_pot"] = 0.0
        return TexasHoldEmState(**d)

    def validate_action(self, action) -> bool:
        return isinstance(action, str) and action in VALID_ACTIONS

    def validate_player_action(self, state: TexasHoldEmState, player: str, action) -> bool:
        if state.phase == "complete":
            raise ValueError("game is already complete")
        if player not in ("A", "B"):
            raise ValueError(f"unknown player: {player!r}")
        if player not in state.awaiting:
            raise ValueError(f"player {player!r} is not on turn")
        if not self.validate_action(action):
            raise ValueError(f"invalid action {action!r}")
        tc = _to_call(state.hand_start_chips, state.chips, player)
        if action == "check" and tc > 0:
            raise ValueError("cannot check when facing a bet")
        if action == "call" and tc == 0:
            raise ValueError("cannot call when no bet to match, try check")
        if action == "call" and state.chips[player] < tc:
            raise ValueError("not enough chips to call")
        if action == "raise":
            if player in state.raised_this_street:
                raise ValueError("cannot raise twice on same street")
            if state.chips[player] < BET_SIZE:
                raise ValueError("not enough chips to raise")
        return True

    def apply_action(self, state: TexasHoldEmState, player: str, action: str) -> TexasHoldEmState:
        self.validate_player_action(state, player, action)
        state = deepcopy(state)
        state.pending_actions[player] = action
        state.awaiting = [p for p in state.awaiting if p != player]
        return self._process_action(state, player, action)

    def _process_action(self, state: TexasHoldEmState, player: str, action: str) -> TexasHoldEmState:
        opp = "B" if player == "A" else "A"
        tc = _to_call(state.hand_start_chips, state.chips, player)
        entry = {"player": player, "action": action, "street": state.street}

        if action == "fold":
            state.final_hand_pot = state.pot
            state.chips[opp] += state.pot
            state.pot = 0
            state.street_actions.append(entry)
            state.hand_result = {"outcome": "fold", "winner": opp}
            return self._finalize_hand(state)

        if action == "check":
            state.street_actions.append(entry)
            return self._advance_if_done(state, opp)

        if action == "call":
            actual_cost = min(tc, state.chips[player])
            state.chips[player] -= actual_cost
            state.pot += actual_cost
            entry["bet"] = actual_cost
            state.street_actions.append(entry)
            return self._advance_if_done(state, opp)

        if action == "raise":
            cost = BET_SIZE + tc
            state.chips[player] -= cost
            state.pot += cost
            state.raised_this_street.append(player)
            entry["bet"] = cost
            state.street_actions.append(entry)
            return self._advance_if_done(state, opp)

        return state

    def _advance_if_done(self, state: TexasHoldEmState, opp: str) -> TexasHoldEmState:
        if self._street_is_complete(state):
            return self._advance_street(state)
        state.awaiting = [opp]
        state.current_player = opp
        state.pending_actions = {}
        return state

    def _street_is_complete(self, state: TexasHoldEmState) -> bool:
        sa = state.street_actions
        if not sa:
            return False
        last_a = sa[-1]["action"]
        if last_a == "fold":
            return True
        if len(sa) < 2:
            return False
        prev_a = sa[-2]["action"]
        if last_a == "call":
            return True
        if last_a == "check" and prev_a == "check":
            return True
        return False

    def _advance_street(self, state: TexasHoldEmState) -> TexasHoldEmState:
        ns = _next_street(state.street)
        if ns is None:
            return self._do_showdown(state)
        state.street = ns
        state.raised_this_street = []
        state.last_raise = 0.0
        state.street_actions = []
        need = _community_count(ns)
        dc = need - len(state.community_cards)
        state.community_cards = state.community_cards + state.deck[:dc]
        state.deck = state.deck[dc:]
        state.current_player = "B"
        state.awaiting = ["B"]
        state.pending_actions = {}
        return state

    def _do_showdown(self, state: TexasHoldEmState) -> TexasHoldEmState:
        state.final_hand_pot = state.pot
        ra, ka, h5a = _best_hand(state.hole_cards["A"], state.community_cards)
        rb, kb, h5b = _best_hand(state.hole_cards["B"], state.community_cards)
        if (ra, ka) > (rb, kb):
            w, pot_a, pot_b = "A", state.pot, 0.0
        elif (rb, kb) > (ra, ka):
            w, pot_a, pot_b = "B", 0.0, state.pot
        else:
            w, pot_a, pot_b = "Tie", state.pot / 2, state.pot / 2
        state.chips["A"] += pot_a
        state.chips["B"] += pot_b
        state.hand_result = {
            "outcome": "showdown", "winner": w,
            "community": list(state.community_cards),
            "hand_a": {"cards": h5a, "hand": _hand_name(ra)},
            "hand_b": {"cards": h5b, "hand": _hand_name(rb)},
        }
        state.pot = 0
        return self._finalize_hand(state)

    def _finalize_hand(self, state: TexasHoldEmState) -> TexasHoldEmState:
        state.total_scores = {
            "A": state.chips["A"] - STARTING_CHIPS,
            "B": state.chips["B"] - STARTING_CHIPS,
        }
        state.history.append({
            "hand": state.hand_number,
            "street_actions": list(state.street_actions),
            "hole_cards": dict(state.hole_cards),
            "community_cards": list(state.community_cards),
            "result": state.hand_result,
            "chips_after": dict(state.chips),
            "pot": state.final_hand_pot,
            "street": state.street,
            "total_scores": dict(state.total_scores),
        })
        if state.hand_number >= self.num_rounds:
            state.phase = "complete"
            state.awaiting = []
            return state
        n = state.hand_number + 1
        deck, hole, _ = self._deal_new_hand(n)
        state.round_number = n
        state.hand_number = n
        state.street = "preflop"
        state.deck = deck
        state.hole_cards = hole
        state.community_cards = []
        state.street_actions = []
        state.last_raise = 0.0
        state.raised_this_street = []
        state.hand_over = False
        state.hand_result = None
        state.awaiting = ["A"]
        state.pending_actions = {}
        state.current_player = "A"
        pot_ante = 0.0
        for p in ("A", "B"):
            actual = min(ANTE, max(0.0, state.chips[p]))
            state.chips[p] -= actual
            pot_ante += actual
        state.pot = pot_ante
        state.hand_start_chips = dict(state.chips)
        return state

    def is_terminal(self, state: TexasHoldEmState) -> bool:
        return state.phase == "complete"

    def compute_results(self, state: TexasHoldEmState,
                        session_id: str | None = None,
                        config_hash: str | None = None) -> dict:
        if not self.is_terminal(state):
            raise ValueError("game is not complete")
        fc = state.history[-1]["chips_after"] if state.history else state.chips
        sa, sb = fc["A"] - STARTING_CHIPS, fc["B"] - STARTING_CHIPS
        w = "A" if sa > sb else ("B" if sb > sa else "Tie")
        r = {
            "total_scores": {"A": sa, "B": sb}, "winner": w,
            "history": list(state.history),
            "metrics": self.metrics_engine.compute(state.history, {"A": sa, "B": sb}),
        }
        if session_id:
            r["session_id"] = session_id
        if config_hash:
            r["config_hash"] = config_hash
        return r

    def public_state(self, state: TexasHoldEmState, config,
                     session_id: str, config_hash: str) -> dict:
        return {
            "session_id": session_id, "config_hash": config_hash,
            "round": state.hand_number, "round_total": self.num_rounds,
            "phase": state.phase, "awaiting": list(state.awaiting),
            "total_scores": dict(state.total_scores),
            "history": list(state.history),
            "hole_cards": dict(state.hole_cards),
            "community_cards": list(state.community_cards),
            "chips": dict(state.chips), "hand_start_chips": dict(state.hand_start_chips),
            "pot": state.pot,
            "street": state.street, "current_player": state.current_player,
            "street_actions": list(state.street_actions),
            "hand_number": state.hand_number,
            "messages": self.communication_log(state),
            "communication_config": self.communication_config().to_dict(),
        }

    def forfeit_round(self, state: TexasHoldEmState, player: str) -> TexasHoldEmState:
        opp = "B" if player == "A" else "A"
        state = deepcopy(state)
        state.final_hand_pot = state.pot
        state.chips[opp] += state.pot
        state.pot = 0
        state.total_scores = {
            "A": state.chips["A"] - STARTING_CHIPS,
            "B": state.chips["B"] - STARTING_CHIPS,
        }
        state.hand_result = {"outcome": "forfeit", "winner": opp, "forfeit_by": player}
        state.history.append({
            "hand": state.hand_number, "street_actions": list(state.street_actions),
            "hole_cards": dict(state.hole_cards),
            "community_cards": list(state.community_cards),
            "result": state.hand_result, "chips_after": dict(state.chips),
            "pot": state.final_hand_pot, "street": state.street,
            "total_scores": dict(state.total_scores),
        })
        if state.hand_number >= self.num_rounds:
            state.phase = "complete"
            state.awaiting = []
            return state
        n = state.hand_number + 1
        deck, hole, _ = self._deal_new_hand(n)
        state.round_number = n
        state.hand_number = n
        state.street = "preflop"
        state.deck = deck
        state.hole_cards = hole
        state.community_cards = []
        state.street_actions = []
        state.last_raise = 0.0
        state.raised_this_street = []
        state.hand_over = False
        state.hand_result = None
        state.awaiting = ["A"]
        state.pending_actions = {}
        state.current_player = "A"
        pot_ante = 0.0
        for p in ("A", "B"):
            actual = min(ANTE, max(0.0, state.chips[p]))
            state.chips[p] -= actual
            pot_ante += actual
        state.pot = pot_ante
        state.hand_start_chips = dict(state.chips)
        return state
