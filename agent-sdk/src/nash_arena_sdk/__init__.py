"""NashArena SDK for building and testing agents."""

from nash_arena_sdk.agent import MCPAgent, RESTAgent
from nash_arena_sdk.client import ArenaClient
from nash_arena_sdk.llm_agent import (
    LLMAgent,
    LLMConfig,
    LLMAgentConfig,
    parse_accept_reject,
    parse_allocation,
    parse_offer,
)
from nash_arena_sdk.mcp_client import MCPClient
from nash_arena_sdk.orchestrator import (
    AgentSpec,
    GameOrchestrator,
    OrchestratorConfig,
)
from nash_arena_sdk.quick_launch import quick_play
from nash_arena_sdk.reasoning import (
    MODEL_PROFILES,
    ModelProfile,
    ReasoningConfig,
    ReasoningEffort,
    ReasoningModerator,
    ReasoningStrategy,
)
from nash_arena_sdk.results import format_results, save_results

__version__ = "0.1.0"

__all__ = [
    "ArenaClient",
    "MCPAgent",
    "MCPClient",
    "RESTAgent",
    "LLMAgent",
    "LLMConfig",
    "LLMAgentConfig",
    "AgentSpec",
    "GameOrchestrator",
    "OrchestratorConfig",
    "quick_play",
    "format_results",
    "save_results",
    "parse_allocation",
    "parse_offer",
    "parse_accept_reject",
    "MODEL_PROFILES",
    "ModelProfile",
    "ReasoningConfig",
    "ReasoningEffort",
    "ReasoningModerator",
    "ReasoningStrategy",
]
