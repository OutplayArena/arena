from .config import BattlefieldConfig, ColonelBlottoExperimentConfig, config_from_dict
from .engine import ColonelBlottoGame, ColonelBlottoState
from .metrics import ColonelBlottoMetrics


def game_from_config(config):
    return ColonelBlottoGame.from_config(config)


__all__ = [
    "BattlefieldConfig",
    "ColonelBlottoExperimentConfig",
    "ColonelBlottoGame",
    "ColonelBlottoMetrics",
    "ColonelBlottoState",
    "config_from_dict",
    "game_from_config",
]
