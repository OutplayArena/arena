# ruff: noqa: E402
import asyncio
import json
import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, AsyncIterator
from uuid import uuid4

import yaml
from dotenv import load_dotenv

load_dotenv()

from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request
from fastapi.responses import RedirectResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware
from pydantic import BaseModel
from sqlalchemy import select, func, delete
from sqlalchemy.ext.asyncio import AsyncSession

from outplaylabs_arena.db import get_db, async_session as _async_session_factory
from outplaylabs_arena.experiment_config import split_runtime_config
from outplaylabs_arena.game_registry import GameRegistry, GameRegistryError
from outplaylabs_arena.manifest import build_agent_manifest
from outplaylabs_arena.messaging import RedisBroker, StatePersister, MessageLogger
from outplaylabs_arena.messaging.broker import MessageBroker
from outplaylabs_arena.metrics import AgentRegistry, get_global_registry, set_global_registry, MatchEvaluator, load_registry, save_registry
from outplaylabs_arena.session import GameSession, _serialize_state
from outplaylabs_arena.models.session import SessionModel
from outplaylabs_arena.models.api_key import ApiKey
from outplaylabs_arena.models.message_log import MessageLog
from outplaylabs_arena.auth.oauth import github_login, github_callback, google_login, google_callback, CALLBACK_BASE
from outplaylabs_arena.auth.jwt import create_access_token
from outplaylabs_arena.auth.dependencies import get_current_user, get_local_or_optional_user, require_user
from outplaylabs_arena.auth.apikey import generate_platform_key
from outplaylabs_arena.models.user import User


API_PREFIX = os.environ.get("API_PREFIX", "/api")
MCP_ENDPOINT = os.environ.get("MCP_ENDPOINT")
_SITE_YAML = Path(__file__).resolve().parent.parent.parent / "frontend" / "site.yaml"
if not _SITE_YAML.is_file():
    _SITE_YAML = Path(__file__).resolve().parent.parent / "site.yaml"
SITE_YAML = _SITE_YAML
STATIC_ROOT = Path(__file__).resolve().parent.parent / "static"
GAME_REGISTRY = GameRegistry()

_broker: RedisBroker | None = None
_persister: StatePersister | None = None
_logger: MessageLogger | None = None


@asynccontextmanager
async def lifespan(application: FastAPI) -> AsyncIterator[None]:
    global _broker, _persister, _logger
    _broker = RedisBroker()
    _persister = StatePersister(_broker, _async_session_factory)
    await _persister.start()
    _logger = MessageLogger(_broker, _async_session_factory)
    await _logger.start()
    yield
    if _logger is not None:
        await _logger.stop()
        _logger = None
    if _persister is not None:
        await _persister.stop()
        _persister = None
    if _broker is not None:
        await _broker.close()
        _broker = None


app = FastAPI(title="OutplayLabs Arena Agent Arena", lifespan=lifespan)
app.add_middleware(SessionMiddleware, secret_key=os.environ.get("JWT_SECRET", "dev-secret-change-me"))


@app.on_event("startup")
async def _load_registry_from_db() -> None:
    try:
        async with _async_session_factory() as db:
            registry = await load_registry(db)
            set_global_registry(registry)
    except Exception:
        pass


class ActionRequest(BaseModel):
    allocation: Any = None
    forfeit: bool = False


class UserResponse(BaseModel):
    id: str
    email: str
    name: str
    avatar_url: str | None

    model_config = {"from_attributes": True}


def config_from_request(request: dict[str, Any]):
    game_payload, _ = split_runtime_config(request)
    return GAME_REGISTRY.config_from_request(game_payload)


async def get_session(session_id: str, db: AsyncSession) -> GameSession:
    result = await db.execute(select(SessionModel).where(SessionModel.id == session_id))
    row = result.scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="session not found")
    return GameSession.from_db_row(row)


def bearer_token(authorization: str | None) -> str:
    prefix = "Bearer "
    if not authorization or not authorization.startswith(prefix):
        raise HTTPException(status_code=401, detail="missing bearer token")
    token = authorization[len(prefix):].strip()
    if not token:
        raise HTTPException(status_code=401, detail="missing bearer token")
    return token


def action_error(exc: ValueError) -> HTTPException:
    message = str(exc)
    if "invalid player token" in message or "invalid session key" in message:
        return HTTPException(status_code=401, detail=message)
    if "already submitted" in message or "already complete" in message:
        return HTTPException(status_code=409, detail=message)
    return HTTPException(status_code=400, detail=message)


