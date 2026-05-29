from typing import Any

from fastapi import APIRouter, Header, HTTPException

from nash_arena.game_registry import GameRegistryError
from nash_arena.routes.game import ActionRequest, action_error, bearer_token, get_session
from nash_arena.session import GameSession


def create_frontend_router(game_registry, sessions: dict[str, GameSession]):
    router = APIRouter()

    @router.get("/games")
    def list_games():
        return game_registry.list_games()

    @router.get("/games/{name}")
    def get_game(name: str):
        try:
            return game_registry.get_game(name)
        except GameRegistryError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @router.post("/experiment")
    def create_experiment(request: dict[str, Any]):
        try:
            config = game_registry.config_from_request(request)
            game = game_registry.game_from_config(config)
        except (ValueError, GameRegistryError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

        session = GameSession.create(config, game=game)
        sessions[session.session_id] = session
        return session.creation_response()

    @router.get("/session/{session_id}/state")
    def get_state(session_id: str):
        return get_session(sessions, session_id).public_state()

    @router.post("/session/{session_id}/action")
    def submit_action(
        session_id: str,
        request: ActionRequest,
        authorization: str | None = Header(default=None),
    ):
        session = get_session(sessions, session_id)
        token = bearer_token(authorization)

        try:
            session.submit_action_with_token(token, request.allocation)
        except ValueError as exc:
            raise action_error(exc) from exc

        return session.public_state()

    @router.get("/session/{session_id}/results")
    def get_results(session_id: str):
        session = get_session(sessions, session_id)
        try:
            return session.results()
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    return router
