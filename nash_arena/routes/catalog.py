from fastapi import APIRouter, HTTPException

from nash_arena.game_registry import GameRegistryError


def create_catalog_router(game_registry):
    router = APIRouter()

    def game_registry_error(exc):
        return HTTPException(status_code=404, detail=str(exc))

    @router.get("/games")
    def list_games():
        return game_registry.list_games()

    @router.get("/games/{name}")
    def get_game(name: str):
        try:
            return game_registry.get_game(name)
        except GameRegistryError as exc:
            raise game_registry_error(exc) from exc

    @router.get("/games/{name}/metrics")
    def get_game_metrics(name: str):
        try:
            return game_registry.get_game_metrics(name)
        except GameRegistryError as exc:
            raise game_registry_error(exc) from exc

    @router.get("/games/{name}/prompts")
    def get_game_prompts(name: str):
        try:
            return game_registry.get_game_prompts(name)
        except GameRegistryError as exc:
            raise game_registry_error(exc) from exc

    @router.get("/games/{name}/skill")
    def get_game_skill(name: str):
        try:
            return {"game": name, "skill": game_registry.get_game_skill(name)}
        except GameRegistryError as exc:
            raise game_registry_error(exc) from exc

    return router