async def require_agent_api_dep(
    request: Request,
    authorization: str | None = Header(default=None),
    db: AsyncSession = Depends(get_db),
) -> None:
    if os.environ.get("ENABLE_AGENT_REST_API", "false").lower() == "true":
        return
    if authorization and authorization.startswith("Bearer "):
        token = authorization[len("Bearer "):]
        from outplaylabs_arena.auth.session_key import SESSION_KEY_PREFIX, validate_session_key
        if token.startswith(SESSION_KEY_PREFIX):
            try:
                validate_session_key(token)
                return
            except ValueError:
                pass
        try:
            from outplaylabs_arena.auth.dependencies import get_current_user
            await get_current_user(authorization, db)
            return
        except HTTPException:
            pass
    raise HTTPException(status_code=403, detail="Agent REST API is disabled")


def require_agent_api():
    return Depends(require_agent_api_dep)


def game_registry_error(exc: GameRegistryError) -> HTTPException:
    return HTTPException(status_code=404, detail=str(exc))


async def get_broker() -> AsyncIterator[MessageBroker]:
    if _broker is None:
        raise RuntimeError("broker not initialized")
    yield _broker


@app.get(f"{API_PREFIX}/health")
def health():
    """Health check endpoint."""
    return {"status": "ok"}


@app.get(f"{API_PREFIX}/games")
def list_games():
    """List all registered games."""
    return GAME_REGISTRY.list_games()


@app.get(f"{API_PREFIX}/games/{{name}}")
def get_game(name: str):
    """Get configuration details for a specific game."""
    try:
        return GAME_REGISTRY.get_game(name)
    except GameRegistryError as exc:
        raise game_registry_error(exc) from exc


@app.get(f"{API_PREFIX}/games/{{name}}/metrics")
def get_game_metrics(name: str):
    """Get scoring metrics for a specific game."""
    try:
        return GAME_REGISTRY.get_game_metrics(name)
    except GameRegistryError as exc:
        raise game_registry_error(exc) from exc


@app.get(f"{API_PREFIX}/games/{{name}}/prompts")
def get_game_prompts(name: str):
    """Get prompt templates for a specific game."""
    try:
        return GAME_REGISTRY.get_game_prompts(name)
    except GameRegistryError as exc:
        raise game_registry_error(exc) from exc


@app.get(f"{API_PREFIX}/games/{{name}}/scenarios")
def get_game_scenarios(name: str):
    """Get available scenarios for a specific game."""
    try:
        return {"scenarios": GAME_REGISTRY.get_game_scenarios(name)}
    except GameRegistryError as exc:
        raise game_registry_error(exc) from exc


@app.get(f"{API_PREFIX}/games/{{name}}/agents")
def get_game_agents(name: str):
    """Get registered agents for a specific game."""
    try:
        return GAME_REGISTRY.get_game_agents(name)
    except GameRegistryError as exc:
        raise game_registry_error(exc) from exc


@app.get(f"{API_PREFIX}/games/{{name}}/skill")
def get_game_skill(name: str):
    """Get the strategy skill/guide for a game (parsed sections)."""
    try:
        return GAME_REGISTRY.get_game_skill(name, structured=True)
    except GameRegistryError as exc:
        raise game_registry_error(exc) from exc


@app.get(f"{API_PREFIX}/games/{{name}}/manifest")
def get_game_manifest(name: str, request: Request):
    """Get a downloadable agent manifest for a game.

    Returns tool definitions (MCP + OpenAI function-calling), game lifecycle,
    action format, strategy guide, and examples. Public — no auth required.
    """
    try:
        return build_agent_manifest(
            game_name=name,
            registry=GAME_REGISTRY,
            mcp_url=MCP_ENDPOINT,
        )
    except GameRegistryError as exc:
        raise game_registry_error(exc) from exc


