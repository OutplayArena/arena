from .config import PDExperimentConfig, config_from_dict
from .engine import PDGame, PDState
from .metrics import PDMetrics


def game_from_config(config) -> PDGame:
    return PDGame.from_config(config)


__all__ = [
    "PDExperimentConfig",
    "PDGame",
    "PDMetrics",
    "PDState",
    "config_from_dict",
    "game_from_config",
]
