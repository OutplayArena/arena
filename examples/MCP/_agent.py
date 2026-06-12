"""
MCPAgent — wraps the MCP server tool interface for use in multi-agent scripts.

Each agent only needs:
  - player_token  (nks_… from create_experiment response["player_tokens"])
  - base_url      (NASH_ARENA_BASE_URL, defaults to localhost)

Exposes exactly the four tools the MCP server exposes to real agents:
  get_observation()  → {"system": str, "turn": str}
  submit_action()    → submit the action for this round
  get_game_state()   → raw game state dict
  get_results()      → final scores and metrics

In production, a real Claude/LLM agent connects to the MCP server process with
NASH_ARENA_KEY=<player_token> set in its environment. This class mirrors that
interface in-process so the same orchestration logic works in scripts.
"""
import os
from dotenv import load_dotenv
load_dotenv()  # must run before nash_arena.auth imports JWT_SECRET

from nash_arena.client import ArenaClient
from nash_arena.auth.session_key import validate_session_key


class MCPAgent:
    def __init__(self, player_token: str, base_url: str | None = None):
        self.token = player_token
        self.base_url = (
            base_url
            or os.environ.get("NASH_ARENA_BASE_URL")
            or os.environ.get("ARENA_BASE_URL", "http://127.0.0.1:8000/api")
        )
        session_id, self.player = validate_session_key(player_token)
        self._client = ArenaClient(
            base_url=self.base_url, session_id=session_id, token=player_token
        )

    def get_observation(self, variant: str = "neutral") -> dict:
        """Return rendered system + turn prompts for the current game state."""
        return self._client.get_observation(self.player, variant=variant)

    def submit_action(self, allocation) -> dict:
        """Submit this agent's action for the current round."""
        return self._client.submit_action(allocation)

    def get_game_state(self) -> dict:
        """Return the raw current game state."""
        return self._client.get_state()

    def get_results(self) -> dict:
        """Return final scores and metrics once the game is complete."""
        return self._client.get_results()
