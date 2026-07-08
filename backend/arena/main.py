# ruff: noqa: E402
import asyncio
import json
import logging
import os
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, AsyncIterator
from uuid import UUID, uuid4

import yaml
from dotenv import load_dotenv

load_dotenv()

from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.middleware.sessions import SessionMiddleware
from pydantic import BaseModel
from sqlalchemy import select, func, delete
from sqlalchemy.ext.asyncio import AsyncSession

from arena._version import ARENA_VERSION
from arena.db import get_db, async_session as _async_session_factory
from arena.experiment_config import split_runtime_config
from arena.game_registry import GameRegistry, GameRegistryError
from arena.manifest import build_agent_manifest
from arena.messaging import RedisBroker, StatePersister, MessageLogger
from arena.messaging.broker import MessageBroker
from arena.metrics import AgentRegistry, get_global_registry, set_global_registry, get_all_registries, get_game_registry, MatchEvaluator, save_registry
from arena.session import GameSession, _serialize_state
from arena.models.session import SessionModel
from arena.models.api_key import ApiKey
from arena.models.message_log import MessageLog
from arena.models.wandb_credential import WandbCredential
from arena.models.match import Match
from arena.integrations.wandb_logger import encrypt_api_key, decrypt_api_key, WandbConfigError, WandbGameLogger
from arena.experiment_config import WandbConfig
from arena.auth.oauth import github_login, github_callback, google_login, google_callback, _callback_base_for
from arena.auth.jwt import create_access_token
from arena.auth.dependencies import get_current_user, get_local_or_optional_user, require_user, require_admin
from arena.auth.apikey import generate_platform_key
from arena.models.user import User
from arena.concurrency import evaluate_admission, _queue_drainer_loop as _concurrency_drain
from arena.matchmaking import (
    create_lobby_match,
    list_open_matches as _lobby_list,
    get_match_detail as _lobby_get,
    join_match as _lobby_join,
    cancel_match as _lobby_cancel,
    _matchmaking_sweeper_loop,
    is_match_participant,
)


API_PREFIX = os.environ.get("API_PREFIX", "/api")
MCP_ENDPOINT = os.environ.get("MCP_ENDPOINT")
_SITE_YAML = Path(__file__).resolve().parent.parent.parent / "frontend" / "site.yaml"
if not _SITE_YAML.is_file():
    _SITE_YAML = Path(__file__).resolve().parent.parent / "site.yaml"
SITE_YAML = _SITE_YAML
STATIC_ROOT = Path(__file__).resolve().parent.parent / "static"
GAME_REGISTRY = GameRegistry()

_logger_main = logging.getLogger(__name__)

_broker: RedisBroker | None = None
_persister: StatePersister | None = None
_logger: MessageLogger | None = None


@asynccontextmanager
async def lifespan(application: FastAPI) -> AsyncIterator[None]:
    global _broker, _persister, _logger

    # Fail fast if JWT_SECRET is still the insecure default. Bypass by setting
    # ALLOW_INSECURE_JWT_SECRET=1 in local dev (or set a real secret in .env).
    from arena.auth import JWT_SECRET as _jwt_secret
    if _jwt_secret == "dev-secret-change-me" and not os.environ.get("ALLOW_INSECURE_JWT_SECRET"):
        raise RuntimeError(
            "JWT_SECRET is set to the insecure default value. "
            "Generate a real secret with: openssl rand -hex 32\n"
            "Set ALLOW_INSECURE_JWT_SECRET=1 to bypass this check in local dev."
        )

    # Run pending Alembic migrations before any service touches the
    # schema. ``upgrade head`` is idempotent — it only applies revisions
    # newer than the current head, so it's safe to call on every boot.
    # We invoke the synchronous alembic API from a thread executor so
    # the async event loop is never blocked (alembic uses a sync engine).
    await _run_alembic_upgrade()

    _broker = RedisBroker()
    _persister = StatePersister(_broker, _async_session_factory)
    await _persister.start()
    _logger = MessageLogger(_broker, _async_session_factory)
    await _logger.start()
    await _load_registries_from_db()
    _gdpr_task = asyncio.create_task(_gdpr_purge_loop())
    _concurrency_task = asyncio.create_task(_concurrency_drain(_broker))
    _matchmaking_task = asyncio.create_task(_matchmaking_sweeper_loop(_broker))
    yield
    _gdpr_task.cancel()
    _concurrency_task.cancel()
    _matchmaking_task.cancel()
    if _logger is not None:
        await _logger.stop()
        _logger = None
    if _persister is not None:
        await _persister.stop()
        _persister = None
    if _broker is not None:
        await _broker.close()
        _broker = None


async def _run_alembic_upgrade() -> None:
    """Apply pending Alembic migrations on app startup.

    Alembic itself is sync; we run it in the default executor so the
    event loop isn't blocked. We log the head before and after so an
    operator can see what changed.
    """
    import asyncio
    from logging import getLogger

    from alembic import command
    from alembic.config import Config
    from alembic.runtime.migration import MigrationContext
    from sqlalchemy import create_engine

    from arena.db import DATABASE_URL

    alembic_log = getLogger("arena.migrations")

    sync_url = DATABASE_URL.replace("+asyncpg", "")
    cfg = Config(str(Path(__file__).resolve().parent.parent / "alembic.ini"))
    cfg.set_main_option("sqlalchemy.url", sync_url)

    def _current_head() -> str | None:
        engine = create_engine(sync_url)
        try:
            with engine.connect() as conn:
                ctx = MigrationContext.configure(conn)
                return ctx.get_current_revision()
        finally:
            engine.dispose()

    def _upgrade() -> None:
        before = _current_head()
        command.upgrade(cfg, "head")
        after = _current_head()
        if before != after:
            alembic_log.info("Applied Alembic migrations: %s -> %s", before, after)
        else:
            alembic_log.info("Alembic schema up to date at head=%s", after)

    try:
        await asyncio.get_running_loop().run_in_executor(None, _upgrade)
    except Exception as exc:  # noqa: BLE001
        # Migration failure is fatal: the rest of the lifespan and the
        # request handlers all assume the schema is current. Re-raise so
        # uvicorn exits with a non-zero status and Docker restarts us.
        alembic_log.exception("Alembic upgrade failed: %s", exc)
        raise


app = FastAPI(
    title="OutplayArena",
    lifespan=lifespan,
    # Move Swagger UI / ReDoc / OpenAPI schema off the SPA's reserved
    # paths (/docs and /redoc are mounted as an in-app iframe of the
    # mkdocs site, /openapi.json conflicts with the SPA's router).
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
)
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

# Catch-all exception handler: every unhandled error gets a UUID, the
# traceback is persisted to error_logs, and the response shows the
# UUID with a link to a prefilled GitHub issue. See arena.error_handler.
from arena.error_handler import register_error_handlers  # noqa: E402
register_error_handlers(app)


