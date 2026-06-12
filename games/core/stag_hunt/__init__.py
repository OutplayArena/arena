from .config import StagHuntConfig, config_from_dict
from .engine import StagHuntGame, StagHuntState
from .metrics import StagHuntMetrics


def game_from_config(config) -> StagHuntGame:
    return StagHuntGame.from_config(config)


__all__ = [
    "StagHuntConfig",
    "StagHuntGame",
    "StagHuntMetrics",
    "StagHuntState",
    "config_from_dict",
    "game_from_config",
]
