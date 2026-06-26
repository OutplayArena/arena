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
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware
from pydantic import BaseModel
from sqlalchemy import select, func, delete
from sqlalchemy.ext.asyncio import AsyncSession

from arena.db import get_db, async_session as _async_session_factory
from arena.experiment_config import split_runtime_config
from arena.game_registry import GameRegistry, GameRegistryError
from arena.manifest import build_agent_manifest
from arena.messaging import RedisBroker, StatePersister, MessageLogger
from arena.messaging.broker import MessageBroker
from arena.metrics import AgentRegistry, get_global_registry, set_global_registry, set_registry, get_all_registries, get_game_registry, MatchEvaluator, save_registry
from arena.session import GameSession, _serialize_state
from arena.models.session import SessionModel
from arena.models.api_key import ApiKey
from arena.models.message_log import MessageLog
from arena.auth.oauth import github_login, github_callback, google_login, google_callback, _callback_base_for
from arena.auth.jwt import create_access_token
from arena.auth.dependencies import get_current_user, get_local_or_optional_user, require_user
from arena.auth.apikey import generate_platform_key
from arena.models.user import User


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
    await _load_registries_from_db()
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


app = FastAPI(title="OutplayArena", lifespan=lifespan)
app.add_middleware(SessionMiddleware, secret_key=os.environ.get("JWT_SECRET", "dev-secret-change-me"))

