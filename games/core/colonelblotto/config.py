from dataclasses import dataclass
import hashlib
import json

from nash_arena.game_components.game_config import GameConfig


# Allow for named Battlefield objects
@dataclass(frozen=True)
class BattlefieldConfig:
    id: str
    value: float = 1.0
    
    def __post_init__(self):
        if not isinstance(self.id, str) or not self.id.strip():
            raise ValueError("battlefield id must be a non-empty string")
        if not isinstance(self.value, (int, float)) or isinstance(self.value, bool):
            raise ValueError("battlefield value must be a number")
        if self.value <= 0:
            raise ValueError("battlefield value must be positive")
    
# Experiment becomes one object
# POST / experiment will accept almost exactly this shape as JSON
@dataclass(frozen=True)
class ColonelBlottoExperimentConfig(GameConfig):
    game: str
    variant: str
    players: int
    budget: list[int]
    battlefields: list[BattlefieldConfig]
    rounds: int
    seed: int | None = None
    
    def __post_init__(self):
        if self.game != "colonelblotto":
            raise ValueError("game must be 'colonelblotto'")
        if self.variant != "classic":
            raise ValueError("variant must be 'classic'")
        if self.players != 2:
            raise ValueError("only 2 players are currently supported")
        if not isinstance(self.rounds, int) or isinstance(self.rounds, bool):
            raise ValueError("rounds must be an integer")
        if self.rounds < 1:
            raise ValueError("rounds must be at least 1")
        if self.seed is not None and (
            not isinstance(self.seed, int) or isinstance(self.seed, bool)
        ):
            raise ValueError("seed must be an integer or None")

        if len(self.budget) != self.players:
            raise ValueError("budget length must equal players")
        if not all(
            isinstance(value, int) and not isinstance(value, bool)
            for value in self.budget
        ):
            raise ValueError("budgets must be integers")
        if not all(value > 0 for value in self.budget):
            raise ValueError("budgets must be positive")
        if len(set(self.budget)) != 1:
            raise ValueError("only equal player budgets are currently supported")

        if len(self.battlefields) < 1:
            raise ValueError("at least one battlefield is required")
        if not all(isinstance(field, BattlefieldConfig) for field in self.battlefields):
            raise ValueError("battlefields must contain BattlefieldConfig objects")

        ids = [field.id for field in self.battlefields]
        if len(ids) != len(set(ids)):
            raise ValueError("battlefield ids must be unique")

    def player_ids(self):
        return ["A", "B"]
    
    @classmethod
    def classic(
        cls, 
        num_battlefields: int=5,
        total_resources: int=100,
        rounds: int=10,
        seed: int | None = None,
    ):
        return cls(
            game="colonelblotto",
            variant="classic",
            players=2,
            budget=[total_resources, total_resources],
            battlefields=[
                BattlefieldConfig(id=f"battlefield_{i + 1}", value=1.0)
                for i in range(num_battlefields)
            ],
            rounds=rounds,
            seed=seed,
        )
        
    # Serialization
    def to_dict(self):
        return {
            "game": self.game,
            "variant": self.variant,
            "players": self.players,
            "budget": list(self.budget),
            "battlefields": [
                {"id": b.id, "value": b.value}
                for b in self.battlefields
            ],
            "rounds": self.rounds,
            "seed": self.seed,
        }
        
    # Hashing for easy config/setup identification
    def config_hash(self) -> str:
        canonical = json.dumps(
            self.to_dict(),
            sort_keys=True,
            separators=(",", ":")
        )
        digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
        return f"sha256:{digest}"


def config_from_dict(data):
    if "budget" in data and "battlefields" in data:
        budget = list(data["budget"])
        battlefields = [
            BattlefieldConfig(id=field["id"], value=field.get("value", 1.0))
            for field in data["battlefields"]
        ]
    else:
        total_resources = data.get("total_resources", 100)
        num_battlefields = data.get("num_battlefields", 5)
        budget = [total_resources, total_resources]
        battlefields = [
            BattlefieldConfig(id=f"battlefield_{i + 1}", value=1.0)
            for i in range(num_battlefields)
        ]

    return ColonelBlottoExperimentConfig(
        game=data["game"],
        variant=data["variant"],
        players=data["players"],
        budget=budget,
        battlefields=battlefields,
        rounds=data["rounds"],
        seed=data.get("seed"),
    )
