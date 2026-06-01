from typing import Any
from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel
import os

from nash_arena.experiment_config import split_runtime_config
from nash_arena.game_registry import GameRegistryError
from nash_arena.session import GameSession


INTERNAL_TOKEN_HEADER = "X-Nash-Arena-Internal-Token"
INTERNAL_TOKEN_ENV = "NASH_ARENA_INTERNAL_API_TOKEN"


class ActionRequest(BaseModel):
    allocation: list[int]


def require_internal_api_token(token: str | None):
    expected = os.environ.get(INTERNAL_TOKEN_ENV)
    if not expected:
        raise HTTPException(
            status_code=500,
            detail=f"{INTERNAL_TOKEN_ENV} not configured"
        )
    if token != expected:
        raise HTTPException(status_code=401, detail="invalid internal API token")


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
    if "invalid player token" in message:
        return HTTPException(status_code=401, detail=message)
    if "already submitted" in message or "already complete" in message:
        return HTTPException(status_code=409, detail=message)
    return HTTPException(status_code=400, detail=message)


def get_session(sessions: dict[str, GameSession], session_id: str) -> GameSession:
    session = sessions.get(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="session not found")
    return session


def create_game_router(game_registry,
                       sessions: dict[str, GameSession],
                       require_internal_token=False):
    router = APIRouter()

    def config_from_request(request: dict[str, Any]):
        return game_registry.config_from_request(request)

    def verify_internal_token(internal_token: str | None):
        if require_internal_token:
            require_internal_api_token(internal_token)

    @router.post("/experiment")
    def create_experiment(request: dict[str, Any],
                          internal_token: str | None = Header(default=None, alias=INTERNAL_TOKEN_HEADER)):
        verify_internal_token(internal_token)

        try:
            game_payload, runtime_config = split_runtime_config(request)
            config = config_from_request(game_payload)
            game = game_registry.game_from_config(config)
            session = GameSession.create(config, game=game, runtime_config=runtime_config)
        except (ValueError, GameRegistryError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

        sessions[session.session_id] = session
        return session.creation_response()

    @router.get("/session/{session_id}/state")
    def get_state(session_id: str,
                  internal_token: str | None = Header(default=None, alias=INTERNAL_TOKEN_HEADER)):
        verify_internal_token(internal_token)

        return get_session(sessions, session_id).public_state()

    @router.post("/session/{session_id}/action")
    def submit_action(
        session_id: str,
        request: ActionRequest,
        authorization: str | None = Header(default=None),
        internal_token: str | None = Header(default=None, alias=INTERNAL_TOKEN_HEADER)
    ):
        verify_internal_token(internal_token)

        session = get_session(sessions, session_id)
        token = bearer_token(authorization)

        try:
            session.submit_action_with_token(token, request.allocation)
        except ValueError as exc:
            raise action_error(exc) from exc

        return session.public_state()

    @router.get("/session/{session_id}/results")
    def get_results(session_id: str,
                    internal_token: str | None = Header(default=None, alias=INTERNAL_TOKEN_HEADER)):
        verify_internal_token(internal_token)

        session = get_session(sessions, session_id)
        try:
            return session.results()
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    return router
