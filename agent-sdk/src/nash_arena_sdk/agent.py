"""NashArena agent with MCP-first, REST-fallback architecture."""
from __future__ import annotations

import os

from nash_arena_sdk.client import ArenaClient, validate_session_key
from nash_arena_sdk.mcp_client import MCPClient


class MCPAgent:
    """Agent that connects to the arena via MCP protocol (SSE) or REST.

    By default, uses MCP when mcp_url is provided (from create_experiment response).
    Falls back to REST API when MCP is not available.

    Each agent needs:
      - player_token  (nks_... from create_experiment response["player_tokens"])
      - mcp_url       (optional, from create_experiment response["mcp_url"])
      - base_url      (optional, for REST fallback)

    Exposes the same interface regardless of transport:
      get_observation()  -> {"system": str, "turn": str}
      submit_action()    -> submit the action for this round
      get_game_state()   -> raw game state dict
      get_results()      -> final scores and metrics
    """

    def __init__(
        self,
        player_token: str,
        mcp_url: str | None = None,
        base_url: str | None = None,
        jwt_secret: str | None = None,
        use_mcp: bool = True,
    ):
        self.token = player_token
        self.mcp_url = mcp_url
        self.use_mcp = use_mcp and mcp_url is not None

        secret = jwt_secret or os.environ.get("JWT_SECRET", "dev-secret-change-me")
        session_id, self.player = validate_session_key(player_token, secret)

        self.base_url = (
            base_url
            or os.environ.get("NASH_ARENA_BASE_URL")
            or os.environ.get("ARENA_BASE_URL", "http://127.0.0.1:8000/api")
        )

        self._mcp_client: MCPClient | None = None
        self._rest_client = ArenaClient(
            base_url=self.base_url, session_id=session_id, token=player_token
        )

        if self.use_mcp:
            self._mcp_client = MCPClient(mcp_url)
            self._mcp_client.connect()

    @property
    def transport(self) -> str:
        """Return the transport being used: 'mcp' or 'rest'."""
        return "mcp" if self.use_mcp and self._mcp_client else "rest"

    def get_observation(self, variant: str = "neutral") -> dict:
        """Return rendered system + turn prompts for the current game state."""
        if self._mcp_client:
            return self._mcp_client.get_observation(variant=variant)
        return self._rest_client.get_observation(self.player, variant=variant)

    def submit_action(self, allocation: object) -> dict:
        """Submit this agent's action for the current round."""
        if self._mcp_client:
            return self._mcp_client.submit_action(allocation)
        return self._rest_client.submit_action(allocation)

    def get_game_state(self) -> dict:
        """Return the raw current game state."""
        if self._mcp_client:
            return self._mcp_client.get_game_state()
        return self._rest_client.get_state()

    def get_results(self) -> dict:
        """Return final scores and metrics once the game is complete."""
        if self._mcp_client:
            return self._mcp_client.get_results()
        return self._rest_client.get_results()

    def is_terminal(self) -> bool:
        """Return True if the game is complete."""
        if self._mcp_client:
            state = self._mcp_client.get_game_state()
            return state.get("phase") == "complete"
        return self._rest_client.is_terminal()

    def close(self) -> None:
        """Close the MCP connection if open."""
        if getattr(self, '_mcp_client', None):
            self._mcp_client.disconnect()
            self._mcp_client = None

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()

    def __del__(self):
        self.close()


class ArenaAgent(MCPAgent):
    """Alias for MCPAgent for backward compatibility.

    Deprecated: Use MCPAgent directly.
    """

    pass


class RESTAgent:
    """Agent that uses only REST API (no MCP).

    Use this when you need direct REST access without MCP protocol.
    """

    def __init__(
        self,
        player_token: str,
        base_url: str | None = None,
        jwt_secret: str | None = None,
    ):
        self.token = player_token
        secret = jwt_secret or os.environ.get("JWT_SECRET", "dev-secret-change-me")
        session_id, self.player = validate_session_key(player_token, secret)

        self.base_url = (
            base_url
            or os.environ.get("NASH_ARENA_BASE_URL")
            or os.environ.get("ARENA_BASE_URL", "http://127.0.0.1:8000/api")
        )

        self._client = ArenaClient(
            base_url=self.base_url, session_id=session_id, token=player_token
        )

    @property
    def transport(self) -> str:
        return "rest"

    def get_observation(self, variant: str = "neutral") -> dict:
        return self._client.get_observation(self.player, variant=variant)

    def submit_action(self, allocation: object) -> dict:
        return self._client.submit_action(allocation)

    def get_game_state(self) -> dict:
        return self._client.get_state()

    def get_results(self) -> dict:
        return self._client.get_results()

    def is_terminal(self) -> bool:
        return self._client.is_terminal()
