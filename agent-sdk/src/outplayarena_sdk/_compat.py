"""Backward-compat shim. Prefer :class:`outplayarena_sdk.MCPClient` directly,
or use :class:`outplayarena_sdk.BaseAgent` for the new autonomous-loop API.

This module exists so existing scripts and examples that imported ``MCPAgent``
keep working after the rework.  New code should use :class:`BaseAgent` (see
``agents/games/`` for per-game subclasses) or :class:`MCPClient` directly.
"""
from __future__ import annotations

from typing import Any

from outplayarena_sdk.mcp_client import MCPClient as _MCPClient


class MCPAgent(_MCPClient):
    """Thin alias for :class:`MCPClient` kept for backward compatibility.

    The previous ``MCPAgent`` wrapped :class:`MCPClient` and exposed a
    ``player`` property that *decoded* the session key with the backend's
    shared HMAC secret to recover the player identifier. As of v0.2.0 the
    SDK no longer holds the secret and treats the session key as an opaque
    auth handle. Pass the player explicitly instead::

        MCPAgent(mcp_url, session_key, player="A")

    If you don't know the player at construction time, set it on the
    returned instance before the first call that needs it::

        agent = MCPAgent(mcp_url, session_key)
        agent.player = "A"
    """

    def get_observation(self, variant: str = "neutral") -> dict[str, str]:
        """Alias for :meth:`_call_tool` returning a dict."""
        result = self._call_tool("get_observation", {"variant": variant})
        if isinstance(result, dict):
            return result
        return {"system": "", "turn": ""}

    def get_game_state(self) -> dict[str, Any]:
        """Alias for :meth:`_call_tool` returning the state dict."""
        result = self._call_tool("get_game_state")
        if isinstance(result, dict):
            return result
        return {}

    def submit_action(self, allocation: Any) -> dict[str, Any]:
        """Alias for :meth:`_call_tool` returning the action response."""
        result = self._call_tool("submit_action", {"allocation": allocation})
        if isinstance(result, dict):
            return result
        return {}

    def get_results(self) -> dict[str, Any]:
        """Alias for :meth:`_call_tool` returning the final results."""
        result = self._call_tool("get_results")
        if isinstance(result, dict):
            return result
        return {}


__all__ = ["MCPAgent"]
