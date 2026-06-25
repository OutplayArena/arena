from arena.metrics.contracts import Match, Move
from arena.metrics.extension import GameMetricsExtension
from arena.metrics.registry import AgentRegistry
from arena.metrics.evaluator import MatchEvaluator
from arena.metrics.persistence import load_registry as _load_registry, save_registry as _save_registry

from arena.metrics.behavioral import BehavioralMetrics
from arena.metrics.cooperative import CooperativeMetrics
from arena.metrics.equilibrium import EquilibriumMetrics
from arena.metrics.ranking import RankingMetrics

_global_registry: AgentRegistry | None = None
_registries: dict[str, AgentRegistry] = {}


def get_global_registry() -> AgentRegistry:
    global _global_registry
    if _global_registry is None:
        _global_registry = AgentRegistry()
    return _global_registry


def set_global_registry(registry: AgentRegistry) -> None:
    global _global_registry
    _global_registry = registry


def get_registry(key: str) -> AgentRegistry:
    if key not in _registries:
        _registries[key] = AgentRegistry()
    return _registries[key]


def set_registry(registry: AgentRegistry, key: str) -> None:
    _registries[key] = registry


def get_game_registry(game_type: str) -> AgentRegistry:
    return get_registry(f"game:{game_type}")


def get_all_registries() -> dict[str, AgentRegistry]:
    result = {"overall": get_global_registry()}
    result.update(_registries)
    return result


def get_registry_keys_with_data() -> list[str]:
    keys = ["overall"]
    keys.extend(_registries.keys())
    return keys


async def load_registry(db, key: str = "global"):
    return await _load_registry(db, key)


async def save_registry(registry: AgentRegistry, db, key: str = "global"):
    await _save_registry(registry, db, key)


__all__ = [
    "Match",
    "Move",
    "GameMetricsExtension",
    "AgentRegistry",
    "MatchEvaluator",
    "BehavioralMetrics",
    "CooperativeMetrics",
    "EquilibriumMetrics",
    "RankingMetrics",
    "get_global_registry",
    "set_global_registry",
    "get_registry",
    "set_registry",
    "get_game_registry",
    "get_all_registries",
    "get_registry_keys_with_data",
    "load_registry",
    "save_registry",
]