async def _gdpr_purge_loop() -> None:
    """Background task: purge accounts inactive for _INACTIVITY_PURGE_DAYS days.

    Runs once immediately on startup (so a reboot after a long downtime
    still applies the purge), then every 24 hours.  Uses its own DB
    session — never interferes with request-scoped sessions.
    """
    _log = logging.getLogger("arena.gdpr.purge")
    while True:
        try:
            cutoff = datetime.now(timezone.utc) - timedelta(days=_INACTIVITY_PURGE_DAYS)
            async with _async_session_factory() as db:
                result = await db.execute(
                    select(User).where(User.last_login_at < cutoff)
                )
                inactive = result.scalars().all()
                for u in inactive:
                    try:
                        await _delete_user_data(db, u.id)
                        _log.info(
                            "GDPR auto-purge: deleted user %s (last login %s)",
                            u.id,
                            u.last_login_at,
                        )
                    except Exception:
                        _log.warning("Failed to purge user %s", u.id, exc_info=True)
        except asyncio.CancelledError:
            raise
        except Exception:
            _log.warning("GDPR purge loop error", exc_info=True)
        await asyncio.sleep(24 * 3600)


async def _log_session_to_wandb(session: "GameSession", row: Any, db: AsyncSession) -> None:
    """Log a completed session to W&B in one stateless call.

    Fetches the user's encrypted key from the DB, creates a run, logs all
    rounds and terminal metrics, finishes the run, and persists the run_meta.
    Never raises — W&B failures are logged as warnings so they never block
    the game response.
    """
    try:
        cred_result = await db.execute(
            select(WandbCredential).where(WandbCredential.user_id == row.user_id)
        )
        cred = cred_result.scalar_one_or_none()
        if cred is None:
            _logger_main.warning(
                "W&B logging requested for session %s but user has no stored key",
                session.session_id,
            )
            return

        wcfg = row.wandb_config_json
        wandb_cfg = WandbConfig(
            api_key="[fetched-below]",
            project=wcfg.get("project", "outplayarena"),
            entity=wcfg.get("entity"),
            run_name=wcfg.get("run_name"),
            tags=wcfg.get("tags"),
        )
        logger = WandbGameLogger(
            wandb_config=wandb_cfg,
            game_config=session.config,
            encrypted_api_key=cred.encrypted_api_key,
            agents=session.agents,
        )
        round_payloads = session.build_wandb_round_payloads()
        terminal_payload = session.build_wandb_terminal_payload()
        run_meta = logger.log_complete_session(round_payloads, terminal_payload)
        if run_meta:
            row.wandb_run_json = run_meta
            await db.commit()
            _logger_main.info(
                "W&B run %s logged for session %s",
                run_meta.get("run_id"),
                session.session_id,
            )
    except Exception:
        _logger_main.warning(
            "W&B logging failed for session %s — game result unaffected",
            session.session_id,
            exc_info=True,
        )


def _public_agent_id(model_name: str, username: str | None) -> str:
    """Return a namespaced agent ID for the global public registry.

    Format: ``model@username`` (e.g. ``gpt-4o@herbertw``).
    The ``@username`` suffix is what the leaderboard uses to attribute results
    to a specific user without exposing anything beyond their public handle.
    Falls back to bare model_name when username is unavailable.
    """
    return f"{model_name}@{username}" if username else model_name


def _namespace_match(match: Any, username: str | None) -> Any:
    """Return a copy of match with agent_ids and move agent_ids namespaced."""
    from arena.metrics.contracts import Match, Move
    namespaced_ids = [_public_agent_id(a, username) for a in match.agent_ids]
    id_map = dict(zip(match.agent_ids, namespaced_ids))
    new_moves = [
        Move(
            agent_id=id_map.get(m.agent_id, m.agent_id),
            round_number=m.round_number,
            action=m.action,
            payoff=m.payoff,
        )
        for m in match.moves
    ]
    return Match(
        match_id=match.match_id,
        game_type=match.game_type,
        agent_ids=namespaced_ids,
        moves=new_moves,
        config=match.config,
    )


async def _rebuild_leaderboard_registries() -> None:
    """Clear all in-memory registries and rebuild from only is_public=True sessions.

    Agent IDs in the public registry are namespaced as ``model@username`` so
    different users' runs of the same model appear as distinct leaderboard
    entries with attribution.  Called on startup and whenever a session's
    visibility changes.
    """
    import numpy as np
    import logging
    log = logging.getLogger("arena.leaderboard")

    for reg in get_all_registries().values():
        reg.clear()

    count = 0
    try:
        async with _async_session_factory() as db:
            result = await db.execute(
                select(SessionModel, User)
                .outerjoin(User, SessionModel.user_id == User.id)
                .where(SessionModel.status.in_(("complete", "completed")))
                .where(SessionModel.is_public.is_(True))
            )
            rows = result.all()

        for sess_row, user_row in rows:
            try:
                username = user_row.username if user_row else None
                session = GameSession.from_db_row(sess_row)
                match = session.to_match()
                game_type = match.game_type
                if not game_type or game_type == "unknown":
                    continue
                namespaced = _namespace_match(match, username)
                game_registry = get_game_registry(game_type)
                if namespaced.match_id in game_registry.match_history:
                    continue
                avg_payoffs = {
                    a: float(np.mean(namespaced.payoffs(a))) if namespaced.payoffs(a) else 0.0
                    for a in namespaced.agent_ids
                }
                ts = sess_row.created_at.isoformat() if sess_row.created_at else None
                game_registry.record_match(namespaced, avg_payoffs, timestamp=ts)
                count += 1
            except Exception:
                continue

        async with _async_session_factory() as db:
            for key, reg in get_all_registries().items():
                try:
                    await save_registry(reg, db, key)
                except Exception:
                    pass
        log.info("Leaderboard rebuilt from %d public sessions", count)
    except Exception:
        log.warning("Leaderboard rebuild error", exc_info=True)


async def _build_personal_registry(user_id: Any) -> "AgentRegistry":
    """Compute a fresh per-user registry from all of the user's completed sessions.

    Uses bare model names (no @username suffix) since all entries belong to
    the same user.  Not cached — computed on demand per leaderboard request.
    """
    import numpy as np
    reg = AgentRegistry()
    try:
        async with _async_session_factory() as db:
            result = await db.execute(
                select(SessionModel).where(
                    SessionModel.user_id == user_id,
                    SessionModel.status.in_(("complete", "completed")),
                )
            )
            rows = result.scalars().all()

        for sess_row in rows:
            try:
                session = GameSession.from_db_row(sess_row)
                match = session.to_match()
                if not match.game_type or match.game_type == "unknown":
                    continue
                if match.match_id in reg.match_history:
                    continue
                avg_payoffs = {
                    a: float(np.mean(match.payoffs(a))) if match.payoffs(a) else 0.0
                    for a in match.agent_ids
                }
                ts = sess_row.created_at.isoformat() if sess_row.created_at else None
                reg.record_match(match, avg_payoffs, timestamp=ts)
            except Exception:
                continue
    except Exception:
        pass
    return reg


async def _load_registries_from_db() -> None:
    """Build the public leaderboard registries from all is_public=True sessions.

    The old agent_registry_states cache is no longer used as a primary source
    because it may contain state derived from sessions that were later marked
    private.  We always rebuild from the session table on startup, with agent
    IDs namespaced as model@username for attribution.
    """
    set_global_registry(AgentRegistry())
    try:
        await _rebuild_leaderboard_registries()
    except Exception as exc:
        import logging
        logging.getLogger("arena.leaderboard").warning("Leaderboard rebuild failed: %s", exc)


