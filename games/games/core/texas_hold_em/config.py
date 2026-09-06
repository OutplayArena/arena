from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass

from arena.game_components.game_config import GameConfig


@dataclass(frozen=True)
class TexasHoldEmExperimentConfig(GameConfig):
    game: str
    variant: str
    players: int
    rounds: int
    seed: int | None = None
    # Opt-in (#24): compute a Monte-Carlo/exact preflop hand-equity estimate
    # for every hand. Off by default -- it adds real per-hand cost, which
    # matters for long benchmark tournaments (hundreds-to-thousands of hands).
    compute_hand_equity: bool = False

    def __post_init__(self):
        if self.game != "texas_hold_em":
            raise ValueError(f"expected game='texas_hold_em', got {self.game!r}")
        if self.variant not in ("classic", "face_down"):
            raise ValueError(f"unknown variant: {self.variant!r}")
        if not (2 <= self.players <= 6):
            raise ValueError("texas_hold_em supports 2-6 players")
        if self.rounds < 1:
            raise ValueError("rounds must be >= 1")

    @property
    def is_face_up(self) -> bool:
        return self.variant == "classic"

    def player_ids(self) -> list[str]:
        return [chr(ord("A") + i) for i in range(self.players)]

    def to_dict(self) -> dict:
        return {
            "game": self.game,
            "variant": self.variant,
            "players": self.players,
            "rounds": self.rounds,
            "seed": self.seed,
            "compute_hand_equity": self.compute_hand_equity,
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
        compute_hand_equity=bool(data.get("compute_hand_equity", False)),
    )
