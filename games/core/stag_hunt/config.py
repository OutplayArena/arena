from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass

from nash_arena.game_components.game_config import GameConfig

VALID_VARIANTS = frozenset({"classic", "noisy"})


@dataclass(frozen=True)
class StagHuntConfig(GameConfig):
    game: str
    variant: str
    players: int
    rounds: int
    payoff_stag_stag: float = 4.0
    payoff_hare_hare: float = 2.0
    payoff_stag_hare: float = 0.0
    noise: float = 0.0
    seed: int | None = None
    system_prompt: str = ""

    def __post_init__(self):
        if self.game != "stag_hunt":
            raise ValueError(f"expected game='stag_hunt', got {self.game!r}")
        if self.variant not in VALID_VARIANTS:
            raise ValueError(f"unknown variant: {self.variant!r}")
        if self.players != 2:
            raise ValueError("stag_hunt supports exactly 2 players")
        if self.rounds < 1:
            raise ValueError("rounds must be >= 1")
        if not (self.payoff_stag_stag > self.payoff_hare_hare > self.payoff_stag_hare):
            raise ValueError("payoffs must satisfy stag_stag > hare_hare > stag_hare")
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
            "payoff_stag_stag": self.payoff_stag_stag,
            "payoff_hare_hare": self.payoff_hare_hare,
            "payoff_stag_hare": self.payoff_stag_hare,
            "noise": self.noise,
            "seed": self.seed,
            "system_prompt": self.system_prompt,
        }

    def config_hash(self) -> str:
        canonical = json.dumps(self.to_dict(), sort_keys=True)
        return f"sha256:{hashlib.sha256(canonical.encode()).hexdigest()}"


def config_from_dict(data: dict) -> StagHuntConfig:
    return StagHuntConfig(
        game=data.get("game", "stag_hunt"),
        variant=data.get("variant", "classic"),
        players=int(data.get("players", 2)),
        rounds=int(data.get("rounds", 10)),
        payoff_stag_stag=float(data.get("payoff_stag_stag", 4.0)),
        payoff_hare_hare=float(data.get("payoff_hare_hare", 2.0)),
        payoff_stag_hare=float(data.get("payoff_stag_hare", 0.0)),
        noise=float(data.get("noise", 0.0)),
        seed=data.get("seed"),
        system_prompt=data.get("system_prompt") or "",
    )