class ActionRequest(BaseModel):
    allocation: Any = None
    forfeit: bool = False


class UserResponse(BaseModel):
    id: str
    email: str
    name: str
    avatar_url: str | None
    privacy_accepted: bool = False
    username: str | None = None
    show_own_leaderboard_badge: bool = False
    is_admin: bool = False

    model_config = {"from_attributes": True}


class UpdatePreferencesRequest(BaseModel):
    show_own_leaderboard_badge: bool


def config_from_request(request: dict[str, Any]):
    game_payload, _ = split_runtime_config(request)
    return GAME_REGISTRY.config_from_request(game_payload)


async def get_session(session_id: str, db: AsyncSession) -> GameSession:
    result = await db.execute(select(SessionModel).where(SessionModel.id == session_id))
    row = result.scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="session not found")
    return GameSession.from_db_row(row)


async def _check_match_participation(
    session_id: str,
    authorization: str | None,
    db: AsyncSession,
) -> None:
    """Harden state/observation access for matched sessions (#96).

    When a session was spawned by a matchmaking match (``match_id`` set),
    a caller using a **platform user token** (not an ``nks_`` session key)
    must be a participant in that match. The ``nks_`` token remains the
    primary capability and passes through unchecked. No-op for sessions
    without a ``match_id`` (preserves legacy behavior).
    """
    from arena.auth.session_key import SESSION_KEY_PREFIX
    from arena.auth.jwt import decode_access_token

    if not authorization or not authorization.startswith("Bearer "):
        return
    token = authorization[len("Bearer "):].strip()
    if token.startswith(SESSION_KEY_PREFIX):
        return
    try:
        user_id_str = decode_access_token(token)
        if not user_id_str:
            return
        user_id = UUID(user_id_str)
    except Exception:
        return
    is_participant = await is_match_participant(
        db, session_id=session_id, user_id=user_id
    )
    if not is_participant:
        raise HTTPException(
            status_code=403,
            detail="not a participant in this match",
        )


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


@app.get(f"{API_PREFIX}/version")
def get_version():
    """Return the running arena platform version."""
    return {"version": ARENA_VERSION}


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
    # Reject any inline api_key in the wandb block — keys must come from the
    # user's stored credential, never from the request payload.
    if "api_key" in (request.get("wandb") or {}):
        raise HTTPException(
            status_code=400,
            detail="wandb.api_key must not be sent in the request — configure your W&B key in Settings",
        )

    try:
        game_payload, wandb_fields = split_runtime_config(request)
        config = GAME_REGISTRY.config_from_request(game_payload)
        game = GAME_REGISTRY.game_from_config(config)
    except (ValueError, GameRegistryError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    # Resolve agents.
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

    # If the caller asked for W&B logging, verify the user has a stored
    # credential and persist the config for end-of-game logging.  The key is
    # never decrypted here — it is fetched fresh from the DB when the game
    # completes and the logger runs in a single stateless call.
    wandb_config_json: dict | None = None
    if wandb_fields.enabled:
        cred_check = await db.execute(
            select(WandbCredential).where(WandbCredential.user_id == user.id)
        )
        if cred_check.scalar_one_or_none() is None:
            _logger_main.warning(
                "User %s requested wandb_logging but has no W&B key configured "
                "(add one in Settings) — continuing without W&B logging.",
                user.id,
            )
        else:
            wandb_config_json = {
                "project": wandb_fields.project,
                "entity": wandb_fields.entity,
                "run_name": wandb_fields.run_name,
                "tags": wandb_fields.tags,
            }

    interactive = request.get("interactive", False)
    locked = not interactive

    session = GameSession.create(
        config,
        game=game,
        locked=locked,
        agents=agents,
    )

    # Concurrency admission gate (#117): if the global or per-user active
    # session count is already at its cap, persist this session with
    # status='queued' and return 202 with a queue position. The
    # background drainer promotes it to 'ready' once a slot frees.
    admission = await evaluate_admission(db, str(user.id))
    if admission.queued:
        session.status = "queued"

    await session.save_new(
        db,
        user_id=str(user.id),
        agents=agents,
        wandb_config_json=wandb_config_json,
    )

    response = session.creation_response()

    _logger_main.info(
        "Session %s created (arena v%s, game=%s, user=%s)",
        session.session_id,
        response["arena_version"],
        response.get("config", {}).get("game", "unknown"),
        user.id,
    )

    if MCP_ENDPOINT:
        response["mcp_url"] = MCP_ENDPOINT

    if admission.queued:
        response["queue_position"] = admission.position
        response["max_concurrent_sessions"] = admission.max_concurrent_sessions
        response["max_concurrent_sessions_per_user"] = admission.max_concurrent_sessions_per_user

    await broker.publish(f"session:{session.session_id}:events", {
        "event": "session_created",
        "session_id": session.session_id,
        "status": session.status,
    })

    if admission.queued:
        return JSONResponse(status_code=202, content=response)
    return response


# ── Lobby / matchmaking (#96) ─────────────────────────────────────────
# All /api/lobby/* endpoints check `_providers_configured()` first —
# matchmaking is intrinsically multi-user; in local mode (no OAuth) they
# return 403 with a clear message. The host creates an open match and
# immediately receives their nks_ token (derived from a pre-allocated
# session_id). Joiners claim slots via a race-safe DB constraint.

def _require_multi_user_mode():
    """Raise 403 when no OAuth providers are configured (local mode)."""
    from arena.auth.dependencies import _providers_configured

    if not _providers_configured():
        raise HTTPException(
            status_code=403,
            detail="matchmaking requires multi-user mode (configure GitHub or Google OAuth)",
        )


def _matchmaking_enabled() -> bool:
    from arena.settings import get_settings

    return bool(get_settings().enable_matchmaking)


@app.post(f"{API_PREFIX}/lobby/matches")
async def lobby_create_match(
    request: dict[str, Any],
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_user),
    _: None = require_agent_api(),
):
    """Create an open match in the lobby (#96).

    The host picks a game config and implicitly claims the first player
    slot. Returns the match_id, invite_code, invite_url, and the host's
    nks_ token (so the host agent can poll until the match starts).
    """
    _require_multi_user_mode()
    if not _matchmaking_enabled():
        raise HTTPException(status_code=403, detail="matchmaking is disabled")

    game_payload, _wandb = split_runtime_config(request)
    try:
        config = GAME_REGISTRY.config_from_request(game_payload)
        GAME_REGISTRY.game_from_config(config)
    except (ValueError, GameRegistryError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    agents = request.get("agents")
    if not isinstance(agents, dict):
        agents = None

    game_type = config.to_dict().get("game", "unknown") if hasattr(config, "to_dict") else "unknown"
    config_hash = config.config_hash()

    try:
        match, host_token = await create_lobby_match(
            db,
            host_user_id=user.id,
            game_type=game_type,
            config=config,
            config_hash=config_hash,
            agents=agents,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    host_slot = config.player_ids()[0] if config.player_ids() else "A"
    return {
        "match_id": match.id,
        "status": match.status,
        "invite_code": match.invite_code,
        "invite_url": f"/lobby/{match.id}?code={match.invite_code}",
        "host_token": host_token,
        "host_slot": host_slot,
        "total_slots": match.total_slots,
        "filled_slots": match.filled_slots,
        "open_slots": match.total_slots - match.filled_slots,
        "expires_at": match.expires_at.isoformat(),
    }


@app.get(f"{API_PREFIX}/lobby/matches")
async def lobby_list_matches(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_user),
):
    """List all open matches waiting for opponents (#96)."""
    _require_multi_user_mode()
    return {"matches": await _lobby_list(db)}


@app.get(f"{API_PREFIX}/lobby/matches/{{match_id}}")
async def lobby_get_match(
    match_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_user),
):
    """Get details for a specific match (#96)."""
    _require_multi_user_mode()
    detail = await _lobby_get(db, match_id)
    if detail is None:
        raise HTTPException(status_code=404, detail="match not found")
    return detail


