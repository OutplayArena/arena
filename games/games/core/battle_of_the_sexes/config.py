from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass

from nash_arena.game_components.game_config import GameConfig


@dataclass(frozen=True)
class BoSConfig(GameConfig):
    game: str
    players: int
    rounds: int
    payoff_preferred_a: float = 3.0
    payoff_preferred_b: float = 3.0
    payoff_nonpreferred: float = 2.0
    payoff_mismatch: float = 0.0
    option_a_label: str = "opera"
    option_b_label: str = "football"
    seed: int | None = None
    system_prompt: str = ""

    def __post_init__(self):
        if self.game != "battle_of_the_sexes":
            raise ValueError(f"expected game='battle_of_the_sexes', got {self.game!r}")
        if self.players != 2:
            raise ValueError("battle_of_the_sexes supports exactly 2 players")
        if self.rounds < 1:
            raise ValueError("rounds must be >= 1")

    def player_ids(self) -> list[str]:
        return ["A", "B"]

    def to_dict(self) -> dict:
        return {
            "game": self.game,
            "players": self.players,
            "rounds": self.rounds,
            "payoff_preferred_a": self.payoff_preferred_a,
            "payoff_preferred_b": self.payoff_preferred_b,
            "payoff_nonpreferred": self.payoff_nonpreferred,
            "payoff_mismatch": self.payoff_mismatch,
            "option_a_label": self.option_a_label,
            "option_b_label": self.option_b_label,
            "seed": self.seed,
            "system_prompt": self.system_prompt,
        }

    def config_hash(self) -> str:
        canonical = json.dumps(self.to_dict(), sort_keys=True)
        return f"sha256:{hashlib.sha256(canonical.encode()).hexdigest()}"


def config_from_dict(data: dict) -> BoSConfig:
    return BoSConfig(
        game=data.get("game", "battle_of_the_sexes"),
        players=int(data.get("players", 2)),
        rounds=int(data.get("rounds", 10)),
        payoff_preferred_a=float(data.get("payoff_preferred_a", 3.0)),
        payoff_preferred_b=float(data.get("payoff_preferred_b", 3.0)),
        payoff_nonpreferred=float(data.get("payoff_nonpreferred", 2.0)),
        payoff_mismatch=float(data.get("payoff_mismatch", 0.0)),
        option_a_label=data.get("option_a_label", "opera"),
        option_b_label=data.get("option_b_label", "football"),
        seed=data.get("seed"),
        system_prompt=data.get("system_prompt") or "",
    )
