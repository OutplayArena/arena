from .config import RPSExperimentConfig, config_from_dict
from .engine import RPSGame, RPSState
from .metrics import RPSMetrics


def game_from_config(config) -> RPSGame:
    return RPSGame.from_config(config)


__all__ = [
    "RPSExperimentConfig",
    "RPSGame",
    "RPSMetrics",
    "RPSState",
    "config_from_dict",
    "game_from_config",
]
