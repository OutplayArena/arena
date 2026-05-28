import os
from mcp.server.fastmcp import FastMCP
from arena.client import ArenaClient

mcp = FastMCP("blotto-arena")

def required_env(name):
    value = os.environ.get(name)
    if not value:
        raise RuntimeError(f"{name} is required")
    return value

def arena_client():
    base_url = os.environ.get("ARENA_BASE_URL", "http://127.0.0.1:8000")
    session_id = required_env("ARENA_SESSION_ID")
    token = required_env("ARENA_SESSION_TOKEN")
    return ArenaClient(base_url=base_url, session_id=session_id, token=token)

@mcp.tool()
def get_game_state() -> dict:
    """Get the current game state for your assigned Blotto session."""
    return arena_client().get_state()

@mcp.tool()
def submit_action(allocation: list[int]) -> dict:
    """Submit your resource allocation for the current round."""
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
