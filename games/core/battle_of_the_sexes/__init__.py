from .config import BoSConfig, config_from_dict
from .engine import BoSGame, BoSState
from .metrics import BoSMetrics


def game_from_config(config) -> BoSGame:
    return BoSGame.from_config(config)


__all__ = [
    "BoSConfig",
    "BoSGame",
    "BoSMetrics",
    "BoSState",
    "config_from_dict",
    "game_from_config",
]