@app.post(f"{API_PREFIX}/lobby/matches/{{match_id}}/join")
async def lobby_join_match(
    match_id: str,
    request: dict[str, Any] | None = None,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_user),
    broker: MessageBroker = Depends(get_broker),
    _: None = require_agent_api(),
):
    """Claim an open slot in a match. Race-safe (#96).

    Returns 200 with the joiner's nks_ token and the match status. If the
    match fills on this join, returns 200 with ``status='running'`` and
    the ``session_id``. Returns 409 if the slot was claimed by another
    user at the same instant (DB unique constraint catches the race).
    """
    _require_multi_user_mode()
    if not _matchmaking_enabled():
        raise HTTPException(status_code=403, detail="matchmaking is disabled")

    slot = None
    if request and isinstance(request, dict):
        slot = request.get("slot")

    try:
        token, claimed_slot, match_filled, m = await _lobby_join(
            db, match_id=match_id, user_id=user.id, slot=slot
        )
    except ValueError as exc:
        status_code = 404 if "not found" in str(exc) else 409
        if "expired" in str(exc) or "not open" in str(exc):
            status_code = 409
        raise HTTPException(status_code=status_code, detail=str(exc)) from exc

    if match_filled and m.session_id:
        await broker.publish(
            f"match:{match_id}:events",
            {
                "event": "match_filled",
                "match_id": match_id,
                "session_id": m.session_id,
                "status": "running",
            },
        )

    response = {
        "match_id": match_id,
        "slot": claimed_slot,
        "player_token": token,
        "status": m.status,
        "filled_slots": m.filled_slots,
        "total_slots": m.total_slots,
    }
    if m.session_id:
        response["session_id"] = m.session_id
    return response


@app.delete(f"{API_PREFIX}/lobby/matches/{{match_id}}")
async def lobby_cancel_match(
    match_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_user),
):
    """Cancel a waiting match (host only) (#96)."""
    _require_multi_user_mode()
    try:
        ok = await _lobby_cancel(db, match_id=match_id, user_id=user.id)
    except ValueError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    if not ok:
        raise HTTPException(status_code=404, detail="match not found")
    return {"cancelled": True}


@app.get(f"{API_PREFIX}/lobby/matches/{{match_id}}/stream")
async def lobby_stream_match(
    match_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_user),
):
    """SSE stream for a match: emits match_filled / match_expired events (#96).

    Used by the SDK's ``wait_for_opponent`` helper and the frontend's
    wait screen. Events:
    - ``match_filled`` → the match started; ``session_id`` included.
    - ``match_expired`` → the match TTL elapsed; the host should retry.
    """
    _require_multi_user_mode()

    match = (
        await db.execute(select(Match).where(Match.id == match_id))
    ).scalar_one_or_none()
    if match is None:
        raise HTTPException(status_code=404, detail="match not found")

    async def _event_stream():
        from arena.messaging.broker import MessageBroker

        broker = get_broker()
        if not isinstance(broker, MessageBroker):
            yield f"event: match_status\ndata: {json.dumps({'status': match.status})}\n\n"
            return
        channel = f"match:{match_id}:events"
        async for msg in await broker.subscribe(channel):
            yield f"data: {json.dumps(msg)}\n\n"
            if msg.get("event") in ("match_filled", "match_expired"):
                break

    return StreamingResponse(_event_stream(), media_type="text/event-stream")


@app.get(f"{API_PREFIX}/session/{{session_id}}/state")
async def get_state(
    session_id: str,
    authorization: str | None = Header(default=None),
    db: AsyncSession = Depends(get_db),
    broker: MessageBroker = Depends(get_broker),
    _: None = require_agent_api(),
):
    """Get the current state of a session."""
    await _check_match_participation(session_id, authorization, db)
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
    authorization: str | None = Header(default=None),
    db: AsyncSession = Depends(get_db),
    _: None = require_agent_api(),
):
    """Get the observation for a player in the current session state."""
    await _check_match_participation(session_id, authorization, db)
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


@app.get(f"{API_PREFIX}/session/{{session_id}}/status")
async def get_session_status(
    session_id: str,
    db: AsyncSession = Depends(get_db),
    _: None = require_agent_api(),
):
    """Return the lifecycle status of a session and its queue position.

    The SDK's ``wait_until_ready`` helper polls this endpoint after a
    session is created with ``status='queued'`` (HTTP 202 from
    ``POST /experiment``). Returns 200 with ``{"status": ..., "queue_position": ...}``.
    A non-queued session reports ``queue_position: 0``.
    """
    row = (
        await db.execute(select(SessionModel).where(SessionModel.id == session_id))
    ).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="session not found")
    queue_position = 0
    if row.status == "queued":
        ahead = (
            await db.execute(
                select(func.count())
                .select_from(SessionModel)
                .where(
                    SessionModel.status == "queued",
                    SessionModel.created_at < row.created_at,
                )
            )
        ).scalar_one()
        queue_position = int(ahead) + 1
    return {"status": row.status, "queue_position": queue_position}


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
    if session.status == "queued":
        raise HTTPException(
            status_code=409,
            detail="session is queued waiting for a concurrency slot; call GET /session/{id}/status until status is ready",
        )
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

    # Stateless W&B logging: when the game completes, open a run, log all
    # rounds + terminal metrics in one shot, finish, store run_meta in DB.
    if session.status == "completed" and row.wandb_config_json and row.user_id:
        await _log_session_to_wandb(session, row, db)

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

        # Only record in the public leaderboard registry when the session is
        # explicitly marked public by its owner.
        sess_row_result = await db.execute(
            select(SessionModel).where(SessionModel.id == session_id)
        )
        sess = sess_row_result.scalar_one_or_none()

        match = session.to_match()
        game_type = match.game_type
        if game_type and game_type != "unknown" and sess and getattr(sess, "is_public", False):
            import numpy as np
            # Look up owner username for attribution in the public registry.
            username: str | None = None
            if sess.user_id:
                user_row_result = await db.execute(
                    select(User).where(User.id == sess.user_id)
                )
                user_row = user_row_result.scalar_one_or_none()
                username = user_row.username if user_row else None
            namespaced = _namespace_match(match, username)
            game_registry = get_game_registry(game_type)
            avg_payoffs = {
                a: float(np.mean(namespaced.payoffs(a))) if namespaced.payoffs(a) else 0.0
                for a in namespaced.agent_ids
            }
            rich = result.get("rich_metrics", {})
            agent_metrics = rich.get("agents", None)
            ts = sess.created_at.isoformat() if sess.created_at else None
            game_registry.record_match(namespaced, avg_payoffs, agent_metrics=agent_metrics, timestamp=ts)

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
    authorization: str | None = Header(default=None),
    _: None = require_agent_api(),
):
    """Mark a session as failed with an error message."""
    session = await get_session(session_id, db)
    # Require a valid session key for this session — prevents unauthenticated
    # callers from disrupting sessions when ENABLE_AGENT_REST_API=true.
    token = bearer_token(authorization)
    try:
        session.player_for_token(token)
    except ValueError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc
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
        # Full config as it was submitted to create the session.  The config
        # tab on the play page uses this to display the exact parameters that
        # were used to run a current/completed/failed game (rendered locked
        # and read-only).  The flattened convenience fields above are kept
        # for backward compatibility with existing list/history views.
        "config": config,
        "status": row.status,
        "locked": row.locked,
        "is_public": row.is_public if hasattr(row, "is_public") else False,
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


