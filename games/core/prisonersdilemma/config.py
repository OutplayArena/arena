from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass

from nash_arena.game_components.game_config import GameConfig

from games.core.prisonersdilemma.scenarios import ALL_SCENARIOS, get_scenario

VALID_VARIANTS = frozenset({"classic", "noisy"})


@dataclass(frozen=True)
class PDExperimentConfig(GameConfig):
    game: str
    variant: str
    players: int
    rounds: int
    payoff_T: float = 5.0
    payoff_R: float = 3.0
    payoff_P: float = 1.0
    payoff_S: float = 0.0
    noise: float = 0.0
    seed: int | None = None
    scenario: str = "prison"
    system_prompt: str = ""

    def __post_init__(self):
        if self.game != "prisonersdilemma":
            raise ValueError(f"expected game='prisonersdilemma', got {self.game!r}")
        if self.variant not in VALID_VARIANTS:
            raise ValueError(f"unknown variant: {self.variant!r}")
        if self.players != 2:
            raise ValueError("prisonersdilemma supports exactly 2 players")
        if self.rounds < 1:
            raise ValueError("rounds must be >= 1")
        if not (self.payoff_T > self.payoff_R > self.payoff_P > self.payoff_S):
            raise ValueError("payoffs must satisfy T > R > P > S")
        if not (2 * self.payoff_R > self.payoff_T + self.payoff_S):
            raise ValueError("payoffs must satisfy 2R > T + S")
        if not (0.0 <= self.noise <= 0.5):
            raise ValueError("noise must be in [0.0, 0.5]")
        if self.scenario not in ALL_SCENARIOS:
            raise ValueError(
                f"unknown scenario {self.scenario!r}. "
                f"Valid: {', '.join(ALL_SCENARIOS)}"
            )
        if not isinstance(self.system_prompt, str):
            raise ValueError("system_prompt must be a string")

    def player_ids(self) -> list[str]:
        return ["A", "B"]

    def get_scenario(self):
        return get_scenario(self.scenario)

    def to_dict(self) -> dict:
        return {
            "game": self.game,
            "variant": self.variant,
            "players": self.players,
            "rounds": self.rounds,
            "payoff_T": self.payoff_T,
            "payoff_R": self.payoff_R,
            "payoff_P": self.payoff_P,
            "payoff_S": self.payoff_S,
            "noise": self.noise,
            "seed": self.seed,
            "scenario": self.scenario,
            "system_prompt": self.system_prompt,
        }

    def config_hash(self) -> str:
        canonical = json.dumps(self.to_dict(), sort_keys=True)
        return f"sha256:{hashlib.sha256(canonical.encode()).hexdigest()}"


def config_from_dict(data: dict) -> PDExperimentConfig:
    return PDExperimentConfig(
        game=data.get("game", "prisonersdilemma"),
        variant=data.get("variant", "classic"),
        players=int(data.get("players", 2)),
        rounds=int(data.get("rounds", 10)),
        payoff_T=float(data.get("payoff_T", 5.0)),
        payoff_R=float(data.get("payoff_R", 3.0)),
        payoff_P=float(data.get("payoff_P", 1.0)),
        payoff_S=float(data.get("payoff_S", 0.0)),
        noise=float(data.get("noise", 0.0)),
        seed=data.get("seed"),
        scenario=data.get("scenario", "prison"),
        system_prompt=data.get("system_prompt") or "",
    )
