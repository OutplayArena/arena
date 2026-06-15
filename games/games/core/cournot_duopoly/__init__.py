from .config import CournotConfig, config_from_dict
from .engine import CournotGame, CournotState
from .metrics import CournotMetrics


def game_from_config(config) -> CournotGame:
    return CournotGame.from_config(config)


__all__ = [
    "CournotConfig",
    "CournotGame",
    "CournotMetrics",
    "CournotState",
    "config_from_dict",
    "game_from_config",
]