class VisibilityUpdate(BaseModel):
    is_public: bool


@app.patch(f"{API_PREFIX}/sessions/{{session_id}}/visibility")
async def set_session_visibility(
    session_id: str,
    payload: VisibilityUpdate,
    db: AsyncSession = Depends(get_db),
    user: User | None = Depends(get_local_or_optional_user),
):
    """Toggle whether a completed session appears on the public leaderboard.

    Only the owning user may change visibility.  Triggers a full registry
    rebuild so the leaderboard immediately reflects the new state.
    """
    stmt = select(SessionModel).where(SessionModel.id == session_id)
    if user:
        stmt = stmt.where(SessionModel.user_id == user.id)
    else:
        stmt = stmt.where(SessionModel.user_id.is_(None))
    result = await db.execute(stmt)
    row = result.scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="session not found")

    row.is_public = payload.is_public
    await db.commit()

    # Rebuild the global public registry to reflect the visibility change.
    try:
        await _rebuild_leaderboard_registries()
    except Exception:
        _logger_main.warning("Leaderboard rebuild failed after visibility change", exc_info=True)

    return {"session_id": session_id, "is_public": row.is_public}


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


# ── W&B Settings ────────────────────────────────────────────────────────


class WandbKeyUpsert(BaseModel):
    api_key: str


@app.get(f"{API_PREFIX}/settings/wandb-key")
async def get_wandb_key_status(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_user),
):
    """Return whether the current user has a W&B API key configured.

    The key itself is never returned — only its presence and last-updated
    timestamp are exposed.
    """
    result = await db.execute(
        select(WandbCredential).where(WandbCredential.user_id == user.id)
    )
    row = result.scalar_one_or_none()
    if row is None:
        return {"configured": False, "updated_at": None, "key_fingerprint": None}
    # Expose the last 8 characters of the base64url-encoded ciphertext as a
    # visual fingerprint — safe (derived from random nonce + ciphertext,
    # reveals nothing about the plaintext), stable for a given stored key,
    # and changes when the user replaces their key.
    fingerprint = row.encrypted_api_key[-8:] if row.encrypted_api_key else None
    return {
        "configured": True,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
        "key_fingerprint": fingerprint,
    }


@app.put(f"{API_PREFIX}/settings/wandb-key", status_code=200)
async def upsert_wandb_key(
    payload: WandbKeyUpsert,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_user),
):
    """Store (or replace) the current user's W&B API key, encrypted at rest.

    The plaintext key is never persisted or returned — it is encrypted with
    AES-256-GCM before being written to the database.
    """
    try:
        encrypted = encrypt_api_key(payload.api_key)
    except WandbConfigError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    result = await db.execute(
        select(WandbCredential).where(WandbCredential.user_id == user.id)
    )
    row = result.scalar_one_or_none()
    if row is None:
        row = WandbCredential(user_id=user.id, encrypted_api_key=encrypted)
        db.add(row)
    else:
        row.encrypted_api_key = encrypted

    await db.commit()
    return {"configured": True}


@app.delete(f"{API_PREFIX}/settings/wandb-key", status_code=200)
async def delete_wandb_key(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_user),
):
    """Remove the current user's stored W&B API key."""
    result = await db.execute(
        select(WandbCredential).where(WandbCredential.user_id == user.id)
    )
    row = result.scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="no W&B key configured")
    await db.delete(row)
    await db.commit()
    return {"configured": False}


@app.get(f"{API_PREFIX}/settings/wandb-key/entities")
async def get_wandb_entities(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_user),
):
    """Return the W&B entities (personal + teams) for the stored API key.

    Used to populate the entity dropdown on the logging config surface.
    The API key is never included in the response — it is decrypted
    transiently, used for a single W&B API call, then discarded.
    """
    result = await db.execute(
        select(WandbCredential).where(WandbCredential.user_id == user.id)
    )
    row = result.scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="no W&B key configured")

    api_key = None
    try:
        api_key = decrypt_api_key(row.encrypted_api_key)
        import wandb as _wandb
        api = _wandb.Api(api_key=api_key)
        viewer = api.viewer
        personal_entity: str = viewer.entity
        teams: list[str] = viewer.teams
        entities = [personal_entity] + [t for t in teams if t != personal_entity]
        return {"personal_entity": personal_entity, "entities": entities}
    except WandbConfigError as exc:
        raise HTTPException(status_code=500, detail="could not decrypt W&B credentials") from exc
    except Exception:
        _logger_main.warning(
            "Could not fetch W&B entities for user %s — key may be invalid or W&B unreachable",
            user.id,
        )
        raise HTTPException(status_code=502, detail="could not verify W&B credentials")
    finally:
        # Ensure the decrypted key never lingers in memory.
        api_key = None
        del api_key


# ── GDPR: data export, account deletion ─────────────────────────────────

_GDPR_LOG = logging.getLogger("arena.gdpr")

# How long a user may be inactive before their account is automatically
# purged (GDPR data-minimisation principle).
_INACTIVITY_PURGE_DAYS = int(os.environ.get("GDPR_INACTIVITY_DAYS", "90"))


async def _delete_user_data(db: AsyncSession, user_id: Any) -> None:
    """Delete all data belonging to user_id in the correct cascade order.

    1. MessageLog rows have no FK cascade — delete them first.
    2. ApiKey / WandbCredential rows point at the user — delete them.
    3. SessionModel rows (cascades MailboxMessage via DB ON DELETE CASCADE).
    4. User row itself.
    """
    from sqlalchemy import delete as _del

    # 1. Message logs linked through sessions (no ORM cascade)
    session_ids_q = select(SessionModel.id).where(SessionModel.user_id == user_id)
    await db.execute(_del(MessageLog).where(MessageLog.session_id.in_(session_ids_q)))

    # 2. Platform API keys
    await db.execute(_del(ApiKey).where(ApiKey.user_id == user_id))

    # 3. W&B credential
    await db.execute(_del(WandbCredential).where(WandbCredential.user_id == user_id))

    # 4. Sessions (cascades MailboxMessage)
    await db.execute(_del(SessionModel).where(SessionModel.user_id == user_id))

    # 5. User record
    await db.execute(_del(User).where(User.id == user_id))

    await db.commit()


