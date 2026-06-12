from __future__ import annotations

import os

from nash_arena_sdk.client import ArenaClient, validate_session_key


class MCPAgent:
    """Agent that wraps the MCP server tool interface for use in multi-agent scripts.

    Each agent only needs:
      - player_token  (nks_... from create_experiment response["player_tokens"])
      - base_url      (NASH_ARENA_BASE_URL, defaults to localhost)

    Exposes the tools the MCP server exposes to real agents:
      get_observation()  -> {"system": str, "turn": str}
      submit_action()    -> submit the action for this round
      get_game_state()   -> raw game state dict
      get_results()      -> final scores and metrics
    """

    def __init__(
        self,
        player_token: str,
        base_url: str | None = None,
        jwt_secret: str | None = None,
    ):
        self.token = player_token
        self.base_url = (
            base_url
            or os.environ.get("NASH_ARENA_BASE_URL")
            or os.environ.get("ARENA_BASE_URL", "http://127.0.0.1:8000/api")
        )
        secret = jwt_secret or os.environ.get("JWT_SECRET", "dev-secret-change-me")
        session_id, self.player = validate_session_key(player_token, secret)
        self._client = ArenaClient(
            base_url=self.base_url, session_id=session_id, token=player_token
        )

    def get_observation(self, variant: str = "neutral") -> dict:
        """Return rendered system + turn prompts for the current game state."""
        return self._client.get_observation(self.player, variant=variant)

    def submit_action(self, allocation: object) -> dict:
        """Submit this agent's action for the current round."""
        return self._client.submit_action(allocation)

    def get_game_state(self) -> dict:
        """Return the raw current game state."""
        return self._client.get_state()

    def get_results(self) -> dict:
        """Return final scores and metrics once the game is complete."""
        return self._client.get_results()

    def is_terminal(self) -> bool:
        """Return True if the game is complete."""
        return self._client.is_terminal()
