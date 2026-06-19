import os
from contextvars import ContextVar

import httpx
from dotenv import load_dotenv

load_dotenv()

from mcp.server.transport_security import TransportSecuritySettings  # noqa: E402
from mcp.server.fastmcp import FastMCP  # noqa: E402
from nash_arena_sdk.client import ArenaClient  # noqa: E402
from nash_arena.auth.session_key import SESSION_KEY_PREFIX, validate_session_key  # noqa: E402

NASH_ARENA_BASE_URL = (
    os.environ.get("NASH_ARENA_BASE_URL")
    or os.environ.get("ARENA_BASE_URL", "http://127.0.0.1:8000/api")
)

# Per-request context: (session_id, player, raw_session_key)
_session_ctx: ContextVar[tuple[str, str, str]] = ContextVar("session_ctx")

# Stdio-mode fallback: when LLMAgent spawns a local MCP subprocess it passes
# NASH_ARENA_KEY via the environment.  Pre-populate the ContextVar for the
# lifetime of that process so tool calls work without HTTP middleware.
_stdio_key = os.environ.get("NASH_ARENA_KEY")
if _stdio_key:
    try:
        _stdio_sid, _stdio_player = validate_session_key(_stdio_key)
        _session_ctx.set((_stdio_sid, _stdio_player, _stdio_key))
    except ValueError:
        pass


async def _send_json_error(send, status: int, message: str) -> None:
    body = f'{{"error": "{message}"}}'.encode()
    await send({
        "type": "http.response.start",
        "status": status,
        "headers": [
            (b"content-type", b"application/json"),
            (b"content-length", str(len(body)).encode()),
        ],
    })
    await send({"type": "http.response.body", "body": body})


class _SessionKeyMiddleware:
    """ASGI middleware that validates Bearer nks_... tokens and populates _session_ctx."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        path = scope.get("path", "")
        if path == "/health" or path.endswith("/health"):
            body = b'{"status":"ok"}'
            await send({"type": "http.response.start", "status": 200, "headers": [
                (b"content-type", b"application/json"),
                (b"content-length", str(len(body)).encode()),
            ]})
            await send({"type": "http.response.body", "body": body})
            return

        headers = {k: v for k, v in scope.get("headers", [])}
        auth = headers.get(b"authorization", b"").decode()

        if not auth.startswith(f"Bearer {SESSION_KEY_PREFIX}"):
            await _send_json_error(send, 401, "Missing session key")
            return

        session_key = auth[len("Bearer "):]
        try:
            session_id, player = validate_session_key(session_key)
        except ValueError:
            await _send_json_error(send, 401, "Invalid session key")
            return

        token = _session_ctx.set((session_id, player, session_key))
        try:
            await self.app(scope, receive, send)
        finally:
            _session_ctx.reset(token)


def get_session() -> tuple[str, str, str]:
    try:
        return _session_ctx.get()
    except LookupError:
        raise RuntimeError("No session context — Authorization: Bearer nks_... header required")


def arena_client() -> ArenaClient:
    session_id, _player, session_key = get_session()
    return ArenaClient(
        base_url=NASH_ARENA_BASE_URL,
        session_id=session_id,
        token=session_key,
        http_client=httpx.Client(timeout=10.0),
    )


def player_id() -> str:
    _, player, _ = get_session()
    return player


mcp = FastMCP("nash-arena", stateless_http=True, transport_security=TransportSecuritySettings(enable_dns_rebinding_protection=False))


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


@mcp.tool()
def get_mailbox() -> dict:
    """
    Read mailbox messages visible to you.

    Returns ``{"messages": [...]}`` where each message has:
    id, sender, recipient, content, round, created_at.
    """
    return {"messages": arena_client().get_mailbox(player_id())}


@mcp.tool()
def send_message(content: str, recipient: str = "all") -> dict:
    """
    Send a message to opponent(s) via mailbox.

    Use strategically — you may send honest signals or decoys.
    Like sending an email: the recipient sees your message, but your true
    intentions remain private.

    content: Message text (max 200 characters).
    recipient: Target player ID or "all" for broadcast (default).
    """
    return arena_client().send_message(content=content, recipient=recipient)


# Build the ASGI app: session-key middleware wrapping the stateless MCP HTTP server
app = _SessionKeyMiddleware(mcp.streamable_http_app())


if __name__ == "__main__":
    import uvicorn
    host = os.environ.get("FASTMCP_HOST", "127.0.0.1")
    port = int(os.environ.get("FASTMCP_PORT", "8000"))
    uvicorn.run("nash_arena.mcp_server:app", host=host, port=port)