@app.get(f"{API_PREFIX}/settings/data-export")
async def export_user_data(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_user),
):
    """Return a complete JSON dump of all data stored for the current user.

    Sensitive credentials are never included in plaintext:
    - Platform API keys: only prefix / metadata, never the key hash.
    - W&B API key: only whether one is configured + its fingerprint, never
      the encrypted blob.
    - Player tokens: omitted entirely (session bearer credentials, equivalent
      to passwords).
    """
    # User profile
    profile = {
        "id": str(user.id),
        "email": user.email,
        "name": user.name,
        "provider": user.provider,
        "created_at": user.created_at.isoformat() if user.created_at else None,
        "last_login_at": user.last_login_at.isoformat() if user.last_login_at else None,
    }

    # Platform API keys — never key_hash
    keys_result = await db.execute(
        select(ApiKey).where(ApiKey.user_id == user.id).order_by(ApiKey.created_at)
    )
    api_keys = [
        {
            "id": str(row.id),
            "key_prefix": row.key_prefix,
            "name": row.name,
            "is_active": row.is_active,
            "created_at": row.created_at.isoformat() if row.created_at else None,
            "last_used_at": row.last_used_at.isoformat() if row.last_used_at else None,
        }
        for row in keys_result.scalars().all()
    ]

    # W&B integration — never the encrypted key blob
    cred_result = await db.execute(
        select(WandbCredential).where(WandbCredential.user_id == user.id)
    )
    cred = cred_result.scalar_one_or_none()
    wandb_integration = {
        "configured": cred is not None,
        "key_fingerprint": cred.encrypted_api_key[-8:] if cred else None,
        "updated_at": cred.updated_at.isoformat() if cred and cred.updated_at else None,
    }

    # Game sessions — omit player_tokens_json (bearer credentials)
    sessions_result = await db.execute(
        select(SessionModel).where(SessionModel.user_id == user.id).order_by(SessionModel.created_at)
    )
    sessions = [
        {
            "id": row.id,
            "status": row.status,
            "locked": row.locked,
            "config": row.config_json,
            "agents": row.agents_json,
            "state": row.state_json,
            "error_message": row.error_message,
            "created_at": row.created_at.isoformat() if row.created_at else None,
            "updated_at": row.updated_at.isoformat() if row.updated_at else None,
        }
        for row in sessions_result.scalars().all()
    ]

    # Per-session message logs
    if sessions:
        session_ids = [s["id"] for s in sessions]
        logs_result = await db.execute(
            select(MessageLog)
            .where(MessageLog.session_id.in_(session_ids))
            .order_by(MessageLog.session_id, MessageLog.round_number)
        )
        message_logs = [
            {
                "session_id": row.session_id,
                "player": row.player,
                "round_number": row.round_number,
                "agent_id": row.agent_id,
                "payload": row.payload,
                "created_at": row.created_at.isoformat() if row.created_at else None,
            }
            for row in logs_result.scalars().all()
        ]
    else:
        message_logs = []

    payload = {
        "export_date": datetime.now(timezone.utc).isoformat(),
        "platform": "OutplayArena",
        "user": profile,
        "api_keys": api_keys,
        "wandb_integration": wandb_integration,
        "sessions": sessions,
        "message_logs": message_logs,
    }

    filename = f"outplayarena-export-{datetime.now(timezone.utc).strftime('%Y%m%d')}.json"
    return JSONResponse(
        content=payload,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@app.delete(f"{API_PREFIX}/settings/account", status_code=200)
async def delete_account(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_user),
):
    """Permanently delete the current user's account and all associated data.

    Cascade order: MessageLog → ApiKey → WandbCredential → SessionModel
    (which cascades MailboxMessage) → User.  Irreversible.
    """
    await _delete_user_data(db, user.id)
    _GDPR_LOG.info("Account deleted by user %s (%s)", user.id, user.email)
    return {"deleted": True}


# ── Admin dashboard (#116) ─────────────────────────────────────────────
# All /api/admin/* endpoints are gated by `require_admin` (checks
# ENABLE_ADMIN_DASHBOARD env + is_admin column OR ADMIN_USER_IDS allowlist).
# Email addresses are masked (partial) so admin UI never surfaces full
# addresses. Response shapes are intentionally small and dashboard-shaped.

def _mask_email(email: str) -> str:
    """Partial email redaction: keep name[0] + domain[0..<2] chars."""
    if not email or "@" not in email:
        return email
    name, _, domain = email.partition("@")
    if not name or not domain:
        return email
    shown_name = name[0] if len(name) >= 1 else ""
    shown_domain = domain[0] + domain[1] if len(domain) >= 1 else ""
    return f"{shown_name}***@***.{domain.split('.')[-1]}" if "." in domain else f"{shown_name}***@***.{shown_domain}"


def _admin_user_row(u: User) -> dict:
    return {
        "id": str(u.id),
        "username": u.username,
        "name": u.name,
        "provider": u.provider,
        "email_masked": _mask_email(u.email),
        "is_admin": bool(getattr(u, "is_admin", False)),
        "created_at": u.created_at.isoformat() if u.created_at else None,
        "last_login_at": u.last_login_at.isoformat() if u.last_login_at else None,
    }


@app.get(f"{API_PREFIX}/admin/users")
async def admin_list_users(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_admin),
):
    """List registered users with masked emails (#116)."""
    result = await db.execute(select(User).order_by(User.created_at.desc()))
    users = result.scalars().all()
    return {"users": [_admin_user_row(u) for u in users]}


@app.get(f"{API_PREFIX}/admin/sessions")
async def admin_list_sessions(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_admin),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
):
    """List all sessions across all users (#116)."""
    total_r = await db.execute(select(func.count()).select_from(SessionModel))
    total = total_r.scalar_one()
    rows_r = await db.execute(
        select(SessionModel)
        .order_by(SessionModel.created_at.desc())
        .offset(offset)
        .limit(limit)
    )
    rows = rows_r.scalars().all()
    return {
        "total": total,
        "sessions": [
            {
                "id": r.id,
                "status": r.status,
                "game": r.config_json.get("game") if isinstance(r.config_json, dict) else None,
                "user_id": str(r.user_id) if r.user_id else None,
                "is_public": r.is_public,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in rows
        ],
    }


@app.get(f"{API_PREFIX}/admin/stats")
async def admin_stats(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_admin),
):
    """Platform-wide telemetry for the admin dashboard (#116)."""
    from arena.platform_settings import get_platform_setting as _get_set

    running = int(
        (
            await db.execute(
                select(func.count())
                .select_from(SessionModel)
                .where(SessionModel.status == "running")
            )
        ).scalar_one()
    )
    ready = int(
        (
            await db.execute(
                select(func.count())
                .select_from(SessionModel)
                .where(SessionModel.status == "ready")
            )
        ).scalar_one()
    )
    queued = int(
        (
            await db.execute(
                select(func.count())
                .select_from(SessionModel)
                .where(SessionModel.status == "queued")
            )
        ).scalar_one()
    )
    failed = int(
        (
            await db.execute(
                select(func.count())
                .select_from(SessionModel)
                .where(SessionModel.status == "failed")
            )
        ).scalar_one()
    )
    completed = int(
        (
            await db.execute(
                select(func.count())
                .select_from(SessionModel)
                .where(SessionModel.status == "completed")
            )
        ).scalar_one()
    )
    wandb_users = int(
        (
            await db.execute(select(func.count()).select_from(WandbCredential))
        ).scalar_one()
    )
    login_enabled = await _get_set("login_enabled", db, cast=bool)
    db_size = "unavailable"
    try:
        size_r = await db.execute(
            select(func.pg_database_size(func.current_database()))
        )
        db_size = size_r.scalar_one()
    except Exception:
        _logger_main.debug("pg_database_size unavailable; reporting placeholder", exc_info=True)
    return {
        "sessions_running": running,
        "sessions_ready": ready,
        "sessions_queued": queued,
        "sessions_failed": failed,
        "sessions_completed": completed,
        "wandb_users": wandb_users,
        "login_enabled": login_enabled,
        "db_size_bytes": db_size,
        "backup": {"status": "not_configured"},
    }