@app.post(f"{API_PREFIX}/experiment")
async def create_experiment(
    request: dict[str, Any],
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_user),
    broker: MessageBroker = Depends(get_broker),
    _: None = require_agent_api(),
):
    """Create a new experiment session for a game."""
    try:
        config = config_from_request(request)
        game = GAME_REGISTRY.game_from_config(config)
    except (ValueError, GameRegistryError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    interactive = request.get("interactive", False)
    locked = not interactive

    session = GameSession.create(config, game=game, locked=locked)

    agents = request.get("agents")
    if not isinstance(agents, dict):
        agent_a = request.get("agent_a")
        agent_b = request.get("agent_b")
        agents = {}
        if agent_a:
            agents["A"] = str(agent_a)
        if agent_b:
            agents["B"] = str(agent_b)
    if not agents:
        agents = None

    await session.save_new(
        db,
        user_id=str(user.id),
        agents=agents,
    )

    response = session.creation_response()

    if MCP_ENDPOINT:
        response["mcp_url"] = MCP_ENDPOINT

    await broker.publish(f"session:{session.session_id}:events", {
        "event": "session_created",
        "session_id": session.session_id,
        "status": session.status,
    })

    return response


@app.get(f"{API_PREFIX}/session/{{session_id}}/state")
async def get_state(
    session_id: str,
    db: AsyncSession = Depends(get_db),
    broker: MessageBroker = Depends(get_broker),
    _: None = require_agent_api(),
):
    """Get the current state of a session."""
    cached = await broker.cache_get(f"session:{session_id}:state")
    if cached is not None:
        return cached
    session = await get_session(session_id, db)
    return session.public_state()


@app.get(f"{API_PREFIX}/session/{{session_id}}/observation")
async def get_observation(
    session_id: str,
    player: str = Query(..., description="Player ID (e.g. A or B)"),
    variant: str = Query("neutral", description="Prompt variant: neutral, gain_framed, loss_framed"),
    db: AsyncSession = Depends(get_db),
    _: None = require_agent_api(),
):
    """Get the observation for a player in the current session state."""
    session = await get_session(session_id, db)
    state = session.public_state()
    config_dict = session.config.to_dict() if hasattr(session.config, "to_dict") else {}
    game_type = config_dict.get("game", "unknown")
    try:
        return GAME_REGISTRY.render_observation(game_type, state, config_dict, player, variant)
    except GameRegistryError as exc:
        raise game_registry_error(exc) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post(f"{API_PREFIX}/session/{{session_id}}/action")
async def submit_action(
    session_id: str,
    request: ActionRequest,
    db: AsyncSession = Depends(get_db),
    authorization: str | None = Header(default=None),
    broker: MessageBroker = Depends(get_broker),
    _: None = require_agent_api(),
):
    """Submit an action (allocation or forfeit) for a player in a session."""
    session = await get_session(session_id, db)
    token = bearer_token(authorization)

    try:
        session.submit_action_with_token(token, request.allocation, forfeit=request.forfeit)
    except ValueError as exc:
        raise action_error(exc) from exc
    except Exception as exc:
        session.mark_failed(str(exc))
        state_dict = _serialize_state(session.state)
        await broker.enqueue("state:persist", {
            "session_id": session_id,
            "state": state_dict,
            "status": session.status,
            "error_message": session.error_message,
            "locked": session.locked,
            "player_tokens": session.player_tokens,
        })
        player = session.player_for_token(token)
        round_number = state_dict.get("round_number", 0)
        agent_id = (session.agents or {}).get(player)
        await broker.enqueue("message:log", {
            "session_id": session_id,
            "player": player,
            "round_number": round_number,
            "agent_id": agent_id,
            "payload": request.allocation,
        })
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    state_dict = _serialize_state(session.state)
    session_row = await db.execute(select(SessionModel).where(SessionModel.id == session_id))
    row = session_row.scalar_one()
    row.state_json = state_dict
    row.status = session.status
    row.locked = session.locked
    row.player_tokens_json = session.player_tokens
    await db.commit()

    player = session.player_for_token(token)
    public = session.public_state()
    round_number = public.get("round", 0) or state_dict.get("round_number", 0)
    agent_id = (session.agents or {}).get(player)
    action_meta = {
        "player": player,
        "action": request.allocation,
        "agent_id": agent_id,
        "round_number": round_number,
    }
    public["_last_action"] = action_meta

    cache_payload = {**public}
    cache_payload.pop("_last_action", None)
    await broker.cache_set(f"session:{session_id}:state", cache_payload, ttl=600)
    await broker.publish(f"session:{session_id}:state", public)
    await broker.enqueue("message:log", {
        "session_id": session_id,
        "player": player,
        "round_number": round_number,
        "agent_id": agent_id,
        "payload": request.allocation,
    })
    await broker.publish(f"session:{session_id}:events", {
        "event": "action_submitted",
        "session_id": session_id,
        "player": player,
        "status": session.status,
    })
    return public


class HumanActionRequest(BaseModel):
    action: Any = None
    forfeit: bool = False


@app.get(f"{API_PREFIX}/session/{{session_id}}/interactive/schema")
async def get_interactive_schema(
    session_id: str,
    player: str = Query(..., description="Player ID (e.g. A or B)"),
    db: AsyncSession = Depends(get_db),
):
    """Get the action schema for interactive play."""
    session = await get_session(session_id, db)
    game = session.game

    from outplaylabs_arena.interactive_game_engine import InteractiveGameEngine
    if not isinstance(game, InteractiveGameEngine):
        raise HTTPException(status_code=400, detail="game does not support interactive play")

    return {
        "schema": game.human_action_schema(session.config),
        "ui_metadata": game.ui_metadata(session.config),
        "state": game.interactive_public_state(session.state, session.config, session_id, session.config_hash, player),
    }


@app.post(f"{API_PREFIX}/session/{{session_id}}/interactive/action")
async def submit_human_action(
    session_id: str,
    request: HumanActionRequest,
    player: str = Query(..., description="Player ID (e.g. A or B)"),
    db: AsyncSession = Depends(get_db),
    authorization: str | None = Header(default=None),
):
    """Submit a human player action with automatic formatting."""
    session = await get_session(session_id, db)
    token = bearer_token(authorization)

    from outplaylabs_arena.interactive_game_engine import InteractiveGameEngine
    if not isinstance(session.game, InteractiveGameEngine):
        raise HTTPException(status_code=400, detail="game does not support interactive play")

    game = session.game

    try:
        token_player = session.player_for_token(token)
        if token_player != player:
            raise HTTPException(status_code=403, detail="token does not match player")

        if request.forfeit:
            if hasattr(game, "forfeit_round"):
                session.state = game.forfeit_round(session.state, player)
            else:
                raise HTTPException(status_code=400, detail="game does not support forfeit")
        else:
            formatted_action = game.format_human_action(request.action, session.config)
            game.validate_human_action(session.state, player, formatted_action, session.config)
            session.submit_action(player, formatted_action)

        session._update_status_from_state()
    except HTTPException:
        raise
    except ValueError as exc:
        raise action_error(exc) from exc
    except Exception as exc:
        session.mark_failed(str(exc))
        await session.save_state(db)
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    await session.save_state(db)
    return game.interactive_public_state(session.state, session.config, session_id, session.config_hash, player)


@app.get(f"{API_PREFIX}/session/{{session_id}}/interactive/state")
async def get_interactive_state(
    session_id: str,
    player: str = Query(..., description="Player ID (e.g. A or B)"),
    db: AsyncSession = Depends(get_db),
):
    """Get interactive state with player-specific context."""
    session = await get_session(session_id, db)
    game = session.game

    from outplaylabs_arena.interactive_game_engine import InteractiveGameEngine
    if not isinstance(game, InteractiveGameEngine):
        return session.public_state()

    state = game.interactive_public_state(session.state, session.config, session_id, session.config_hash, player)
    state["messages"] = session.messages or []
    return state


@app.get(f"{API_PREFIX}/games/{{name}}/interactive/agents")
async def get_interactive_agents(name: str):
    """Get available agents for interactive play."""
    try:
        game_info = GAME_REGISTRY.get_game(name)
        config = GAME_REGISTRY.config_from_request({"game": name, **game_info.get("example_config", {})})
        game = GAME_REGISTRY.game_from_config(config)

        from outplaylabs_arena.interactive_game_engine import InteractiveGameEngine
        if isinstance(game, InteractiveGameEngine):
            return {"agents": game.get_available_agents(config)}
        return {"agents": []}
    except GameRegistryError as exc:
        raise game_registry_error(exc) from exc
    except Exception:
        return {"agents": []}


class MailboxSendRequest(BaseModel):
    content: str
    recipient: str = "all"


@app.post(f"{API_PREFIX}/session/{{session_id}}/mailbox/send")
async def send_mailbox_message(
    session_id: str,
    request: MailboxSendRequest,
    db: AsyncSession = Depends(get_db),
    authorization: str | None = Header(default=None),
    broker: MessageBroker = Depends(get_broker),
):
    """Send a mailbox message from a player."""
    session = await get_session(session_id, db)
    token = bearer_token(authorization)
    player = session.player_for_token(token)

    if not request.content or not request.content.strip():
        raise HTTPException(status_code=400, detail="message content cannot be empty")

    state_dict = _serialize_state(session.state)
    if state_dict.get("phase") == "complete":
        raise HTTPException(status_code=409, detail="game is already complete")

    msg = session.add_message(sender=player, content=request.content.strip(), recipient=request.recipient)

    session_row = await db.execute(select(SessionModel).where(SessionModel.id == session_id))
    row = session_row.scalar_one()
    row.messages_json = session.messages or []
    await db.commit()

    await broker.publish(f"mailbox:{session_id}", msg)
    return msg


@app.get(f"{API_PREFIX}/session/{{session_id}}/mailbox/messages")
async def get_mailbox_messages(
    session_id: str,
    player: str | None = Query(default=None, description="Player ID to filter visible messages"),
    db: AsyncSession = Depends(get_db),
):
    """Get mailbox messages for a session."""
    session = await get_session(session_id, db)
    messages = session.messages or []

    if player:
        messages = [
            m for m in messages
            if m.get("recipient") == "all"
            or m.get("recipient") == player
            or m.get("sender") == player
        ]

    return {"messages": messages}


def sanitize_for_json(obj: Any) -> Any:
    """Recursively sanitize an object to ensure JSON compatibility."""
    import math
    if isinstance(obj, float):
        if math.isnan(obj) or math.isinf(obj):
            return 0.0
        return obj
    if isinstance(obj, dict):
        return {k: sanitize_for_json(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [sanitize_for_json(item) for item in obj]
    return obj


@app.get(f"{API_PREFIX}/session/{{session_id}}/results")
async def get_results(session_id: str, db: AsyncSession = Depends(get_db)):
    """Get the final results and scores for a completed session."""
    session = await get_session(session_id, db)
    try:
        registry = get_global_registry()
        evaluator = MatchEvaluator(registry)
        result = session.results(evaluator=evaluator)
        result = sanitize_for_json(result)
        try:
            await save_registry(registry, db)
            await db.commit()
        except Exception:
            await db.rollback()

        return result
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@app.post(f"{API_PREFIX}/session/{{session_id}}/fail")
async def fail_session(
    session_id: str,
    request: dict[str, Any],
    db: AsyncSession = Depends(get_db),
    broker: MessageBroker = Depends(get_broker),
    _: None = require_agent_api(),
):
    """Mark a session as failed with an error message."""
    session = await get_session(session_id, db)
    session.mark_failed(request.get("error", "unknown error"))
    state_dict = _serialize_state(session.state)
    await broker.enqueue("state:persist", {
        "session_id": session_id,
        "state": state_dict,
        "status": session.status,
        "error_message": session.error_message,
        "locked": session.locked,
        "player_tokens": session.player_tokens,
    })

    return {"session_id": session_id, "status": session.status, "error_message": session.error_message}


@app.get(f"{API_PREFIX}/session/{{session_id}}/stream")
async def stream_session(
    session_id: str,
    broker: MessageBroker = Depends(get_broker),
):
    async def event_generator():
        try:
            async for state in broker.subscribe(f"session:{session_id}:state"):
                yield f"event: state_change\ndata: {json.dumps(state)}\n\n"
        except asyncio.CancelledError:
            pass

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


# ── Session history & dashboard ────────────────────────────────────────


class SessionRow(BaseModel):
    id: str
    game_slug: str
    agent_a: str | None = None
    agent_b: str | None = None
    winner: str | None = None
    total_score_a: int | None = None
    total_score_b: int | None = None
    created_at: str | None = None

    model_config = {"from_attributes": True}


def _session_summary(row: SessionModel) -> dict[str, Any]:
    state = row.state_json or {}
    history = state.get("history", [])
    winner = None
    score_a = None
    score_b = None
    if history and isinstance(history, list):
        last_round = history[-1]
        if isinstance(last_round, dict):
            ts = last_round.get("total_scores") or last_round.get("scores", {})
            score_a = ts.get("A")
            score_b = ts.get("B")
            if score_a is not None and score_b is not None:
                if score_a > score_b:
                    winner = "A"
                elif score_b > score_a:
                    winner = "B"
                else:
                    winner = "Tie"
    config = row.config_json or {}
    battlefields = config.get("battlefields", [])
    budget = config.get("budget", [100, 100])
    agents = row.agents_json or {}
    return {
        "id": row.id,
        "game_slug": config.get("game", "unknown"),
        "agents": agents,
        "agent_a": agents.get("A"),
        "agent_b": agents.get("B"),
        "winner": winner,
        "total_score_a": score_a,
        "total_score_b": score_b,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "rounds": config.get("rounds"),
        "num_battlefields": len(battlefields) if isinstance(battlefields, list) else 0,
        "resources": budget[0] if isinstance(budget, list) and len(budget) > 0 else 100,
        "seed": config.get("seed"),
        "status": row.status,
        "locked": row.locked,
    }


@app.get(f"{API_PREFIX}/session/{{session_id}}/summary")
async def get_session_summary(session_id: str, db: AsyncSession = Depends(get_db)):
    """Get a summary of a session including agents, scores, and winner."""
    result = await db.execute(select(SessionModel).where(SessionModel.id == session_id))
    row = result.scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="session not found")
    return _session_summary(row)


def _agent_filter(agents_json_col, agent: str):
    return func.coalesce(
        agents_json_col["A"].astext, ""
    ).ilike(f"%{agent}%") | func.coalesce(
        agents_json_col["B"].astext, ""
    ).ilike(f"%{agent}%")


@app.get(f"{API_PREFIX}/sessions")
async def list_sessions(
    game: str | None = Query(default=None),
    agent: str | None = Query(default=None),
    date_from: str | None = Query(default=None),
    date_to: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
    user: User | None = Depends(get_local_or_optional_user),
):
    """List sessions with optional filters for game, agent, and date range."""
    stmt = select(SessionModel)

    if user:
        stmt = stmt.where(SessionModel.user_id == user.id)
    else:
        stmt = stmt.where(SessionModel.user_id.is_(None))

    if game:
        stmt = stmt.where(SessionModel.config_json["game"].astext == game)

    if agent:
        stmt = stmt.where(SessionModel.agents_json.isnot(None))
        stmt = stmt.where(_agent_filter(SessionModel.agents_json, agent))

    if date_from:
        stmt = stmt.where(SessionModel.created_at >= date_from)

    if date_to:
        stmt = stmt.where(SessionModel.created_at <= date_to)

    count_stmt = select(func.count()).select_from(SessionModel)
    if user:
        count_stmt = count_stmt.where(SessionModel.user_id == user.id)
    else:
        count_stmt = count_stmt.where(SessionModel.user_id.is_(None))
    if game:
        count_stmt = count_stmt.where(SessionModel.config_json["game"].astext == game)
    if agent:
        count_stmt = count_stmt.where(SessionModel.agents_json.isnot(None))
        count_stmt = count_stmt.where(_agent_filter(SessionModel.agents_json, agent))
    total_result = await db.execute(count_stmt)
    total = total_result.scalar() or 0

    stmt = stmt.order_by(SessionModel.created_at.desc()).offset(offset).limit(limit)
    result = await db.execute(stmt)
    rows = result.scalars().all()

    return {
        "sessions": [_session_summary(row) for row in rows],
        "total": total,
    }


@app.delete(f"{API_PREFIX}/sessions/{{session_id}}")
async def delete_session(
    session_id: str,
    db: AsyncSession = Depends(get_db),
    user: User | None = Depends(get_local_or_optional_user),
):
    """Delete a session by ID."""
    stmt = select(SessionModel).where(SessionModel.id == session_id)
    if user:
        stmt = stmt.where(SessionModel.user_id == user.id)
    else:
        stmt = stmt.where(SessionModel.user_id.is_(None))
    result = await db.execute(stmt)
    row = result.scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="session not found")
    await db.execute(delete(MessageLog).where(MessageLog.session_id == session_id))
    await db.delete(row)
    await db.commit()
    return {"deleted": session_id}


@app.get(f"{API_PREFIX}/dashboard")
async def dashboard(
    db: AsyncSession = Depends(get_db),
    user: User | None = Depends(get_local_or_optional_user),
):
    """Get dashboard summary with game counts and recent sessions."""
    user_filter = SessionModel.user_id == user.id if user else SessionModel.user_id.is_(None)

    count_result = await db.execute(
        select(func.count()).select_from(SessionModel).where(user_filter)
    )
    total_games = count_result.scalar() or 0

    game_expr = SessionModel.config_json["game"].astext
    game_stmt = (
        select(game_expr, func.count().label("game_count"))
        .where(user_filter)
        .group_by(game_expr)
        .order_by(game_expr)
    )
    game_result = await db.execute(game_stmt)
    game_counts = {row[0]: row.game_count for row in game_result.fetchall()}

    games = {}
    for game_slug in game_counts:
        recent_stmt = (
            select(SessionModel)
            .where(user_filter, SessionModel.config_json["game"].astext == game_slug)
            .order_by(SessionModel.created_at.desc())
            .limit(5)
        )
        recent_result = await db.execute(recent_stmt)
        rows = recent_result.scalars().all()
        games[game_slug] = {
            "count": game_counts[game_slug],
            "sessions": [_session_summary(row) for row in rows],
        }

    return {
        "total_games": total_games,
        "games": games,
    }


# ── API Keys ────────────────────────────────────────────────────────────


class ApiKeyCreate(BaseModel):
    name: str | None = None


class ApiKeyResponse(BaseModel):
    id: str
    key_prefix: str
    name: str | None = None
    is_active: bool = True
    last_used_at: str | None = None
    created_at: str | None = None


class ApiKeyCreatedResponse(ApiKeyResponse):
    full_key: str


def _api_key_response(row: ApiKey) -> ApiKeyResponse:
    return ApiKeyResponse(
        id=str(row.id),
        key_prefix=row.key_prefix,
        name=row.name,
        is_active=row.is_active,
        last_used_at=row.last_used_at.isoformat() if row.last_used_at else None,
        created_at=row.created_at.isoformat() if row.created_at else None,
    )


@app.get(f"{API_PREFIX}/keys", response_model=list[ApiKeyResponse])
async def list_keys(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_user),
):
    """List all API keys for the current user."""
    result = await db.execute(
        select(ApiKey)
        .where(ApiKey.user_id == user.id)
        .order_by(ApiKey.created_at.desc())
    )
    rows = result.scalars().all()
    return [_api_key_response(row) for row in rows]


