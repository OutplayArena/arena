from nash_arena.metrics.contracts import Match, Move
from nash_arena.metrics.extension import GameMetricsExtension
from nash_arena.metrics.registry import AgentRegistry
from nash_arena.metrics.evaluator import MatchEvaluator
from nash_arena.metrics.persistence import load_registry, save_registry

from nash_arena.metrics.behavioral import BehavioralMetrics
from nash_arena.metrics.cooperative import CooperativeMetrics
from nash_arena.metrics.equilibrium import EquilibriumMetrics
from nash_arena.metrics.ranking import RankingMetrics

_global_registry: AgentRegistry | None = None


def get_global_registry() -> AgentRegistry:
    global _global_registry
    if _global_registry is None:
        _global_registry = AgentRegistry()
    return _global_registry


def set_global_registry(registry: AgentRegistry) -> None:
    global _global_registry
    _global_registry = registry


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
    "load_registry",
    "save_registry",
]