@app.get(f"{API_PREFIX}/admin/errors")
async def admin_list_errors(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_admin),
    limit: int = Query(50, ge=1, le=500),
):
    """Recent server errors from the error_logs table (#116)."""
    from arena.models.error_log import ErrorLog

    result = await db.execute(
        select(ErrorLog).order_by(ErrorLog.created_at.desc()).limit(limit)
    )
    errors = result.scalars().all()
    return {
        "errors": [
            {
                "id": str(e.id),
                "method": e.method,
                "path": e.path,
                "exception_type": e.exception_type,
                "message": e.message,
                "client_ip": e.client_ip,
                "user_agent": e.user_agent,
                "created_at": e.created_at.isoformat() if e.created_at else None,
            }
            for e in errors
        ]
    }


@app.get(f"{API_PREFIX}/admin/settings")
async def admin_get_settings(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_admin),
):
    """Read the runtime-editable platform settings (#116)."""
    from arena.platform_settings import get_platform_setting as _get_set

    return {
        "max_concurrent_sessions": await _get_set("max_concurrent_sessions", db, cast=int),
        "max_concurrent_sessions_per_user": await _get_set(
            "max_concurrent_sessions_per_user", db, cast=int
        ),
        "login_enabled": await _get_set("login_enabled", db, cast=bool),
    }


@app.put(f"{API_PREFIX}/admin/settings")
async def admin_update_settings(
    body: dict[str, Any],
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_admin),
):
    """Update runtime-editable platform settings (#116).

    Accepts a partial body; only the provided keys are updated. Boolean
    ``login_enabled`` toggles whether new logins are accepted (enforced
    in the OAuth callback endpoints).
    """
    from arena.platform_settings import set_platform_setting as _set_set

    allowed = {"max_concurrent_sessions", "max_concurrent_sessions_per_user", "login_enabled"}
    updated = {}
    for key, value in body.items():
        if key not in allowed:
            continue
        await _set_set(key, value, db, updated_by=user.id)
        updated[key] = value
    return updated


# ── OAuth ──────────────────────────────────────────────────────────────

async def _enforce_login_enabled(db: AsyncSession) -> None:
    """Reject new logins when the admin has toggled login_enabled=false (#116).

    Reads the ``login_enabled`` platform setting (env-fallback True).
    Called at the start of each OAuth login redirect so the toggle is
    enforced before the user is bounced out to the provider.
    """
    from arena.platform_settings import get_platform_setting as _get_set

    enabled = await _get_set("login_enabled", db, cast=bool)
    if not enabled:
        raise HTTPException(status_code=403, detail="login is temporarily disabled")


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
async def auth_github_login(request: Request, db: AsyncSession = Depends(get_db)):
    """Initiate GitHub OAuth login flow."""
    await _enforce_login_enabled(db)
    return await github_login(request)


@app.get(f"{API_PREFIX}/auth/github/callback")
async def auth_github_callback(request: Request, db: AsyncSession = Depends(get_db)):
    """Handle GitHub OAuth callback and issue a JWT."""
    user = await github_callback(request, db)
    token = create_access_token(str(user.id))
    return RedirectResponse(url=f"{_callback_base_for(request)}/?token={token}")


@app.get(f"{API_PREFIX}/auth/google/login")
async def auth_google_login(request: Request, db: AsyncSession = Depends(get_db)):
    """Initiate Google OAuth login flow."""
    await _enforce_login_enabled(db)
    return await google_login(request)


@app.get(f"{API_PREFIX}/auth/google/callback")
async def auth_google_callback(request: Request, db: AsyncSession = Depends(get_db)):
    """Handle Google OAuth callback and issue a JWT."""
    user = await google_callback(request, db)
    token = create_access_token(str(user.id))
    return RedirectResponse(url=f"{_callback_base_for(request)}/?token={token}")


def _user_response(user: User) -> UserResponse:
    from arena.auth.dependencies import _user_is_admin

    return UserResponse(
        id=str(user.id),
        email=user.email,
        name=user.name,
        avatar_url=user.avatar_url,
        privacy_accepted=user.privacy_accepted_at is not None,
        username=user.username,
        show_own_leaderboard_badge=user.show_own_leaderboard_badge,
        is_admin=_user_is_admin(user),
    )


@app.get(f"{API_PREFIX}/auth/me", response_model=UserResponse)
async def auth_me(user: User = Depends(get_current_user)):
    """Get the currently authenticated user profile."""
    return _user_response(user)


@app.get(f"{API_PREFIX}/auth/user", response_model=UserResponse)
async def auth_user(
    db: AsyncSession = Depends(get_db),
    user: User | None = Depends(get_local_or_optional_user),
):
    """Get the authenticated user profile (supports local auth)."""
    if user is None:
        raise HTTPException(status_code=401, detail="authentication required")
    return _user_response(user)


@app.post(f"{API_PREFIX}/settings/accept-privacy", status_code=200)
async def accept_privacy(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_user),
):
    """Record that the current user has accepted the privacy notice.

    Called once from the first-login modal.  Idempotent — safe to call
    again without resetting the original acceptance timestamp.
    """
    if user.privacy_accepted_at is None:
        result = await db.execute(select(User).where(User.id == user.id))
        row = result.scalar_one_or_none()
        if row is not None:
            row.privacy_accepted_at = datetime.now(timezone.utc)
            await db.commit()
    return {"privacy_accepted": True}


@app.patch(f"{API_PREFIX}/settings/preferences", response_model=UserResponse)
async def update_preferences(
    body: UpdatePreferencesRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_user),
):
    """Update the current user's personal display preferences.

    Currently only controls whether the "You" badge highlighting the
    user's own rows is shown on the leaderboard (default hidden/opt-in).
    """
    result = await db.execute(select(User).where(User.id == user.id))
    row = result.scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="user not found")
    row.show_own_leaderboard_badge = body.show_own_leaderboard_badge
    await db.commit()
    await db.refresh(row)
    return _user_response(row)


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


