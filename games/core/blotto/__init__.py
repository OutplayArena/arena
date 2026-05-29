from .config import BattlefieldConfig, BlottoExperimentConfig, config_from_dict
from .engine import BlottoGame, BlottoState
from .metrics import BlottoMetrics


def game_from_config(config):
    return BlottoGame.from_config(config)


__all__ = [
    "BattlefieldConfig",
    "BlottoExperimentConfig",
    "BlottoGame",
    "BlottoMetrics",
    "BlottoState",
    "config_from_dict",
    "game_from_config",
]
