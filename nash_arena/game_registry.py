from pathlib import Path
import importlib

import yaml


CATALOG_ROOT = Path(__file__).resolve().parent.parent / "games"


class GameRegistryError(ValueError):
    pass


def _has_ui_component(game_dir: Path, name: str) -> bool:
    return (game_dir / "ui" / f"{name}.tsx").exists()


def _detect_ui(game_dir: Path) -> dict:
    ui_dir = game_dir / "ui"
    has_live_view = _has_ui_component(game_dir, "LiveView")
    has_config = _has_ui_component(game_dir, "ConfigForm")
    has_history = _has_ui_component(game_dir, "HistoryView")
    return {
        "live_view": has_live_view,
        "custom_config": has_config,
        "custom_history": has_history,
    }


class GameRegistry:
    def __init__(self, catalog_root: Path | None = None):
        self.catalog_root = Path(catalog_root) if catalog_root else CATALOG_ROOT

    def list_games(self) -> list[dict]:
        games = [self._summary(metadata, slug) for slug, metadata in self._iter_game_metadata()]
        return sorted(games, key=lambda game: game["name"])

    def get_game(self, name: str) -> dict:
        game_dir = self._game_dir(name)
        metadata = self._load_yaml(game_dir / "game.yaml")
        metadata["slug"] = name
        metadata["ui"] = _detect_ui(game_dir)
        return metadata

    def get_game_metrics(self, name: str) -> dict:
        return self._load_yaml(self._game_dir(name) / "metrics.yaml")

    def get_game_prompts(self, name: str) -> dict:
        return self._load_yaml(self._game_dir(name) / "prompts.yaml")

    def get_game_agents(self, name: str) -> dict:
        game_dir = self._game_dir(name)
        agents_yaml = game_dir / "agents.yaml"
        if agents_yaml.exists():
            return self._load_yaml(agents_yaml)
        return {"agents": []}

    def get_game_skill(self, name: str) -> str:
        game_dir = self._game_dir(name)
        skill_path = game_dir / "skill.md"
        if not skill_path.exists():
            raise GameRegistryError(f"skill not found for game: {name}")
        return skill_path.read_text(encoding="utf-8")

    def config_from_request(self, payload: dict):
        game = payload.get("game")
        if not game:
            raise GameRegistryError("experiment config must include game")
        module = self._game_module(game)
        return module.config_from_dict(payload)

    def game_from_config(self, config):
        module = self._game_module(config.game)
        return module.game_from_config(config)

    def _iter_game_metadata(self):
        for namespace in ("core", "community"):
            namespace_dir = self.catalog_root / namespace
            if not namespace_dir.exists():
                continue
            for game_yaml in namespace_dir.glob("*/game.yaml"):
                metadata = self._load_yaml(game_yaml)
                if metadata.get("status") == "deprecated":
                    continue
                slug = game_yaml.parent.name
                yield slug, metadata

    def _game_dir(self, name: str) -> Path:
        for namespace in ("core", "community"):
            candidate = self.catalog_root / namespace / name
            if (candidate / "game.yaml").exists():
                return candidate
        raise GameRegistryError(f"game not found: {name}")

    def _game_module(self, name: str):
        game_dir = self._game_dir(name)
        namespace = game_dir.parent.name
        try:
            return importlib.import_module(f"games.{namespace}.{name}")
        except ImportError as exc:
            raise GameRegistryError(f"could not import game module: {name}") from exc

    def _load_yaml(self, path: Path) -> dict:
        if not path.exists():
            raise GameRegistryError(f"missing game file: {path}")
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise GameRegistryError(f"invalid game file: {path}")
        return data

    def _summary(self, metadata: dict, slug: str) -> dict:
        return {
            "name": metadata["name"],
            "slug": slug,
            "version": metadata.get("version"),
            "status": metadata.get("status"),
            "description": metadata.get("description"),
            "tags": metadata.get("tags", []),
            "players": metadata.get("players", {}),
            "ontology": metadata.get("ontology", {}),
        }