# CORS — defaults to "*" for local dev. Override with CORS_ALLOW_ORIGINS, e.g.
#   CORS_ALLOW_ORIGINS="https://app.example.com,https://admin.example.com"
#   CORS_ALLOW_ORIGINS="*"           # any origin (dev default)
_cors_raw = os.environ.get("CORS_ALLOW_ORIGINS", "*").strip()
_cors_list = [o.strip() for o in _cors_raw.split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


async def _load_registries_from_db() -> None:
    """Load persisted AgentRegistry state from the agent_registry_states
    table, then replay any completed sessions whose match_id is not yet in
    the registries (backfill for sessions that completed against an older
    backend version that didn't record per-game state)."""
    import json
    import logging
    logger = logging.getLogger("arena.leaderboard")
    try:
        async with _async_session_factory() as db:
            from arena.models.agent_registry import AgentRegistryState
            from sqlalchemy import select
            result = await db.execute(select(AgentRegistryState))
            loaded_global = False
            loaded_count = 0
            for row in result.scalars().all():
                state = row.state_json
                if isinstance(state, (str, bytes, bytearray)):
                    state = json.loads(state)
                try:
                    reg = AgentRegistry.from_dict(state)
                except Exception as exc:
                    logger.warning(
                        "Skipping malformed agent_registry_states row key=%r: %s",
                        row.key, exc,
                    )
                    continue
                if row.key == "global" or row.key == "overall":
                    set_global_registry(reg)
                    loaded_global = True
                else:
                    set_registry(reg, row.key)
                loaded_count += 1
            if not loaded_global:
                set_global_registry(AgentRegistry())
            logger.info("Loaded %d agent registry rows from DB (global=%s)",
                        loaded_count, loaded_global)
    except Exception as exc:
        logger.warning("Failed to load agent registries from DB on startup: %s", exc)

    # Backfill: any completed session whose match_id is not yet in the
    # in-memory registries gets replayed through get_results() so its
    # per-game metrics, Elo snapshots, and aggregated values are recorded.
    try:
        from arena.models.session import SessionModel
        async with _async_session_factory() as db:
            from sqlalchemy import select
            result = await db.execute(
                select(SessionModel).where(SessionModel.status.in_(("complete", "completed")))
            )
            sessions = result.scalars().all()
        backfilled = 0
        for sess_row in sessions:
            try:
                session = GameSession.from_db_row(sess_row)
                evaluator = MatchEvaluator(get_global_registry())
                _ = session.results(evaluator=evaluator)
                match = session.to_match()
                game_type = match.game_type
                if game_type and game_type != "unknown":
                    import numpy as np
                    game_registry = get_game_registry(game_type)
                    if match.match_id in game_registry.match_history:
                        continue
                    avg_payoffs = {
                        a: float(np.mean(match.payoffs(a))) if match.payoffs(a) else 0.0
                        for a in match.agent_ids
                    }
                    ts = sess_row.created_at.isoformat() if sess_row.created_at else None
                    game_registry.record_match(match, avg_payoffs, timestamp=ts)
                    backfilled += 1
            except Exception:
                continue
        if backfilled:
            async with _async_session_factory() as db:
                for key, reg in get_all_registries().items():
                    try:
                        await save_registry(reg, db, key)
                    except Exception:
                        pass
        logger.info("Backfilled %d completed sessions into leaderboard registries", backfilled)
    except Exception as exc:
        logger.warning("Leaderboard backfill failed: %s", exc)


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
        from arena.auth.session_key import SESSION_KEY_PREFIX, validate_session_key
        if token.startswith(SESSION_KEY_PREFIX):
            try:
                validate_session_key(token)
                return
            except ValueError:
                pass
        try:
            from arena.auth.dependencies import get_current_user
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

    from arena.interactive_game_engine import InteractiveGameEngine
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

    from arena.interactive_game_engine import InteractiveGameEngine
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

    from arena.interactive_game_engine import InteractiveGameEngine
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

        from arena.interactive_game_engine import InteractiveGameEngine
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

        # Also record in per-game registry with agent metrics
        match = session.to_match()
        game_type = match.game_type
        if game_type and game_type != "unknown":
            import numpy as np
            game_registry = get_game_registry(game_type)
            avg_payoffs = {
                a: float(np.mean(match.payoffs(a))) if match.payoffs(a) else 0.0
                for a in match.agent_ids
            }
            rich = result.get("rich_metrics", {})
            agent_metrics = rich.get("agents", None)
            session_row = await db.execute(
                select(SessionModel).where(SessionModel.id == session_id)
            )
            sess = session_row.scalar_one_or_none()
            ts = sess.created_at.isoformat() if sess and sess.created_at else None
            game_registry.record_match(match, avg_payoffs, agent_metrics=agent_metrics, timestamp=ts)

        try:
            for key, reg in get_all_registries().items():
                await save_registry(reg, db, key)
        except Exception:
            await db.rollback()

        result["config"] = (
            session.config.to_dict() if hasattr(session.config, "to_dict") else {}
        )
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
    return RedirectResponse(url=f"{_callback_base_for(request)}/?token={token}")


@app.get(f"{API_PREFIX}/auth/google/login")
async def auth_google_login(request: Request):
    """Initiate Google OAuth login flow."""
    return await google_login(request)


@app.get(f"{API_PREFIX}/auth/google/callback")
async def auth_google_callback(request: Request, db: AsyncSession = Depends(get_db)):
    """Handle Google OAuth callback and issue a JWT."""
    user = await google_callback(request, db)
    token = create_access_token(str(user.id))
    return RedirectResponse(url=f"{_callback_base_for(request)}/?token={token}")


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
    game: str | None = Query(default=None, description="Game type to filter by (e.g. colonelblotto)"),
    date_from: str | None = Query(default=None, description="ISO date: only include agents active after this"),
    date_to: str | None = Query(default=None, description="ISO date: only include agents active before this"),
    db: AsyncSession = Depends(get_db),
):
    """
    Return the current benchmark leaderboard — Elo, α-Rank, and per-dimension scores
    for all tracked agents. Pass ?agent_ids=a,b,c to restrict to specific agents,
    or ?game=colonelblotto to view per-game rankings.
    """
    if game:
        registry = get_game_registry(game)
    else:
        registry = get_global_registry()

    known_agents = list(registry.elo_ratings.keys())
    if agent_ids:
        requested = [a.strip() for a in agent_ids.split(",") if a.strip()]
        target = [a for a in requested if a in registry.elo_ratings]
    else:
        target = known_agents

    # Time-range filter on agent activity (mirrors the leaderboard's logic).
    if date_from or date_to:
        filtered = []
        for a in target:
            snaps = registry.elo_snapshots.get(a, [])
            if not snaps:
                continue
            day_min = min(t[:10] for t, _ in snaps)
            day_max = max(t[:10] for t, _ in snaps)
            if date_from and day_max < date_from:
                continue
            if date_to and day_min > date_to:
                continue
            filtered.append(a)
        target = filtered

    if len(target) < 2:
        return sanitize_for_json({
            "agents": {a: {"elo": registry.elo_ratings.get(a), "matches_played": 0} for a in target},
            "ranking": target,
            "population": {},
            "total_matches": len(registry.match_history),
            "date_range": _registry_date_range(registry),
            "note": "Need at least 2 agents for α-Rank computation.",
        })

    evaluator = MatchEvaluator(registry)
    pop = evaluator.population_report(target)
    agg = registry.aggregated_metrics(target)
    agent_summaries = {}
    for agent_id in target:
        base = {
            "elo": pop["elo_ratings"].get(agent_id),
            "alpha_rank": pop["alpha_rank_scores"].get(agent_id),
            "matches_played": registry.matches_played.get(agent_id, 0),
        }
        if agent_id in agg:
            base["metrics"] = agg[agent_id]
        agent_summaries[agent_id] = base

    return sanitize_for_json({
        "agents": agent_summaries,
        "ranking": pop["alpha_rank_ranking"],
        "population": pop,
        "total_matches": len(registry.match_history),
        "date_range": _registry_date_range(registry),
    })