def _leaderboard_agent_entry(agent_id: str, registry: AgentRegistry, pop: dict, agg: dict,
                              current_username: str | None, is_personal: bool) -> dict:
    """Build a single leaderboard agent entry, adding display name and attribution.

    Public registry agent IDs are ``model@username`` (e.g. ``gpt-4o@herbertw``).
    Personal registry agent IDs are bare model names (e.g. ``gpt-4o``).
    """
    if "@" in agent_id:
        display_name, owner_username = agent_id.rsplit("@", 1)
    else:
        display_name = agent_id
        owner_username = current_username if is_personal else None

    is_own = is_personal or (owner_username is not None and owner_username == current_username)

    return {
        "agent_id": agent_id,
        "display_name": display_name,
        "owner_username": owner_username,
        "is_own": is_own,
        "elo": pop.get("elo_ratings", {}).get(agent_id),
        "alpha_rank": pop.get("alpha_rank_scores", {}).get(agent_id),
        "matches_played": registry.matches_played.get(agent_id, 0),
        "metrics": agg.get(agent_id, {}),
    }


def _build_leaderboard_response(
    registry: AgentRegistry,
    target: list[str],
    sort_by: str,
    sort_dir: str,
    page: int,
    page_size: int,
    current_username: str | None = None,
    is_personal: bool = False,
) -> dict:
    date_range = _registry_date_range(registry)
    if len(target) < 2:
        entries = [
            _leaderboard_agent_entry(a, registry,
                                     {"elo_ratings": registry.elo_ratings,
                                      "alpha_rank_scores": {}},
                                     registry.aggregated_metrics([a]),
                                     current_username, is_personal)
            for a in target
        ]
        return {
            "agents": entries, "total": len(entries),
            "page": page, "page_size": page_size,
            "total_matches": len(registry.match_history),
            "date_range": date_range,
            "note": "Need at least 2 agents for α-Rank computation.",
        }

    evaluator = MatchEvaluator(registry)
    pop = evaluator.population_report(target)
    agg = registry.aggregated_metrics(target)

    entries = [
        _leaderboard_agent_entry(a, registry, pop, agg, current_username, is_personal)
        for a in target
    ]
    reverse = sort_dir.lower() != "asc"
    entries.sort(key=lambda e: _safe_sort_key(e, sort_by), reverse=reverse)
    total = len(entries)
    return {
        "agents": entries[(page - 1) * page_size: page * page_size],
        "total": total, "page": page, "page_size": page_size,
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
    scope: str = Query(default="public", description="personal | public | all (ignored for anonymous users)"),
    db: AsyncSession = Depends(get_db),
    user: User | None = Depends(get_local_or_optional_user),
):
    """Paginated, sortable leaderboard with privacy scoping.

    - Anonymous / scope=public: only sessions explicitly marked public,
      agents attributed as model@username.
    - Logged-in / scope=personal (recommended default for UI): the user's
      own sessions (public + private), bare model names, no attribution.
    - Logged-in / scope=all: personal entries (is_own=True) + other users'
      public entries (is_own=False, attributed with owner_username).
    """
    effective_scope = "public"
    if user:
        effective_scope = scope if scope in ("personal", "public", "all") else "personal"

    current_username = user.username if user else None

    def _get_registry(is_personal: bool) -> AgentRegistry:
        if game:
            return get_game_registry(game) if not is_personal else get_game_registry(game)
        return get_global_registry()

    def _filtered_target(registry: AgentRegistry) -> list[str]:
        known = list(registry.elo_ratings.keys())
        if agent_ids:
            requested = [a.strip() for a in agent_ids.split(",") if a.strip()]
            target = [a for a in requested if a in known]
        else:
            target = known
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
            return filtered
        return target

    actual_sort = sort_by if sort_by in _SORTABLE_KEYS else "alpha_rank"

    if effective_scope == "personal" and user:
        personal_reg = await _build_personal_registry(user.id)
        target = _filtered_target(personal_reg)
        result = _build_leaderboard_response(
            personal_reg, target, actual_sort, sort_dir, page, page_size,
            current_username=current_username, is_personal=True,
        )
        result["scope"] = "personal"
        return sanitize_for_json(result)

    if effective_scope == "all" and user:
        # Personal half: user's own sessions including private ones
        personal_reg = await _build_personal_registry(user.id)
        personal_target = _filtered_target(personal_reg)
        personal_entries: list[dict] = []
        if len(personal_target) >= 2:
            evaluator = MatchEvaluator(personal_reg)
            pop = evaluator.population_report(personal_target)
            agg = personal_reg.aggregated_metrics(personal_target)
        else:
            pop = {"elo_ratings": personal_reg.elo_ratings, "alpha_rank_scores": {}}
            agg = personal_reg.aggregated_metrics(personal_target)
        for a in personal_target:
            personal_entries.append(_leaderboard_agent_entry(
                a, personal_reg, pop, agg, current_username, is_personal=True))

        # Public half: other users' public sessions, exclude current user's public entries
        pub_reg = get_game_registry(game) if game else get_global_registry()
        pub_target = [
            a for a in _filtered_target(pub_reg)
            if not (current_username and a.endswith(f"@{current_username}"))
        ]
        public_entries: list[dict] = []
        if pub_target:
            if len(pub_target) >= 2:
                evaluator = MatchEvaluator(pub_reg)
                pop_pub = evaluator.population_report(pub_target)
            else:
                pop_pub = {"elo_ratings": pub_reg.elo_ratings, "alpha_rank_scores": {}}
            agg_pub = pub_reg.aggregated_metrics(pub_target)
            for a in pub_target:
                public_entries.append(_leaderboard_agent_entry(
                    a, pub_reg, pop_pub, agg_pub, current_username, is_personal=False))

        all_entries = personal_entries + public_entries
        reverse = sort_dir.lower() != "asc"
        all_entries.sort(key=lambda e: _safe_sort_key(e, actual_sort), reverse=reverse)
        total = len(all_entries)
        start = (page - 1) * page_size
        result = {
            "agents": all_entries[start: start + page_size],
            "total": total, "page": page, "page_size": page_size,
            "scope": "all",
        }
        return sanitize_for_json(result)

    # Default / public scope
    registry = get_game_registry(game) if game else get_global_registry()
    target = _filtered_target(registry)
    result = _build_leaderboard_response(
        registry, target, actual_sort, sort_dir, page, page_size,
        current_username=current_username, is_personal=False,
    )
    result["scope"] = "public"
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
    from arena.auth.dependencies import _is_admin_enabled

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
        "admin_dashboard_enabled": _is_admin_enabled(),
    }


def _register_spa_fallback(app: FastAPI, static_root: Path, api_prefix: str) -> None:
    app.mount("/", StaticFiles(directory=static_root, html=True), name="static")

    @app.exception_handler(StarletteHTTPException)
    async def spa_fallback(request: Request, exc: StarletteHTTPException):
        """Serve index.html for unmatched non-API GETs so client-side routes survive a reload."""
        if (
            exc.status_code == 404
            and request.method == "GET"
            and not request.url.path.startswith(api_prefix)
        ):
            index_file = static_root / "index.html"
            if index_file.is_file():
                return FileResponse(index_file)
        return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})


if STATIC_ROOT.is_dir():
    _register_spa_fallback(app, STATIC_ROOT, API_PREFIX)
