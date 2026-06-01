import os
from pathlib import Path
from typing import Any

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from nash_arena.experiment_config import split_runtime_config
from nash_arena.game_registry import GameRegistry
from nash_arena.routes.catalog import create_catalog_router
from nash_arena.routes.frontend import create_frontend_router
from nash_arena.routes.game import bearer_token, create_game_router
from nash_arena.routes.stats import create_stats_router
from nash_arena.session import GameSession


API_PREFIX = os.environ.get("API_PREFIX", "/api").rstrip("/")
app = FastAPI(title="Blotto Agent Arena")
SESSIONS: dict[str, GameSession] = {}
STATIC_ROOT = Path(__file__).resolve().parent.parent / "static"
GAME_REGISTRY = GameRegistry()


def config_from_request(request: dict[str, Any]):
    game_payload, _ = split_runtime_config(request)
    return GAME_REGISTRY.config_from_request(game_payload)


def health():
    return {"status": "ok"}


app.add_api_route("/health", health, methods=["GET"])
if API_PREFIX:
    app.add_api_route(f"{API_PREFIX}/health", health, methods=["GET"])

catalog_router = create_catalog_router(GAME_REGISTRY)
internal_game_router = create_game_router(
    GAME_REGISTRY,
    SESSIONS,
    require_internal_token=True,
)
frontend_router = create_frontend_router(GAME_REGISTRY, SESSIONS)
stats_router = create_stats_router(SESSIONS)

app.include_router(catalog_router)
app.include_router(catalog_router, prefix="/api/catalog")
app.include_router(internal_game_router, prefix="/api/game")
app.include_router(frontend_router, prefix="/api/frontend")
app.include_router(stats_router, prefix="/api/stats")

app.mount("/", StaticFiles(directory=STATIC_ROOT, html=True), name="static")
