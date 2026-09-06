from __future__ import annotations

import random
from copy import deepcopy
from dataclasses import dataclass, field
from itertools import combinations

from arena.interactive_game_engine import InteractiveGameEngine
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
DEFAULT_PLAYER_IDS = ["A", "B"]


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


def _to_call(hand_start: dict, chips: dict, player: str, live_players: list[str]) -> float:
    """Amount `player` must add to match the largest total commitment this hand
    among still-live players (folded players' earlier bets don't set the bar)."""
    committed = {p: hand_start.get(p, 0.0) - chips.get(p, 0.0) for p in live_players}
    if not committed:
        return 0.0
    own = committed.get(player, hand_start.get(player, 0.0) - chips.get(player, 0.0))
    return max(0.0, max(committed.values()) - own)


def _seat_after(player_ids: list[str], p: str) -> str:
    idx = player_ids.index(p)
    return player_ids[(idx + 1) % len(player_ids)]


def _first_eligible_from(player_ids: list[str], to_act: list[str], start: str) -> str | None:
    """First player in `to_act`, walking seat order starting at `start` (inclusive)."""
    if not to_act:
        return None
    pending = set(to_act)
    idx = player_ids.index(start)
    n = len(player_ids)
    for offset in range(n):
        cand = player_ids[(idx + offset) % n]
        if cand in pending:
            return cand
    return None


def _build_side_pots(
    contrib: dict[str, float], folded: set[str], player_ids: list[str]
) -> list[dict]:
    """
    Standard side-pot layering.

    `contrib` is each player's total chips committed this hand (folded players
    included — their chips stay in the pot even though they can't win it).
    Returns pots in ascending-commitment order, each ``{"amount", "eligible"}``.
    A pot with a single eligible player represents an uncalled excess bet,
    which the showdown logic below correctly returns to that player without
    needing a separate "uncalled bet" special case.
    """
    levels = sorted({v for v in contrib.values() if v > 1e-9})
    pots = []
    prev = 0.0
    for level in levels:
        layer_per_player = level - prev
        contributors = [p for p in player_ids if contrib.get(p, 0.0) >= level - 1e-9]
        amount = round(layer_per_player * len(contributors), 2)
        if amount > 1e-9:
            eligible = [p for p in contributors if p not in folded]
            pots.append({"amount": amount, "eligible": eligible})
        prev = level
    return pots


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
    player_ids: list[str] = field(default_factory=lambda: list(DEFAULT_PLAYER_IDS))
    folded: list[str] = field(default_factory=list)
    all_in: list[str] = field(default_factory=list)
    to_act: list[str] = field(default_factory=list)
    button_index: int = 0
    # Chips each player had *before* this hand's ante was deducted. Used only
    # at showdown to compute each player's total hand contribution (ante
    # included) for side-pot layering -- `hand_start_chips` above is captured
    # *after* the ante and is deliberately used for `_to_call` instead, since
    # the ante shouldn't count toward what a player owes to call a bet.
    hand_start_chips_pre_ante: dict[str, float] = field(default_factory=dict)


