from pathlib import Path
from typing import Any

from fastapi import FastAPI, Header, HTTPException
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from arena.game_registry import GameRegistry, GameRegistryError
from arena.session import GameSession


app = FastAPI(title="Blotto Agent Arena")
SESSIONS: dict[str, GameSession] = {}
STATIC_ROOT = Path(__file__).resolve().parent.parent / "static"
GAME_REGISTRY = GameRegistry()


class ActionRequest(BaseModel):
    allocation: list[int]


def config_from_request(request: dict[str, Any]):
    return GAME_REGISTRY.config_from_request(request)


def get_session(session_id: str) -> GameSession:
    session = SESSIONS.get(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="session not found")
    return session


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


def game_registry_error(exc: GameRegistryError) -> HTTPException:
    return HTTPException(status_code=404, detail=str(exc))


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/games")
def list_games():
    return GAME_REGISTRY.list_games()


@app.get("/games/{name}")
def get_game(name: str):
    try:
        return GAME_REGISTRY.get_game(name)
    except GameRegistryError as exc:
        raise game_registry_error(exc) from exc


@app.get("/games/{name}/metrics")
def get_game_metrics(name: str):
    try:
        return GAME_REGISTRY.get_game_metrics(name)
    except GameRegistryError as exc:
        raise game_registry_error(exc) from exc


@app.get("/games/{name}/prompts")
def get_game_prompts(name: str):
    try:
        return GAME_REGISTRY.get_game_prompts(name)
    except GameRegistryError as exc:
        raise game_registry_error(exc) from exc


@app.post("/experiment")
def create_experiment(request: dict[str, Any]):
    try:
        config = config_from_request(request)
        game = GAME_REGISTRY.game_from_config(config)
    except (ValueError, GameRegistryError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    session = GameSession.create(config, game=game)
    SESSIONS[session.session_id] = session
    return session.creation_response()


@app.get("/session/{session_id}/state")
def get_state(session_id: str):
    return get_session(session_id).public_state()


@app.post("/session/{session_id}/action")
def submit_action(
    session_id: str,
    request: ActionRequest,
    authorization: str | None = Header(default=None),
):
    session = get_session(session_id)
    token = bearer_token(authorization)

    try:
        session.submit_action_with_token(token, request.allocation)
    except ValueError as exc:
        raise action_error(exc) from exc

    return session.public_state()


@app.get("/session/{session_id}/results")
def get_results(session_id: str):
    session = get_session(session_id)
    try:
        return session.results()
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


app.mount("/", StaticFiles(directory=STATIC_ROOT, html=True), name="static")
