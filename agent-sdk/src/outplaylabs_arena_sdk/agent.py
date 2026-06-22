"""OutplayLabs Arena agent with MCP-first, REST-fallback architecture."""
from __future__ import annotations

import os

from outplaylabs_arena_sdk.client import ArenaClient, validate_session_key
from outplaylabs_arena_sdk.mcp_client import MCPClient


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
            or os.environ.get("OUTPLAYLABS_ARENA_BASE_URL")
            or os.environ.get("ARENA_BASE_URL", "http://127.0.0.1:8000/api")
        )

        self._mcp_client: MCPClient | None = None
        self._rest_client = ArenaClient(
            base_url=self.base_url, session_id=session_id, token=player_token
        )

        if self.use_mcp:
            self._mcp_client = MCPClient(mcp_url, player_token)
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

    def get_mailbox(self) -> list[dict]:
        """Get mailbox messages visible to this player."""
        if self._mcp_client:
            return self._mcp_client.get_mailbox()
        return self._rest_client.get_mailbox(self.player)

    def send_message(self, content: str, recipient: str = "all") -> dict:
        """Send a message via the mailbox."""
        if self._mcp_client:
            return self._mcp_client.send_message(content, recipient)
        return self._rest_client.send_message(content, recipient)

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
    """Agent that communicates with the OutplayLabs Arena server via REST API only.

    Provides the same game interaction interface as :class:`MCPAgent` but
    exclusively uses HTTP REST calls, without any MCP/SSE transport. Use
    this when the MCP endpoint is unavailable or when a simpler REST-only
    integration is preferred.

    Supports the context-manager protocol for automatic cleanup.

    Attributes:
        token: The player token (``nks_...``) used for authentication.
        player: The player identifier extracted from the token.
        base_url: The base URL of the arena REST API.

    Examples:
        >>> agent = RESTAgent(player_token="nks_...", base_url="http://localhost:8000/api")
        >>> agent.transport
        'rest'
        >>> obs = agent.get_observation()
        >>> action = {"allocation": {"A": 5, "B": 5}}
        >>> result = agent.submit_action(action)
        >>> agent.close()
    """

    def __init__(
        self,
        player_token: str,
        base_url: str | None = None,
        jwt_secret: str | None = None,
    ):
        """Initialize a REST-only arena agent.

        Args:
            player_token: The player token (``nks_...``) obtained from
                ``create_experiment`` response's ``player_tokens``.
            base_url: Base URL for the arena REST API. Falls back to the
                ``OUTPLAYLABS_ARENA_BASE_URL`` or ``ARENA_BASE_URL`` environment
                variables, then to ``"http://127.0.0.1:8000/api"``.
            jwt_secret: Secret used to validate the player token's JWT.
                Falls back to the ``JWT_SECRET`` environment variable,
                then to a development default.
        """
        self.token = player_token
        secret = jwt_secret or os.environ.get("JWT_SECRET", "dev-secret-change-me")
        session_id, self.player = validate_session_key(player_token, secret)

        self.base_url = (
            base_url
            or os.environ.get("OUTPLAYLABS_ARENA_BASE_URL")
            or os.environ.get("ARENA_BASE_URL", "http://127.0.0.1:8000/api")
        )

        self._client = ArenaClient(
            base_url=self.base_url, session_id=session_id, token=player_token
        )

    @property
    def transport(self) -> str:
        """Return the transport protocol used by this agent.

        Returns:
            Always returns ``"rest"`` since this agent only uses REST.
        """
        return "rest"

    def get_observation(self, variant: str = "neutral") -> dict:
        """Return rendered system and turn prompts for the current game state.

        Args:
            variant: The prompt variant to retrieve. Defaults to
                ``"neutral"``.

        Returns:
            A dictionary with ``"system"`` and ``"turn"`` keys containing
            the rendered prompt strings for the current game state.
        """
        return self._client.get_observation(self.player, variant=variant)

    def submit_action(self, allocation: object) -> dict:
        """Submit this agent's action for the current round.

        Args:
            allocation: The action to submit. The expected structure
                depends on the game being played (e.g., a dict mapping
                battlefield names to troop counts for Blotto).

        Returns:
            A dictionary containing the server's response after
            processing the submitted action.
        """
        return self._client.submit_action(allocation)

    def get_game_state(self) -> dict:
        """Return the raw current game state.

        Returns:
            A dictionary representing the full game state, including
            phase, round number, and any game-specific data.
        """
        return self._client.get_state()

    def get_results(self) -> dict:
        """Return final scores and metrics once the game is complete.

        Returns:
            A dictionary containing ``"winner"``, ``"total_scores"``,
            and ``"metrics"`` keys with the final game results.
        """
        return self._client.get_results()

    def is_terminal(self) -> bool:
        """Check whether the game has reached a terminal state.

        Returns:
            ``True`` if the game is complete, ``False`` otherwise.
        """
        return self._client.is_terminal()
