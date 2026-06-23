"""One-call helper to spin up a game between two LLM agents.

Auto-picks the right per-game :class:`BaseAgent` subclass based on the
``game=`` argument. Use this when you don't need fine-grained control
over the agent subclass; for custom subclasses, instantiate them
directly.

Example::

    from outplaylabs_arena_sdk import quick_play

    results = quick_play(
        game="colonelblotto",
        agents={
            "A": {"model": "gpt-4", "api_key": "sk-..."},
            "B": {"model": "claude-3-opus", "api_key": "sk-ant-..."},
        },
        arena_url="https://api.agent-arena.local",
        arena_api_key="nk_...",
        config={"rounds": 10, "total": 100, "min_offer": 1},
    )

Internally this:

  1. POSTs to ``/experiment`` with the given config (and seed=42 by
     default) and gets back ``session_id``, ``player_tokens``, and the
     echoed ``config``.
  2. Instantiates the right per-game agent class for each player.
  3. Runs both agents in parallel via :class:`asyncio.gather`.
  4. Returns the final results dict from agent A (both agents see the
     same backend state).
"""
from __future__ import annotations

import asyncio
from typing import Any

from outplaylabs_arena_sdk.base import BaseAgent, LLMConfig
from outplaylabs_arena_sdk.client import ArenaClient
from outplaylabs_arena_sdk.registry import get_agent_class


async def _quick_play_async(
    game: str,
    agents: dict[str, dict[str, Any]],
    arena_url: str = "http://127.0.0.1:8000/api",
    arena_api_key: str | None = None,
    config: dict[str, Any] | None = None,
    seed: int = 42,
    jwt_secret: str | None = None,
    mcp_url: str | None = None,
    poll_interval: float = 1.0,
    max_tools_per_turn: int = 4,
    verbose: bool = False,
) -> dict[str, Any]:
    agent_cls = get_agent_class(game)
    game_config = {"game": game, "seed": seed, **(config or {})}

    # Create the experiment up front so both agents share the same session.
    rest = ArenaClient(arena_url)
    created = rest.create_experiment(
        game_config,
        agents={p: spec.get("model", "unknown") for p, spec in agents.items()},
        api_key=arena_api_key,
    )
    player_tokens = created["player_tokens"]

    if mcp_url is None and "mcp_url" in created:
        mcp_url = created["mcp_url"]

    instances: list[BaseAgent] = []
    for player, spec in agents.items():
        llm_cfg = LLMConfig(
            model=spec["model"],
            api_key=spec["api_key"],
            base_url=spec.get("base_url", "https://api.openai.com/v1"),
            temperature=spec.get("temperature", 0.7),
            max_tokens=spec.get("max_tokens", 4096),
            extra_body=spec.get("extra_body"),
            fallback_model=spec.get("fallback_model"),
            reasoning_effort=spec.get("reasoning_effort", "none"),
        )
        instances.append(agent_cls(
            player=player,
            player_token=player_tokens[player],
            arena_url=arena_url,
            llm_config=llm_cfg,
            mcp_url=mcp_url,
            jwt_secret=jwt_secret,
            poll_interval=poll_interval,
            max_tools_per_turn=max_tools_per_turn,
            verbose=verbose,
            seed=seed,
        ))

    if not instances:
        return {}

    # Run the first agent; the second agent shares the same backend
    # session but the loop is driven by per-agent state polling. The
    # backend serializes actions per player, so a single asyncio.gather
    # works for the two-player case.
    if len(instances) == 1:
        return await instances[0].run()

    results = await asyncio.gather(*(a.run() for a in instances))
    # Return the results from the first player; both players see the
    # same final scores.
    return results[0] if results else {}


def quick_play(
    game: str,
    agents: dict[str, dict[str, Any]],
    arena_url: str = "http://127.0.0.1:8000/api",
    arena_api_key: str | None = None,
    config: dict[str, Any] | None = None,
    seed: int = 42,
    jwt_secret: str | None = None,
    mcp_url: str | None = None,
    poll_interval: float = 1.0,
    max_tools_per_turn: int = 4,
    verbose: bool = False,
) -> dict[str, Any]:
    """Synchronous wrapper around the async quick_play.

    See module docstring for details.
    """
    return asyncio.run(
        _quick_play_async(
            game=game,
            agents=agents,
            arena_url=arena_url,
            arena_api_key=arena_api_key,
            config=config,
            seed=seed,
            jwt_secret=jwt_secret,
            mcp_url=mcp_url,
            poll_interval=poll_interval,
            max_tools_per_turn=max_tools_per_turn,
            verbose=verbose,
        )
    )


__all__ = ["quick_play", "_quick_play_async"]
