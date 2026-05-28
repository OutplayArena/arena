import os
from pathlib import Path

from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

import httpx

from blotto.config import BattlefieldConfig, BlottoExperimentConfig
from blotto.db import get_db
from blotto.k8s import get_orchestrator, MCPOrchestrator
from blotto.models import SessionModel
from blotto.session import GameSession

API_PREFIX = os.environ.get("API_PREFIX", "/api")
BASE_URL = os.environ.get("ARENA_BASE_URL", f"http://127.0.0.1:8000{API_PREFIX}")

app = FastAPI(title="Blotto Agent Arena")
STATIC_ROOT = Path(__file__).resolve().parent.parent / "static"

_orchestrator: MCPOrchestrator | None = None
_mcp_pod_ips: dict[str, dict[str, str]] = {}


def get_orchestrator_singleton() -> MCPOrchestrator:
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = get_orchestrator()
    return _orchestrator


class BattlefieldRequest(BaseModel):
    id: str
    value: float = 1.0


class ExperimentRequest(BaseModel):
    game: str
    variant: str
    players: int
    budget: list[int]
    battlefields: list[BattlefieldRequest]
    rounds: int
    seed: int | None = None


class ActionRequest(BaseModel):
    allocation: list[int]


def config_from_request(request: ExperimentRequest) -> BlottoExperimentConfig:
    return BlottoExperimentConfig(
        game=request.game,
        variant=request.variant,
        players=request.players,
        budget=list(request.budget),
        battlefields=[
            BattlefieldConfig(id=field.id, value=field.value)
            for field in request.battlefields
        ],
        rounds=request.rounds,
        seed=request.seed,
    )


async def get_session_from_db(session_id: str, db: AsyncSession) -> GameSession:
    result = await db.execute(
        select(SessionModel).where(SessionModel.id == session_id)
    )
    row = result.scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="session not found")
    return GameSession.from_db_row(row)


async def save_session(session: GameSession, db: AsyncSession):
    row = SessionModel(**session.to_db_dict())
    await db.merge(row)
    await db.commit()


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


@app.get(f"{API_PREFIX}/health")
async def health(db: AsyncSession = Depends(get_db)):
    try:
        await db.execute(select(SessionModel).limit(1))
        db_status = "ok"
    except Exception:
        db_status = "unavailable"
    return {"status": "ok", "database": db_status}


@app.post(f"{API_PREFIX}/experiment")
async def create_experiment(
    request: ExperimentRequest,
    db: AsyncSession = Depends(get_db),
    skip_mcp: bool = False,
):
    try:
        config = config_from_request(request)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    session = GameSession.create(config)
    await save_session(session, db)

    if not skip_mcp:
        orch = get_orchestrator_singleton()
        for player in ["A", "B"]:
            token = session.player_tokens[player]
            try:
                pod_ip = await orch.start_mcp_server(
                    session_id=session.session_id,
                    player=player,
                    base_url=BASE_URL,
                    token=token,
                )
                _mcp_pod_ips.setdefault(session.session_id, {})[player] = pod_ip
            except Exception:
                pass

    return session.creation_response()


@app.get(f"{API_PREFIX}/session/{{session_id}}/state")
async def get_state(
    session_id: str, db: AsyncSession = Depends(get_db)
):
    session = await get_session_from_db(session_id, db)
    return session.public_state()


@app.post(f"{API_PREFIX}/session/{{session_id}}/action")
async def submit_action(
    session_id: str,
    request: ActionRequest,
    authorization: str | None = Header(default=None),
    db: AsyncSession = Depends(get_db),
):
    session = await get_session_from_db(session_id, db)
    token = bearer_token(authorization)

    try:
        session.submit_action_with_token(token, request.allocation)
    except ValueError as exc:
        raise action_error(exc) from exc

    await save_session(session, db)
    return session.public_state()


@app.get(f"{API_PREFIX}/session/{{session_id}}/results")
async def get_results(
    session_id: str, db: AsyncSession = Depends(get_db)
):
    session = await get_session_from_db(session_id, db)
    try:
        return session.results()
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@app.get(f"{API_PREFIX}/mcp/{{session_id}}/{{player}}/sse")
async def mcp_sse_proxy(session_id: str, player: str, request: Request):
    session_ips = _mcp_pod_ips.get(session_id, {})
    pod_ip = session_ips.get(player)
    if not pod_ip:
        raise HTTPException(status_code=404, detail="MCP server not found for this session")

    upstream_url = f"http://{pod_ip}:8001"

    async def event_generator():
        async with httpx.AsyncClient(timeout=300.0) as client:
            async with client.stream("GET", f"{upstream_url}/sse") as response:
                async for line in response.aiter_lines():
                    if await request.is_disconnected():
                        break
                    yield f"{line}\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


app.mount("/", StaticFiles(directory=STATIC_ROOT, html=True), name="static")