@app.post(f"{API_PREFIX}/keys", response_model=ApiKeyCreatedResponse)
async def create_key(
    payload: ApiKeyCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_user),
):
    """Create a new API key for the current user."""
    full_key, key_hash, key_prefix = generate_platform_key()
    row = ApiKey(
        id=uuid4(),
        user_id=user.id,
        key_hash=key_hash,
        key_prefix=key_prefix,
        name=payload.name.strip() if payload.name and payload.name.strip() else None,
        is_active=True,
    )
    db.add(row)
    await db.commit()
    await db.refresh(row)
    return ApiKeyCreatedResponse(
        id=str(row.id),
        key_prefix=row.key_prefix,
        name=row.name,
        is_active=row.is_active,
        last_used_at=None,
        created_at=row.created_at.isoformat() if row.created_at else None,
        full_key=full_key,
    )


@app.delete(f"{API_PREFIX}/keys/{{key_id}}")
async def delete_key(
    key_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_user),
):
    """Delete an API key by ID."""
    result = await db.execute(
        select(ApiKey).where(ApiKey.id == key_id, ApiKey.user_id == user.id)
    )
    row = result.scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="key not found")
    await db.delete(row)
    await db.commit()
    return {"deleted": key_id}


@app.post(f"{API_PREFIX}/keys/{{key_id}}/disable")
async def disable_key(
    key_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_user),
):
    """Disable an API key without deleting it."""
    result = await db.execute(
        select(ApiKey).where(ApiKey.id == key_id, ApiKey.user_id == user.id)
    )
    row = result.scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="key not found")
    row.is_active = False
    await db.commit()
    return {"disabled": key_id}


