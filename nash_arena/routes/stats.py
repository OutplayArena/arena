import os

from fastapi import APIRouter, Header, HTTPException

from nash_arena.session import GameSession

USER_TOKEN_ENV = "NASH_ARENA_USER_API_TOKEN"


def bearer_token(authorization: str | None) -> str:
    prefix = "Bearer "
    if not authorization or not authorization.startswith(prefix):
        raise HTTPException(status_code=401, detail="missing bearer token")

    token = authorization[len(prefix):].strip()
    if not token:
        raise HTTPException(status_code=401, detail="missing bearer token")
    return token


def require_user_api_token(authorization: str | None) -> None:
    expected = os.environ.get(USER_TOKEN_ENV)
    if not expected:
        raise HTTPException(
            status_code=500,
            detail=f"{USER_TOKEN_ENV} not configured",
        )

    token = bearer_token(authorization)
    if token != expected:
        raise HTTPException(status_code=401, detail="invalid user API token")


def create_stats_router(sessions: dict[str, GameSession]) -> APIRouter:
    router = APIRouter()

    def verify_user_token(authorization: str | None) -> None:
        require_user_api_token(authorization)

    @router.get("/experiments")
    def list_experiments(authorization: str | None = Header(default=None)):
        verify_user_token(authorization)

        experiments = []
        for session in sessions.values():
            state = session.public_state()
            experiments.append(
                {
                    "session_id": session.session_id,
                    "config_hash": session.config_hash,
                    "phase": state["phase"],
                    "round": state["round"],
                    "round_total": state["round_total"],
                }
            )

        return experiments

    @router.get("/experiments/{session_id}")
    def get_experiment(
        session_id: str,
        authorization: str | None = Header(default=None),
    ):
        verify_user_token(authorization)

        session = sessions.get(session_id)
        if session is None:
            raise HTTPException(status_code=404, detail="session not found")

        state = session.public_state()
        body = {
            "session_id": session.session_id,
            "config_hash": session.config_hash,
            "state": state,
        }

        if session.game.is_terminal(session.state):
            body["results"] = session.results()

        return body

    @router.get("/experiments/{session_id}/metrics")
    def get_experiment_metrics(
        session_id: str,
        authorization: str | None = Header(default=None),
    ):
        verify_user_token(authorization)

        session = sessions.get(session_id)
        if session is None:
            raise HTTPException(status_code=404, detail="session not found")

        try:
            return session.results()["metrics"]
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    return router
