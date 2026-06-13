from __future__ import annotations

import asyncio
from typing import Any

from nash_arena_sdk.orchestrator import AgentSpec, GameOrchestrator, OrchestratorConfig


def quick_play(
    game: str,
    agents: dict[str, dict[str, Any]],
    arena_url: str = "http://127.0.0.1:8000/api",
    arena_api_key: str | None = None,
    config: dict[str, Any] | None = None,
    jwt_secret: str | None = None,
    max_steps: int | None = None,
    verbose: bool = True,
) -> dict:
    """Quick launch a game between LLM agents.

    Args:
        game: Game name (e.g., "ultimatum", "colonelblotto")
        agents: Dict of player -> agent config. Each config can have:
            - model: LLM model name
            - api_key: LLM API key
            - base_url: LLM API base URL (default: OpenAI)
            - temperature: LLM temperature
            - max_tokens: Max tokens for LLM response
            - extra_body: Extra body params for LLM API
            - fallback_model: Fallback model if primary fails
            - action_parser: Callable to parse LLM output into game action
            - system_prompt: Custom system prompt
            - use_mcp: Whether to use MCP (default True)
        arena_url: NashArena API URL
        arena_api_key: NashArena API key for creating experiments
        config: Game configuration dict
        jwt_secret: JWT secret for session key validation
        max_steps: Maximum game loop steps
        verbose: Print progress

    Returns:
        Game results dict with scores, winner, metrics, etc.

    Example:
        results = quick_play(
            game="ultimatum",
            agents={
                "A": {"model": "gpt-4", "api_key": "sk-..."},
                "B": {"model": "claude-3-opus", "api_key": "sk-ant-..."},
            },
            arena_url="https://api.agent-arena.local",
            arena_api_key="nk_...",
            config={"rounds": 10, "total": 100, "min_offer": 1},
        )
    """
    agent_specs = {}
    for player, agent_config in agents.items():
        agent_specs[player] = AgentSpec(
            player=player,
            model=agent_config.get("model"),
            api_key=agent_config.get("api_key"),
            base_url=agent_config.get("base_url", "https://api.openai.com/v1"),
            temperature=agent_config.get("temperature", 0.7),
            max_tokens=agent_config.get("max_tokens", 4096),
            extra_body=agent_config.get("extra_body"),
            fallback_model=agent_config.get("fallback_model"),
            action_parser=agent_config.get("action_parser"),
            system_prompt=agent_config.get("system_prompt"),
            use_mcp=agent_config.get("use_mcp", True),
            agent=agent_config.get("agent"),
        )

    game_config = config or {"game": game}
    if "game" not in game_config:
        game_config["game"] = game

    orchestrator_config = OrchestratorConfig(
        game=game,
        config=game_config,
        agents=agent_specs,
        arena_url=arena_url,
        arena_api_key=arena_api_key,
        jwt_secret=jwt_secret,
        max_steps=max_steps,
        verbose=verbose,
    )

    orchestrator = GameOrchestrator(orchestrator_config)
    return asyncio.run(orchestrator.run())
