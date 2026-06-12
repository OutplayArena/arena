"""MCP-based agent that connects to the arena via MCP protocol (SSE transport)."""
from __future__ import annotations

import asyncio
import json
import threading
from contextlib import AsyncExitStack
from typing import Any

from mcp import ClientSession, types
from mcp.client.sse import sse_client


def _extract_tool_result(result: Any) -> Any:
    """Extract JSON data from MCP tool result."""
    for item in result.content:
        if isinstance(item, types.TextContent):
            try:
                return json.loads(item.text)
            except json.JSONDecodeError:
                return {"raw": item.text}
    return {}


class MCPClient:
    """Async MCP client that connects to an MCP server via SSE.

    The MCP server exposes tools like get_observation, submit_action, etc.
    This client provides a synchronous interface for use in agent scripts.
    Runs the event loop in a separate thread to avoid conflicts with async contexts.
    """

    def __init__(
        self,
        mcp_url: str,
        headers: dict[str, str] | None = None,
        timeout: float = 10.0,
    ):
        self.mcp_url = mcp_url.rstrip("/") + "/sse"
        self.headers = headers or {}
        self.timeout = timeout
        self._session: ClientSession | None = None
        self._exit_stack: AsyncExitStack | None = None
        self._connected = False
        self._loop: asyncio.AbstractEventLoop | None = None
        self._thread: threading.Thread | None = None

    def connect(self) -> None:
        """Connect to the MCP server. Must be called before using tools."""
        if self._connected:
            return

        self._loop = asyncio.new_event_loop()
        self._exit_stack = AsyncExitStack()

        def run_loop():
            asyncio.set_event_loop(self._loop)
            self._loop.run_forever()

        self._thread = threading.Thread(target=run_loop, daemon=True)
        self._thread.start()

        async def _connect():
            read, write = await self._exit_stack.enter_async_context(
                sse_client(self.mcp_url, headers=self.headers, timeout=self.timeout)
            )
            self._session = ClientSession(read, write)
            await self._exit_stack.enter_async_context(self._session)
            await self._session.initialize()
            self._connected = True

        # Retry connection a few times in case the server is still starting
        max_retries = 5
        for attempt in range(max_retries):
            try:
                future = asyncio.run_coroutine_threadsafe(_connect(), self._loop)
                future.result(timeout=30)
                return
            except Exception:
                if attempt < max_retries - 1:
                    import time
                    time.sleep(1)
                else:
                    raise

    def disconnect(self) -> None:
        """Disconnect from the MCP server."""
        if not self._connected or not self._exit_stack or not self._loop:
            return

        async def _disconnect():
            await self._exit_stack.aclose()

        future = asyncio.run_coroutine_threadsafe(_disconnect(), self._loop)
        try:
            future.result(timeout=10)
        except Exception:
            pass

        self._loop.call_soon_threadsafe(self._loop.stop)
        if self._thread:
            self._thread.join(timeout=5)

        self._connected = False
        self._session = None
        self._exit_stack = None
        self._loop = None
        self._thread = None

    def _call_tool(self, name: str, arguments: dict[str, Any] | None = None) -> Any:
        """Call an MCP tool and return the result."""
        if not self._connected or not self._session or not self._loop:
            raise RuntimeError("Not connected. Call connect() first.")

        async def _call():
            result = await self._session.call_tool(name, arguments or {})
            return _extract_tool_result(result)

        future = asyncio.run_coroutine_threadsafe(_call(), self._loop)
        return future.result(timeout=60)

    def get_observation(self, variant: str = "neutral") -> dict:
        """Get rendered system + turn prompts for the current game state."""
        return self._call_tool("get_observation", {"variant": variant})

    def get_game_state(self) -> dict:
        """Get the raw current game state."""
        return self._call_tool("get_game_state")

    def submit_action(self, allocation: Any) -> dict:
        """Submit an action for the current round."""
        return self._call_tool("submit_action", {"allocation": allocation})

    def get_results(self) -> dict:
        """Get final scores and metrics after the game is complete."""
        return self._call_tool("get_results")

    def list_games(self) -> list[dict]:
        """List available games."""
        return self._call_tool("list_games")

    def get_game_details(self, game: str) -> dict:
        """Get metadata and config schema for a game."""
        return self._call_tool("get_game_details", {"game": game})

    def get_game_metrics(self, game: str) -> dict:
        """Get metric declarations for a game."""
        return self._call_tool("get_game_metrics", {"game": game})

    def get_game_prompts(self, game: str) -> dict:
        """Get default prompt templates for a game."""
        return self._call_tool("get_game_prompts", {"game": game})

    def __enter__(self):
        self.connect()
        return self

    def __exit__(self, *args):
        self.disconnect()

    def __del__(self):
        self.disconnect()