class TexasHoldEmGame(InteractiveGameEngine):
    def __init__(
        self,
        num_rounds: int = 10,
        seed: int | None = None,
        player_ids: list[str] | None = None,
        compute_hand_equity: bool = False,
    ):
        self.num_rounds = num_rounds
        self.seed = seed
        self.player_ids = list(player_ids) if player_ids else list(DEFAULT_PLAYER_IDS)
        self.compute_hand_equity = compute_hand_equity
        self.metrics_engine = TexasHoldEmMetrics()

    @classmethod
    def from_config(cls, config) -> TexasHoldEmGame:
        player_ids = config.player_ids() if hasattr(config, "player_ids") else None
        return cls(
            num_rounds=config.rounds,
            seed=config.seed,
            player_ids=player_ids,
            compute_hand_equity=getattr(config, "compute_hand_equity", False),
        )

    def human_action_schema(self, config):
        return {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["fold", "call", "raise", "check"],
                    "description": "Poker action",
                },
                "raise_amount": {
                    "type": "number",
                    "minimum": 0,
                    "description": "Raise amount (only if action is 'raise')",
                }
            },
            "required": ["action"],
        }

    def format_human_action(self, raw_action, config):
        if isinstance(raw_action, str):
            return raw_action.lower()
        if isinstance(raw_action, dict):
            action = raw_action.get("action", "").lower()
            if action == "raise" and "raise_amount" in raw_action:
                return {
                    "action": action,
                    "raise_amount": float(raw_action["raise_amount"]),
                }
            return action
        return str(raw_action).lower()

    def ui_metadata(self, config):
        return {
            "input_type": "poker",
            "actions": ["fold", "call", "raise", "check"],
            "layout": "texas_hold_em",
        }

    def get_available_agents(self, config):
        return [
            {"id": "random", "label": "Random", "description": "Random actions"},
            {"id": "conservative", "label": "Conservative", "description": "Plays tight, folds often"},
            {"id": "aggressive", "label": "Aggressive", "description": "Bets and raises often"},
            {"id": "call_station", "label": "Call Station", "description": "Calls frequently, rarely raises"},
        ]

    def interactive_public_state(self, state, config, session_id, config_hash, player=None):
        base_state = self.public_state(state, config, session_id, config_hash)
        if player and hasattr(state, "hole_cards") and player in state.hole_cards:
            base_state["player_cards"] = state.hole_cards[player]
        return base_state

    def _deal_new_hand(self, hand_number: int) -> tuple[list[str], dict, list[str]]:
        s = (self.seed or 0) + hand_number
        deck = _make_deck(s)
        n = len(self.player_ids)
        hole = {p: deck[2 * i:2 * i + 2] for i, p in enumerate(self.player_ids)}
        return deck[2 * n:], hole, []

    def initial_state(self) -> TexasHoldEmState:
        deck, hole, _ = self._deal_new_hand(1)
        start_chips = {p: STARTING_CHIPS for p in self.player_ids}
        state = TexasHoldEmState(
            round_number=1, phase="awaiting_action",
            awaiting=[], pending_actions={}, history=[],
            total_scores={p: 0.0 for p in self.player_ids},
            hand_number=1, street="preflop",
            deck=deck, hole_cards=hole, community_cards=[],
            chips=dict(start_chips), hand_start_chips={},
            pot=0.0, current_player=self.player_ids[0],
            street_actions=[], last_raise=0.0,
            raised_this_street=[], hand_over=False,
            player_ids=list(self.player_ids),
            folded=[], all_in=[], to_act=[], button_index=0,
        )
        state.hand_start_chips_pre_ante = dict(state.chips)
        for p in self.player_ids:
            state.chips[p] -= ANTE
        state.pot = ANTE * len(self.player_ids)
        state.hand_start_chips = dict(state.chips)
        return self._begin_betting_round(state, _first_to_act_preflop)

    def state_from_dict(self, d: dict) -> TexasHoldEmState:
        if "hand_start_chips" not in d:
            d["hand_start_chips"] = dict(d.get("chips", {"A": STARTING_CHIPS, "B": STARTING_CHIPS}))
        if "final_hand_pot" not in d:
            d["final_hand_pot"] = 0.0
        d.setdefault("player_ids", list(d["chips"].keys()) if d.get("chips") else list(DEFAULT_PLAYER_IDS))
        d.setdefault("folded", [])
        d.setdefault("all_in", [])
        awaiting = d.get("awaiting") or []
        d.setdefault("to_act", [p for p in d["player_ids"] if p in awaiting] or list(d["player_ids"]))
        d.setdefault("button_index", 0)
        d.setdefault("hand_start_chips_pre_ante", dict(d["hand_start_chips"]))
        return TexasHoldEmState(**d)

    def validate_action(self, action) -> bool:
        return isinstance(action, str) and action in VALID_ACTIONS

    def _live_players(self, state: TexasHoldEmState) -> list[str]:
        folded = set(state.folded)
        return [p for p in state.player_ids if p not in folded]

    def _players_to_act(self, state: TexasHoldEmState) -> list[str]:
        all_in = set(state.all_in)
        return [p for p in self._live_players(state) if p not in all_in]

    def validate_player_action(self, state: TexasHoldEmState, player: str, action) -> bool:
        if state.phase == "complete":
            raise ValueError("game is already complete")
        if player not in state.player_ids:
            raise ValueError(f"unknown player: {player!r}")
        if player not in state.awaiting:
            raise ValueError(f"player {player!r} is not on turn")
        if not self.validate_action(action):
            raise ValueError(f"invalid action {action!r}")
        tc = _to_call(state.hand_start_chips, state.chips, player, self._live_players(state))
        if action == "check" and tc > 0:
            raise ValueError("cannot check when facing a bet")
        if action == "call" and tc == 0:
            raise ValueError("cannot call when no bet to match, try check")
        if action == "call" and state.chips[player] < tc:
            raise ValueError("not enough chips to call")
        if action == "raise":
            if player in state.raised_this_street:
                raise ValueError("cannot raise twice on same street")
            if state.chips[player] < BET_SIZE + tc:
                raise ValueError("not enough chips to raise")
        return True

    def apply_action(self, state: TexasHoldEmState, player: str, action: str) -> TexasHoldEmState:
        self.validate_player_action(state, player, action)
        state = deepcopy(state)
        state.pending_actions[player] = action
        state.awaiting = [p for p in state.awaiting if p != player]
        return self._process_action(state, player, action)

    def _process_action(self, state: TexasHoldEmState, player: str, action: str) -> TexasHoldEmState:
        tc = _to_call(state.hand_start_chips, state.chips, player, self._live_players(state))
        entry = {"player": player, "action": action, "street": state.street}

        if action == "fold":
            state.folded.append(player)
            state.street_actions.append(entry)
            state.to_act = [p for p in state.to_act if p != player]
            live = self._live_players(state)
            if len(live) == 1:
                winner = live[0]
                state.final_hand_pot = state.pot
                state.chips[winner] += state.pot
                state.pot = 0
                state.hand_result = {"outcome": "fold", "winner": winner}
                return self._finalize_hand(state)
            return self._advance_if_done(state, player)

        if action == "check":
            state.street_actions.append(entry)
            state.to_act = [p for p in state.to_act if p != player]
            return self._advance_if_done(state, player)

        if action == "call":
            actual_cost = min(tc, state.chips[player])
            state.chips[player] -= actual_cost
            state.pot += actual_cost
            entry["bet"] = actual_cost
            state.street_actions.append(entry)
            state.to_act = [p for p in state.to_act if p != player]
            if state.chips[player] <= 1e-9 and player not in state.all_in:
                state.all_in.append(player)
            return self._advance_if_done(state, player)

        if action == "raise":
            cost = BET_SIZE + tc
            state.chips[player] -= cost
            state.pot += cost
            state.raised_this_street.append(player)
            entry["bet"] = cost
            state.street_actions.append(entry)
            if state.chips[player] <= 1e-9 and player not in state.all_in:
                state.all_in.append(player)
            # A raise reopens action for every other player still able to act.
            state.to_act = [p for p in self._players_to_act(state) if p != player]
            return self._advance_if_done(state, player)

        return state

    def _advance_if_done(self, state: TexasHoldEmState, acting_player: str) -> TexasHoldEmState:
        if self._street_is_complete(state):
            return self._advance_street(state)
        nxt = _first_eligible_from(
            state.player_ids, state.to_act, _seat_after(state.player_ids, acting_player)
        )
        state.awaiting = [nxt] if nxt else []
        state.current_player = nxt if nxt else state.current_player
        state.pending_actions = {}
        return state

    def _street_is_complete(self, state: TexasHoldEmState) -> bool:
        return len(state.to_act) == 0

    def _button_player(self, state: TexasHoldEmState) -> str:
        return state.player_ids[state.button_index % len(state.player_ids)]

    def _begin_betting_round(self, state: TexasHoldEmState, first_to_act_fn) -> TexasHoldEmState:
        """Set up `to_act`/`awaiting` at the start of a betting round (preflop or
        any later street). If nobody remaining can act (everyone still live is
        already all-in), there's no more betting possible this hand — deal
        straight through to showdown without waiting for an action."""
        to_act = self._players_to_act(state)
        state.to_act = list(to_act)
        if not to_act:
            if state.street == "river":
                return self._do_showdown(state)
            return self._advance_street(state)
        first = first_to_act_fn(self, state)
        state.awaiting = [first] if first else []
        state.current_player = first if first else state.current_player
        state.pending_actions = {}
        return state

    def _advance_street(self, state: TexasHoldEmState) -> TexasHoldEmState:
        ns = _next_street(state.street)
        if ns is None:
            return self._do_showdown(state)
        state.street = ns
        state.raised_this_street = []
        state.last_raise = 0.0
        # `street_actions` is NOT reset here (#24): it accumulates the whole
        # hand's action log across all streets (each entry already carries
        # its own "street" field for grouping), unlike `raised_this_street`/
        # `last_raise` which are genuinely per-street betting-rule state.
        # Betting-round completion itself is driven by `to_act`, not by
        # inspecting `street_actions`, so this accumulation is purely additive.
        need = _community_count(ns)
        dc = need - len(state.community_cards)
        state.community_cards = state.community_cards + state.deck[:dc]
        state.deck = state.deck[dc:]
        return self._begin_betting_round(state, _first_to_act_postflop)

    def _do_showdown(self, state: TexasHoldEmState) -> TexasHoldEmState:
        state.final_hand_pot = state.pot
        live = self._live_players(state)
        hands = {p: _best_hand(state.hole_cards[p], state.community_cards) for p in live}
        contrib = {
            p: state.hand_start_chips_pre_ante.get(p, state.hand_start_chips.get(p, 0.0))
            - state.chips.get(p, 0.0)
            for p in state.player_ids
        }
        pots = _build_side_pots(contrib, set(state.folded), state.player_ids)

        payouts: dict[str, float] = {p: 0.0 for p in state.player_ids}
        pot_results = []
        for pot in pots:
            eligible = [p for p in pot["eligible"] if p in live]
            if not eligible or pot["amount"] <= 0:
                continue
            best_score = max((hands[p][0], hands[p][1]) for p in eligible)
            winners = [p for p in eligible if (hands[p][0], hands[p][1]) == best_score]
            share = pot["amount"] / len(winners)
            for w in winners:
                payouts[w] += share
            pot_results.append({"amount": pot["amount"], "eligible": eligible, "winners": winners})

        for p, amt in payouts.items():
            state.chips[p] += amt

        max_payout = max(payouts.values()) if payouts else 0.0
        top = [p for p in state.player_ids if max_payout > 0 and abs(payouts[p] - max_payout) < 1e-9]
        overall_winner = top[0] if len(top) == 1 else "Tie"

        state.hand_result = {
            "outcome": "showdown",
            "winner": overall_winner,
            "community": list(state.community_cards),
            "hands": {p: {"cards": hands[p][2], "hand": _hand_name(hands[p][0])} for p in live},
            "pots": pot_results,
        }
        state.pot = 0
        return self._finalize_hand(state)

    def _finalize_hand(self, state: TexasHoldEmState) -> TexasHoldEmState:
        state.total_scores = {
            p: state.chips[p] - STARTING_CHIPS for p in state.player_ids
        }
        entry = {
            "hand": state.hand_number,
            "street_actions": list(state.street_actions),
            "hole_cards": dict(state.hole_cards),
            "community_cards": list(state.community_cards),
            "result": state.hand_result,
            "chips_after": dict(state.chips),
            "pot": state.final_hand_pot,
            "street": state.street,
            "total_scores": dict(state.total_scores),
        }
        if self.compute_hand_equity:
            # Opt-in (#24): every player originally dealt into this hand, not
            # just those still live at showdown.
            from games.core.texas_hold_em.equity import preflop_equity_for_hand
            entry["preflop_equity"] = preflop_equity_for_hand(
                state.hole_cards, state.player_ids, seed=(self.seed or 0) + state.hand_number
            )
        state.history.append(entry)
        if state.hand_number >= self.num_rounds:
            state.phase = "complete"
            state.awaiting = []
            return state
        return self._start_next_hand(state)

    def _start_next_hand(self, state: TexasHoldEmState) -> TexasHoldEmState:
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
        state.pending_actions = {}
        state.folded = []
        state.all_in = []
        # Button stays fixed (no rotation across hands): this matches the
        # historical 2-player behavior (A always acts first preflop, B always
        # first postflop) exactly. Rotating the button across hands would be
        # a reasonable future enhancement but isn't part of this change.
        state.hand_start_chips_pre_ante = dict(state.chips)
        pot_ante = 0.0
        for p in state.player_ids:
            actual = min(ANTE, max(0.0, state.chips[p]))
            state.chips[p] -= actual
            pot_ante += actual
        state.pot = pot_ante
        state.hand_start_chips = dict(state.chips)
        return self._begin_betting_round(state, _first_to_act_preflop)

    def is_terminal(self, state: TexasHoldEmState) -> bool:
        return state.phase == "complete"

    def compute_results(self, state: TexasHoldEmState,
                        session_id: str | None = None,
                        config_hash: str | None = None) -> dict:
        if not self.is_terminal(state):
            raise ValueError("game is not complete")
        fc = state.history[-1]["chips_after"] if state.history else state.chips
        scores = {p: fc.get(p, 0.0) - STARTING_CHIPS for p in state.player_ids}
        max_score = max(scores.values()) if scores else 0.0
        top = [p for p in state.player_ids if abs(scores[p] - max_score) < 1e-9]
        w = top[0] if len(top) == 1 else "Tie"
        r = {
            "total_scores": scores, "winner": w,
            "history": list(state.history),
            "metrics": self.metrics_engine.compute(state.history, scores),
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
            "config": config.to_dict() if hasattr(config, "to_dict") else {},
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
            "player_ids": list(state.player_ids),
            "folded": list(state.folded),
            "all_in": list(state.all_in),
        }

    def forfeit_round(self, state: TexasHoldEmState, player: str) -> TexasHoldEmState:
        """A player forfeits (e.g. action timeout): treated as an auto-fold.

        With exactly one other live player, the hand ends immediately and they
        win the pot (matches the historical 2-player behavior). With 2+ other
        live players, the forfeiting player simply folds and betting continues
        normally among the rest — the hand isn't over just because one player
        timed out.
        """
        state = deepcopy(state)
        state.folded.append(player)
        state.to_act = [p for p in state.to_act if p != player]
        live = self._live_players(state)
        if len(live) == 1:
            winner = live[0]
            state.final_hand_pot = state.pot
            state.chips[winner] += state.pot
            state.pot = 0
            state.hand_result = {"outcome": "forfeit", "winner": winner, "forfeit_by": player}
            return self._finalize_hand(state)
        return self._advance_if_done(state, player)


def _first_to_act_preflop(game: TexasHoldEmGame, state: TexasHoldEmState) -> str | None:
    button = game._button_player(state)
    n = len(state.player_ids)
    # Heads-up is a well-known exception: the button acts first preflop.
    # With 3+ players (and no blinds in this ante-only game), action starts
    # left of the button on every street, preflop included.
    start = button if n == 2 else _seat_after(state.player_ids, button)
    return _first_eligible_from(state.player_ids, state.to_act, start)


def _first_to_act_postflop(game: TexasHoldEmGame, state: TexasHoldEmState) -> str | None:
    button = game._button_player(state)
    start = _seat_after(state.player_ids, button)
    return _first_eligible_from(state.player_ids, state.to_act, start)
