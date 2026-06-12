from .config import UltimatumConfig, config_from_dict
from .engine import UltimatumGame, UltimatumState
from .metrics import UltimatumMetrics


def game_from_config(config) -> UltimatumGame:
    return UltimatumGame.from_config(config)


__all__ = [
    "UltimatumConfig",
    "UltimatumGame",
    "UltimatumMetrics",
    "UltimatumState",
    "config_from_dict",
    "game_from_config",
]
