"""Async backend transport for the OutplayArena SDK.

Wraps :class:`ArenaClient` (REST) and :class:`MCPClient` (streamable-http) in
a single async interface that :class:`BaseAgent` can drive without caring
about the transport. The same call (``fetch_state``, ``submit_action``, ...)
is dispatched to whichever transport is connected.

For most agents the REST transport is enough. MCP is preferred when the
backend exposes an MCP endpoint and the user wants to bypass the HTTP
middleware in :class:`ArenaClient`. The transport is selected at agent
construction time; it is not hot-swapped at runtime.
"""
from __future__ import annotations

from typing import Any

from outplayarena_sdk.client import ArenaClient
from outplayarena_sdk.mcp_client import MCPClient


class AsyncBackend:
    """Thin async wrapper around :class:`ArenaClient` and optional MCP.

    All methods are coroutines; the REST client is synchronous under the
    hood, so the wrapper just trampolines the calls.  When ``mcp_client``
    is provided, the wrapper prefers MCP for the methods it supports
    (``get_state``, ``get_observation``, ``submit_action``, ``get_results``,
    mailbox) and falls back to REST otherwise.

    The agent does not need to await transport calls behind a queue; the
    SDK is single-actor by design (one agent per session).
    """

    def __init__(
        self,
        rest_client: ArenaClient,
        mcp_client: MCPClient | None = None,
        player_id: str | None = None,
    ):
        if rest_client is None:
            raise ValueError("rest_client is required")
        self._rest = rest_client
        self._mcp = mcp_client
        self._player_id = player_id

    @property
    def rest(self) -> ArenaClient:
        return self._rest

    @property
    def mcp(self) -> MCPClient | None:
        return self._mcp

    @property
    def transport(self) -> str:
        return "mcp" if self._mcp is not None else "rest"

    # ── Gameplay ───────────────────────────────────────────────────────────

    async def get_state(self) -> dict[str, Any]:
        if self._mcp is not None:
            return self._mcp.get_game_state()
        return self._rest.get_state()

    async def get_observation(self, variant: str = "neutral") -> dict[str, str]:
        if self._mcp is not None:
            return self._mcp.get_observation(variant=variant)
        return self._rest.get_observation(self._require_player_id(), variant=variant)

    async def submit_action(self, allocation: Any) -> dict[str, Any]:
        if self._mcp is not None:
            return self._mcp.submit_action(allocation)
        return self._rest.submit_action(allocation)

    async def get_results(self) -> dict[str, Any]:
        if self._mcp is not None:
            return self._mcp.get_results()
        return self._rest.get_results()

    # ── Mailbox ────────────────────────────────────────────────────────────

    async def get_mailbox(self) -> list[dict[str, Any]]:
        if self._mcp is not None:
            return self._mcp.get_mailbox()
        return self._rest.get_mailbox(self._require_player_id())

    async def send_message(self, content: str, recipient: str = "all") -> dict[str, Any]:
        if self._mcp is not None:
            return self._mcp.send_message(content, recipient)
        return self._rest.send_message(content=content, recipient=recipient)

    # ── Discovery (one-shot, REST only) ────────────────────────────────────

    async def list_games(self) -> list[dict[str, Any]]:
        return self._rest.list_games()

    async def get_game_details(self, game: str) -> dict[str, Any]:
        return self._rest.get_game_details(game)

    def set_player_id(self, player_id: str) -> None:
        """Bind a player id for REST calls that need one (observation, mailbox)."""
        self._player_id = player_id

    def _require_player_id(self) -> str:
        if not self._player_id:
            raise RuntimeError(
                "AsyncBackend has no player_id; call set_player_id() first"
            )
        return self._player_id


__all__ = ["AsyncBackend"]
