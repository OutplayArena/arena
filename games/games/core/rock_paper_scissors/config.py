from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass

from arena.game_components.game_config import GameConfig

VALID_MOVES = ("rock", "paper", "scissors")


@dataclass(frozen=True)
class RPSExperimentConfig(GameConfig):
    game: str
    variant: str
    players: int
    rounds: int
    seed: int | None = None

    def __post_init__(self):
        if self.game != "rock_paper_scissors":
            raise ValueError(f"expected game='rock_paper_scissors', got {self.game!r}")
        if self.variant != "classic":
            raise ValueError(f"unknown variant: {self.variant!r}")
        if self.players != 2:
            raise ValueError("rock_paper_scissors supports exactly 2 players")
        if self.rounds < 1:
            raise ValueError("rounds must be >= 1")

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


def config_from_dict(data: dict) -> RPSExperimentConfig:
    return RPSExperimentConfig(
        game=data.get("game", "rock_paper_scissors"),
        variant=data.get("variant", "classic"),
        players=int(data.get("players", 2)),
        rounds=int(data.get("rounds", 10)),
        seed=data.get("seed"),
    )
