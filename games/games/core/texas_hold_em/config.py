from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass

from outplaylabs_arena.game_components.game_config import GameConfig


@dataclass(frozen=True)
class TexasHoldEmExperimentConfig(GameConfig):
    game: str
    variant: str
    players: int
    rounds: int
    seed: int | None = None

    def __post_init__(self):
        if self.game != "texas_hold_em":
            raise ValueError(f"expected game='texas_hold_em', got {self.game!r}")
        if self.variant not in ("classic", "face_down"):
            raise ValueError(f"unknown variant: {self.variant!r}")
        if self.players != 2:
            raise ValueError("texas_hold_em supports exactly 2 players")
        if self.rounds < 1:
            raise ValueError("rounds must be >= 1")

    @property
    def is_face_up(self) -> bool:
        return self.variant == "classic"

    def player_ids(self) -> list[str]:
        return ["A", "B"]

    def to_dict(self) -> dict:
        return {
            "game": self.game,
            "variant": self.variant,
            "players": self.players,
            "rounds": self.rounds,
            "seed": self.seed,
        }

    def config_hash(self) -> str:
        canonical = json.dumps(self.to_dict(), sort_keys=True)
        return f"sha256:{hashlib.sha256(canonical.encode()).hexdigest()}"


def config_from_dict(data: dict) -> TexasHoldEmExperimentConfig:
    return TexasHoldEmExperimentConfig(
        game=data.get("game", "texas_hold_em"),
        variant=data.get("variant", "classic"),
        players=int(data.get("players", 2)),
        rounds=int(data.get("rounds", 10)),
        seed=data.get("seed"),
    )