@app.post(f"{API_PREFIX}/keys/{{key_id}}/enable")
async def enable_key(
    key_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_user),
):
    """Re-enable a previously disabled API key."""
    result = await db.execute(
        select(ApiKey).where(ApiKey.id == key_id, ApiKey.user_id == user.id)
    )
    row = result.scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="key not found")
    row.is_active = True
    await db.commit()
    return {"enabled": key_id}


# ── OAuth ──────────────────────────────────────────────────────────────

def _provider_configured(client_id: str | None, client_secret: str | None) -> bool:
    return bool(client_id and client_id.strip() and client_secret and client_secret.strip())


@app.get(f"{API_PREFIX}/auth/providers")
def auth_providers():
    """List available OAuth providers and their configuration status."""
    return {
        "github": _provider_configured(
            os.environ.get("GITHUB_CLIENT_ID"),
            os.environ.get("GITHUB_CLIENT_SECRET"),
        ),
        "google": _provider_configured(
            os.environ.get("GOOGLE_CLIENT_ID"),
            os.environ.get("GOOGLE_CLIENT_SECRET"),
        ),
    }


@app.get(f"{API_PREFIX}/auth/github/login")
async def auth_github_login(request: Request):
    """Initiate GitHub OAuth login flow."""
    return await github_login(request)


