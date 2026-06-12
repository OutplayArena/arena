from .config import CentipedeConfig, config_from_dict
from .engine import CentipedeGame, CentipedeState
from .metrics import CentipedeMetrics


def game_from_config(config) -> CentipedeGame:
    return CentipedeGame.from_config(config)


__all__ = [
    "CentipedeConfig",
    "CentipedeGame",
    "CentipedeMetrics",
    "CentipedeState",
    "config_from_dict",
    "game_from_config",
]
