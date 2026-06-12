import os

from dotenv import load_dotenv
load_dotenv()

from mcp.server.fastmcp import FastMCP
from nash_arena.client import ArenaClient
from nash_arena.auth.session_key import validate_session_key

mcp = FastMCP("nash-arena")

def required_env(name):
    value = os.environ.get(name)
    if not value:
        raise RuntimeError(f"{name} is required")
    return value

def arena_client():
    base_url = os.environ.get("NASH_ARENA_BASE_URL") or os.environ.get("ARENA_BASE_URL", "http://127.0.0.1:8000/api")
    key = required_env("NASH_ARENA_KEY")
    session_id, _player = validate_session_key(key)
    return ArenaClient(base_url=base_url, session_id=session_id, token=key)


def player_id() -> str:
    """Return the player ID encoded in the session key."""
    key = required_env("NASH_ARENA_KEY")
    _, player = validate_session_key(key)
    return player

@mcp.tool()
def get_observation(variant: str = "neutral") -> dict:
    """
    Get your rendered system prompt and turn prompt for the current game state.

    Returns {"system": str, "turn": str} — pass system as the LLM system message
    and turn as the user message. The server selects the correct template for your
    role (e.g. proposer vs responder in Ultimatum) automatically.

    variant: one of "neutral" (default), "gain_framed", "loss_framed"
    """
    return arena_client().get_observation(player_id(), variant=variant)


@mcp.tool()
def get_game_state() -> dict:
    """Get the raw current game state for your assigned game session."""
    return arena_client().get_state()

@mcp.tool()
def submit_action(allocation) -> dict:
    """Submit your action for the current round (format depends on game)."""
    return arena_client().submit_action(allocation=allocation)

@mcp.tool()
def get_results() -> dict:
    """Retrieve final scores and metrics after the game is complete."""
    return arena_client().get_results()

@mcp.tool()
def list_games() -> list[dict]:
    """List games available in the arena game catalog."""
    return arena_client().list_games()

@mcp.tool()
def get_game_details(game: str) -> dict:
    """Get metadata, ontology, config schema, and example config for a game."""
    return arena_client().get_game_details(game)

@mcp.tool()
def get_game_metrics(game: str) -> dict:
    """Get metric declarations for a game."""
    return arena_client().get_game_metrics(game)

@mcp.tool()
def get_game_prompts(game: str) -> dict:
    """Get default prompt templates and action format for a game."""
    return arena_client().get_game_prompts(game)

if __name__ == "__main__":
    mcp.run()
