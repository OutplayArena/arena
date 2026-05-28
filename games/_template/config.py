from dataclasses import dataclass

from arena.game_components.game_config import GameConfig


@dataclass(frozen=True)
class ExampleConfig(GameConfig):
    game: str
    players: int
    rounds: int

    def player_ids(self):
        return [f"P{i + 1}" for i in range(self.players)]

    def to_dict(self):
        return {
            "game": self.game,
            "players": self.players,
            "rounds": self.rounds,
        }

    def config_hash(self):
        raise NotImplementedError("Implement stable config hashing")


def config_from_dict(data):
    return ExampleConfig(
        game=data["game"],
        players=data["players"],
        rounds=data["rounds"],
    )
