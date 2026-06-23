"""OutplayLabs Arena SDK for building and testing agents.

The SDK depends only on third-party libraries (``httpx``, ``mcp``,
``openai``) and contains no imports from the arena backend. It can be
installed and used standalone.

Public surface:

* :class:`BaseAgent` &mdash; autonomous, tool-calling, reasoning-aware
  agent with a lifecycle of overridable hooks.
* :class:`LLMConfig` &mdash; OpenAI-compatible chat backend configuration.
* :class:`ArenaClient` &mdash; typed REST client for every backend
  endpoint (kept for direct use).
* :class:`MCPClient` &mdash; raw MCP streamable-http client (kept for
  direct use).
* :class:`ReasoningModerator` &mdash; per-model reasoning-effort and
  timeout configuration.
* Per-game agent classes (one per game in ``games/games/core/``).
* :func:`quick_play` &mdash; one-call helper that spins up a game
  between two LLM agents.

Example::

    from outplaylabs_arena_sdk import quick_play

    results = quick_play(
        game="colonelblotto",
        agents={
            "A": {"model": "gpt-4o", "api_key": "sk-..."},
            "B": {"model": "claude-3-opus", "api_key": "sk-ant-..."},
        },
        arena_url="https://api.agent-arena.local",
        arena_api_key="nk_...",
        config={"rounds": 10, "total": 100, "min_offer": 1},
    )
"""

from outplaylabs_arena_sdk._compat import MCPAgent
from outplaylabs_arena_sdk.base import BaseAgent, LLMConfig
from outplaylabs_arena_sdk.client import ArenaClient
from outplaylabs_arena_sdk.mcp_client import MCPClient
from outplaylabs_arena_sdk.quick_play import quick_play
from outplaylabs_arena_sdk.reasoning import (
    MODEL_PROFILES,
    ModelProfile,
    ReasoningConfig,
    ReasoningEffort,
    ReasoningModerator,
    ReasoningStrategy,
    build_api_params,
    build_system_prompt,
    get_limits,
    get_model_profile,
)
from outplaylabs_arena_sdk.registry import (
    GAME_AGENTS,
    get_agent_class,
    supported_games,
)

# Per-game agents
from outplaylabs_arena_sdk.agents.games import (
    BattleOfTheSexesAgent,
    CentipedeAgent,
    ColonelBlottoAgent,
    CournotDuopolyAgent,
    PrisonersDilemmaAgent,
    PublicGoodsAgent,
    RockPaperScissorsAgent,
    StagHuntAgent,
    TexasHoldEmAgent,
    UltimatumAgent,
)


__version__ = "0.2.0"


__all__ = [
    # Core
    "BaseAgent",
    "LLMConfig",
    "ArenaClient",
    "MCPClient",
    "MCPAgent",  # backward-compat alias
    "ReasoningModerator",
    "ReasoningConfig",
    "ReasoningEffort",
    "ReasoningStrategy",
    "ModelProfile",
    "MODEL_PROFILES",
    "build_api_params",
    "build_system_prompt",
    "get_limits",
    "get_model_profile",
    # Helpers
    "quick_play",
    "GAME_AGENTS",
    "get_agent_class",
    "supported_games",
    # Per-game agents
    "BattleOfTheSexesAgent",
    "CentipedeAgent",
    "ColonelBlottoAgent",
    "CournotDuopolyAgent",
    "PrisonersDilemmaAgent",
    "PublicGoodsAgent",
    "RockPaperScissorsAgent",
    "StagHuntAgent",
    "TexasHoldEmAgent",
    "UltimatumAgent",
]