@app.get(f"{API_PREFIX}/benchmark/games")
async def benchmark_games(
    db: AsyncSession = Depends(get_db),
):
    """List game types that have benchmark data."""
    try:
        from arena.models.agent_registry import AgentRegistryState
        from sqlalchemy import select
        result = await db.execute(
            select(AgentRegistryState.key).where(AgentRegistryState.key.like("game:%"))
        )
        games = [row[0].replace("game:", "", 1) for row in result.all()]
        return sanitize_for_json({"games": sorted(games)})
    except Exception:
        return sanitize_for_json({"games": []})


@app.delete(f"{API_PREFIX}/benchmark/reset")
async def benchmark_reset(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_user),
):
    """Reset the global AgentRegistry and delete persisted state."""
    from arena.models.agent_registry import AgentRegistryState
    await db.execute(delete(AgentRegistryState))
    await db.commit()
    set_global_registry(AgentRegistry())
    return {"reset": True}


# Leaderboard (paginated, sortable) 
_SORTABLE_KEYS = frozenset({
    "elo", "alpha_rank", "matches_played",
    "avg_payoff", "nash_gap", "cumulative_regret",
    "strategy_entropy", "behavioral_consistency", "cooperation_rate",
})


def _safe_sort_key(agent_data: dict, key: str) -> tuple:
    """Return a sortable value, placing None/missing at the end."""
    val = agent_data.get(key)
    if key == "alpha_rank":
        val = agent_data.get("alpha_rank")
    if key == "elo":
        val = agent_data.get("elo")
    if key == "matches_played":
        val = agent_data.get("matches_played")
    if key in ("avg_payoff", "nash_gap", "cumulative_regret",
               "strategy_entropy", "behavioral_consistency", "cooperation_rate"):
        metrics = agent_data.get("metrics", {})
        val = metrics.get(key)
    if val is None:
        return (1, 0)
    return (0, val)


def _registry_date_range(registry: AgentRegistry) -> dict:
    """Return the inclusive [min_date, max_date] (YYYY-MM-DD) of recorded
    match activity, derived from the registry's Elo snapshots. Empty dict
    when no activity exists yet."""
    ts_min: str | None = None
    ts_max: str | None = None
    for snaps in registry.elo_snapshots.values():
        for ts, _ in snaps:
            day = ts[:10] if len(ts) >= 10 else ts
            if ts_min is None or day < ts_min:
                ts_min = day
            if ts_max is None or day > ts_max:
                ts_max = day
    if ts_min is None or ts_max is None:
        return {"min_date": None, "max_date": None}
    return {"min_date": ts_min, "max_date": ts_max}


def _build_leaderboard_entries(
    registry: AgentRegistry,
    agent_ids: list[str],
    sort_by: str = "alpha_rank",
    sort_dir: str = "desc",
    page: int = 1,
    page_size: int = 50,
) -> dict:
    """Build paginated, sorted leaderboard entries from a registry."""
    date_range = _registry_date_range(registry)
    if len(agent_ids) < 2:
        entries = []
        for a in agent_ids:
            entries.append({
                "agent_id": a,
                "elo": registry.elo_ratings.get(a),
                "alpha_rank": registry.compute_alpha_rank_scores([a]).get(a) if agent_ids else None,
                "matches_played": registry.matches_played.get(a, 0),
                "metrics": registry.aggregated_metrics([a]).get(a, {}),
            })
        return {
            "agents": entries,
            "total": len(entries),
            "page": page,
            "page_size": page_size,
            "total_matches": len(registry.match_history),
            "date_range": date_range,
            "note": "Need at least 2 agents for α-Rank computation.",
        }

    evaluator = MatchEvaluator(registry)
    pop = evaluator.population_report(agent_ids)
    agg = registry.aggregated_metrics(agent_ids)

    entries = []
    for a in agent_ids:
        entries.append({
            "agent_id": a,
            "elo": pop["elo_ratings"].get(a),
            "alpha_rank": pop["alpha_rank_scores"].get(a),
            "matches_played": registry.matches_played.get(a, 0),
            "metrics": agg.get(a, {}),
        })

    reverse = sort_dir.lower() != "asc"
    entries.sort(key=lambda e: _safe_sort_key(e, sort_by), reverse=reverse)

    total = len(entries)
    start = (page - 1) * page_size
    end = start + page_size
    page_entries = entries[start:end]

    return {
        "agents": page_entries,
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_matches": len(registry.match_history),
        "date_range": date_range,
    }


