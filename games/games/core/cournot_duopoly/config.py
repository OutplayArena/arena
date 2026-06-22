from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass

from arena.game_components.game_config import GameConfig


@dataclass(frozen=True)
class CournotConfig(GameConfig):
    game: str
    players: int
    rounds: int
    demand_a: float = 120.0
    demand_b: float = 1.0
    cost_per_unit: float = 0.0
    max_quantity: float = 120.0
    seed: int | None = None
    system_prompt: str = ""

    def __post_init__(self):
        if self.game != "cournot_duopoly":
            raise ValueError(f"expected game='cournot_duopoly', got {self.game!r}")
        if self.players != 2:
            raise ValueError("cournot_duopoly supports exactly 2 players")
        if self.rounds < 1:
            raise ValueError("rounds must be >= 1")
        if self.demand_a <= 0 or self.demand_b <= 0:
            raise ValueError("demand_a and demand_b must be positive")

    def player_ids(self) -> list[str]:
        return ["A", "B"]

    def to_dict(self) -> dict:
        return {
            "game": self.game,
            "players": self.players,
            "rounds": self.rounds,
            "demand_a": self.demand_a,
            "demand_b": self.demand_b,
            "cost_per_unit": self.cost_per_unit,
            "max_quantity": self.max_quantity,
            "seed": self.seed,
            "system_prompt": self.system_prompt,
        }

    def config_hash(self) -> str:
        canonical = json.dumps(self.to_dict(), sort_keys=True)
        return f"sha256:{hashlib.sha256(canonical.encode()).hexdigest()}"

    @property
    def nash_quantity(self) -> float:
        """Symmetric Cournot Nash quantity per firm."""
        return (self.demand_a - self.cost_per_unit) / (3 * self.demand_b)

    @property
    def collusive_quantity(self) -> float:
        """Joint-maximizing (collusive) quantity per firm."""
        return (self.demand_a - self.cost_per_unit) / (4 * self.demand_b)


def config_from_dict(data: dict) -> CournotConfig:
    return CournotConfig(
        game=data.get("game", "cournot_duopoly"),
        players=int(data.get("players", 2)),
        rounds=int(data.get("rounds", 10)),
        demand_a=float(data.get("demand_a", 120.0)),
        demand_b=float(data.get("demand_b", 1.0)),
        cost_per_unit=float(data.get("cost_per_unit", 0.0)),
        max_quantity=float(data.get("max_quantity", 120.0)),
        seed=data.get("seed"),
        system_prompt=data.get("system_prompt") or "",
    )
