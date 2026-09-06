from .config import VickreyAuctionConfig, config_from_dict
from .engine import VickreyAuctionGame, VickreyAuctionState
from .metrics import VickreyAuctionMetrics


def game_from_config(config) -> VickreyAuctionGame:
    return VickreyAuctionGame.from_config(config)


__all__ = [
    "VickreyAuctionConfig",
    "VickreyAuctionGame",
    "VickreyAuctionMetrics",
    "VickreyAuctionState",
    "config_from_dict",
    "game_from_config",
]
