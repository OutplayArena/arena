from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass

from arena.game_components.game_config import GameConfig

VALID_VARIANTS = frozenset({"classic", "noisy"})


@dataclass(frozen=True)
class ChickenGameConfig(GameConfig):
    game: str
    variant: str
    players: int
    rounds: int
    payoff_win: float = 1.0
    payoff_tie: float = 0.0
    payoff_lose: float = -1.0
    payoff_crash: float = -10.0
    noise: float = 0.0
    seed: int | None = None
    system_prompt: str = ""

    def __post_init__(self):
        if self.game != "chicken_game":
            raise ValueError(f"expected game='chicken_game', got {self.game!r}")
        if self.variant not in VALID_VARIANTS:
            raise ValueError(f"unknown variant: {self.variant!r}")
        if self.players != 2:
            raise ValueError("chicken_game supports exactly 2 players")
        if self.rounds < 1:
            raise ValueError("rounds must be >= 1")
        if not (self.payoff_win > self.payoff_tie > self.payoff_lose > self.payoff_crash):
            raise ValueError("payoffs must satisfy payoff_win > payoff_tie > payoff_lose > payoff_crash")
        if not (0.0 <= self.noise <= 0.5):
            raise ValueError("noise must be in [0.0, 0.5]")

    def player_ids(self) -> list[str]:
        return ["A", "B"]

    def to_dict(self) -> dict:
        return {
            "game": self.game,
            "variant": self.variant,
            "players": self.players,
            "rounds": self.rounds,
            "payoff_win": self.payoff_win,
            "payoff_tie": self.payoff_tie,
            "payoff_lose": self.payoff_lose,
            "payoff_crash": self.payoff_crash,
            "noise": self.noise,
            "seed": self.seed,
            "system_prompt": self.system_prompt,
        }

    def config_hash(self) -> str:
        canonical = json.dumps(self.to_dict(), sort_keys=True)
        return f"sha256:{hashlib.sha256(canonical.encode()).hexdigest()}"


def config_from_dict(data: dict) -> ChickenGameConfig:
    return ChickenGameConfig(
        game=data.get("game", "chicken_game"),
        variant=data.get("variant", "classic"),
        players=int(data.get("players", 2)),
        rounds=int(data.get("rounds", 10)),
        payoff_win=float(data.get("payoff_win", 1.0)),
        payoff_tie=float(data.get("payoff_tie", 0.0)),
        payoff_lose=float(data.get("payoff_lose", -1.0)),
        payoff_crash=float(data.get("payoff_crash", -10.0)),
        noise=float(data.get("noise", 0.0)),
        seed=data.get("seed"),
        system_prompt=data.get("system_prompt") or "",
    )
