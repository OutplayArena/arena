"""Backward-compat shim. Prefer :class:`outplayarena_sdk.MCPClient` directly,
or use :class:`outplayarena_sdk.BaseAgent` for the new autonomous-loop API.

This module exists so existing scripts and examples that imported ``MCPAgent``
keep working after the rework.  New code should use ``BaseAgent`` (see
``agents/games/`` for per-game subclasses) or ``MCPClient`` directly.
"""
from __future__ import annotations

from typing import Any

from outplayarena_sdk.mcp_client import MCPClient as _MCPClient


class MCPAgent(_MCPClient):
    """Thin alias for :class:`MCPClient` kept for backward compatibility.

    The previous ``MCPAgent`` wrapped ``MCPClient`` with a few extra
    accessors (``player``, ``base_url``). Those are still available
    because they were already inherited or trivial to recover from the
    session key.

    Prefer :class:`outplayarena_sdk.BaseAgent` (and its
    per-game subclasses) for new code.
    """

    @property
    def player(self) -> str:
        """Player identifier extracted from the session key."""
        from outplayarena_sdk.base import _default_jwt_secret
        from outplayarena_sdk.client import validate_session_key

        try:
            _, player = validate_session_key(self.session_key, _default_jwt_secret())
            return player
        except ValueError:
            return ""

    def get_observation(self, variant: str = "neutral") -> dict[str, str]:
        """Alias for ``_call_tool("get_observation", {...})`` returning a dict."""
        result = self._call_tool("get_observation", {"variant": variant})
        if isinstance(result, dict):
            return result
        return {"system": "", "turn": ""}

    def get_game_state(self) -> dict[str, Any]:
        """Alias for ``_call_tool("get_game_state")`` returning the state dict."""
        return self._call_tool("get_game_state")

    def submit_action(self, allocation: Any) -> dict[str, Any]:
        """Alias for ``_call_tool("submit_action", ...)``."""
        return self._call_tool("submit_action", {"allocation": allocation})

    def get_results(self) -> dict[str, Any]:
        """Alias for ``_call_tool("get_results")``."""
        return self._call_tool("get_results")


__all__ = ["MCPAgent"]