@app.get(f"{API_PREFIX}/auth/github/callback")
async def auth_github_callback(request: Request, db: AsyncSession = Depends(get_db)):
    """Handle GitHub OAuth callback and issue a JWT."""
    user = await github_callback(request, db)
    token = create_access_token(str(user.id))
    return RedirectResponse(url=f"{CALLBACK_BASE}/?token={token}")


@app.get(f"{API_PREFIX}/auth/google/login")
async def auth_google_login(request: Request):
    """Initiate Google OAuth login flow."""
    return await google_login(request)


@app.get(f"{API_PREFIX}/auth/google/callback")
async def auth_google_callback(request: Request, db: AsyncSession = Depends(get_db)):
    """Handle Google OAuth callback and issue a JWT."""
    user = await google_callback(request, db)
    token = create_access_token(str(user.id))
    return RedirectResponse(url=f"{CALLBACK_BASE}/?token={token}")


@app.get(f"{API_PREFIX}/auth/me", response_model=UserResponse)
async def auth_me(user: User = Depends(get_current_user)):
    """Get the currently authenticated user profile."""
    return UserResponse(
        id=str(user.id),
        email=user.email,
        name=user.name,
        avatar_url=user.avatar_url,
    )


@app.get(f"{API_PREFIX}/auth/user", response_model=UserResponse)
async def auth_user(
    db: AsyncSession = Depends(get_db),
    user: User | None = Depends(get_local_or_optional_user),
):
    """Get the authenticated user profile (supports local auth)."""
    if user is None:
        raise HTTPException(status_code=401, detail="authentication required")
    return UserResponse(
        id=str(user.id),
        email=user.email,
        name=user.name,
        avatar_url=user.avatar_url,
    )


