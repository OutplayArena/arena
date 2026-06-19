from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass

from outplaylabs_arena.game_components.game_config import GameConfig


@dataclass(frozen=True)
class UltimatumConfig(GameConfig):
    game: str
    players: int
    rounds: int
    total: float = 100.0
    min_offer: float = 1.0
    seed: int | None = None
    system_prompt: str = ""

    def __post_init__(self):
        if self.game != "ultimatum":
            raise ValueError(f"expected game='ultimatum', got {self.game!r}")
        if self.players != 2:
            raise ValueError("ultimatum supports exactly 2 players")
        if self.rounds < 1:
            raise ValueError("rounds must be >= 1")
        if self.total <= 0:
            raise ValueError("total must be positive")
        if self.min_offer <= 0:
            raise ValueError("min_offer must be positive")

    def player_ids(self) -> list[str]:
        return ["A", "B"]

    def to_dict(self) -> dict:
        return {
            "game": self.game,
            "players": self.players,
            "rounds": self.rounds,
            "total": self.total,
            "min_offer": self.min_offer,
            "seed": self.seed,
            "system_prompt": self.system_prompt,
        }

    def config_hash(self) -> str:
        canonical = json.dumps(self.to_dict(), sort_keys=True)
        return f"sha256:{hashlib.sha256(canonical.encode()).hexdigest()}"


def config_from_dict(data: dict) -> UltimatumConfig:
    return UltimatumConfig(
        game=data.get("game", "ultimatum"),
        players=int(data.get("players", 2)),
        rounds=int(data.get("rounds", 10)),
        total=float(data.get("total", 100.0)),
        min_offer=float(data.get("min_offer", 1.0)),
        seed=data.get("seed"),
        system_prompt=data.get("system_prompt") or "",
    )
