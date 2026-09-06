from __future__ import annotations

import random
from abc import abstractmethod

from arena.game_components.game_agent import GameAgent


class VickreyAuctionAgent(GameAgent):
    """Base class for Vickrey Auction strategies.

    The private value for the current round isn't derivable from `history`
    (it's freshly drawn every round and never leaked to opponents), so the
    caller must set it via `set_value()` before each call to `act()`.
    """

    def __init__(self):
        self.current_value: float = 0.0

    def set_value(self, value: float) -> None:
        self.current_value = value

    @abstractmethod
    def act(self, history: list[dict]) -> float: ...


class TruthfulBidder(VickreyAuctionAgent):
    """Bids exactly its private value — the weakly dominant strategy."""

    def act(self, history: list[dict]) -> float:
        return self.current_value


class Shader(VickreyAuctionAgent):
    """Underbids relative to its private value."""

    def __init__(self, shade_factor: float = 0.8):
        super().__init__()
        self.shade_factor = shade_factor

    def act(self, history: list[dict]) -> float:
        return self.current_value * self.shade_factor


class Overbidder(VickreyAuctionAgent):
    """Overbids relative to its private value, risking the winner's curse."""

    def __init__(self, overbid_factor: float = 1.2):
        super().__init__()
        self.overbid_factor = overbid_factor

    def act(self, history: list[dict]) -> float:
        return self.current_value * self.overbid_factor


class AlwaysMaxBidder(VickreyAuctionAgent):
    """Always bids the maximum allowed bid, regardless of value."""

    def __init__(self, max_bid: float = 200.0):
        super().__init__()
        self.max_bid = max_bid

    def act(self, history: list[dict]) -> float:
        return self.max_bid


class AlwaysZeroBidder(VickreyAuctionAgent):
    """Never bids — never wins, never pays."""

    def act(self, history: list[dict]) -> float:
        return 0.0


class RandomBidder(VickreyAuctionAgent):
    """Bids uniformly at random up to the bid ceiling, ignoring its value."""

    def __init__(self, max_bid: float = 200.0):
        super().__init__()
        self.max_bid = max_bid

    def act(self, history: list[dict]) -> float:
        return random.uniform(0, self.max_bid)