# ── Benchmark report ────────────────────────────────────────────────────


@app.get(f"{API_PREFIX}/benchmark/report")
async def benchmark_report(
    agent_ids: str | None = Query(default=None, description="Comma-separated agent IDs"),
    db: AsyncSession = Depends(get_db),
):
    """
    Return the current benchmark leaderboard — Elo, α-Rank, and per-dimension scores
    for all tracked agents. Pass ?agent_ids=a,b,c to restrict to specific agents.
    """
    registry = get_global_registry()
    known_agents = list(registry.elo_ratings.keys())
    if agent_ids:
        requested = [a.strip() for a in agent_ids.split(",") if a.strip()]
        target = [a for a in requested if a in registry.elo_ratings]
    else:
        target = known_agents

    if len(target) < 2:
        return {
            "agents": {a: {"elo": registry.elo_ratings.get(a), "matches_played": 0} for a in target},
            "ranking": target,
            "population": {},
            "total_matches": len(registry.match_history),
            "note": "Need at least 2 agents for α-Rank computation.",
        }

    pop = registry.population_report(target)
    agent_summaries = {}
    for agent_id in target:
        agent_summaries[agent_id] = {
            "elo": pop["elo_ratings"].get(agent_id),
            "alpha_rank": pop["alpha_rank_scores"].get(agent_id),
        }

    return {
        "agents": agent_summaries,
        "ranking": pop["alpha_rank_ranking"],
        "population": pop,
        "total_matches": len(registry.match_history),
    }


@app.delete(f"{API_PREFIX}/benchmark/reset")
async def benchmark_reset(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_user),
):
    """Reset the global AgentRegistry and delete persisted state."""
    from outplaylabs_arena.models.agent_registry import AgentRegistryState
    await db.execute(delete(AgentRegistryState))
    await db.commit()
    set_global_registry(AgentRegistry())
    return {"reset": True}


# ── Site config ────────────────────────────────────────────────────────

@app.get(f"{API_PREFIX}/site-config")
def site_config():
    """Return site configuration from site.yaml."""
    if SITE_YAML.is_file():
        data = yaml.safe_load(SITE_YAML.read_text(encoding="utf-8")) or {}
    else:
        data = {}
    return {
        "github_url": data.get("github_url", ""),
        "docs_url": data.get("docs_url", ""),
        "privacy_notice_url": data.get("privacy_notice_url", ""),
        "about_text": data.get("about_text", ""),
        "footer": data.get("footer") or {"copyright": "", "tagline": ""},
    }


if STATIC_ROOT.is_dir():
    app.mount("/", StaticFiles(directory=STATIC_ROOT, html=True), name="static")