@app.get(f"{API_PREFIX}/leaderboard")
async def get_leaderboard(
    game: str | None = Query(default=None, description="Game type filter (e.g. colonelblotto)"),
    sort_by: str = Query(default="alpha_rank", description="Field to sort by"),
    sort_dir: str = Query(default="desc", description="Sort direction: asc or desc"),
    page: int = Query(default=1, ge=1, description="Page number"),
    page_size: int = Query(default=50, ge=1, le=200, description="Items per page"),
    agent_ids: str | None = Query(default=None, description="Comma-separated agent IDs to filter"),
    date_from: str | None = Query(default=None, description="ISO date: only include agents active after this"),
    date_to: str | None = Query(default=None, description="ISO date: only include agents active before this"),
    db: AsyncSession = Depends(get_db),
):
    """Paginated, sortable leaderboard. Returns agents sorted by the chosen metric."""
    if game:
        registry = get_game_registry(game)
    else:
        registry = get_global_registry()

    known = list(registry.elo_ratings.keys())
    if agent_ids:
        requested = [a.strip() for a in agent_ids.split(",") if a.strip()]
        target = [a for a in requested if a in known]
    else:
        target = known

    # Time-range filter on agent activity. Agents with no snapshots are
    # excluded when a date filter is set — they have no recorded activity.
    if date_from or date_to:
        filtered = []
        for a in target:
            snaps = registry.elo_snapshots.get(a, [])
            if not snaps:
                continue
            day_min = min(t[:10] for t, _ in snaps)
            day_max = max(t[:10] for t, _ in snaps)
            if date_from and day_max < date_from:
                continue
            if date_to and day_min > date_to:
                continue
            filtered.append(a)
        target = filtered

    if sort_by not in _SORTABLE_KEYS:
        sort_by = "alpha_rank"

    result = _build_leaderboard_entries(
        registry, target,
        sort_by=sort_by, sort_dir=sort_dir,
        page=page, page_size=page_size,
    )
    return sanitize_for_json(result)


@app.get(f"{API_PREFIX}/leaderboard/agents/{{agent_id}}")
async def get_agent_detail(
    agent_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Return per-game breakdown for a single agent across all registries."""
    detail: dict[str, Any] = {
        "agent_id": agent_id,
        "overall": None,
        "per_game": {},
    }

    for key, reg in get_all_registries().items():
        if agent_id not in reg.elo_ratings:
            continue

        known = list(reg.elo_ratings.keys())
        agg = reg.aggregated_metrics([agent_id]).get(agent_id, {})
        entry = {
            "elo": reg.elo_ratings.get(agent_id),
            "matches_played": reg.matches_played.get(agent_id, 0),
            "alpha_rank": None,
            "metrics": agg,
            "total_agents": len(known),
        }

        if len(known) >= 2:
            scores = reg.compute_alpha_rank_scores(known)
            entry["alpha_rank"] = scores.get(agent_id)

        if key == "overall":
            detail["overall"] = entry
        else:
            game_name = key.replace("game:", "", 1)
            detail["per_game"][game_name] = entry

    return sanitize_for_json(detail)


@app.get(f"{API_PREFIX}/leaderboard/agents/{{agent_id}}/history")
async def get_agent_history(
    agent_id: str,
    game: str | None = Query(default=None, description="Game type for per-game history"),
    db: AsyncSession = Depends(get_db),
):
    """Return Elo rating time series for an agent."""
    if game:
        registry = get_game_registry(game)
    else:
        registry = get_global_registry()

    history = registry.get_rating_history(agent_id)
    points = [{"timestamp": ts, "elo": elo} for ts, elo in history]
    return sanitize_for_json({
        "agent_id": agent_id,
        "game": game or "overall",
        "history": points,
    })


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
