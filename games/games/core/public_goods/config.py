from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass

from nash_arena.game_components.game_config import GameConfig

VALID_VARIANTS = frozenset({"classic", "punishment"})


@dataclass(frozen=True)
class PublicGoodsConfig(GameConfig):
    game: str
    variant: str
    players: int
    rounds: int
    endowment: float = 10.0
    multiplier: float = 2.0
    punishment_cost: float = 1.0
    punishment_effect: float = 3.0
    seed: int | None = None
    system_prompt: str = ""

    def __post_init__(self):
        if self.game != "public_goods":
            raise ValueError(f"expected game='public_goods', got {self.game!r}")
        if self.variant not in VALID_VARIANTS:
            raise ValueError(f"unknown variant: {self.variant!r}")
        if not (3 <= self.players <= 10):
            raise ValueError("public_goods requires 3–10 players")
        if self.rounds < 1:
            raise ValueError("rounds must be >= 1")
        if self.endowment <= 0:
            raise ValueError("endowment must be positive")
        if self.multiplier < 1.0:
            raise ValueError("multiplier must be >= 1.0")

    def player_ids(self) -> list[str]:
        return [chr(ord("A") + i) for i in range(self.players)]

    def to_dict(self) -> dict:
        return {
            "game": self.game,
            "variant": self.variant,
            "players": self.players,
            "rounds": self.rounds,
            "endowment": self.endowment,
            "multiplier": self.multiplier,
            "punishment_cost": self.punishment_cost,
            "punishment_effect": self.punishment_effect,
            "seed": self.seed,
            "system_prompt": self.system_prompt,
        }

    def config_hash(self) -> str:
        canonical = json.dumps(self.to_dict(), sort_keys=True)
        return f"sha256:{hashlib.sha256(canonical.encode()).hexdigest()}"


def config_from_dict(data: dict) -> PublicGoodsConfig:
    return PublicGoodsConfig(
        game=data.get("game", "public_goods"),
        variant=data.get("variant", "classic"),
        players=int(data.get("players", 4)),
        rounds=int(data.get("rounds", 10)),
        endowment=float(data.get("endowment", 10.0)),
        multiplier=float(data.get("multiplier", 2.0)),
        punishment_cost=float(data.get("punishment_cost", 1.0)),
        punishment_effect=float(data.get("punishment_effect", 3.0)),
        seed=data.get("seed"),
        system_prompt=data.get("system_prompt") or "",
    )
