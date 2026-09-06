from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass

from arena.game_components.game_config import GameConfig


@dataclass(frozen=True)
class VickreyAuctionConfig(GameConfig):
    game: str
    players: int
    rounds: int
    value_min: float = 0.0
    value_max: float = 100.0
    max_bid: float = 200.0
    truthful_tolerance: float = 1.0
    seed: int | None = None
    system_prompt: str = ""

    def __post_init__(self):
        if self.game != "vickrey_auction":
            raise ValueError(f"expected game='vickrey_auction', got {self.game!r}")
        if not (2 <= self.players <= 8):
            raise ValueError("vickrey_auction requires 2-8 players")
        if self.rounds < 1:
            raise ValueError("rounds must be >= 1")
        if self.value_min < 0:
            raise ValueError("value_min must be >= 0")
        if self.value_max <= self.value_min:
            raise ValueError("value_max must be > value_min")
        if self.max_bid < self.value_max:
            raise ValueError("max_bid must be >= value_max")
        if self.truthful_tolerance < 0:
            raise ValueError("truthful_tolerance must be >= 0")

    def player_ids(self) -> list[str]:
        return [chr(ord("A") + i) for i in range(self.players)]

    def to_dict(self) -> dict:
        return {
            "game": self.game,
            "players": self.players,
            "rounds": self.rounds,
            "value_min": self.value_min,
            "value_max": self.value_max,
            "max_bid": self.max_bid,
            "truthful_tolerance": self.truthful_tolerance,
            "seed": self.seed,
            "system_prompt": self.system_prompt,
        }

    def config_hash(self) -> str:
        canonical = json.dumps(self.to_dict(), sort_keys=True)
        return f"sha256:{hashlib.sha256(canonical.encode()).hexdigest()}"


def config_from_dict(data: dict) -> VickreyAuctionConfig:
    return VickreyAuctionConfig(
        game=data.get("game", "vickrey_auction"),
        players=int(data.get("players", 3)),
        rounds=int(data.get("rounds", 10)),
        value_min=float(data.get("value_min", 0.0)),
        value_max=float(data.get("value_max", 100.0)),
        max_bid=float(data.get("max_bid", 200.0)),
        truthful_tolerance=float(data.get("truthful_tolerance", 1.0)),
        seed=data.get("seed"),
        system_prompt=data.get("system_prompt") or "",
    )
