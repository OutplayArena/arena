import os
from contextvars import ContextVar

import httpx
from dotenv import load_dotenv

load_dotenv()

from mcp.server.transport_security import TransportSecuritySettings  # noqa: E402
from mcp.server.fastmcp import FastMCP  # noqa: E402
from outplaylabs_arena_sdk.client import ArenaClient  # noqa: E402
from outplaylabs_arena.auth.session_key import SESSION_KEY_PREFIX, validate_session_key  # noqa: E402

OUTPLAYLABS_ARENA_BASE_URL = (
    os.environ.get("OUTPLAYLABS_ARENA_BASE_URL")
    or os.environ.get("ARENA_BASE_URL", "http://127.0.0.1:8000/api")
)

# Per-request context: (session_id, player, raw_session_key)
_session_ctx: ContextVar[tuple[str, str, str]] = ContextVar("session_ctx")

# Stdio-mode fallback: when LLMAgent spawns a local MCP subprocess it passes
# OUTPLAYLABS_ARENA_KEY via the environment.  Pre-populate the ContextVar for the
# lifetime of that process so tool calls work without HTTP middleware.
_stdio_key = os.environ.get("OUTPLAYLABS_ARENA_KEY")
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
        base_url=OUTPLAYLABS_ARENA_BASE_URL,
        session_id=session_id,
        token=session_key,
        http_client=httpx.Client(timeout=10.0),
    )


def player_id() -> str:
    _, player, _ = get_session()
    return player


mcp = FastMCP("outplaylabs-arena", stateless_http=True, transport_security=TransportSecuritySettings(enable_dns_rebinding_protection=False))


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


@mcp.tool()
def get_game_skill(game: str) -> dict:
    """
    Get the strategy skill/guide for a specific game.

    Returns the skill.md content parsed into structured sections:
    game, title, and sections (dict of section_name -> content).

    Use this to understand game rules, action format, and strategic hints
    before playing.
    """
    return arena_client().get_game_skill(game)


@mcp.tool()
def get_agent_manifest(game: str) -> dict:
    """
    Get a downloadable agent manifest for a game.

    The manifest is a complete skill package containing:
    - All MCP tool definitions (JSON Schema + OpenAI function-calling format)
    - Game metadata, lifecycle, and action format
    - Strategy guide and prompt templates
    - Auth instructions and MCP endpoint URL

    External agent harnesses can download this manifest to understand
    how to interact with the platform without needing the OutplayLabs Arena SDK.
    """
    return arena_client().get_agent_manifest(game)


@mcp.prompt("outplaylabs-arena-intro")
def outplaylabs_arena_intro() -> list[dict]:
    """
    Universal platform introduction for external MCP agents.

    Teaches the agent how OutplayLabs Arena works: authentication, available tools,
    game lifecycle, and how to discover per-game skills.
    """
    return [
        {
            "role": "user",
            "content": (
                "# OutplayLabs Arena Platform\n\n"
                "You are an agent playing games on the OutplayLabs Arena platform via MCP tools.\n\n"
                "## Authentication\n"
                "Every MCP request carries: `Authorization: Bearer nks_<session_key>`\n"
                "Your session key is provided when an experiment is created via the platform API.\n\n"
                "## Available MCP Tools\n\n"
                "### Game Catalog\n"
                "- `list_games` — list all available games\n"
                "- `get_game_details(game)` — get game metadata and config schema\n"
                "- `get_game_prompts(game)` — get prompt templates and action format\n"
                "- `get_game_metrics(game)` — get metric declarations\n"
                "- `get_game_skill(game)` — get parsed strategy guide for a game\n"
                "- `get_agent_manifest(game)` — get full downloadable skill manifest\n\n"
                "### Gameplay\n"
                "- `get_game_state` — get current game state (phase, round, awaiting, scores)\n"
                "- `get_observation(variant)` — get rendered system + turn prompts for LLM\n"
                "- `submit_action(allocation)` — submit your action for the current round\n"
                "- `get_results` — get final scores and metrics after game completes\n\n"
                "### Communication\n"
                "- `get_mailbox` — read messages from opponent\n"
                "- `send_message(content, recipient)` — send a message to opponent\n\n"
                "## Game Lifecycle\n\n"
                "1. The experiment creator calls POST /api/experiment to create a session\n"
                "2. You receive a session key (nks_...) and mcp_url\n"
                "3. Connect to the MCP server at mcp_url with Bearer auth\n"
                "4. Game loop until phase is 'complete':\n"
                "   a. Call `get_game_state` — check if you are in `awaiting`\n"
                "   b. Call `get_observation` for system + turn prompts\n"
                "   c. Optionally call `get_mailbox` / `send_message` to communicate\n"
                "   d. Call `submit_action` with your action\n"
                "5. Call `get_results` for final scores\n\n"
                "## Discovering Per-Game Skills\n"
                "Call `list_games` to see available games, then `get_game_skill(game)` for "
                "the strategy guide or `get_agent_manifest(game)` for the complete downloadable "
                "skill package with tool definitions in OpenAI function-calling format."
            ),
        },
    ]


@mcp.prompt("outplaylabs-arena-game-{game}")
def outplaylabs_arena_game_prompt(game: str) -> list[dict]:
    """
    Per-game introduction prompt. Returns the skill guide and prompt templates
    for the specified game, ready for use as LLM context.
    """
    try:
        skill_data = arena_client().get_game_skill(game)
    except Exception:
        skill_data = {"game": game, "title": f"{game} Skill", "sections": {}}

    try:
        prompts = arena_client().get_game_prompts(game)
    except Exception:
        prompts = {}

    sections = skill_data.get("sections", {})
    intro_parts = [
        f"# {skill_data.get('title', game)}\n",
        sections.get("introduction", ""),
        "",
        "## Objective",
        sections.get("objective", ""),
        "",
        "## Action Format",
        sections.get("action_format", ""),
        "",
        "## Rules",
        sections.get("rules", ""),
        "",
        "## Strategy Hints",
        sections.get("strategy_hints", sections.get("strategy_notes", "")),
    ]
    intro = "\n".join(intro_parts)

    system_prompt = prompts.get("system", "")
    turn_template = prompts.get("state", prompts.get("turn", ""))

    content = intro
    if system_prompt:
        content += f"\n\n---\n\n## System Prompt Template\n\n{system_prompt}"
    if turn_template:
        content += f"\n\n## Turn Prompt Template\n\n{turn_template}"

    return [{"role": "user", "content": content}]


# Build the ASGI app: session-key middleware wrapping the stateless MCP HTTP server
app = _SessionKeyMiddleware(mcp.streamable_http_app())


if __name__ == "__main__":
    import uvicorn
    host = os.environ.get("FASTMCP_HOST", "127.0.0.1")
    port = int(os.environ.get("FASTMCP_PORT", "8000"))
    uvicorn.run("outplaylabs_arena.mcp_server:app", host=host, port=port)
