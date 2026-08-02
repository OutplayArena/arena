from .config import ChickenGameConfig, config_from_dict
from .engine import ChickenGameGame, ChickenGameState
from .metrics import ChickenGameMetrics


def game_from_config(config) -> ChickenGameGame:
    return ChickenGameGame.from_config(config)


__all__ = [
    "ChickenGameConfig",
    "ChickenGameGame",
    "ChickenGameMetrics",
    "ChickenGameState",
    "config_from_dict",
    "game_from_config",
]
