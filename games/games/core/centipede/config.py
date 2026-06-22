from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass

from arena.game_components.game_config import GameConfig


@dataclass(frozen=True)
class CentipedeConfig(GameConfig):
    game: str
    players: int
    max_steps: int = 6
    initial_pot_a: float = 4.0
    initial_pot_b: float = 1.0
    growth_factor: float = 2.0
    seed: int | None = None
    system_prompt: str = ""

    def __post_init__(self):
        if self.game != "centipede":
            raise ValueError(f"expected game='centipede', got {self.game!r}")
        if self.players != 2:
            raise ValueError("centipede supports exactly 2 players")
        if self.max_steps < 2:
            raise ValueError("max_steps must be >= 2")
        if self.growth_factor <= 1.0:
            raise ValueError("growth_factor must be > 1.0")

    def player_ids(self) -> list[str]:
        return ["A", "B"]

    def to_dict(self) -> dict:
        return {
            "game": self.game,
            "players": self.players,
            "max_steps": self.max_steps,
            "initial_pot_a": self.initial_pot_a,
            "initial_pot_b": self.initial_pot_b,
            "growth_factor": self.growth_factor,
            "seed": self.seed,
            "system_prompt": self.system_prompt,
        }

    def config_hash(self) -> str:
        canonical = json.dumps(self.to_dict(), sort_keys=True)
        return f"sha256:{hashlib.sha256(canonical.encode()).hexdigest()}"


def config_from_dict(data: dict) -> CentipedeConfig:
    return CentipedeConfig(
        game=data.get("game", "centipede"),
        players=int(data.get("players", 2)),
        max_steps=int(data.get("max_steps", 6)),
        initial_pot_a=float(data.get("initial_pot_a", 4.0)),
        initial_pot_b=float(data.get("initial_pot_b", 1.0)),
        growth_factor=float(data.get("growth_factor", 2.0)),
        seed=data.get("seed"),
        system_prompt=data.get("system_prompt") or "",
    )
