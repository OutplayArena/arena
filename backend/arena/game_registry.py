from pathlib import Path
import importlib

import yaml
from jinja2 import Template


def _find_catalog_root() -> Path:
    """Find the games catalog root directory.
    
    Tries multiple locations to support both development and Docker environments:
    1. /app/games/games (Docker container)
    2. ../games/games relative to this file (development)
    """
    # Docker container: /app/games/games
    docker_path = Path("/app/games/games")
    if docker_path.exists():
        return docker_path
    
    # Development: relative to this file
    dev_path = Path(__file__).resolve().parent.parent.parent / "games" / "games"
    if dev_path.exists():
        return dev_path
    
    # Fallback to development path
    return dev_path


CATALOG_ROOT = _find_catalog_root()


class GameRegistryError(ValueError):
    pass


def _parse_skill_markdown(game_slug: str, content: str) -> dict:
    sections: dict[str, str] = {}
    current_key = "introduction"
    current_lines: list[str] = []
    title = ""

    for raw in content.strip().split("\n"):
        line = raw.rstrip()
        if line.startswith("## "):
            if current_lines:
                sections[current_key] = "\n".join(current_lines).strip()
                current_lines = []
            current_key = line[3:].strip().lower().replace(" ", "_")
        elif line.startswith("# ") and not title:
            title = line[2:].strip()
        else:
            current_lines.append(raw)

    if current_lines:
        sections[current_key] = "\n".join(current_lines).strip()

    sections.setdefault("introduction", "")

    return {
        "game": game_slug,
        "title": title,
        "sections": sections,
    }


def _has_ui_component(game_dir: Path, name: str) -> bool:
    return (game_dir / "ui" / f"{name}.tsx").exists()


def _detect_ui(game_dir: Path, metadata: dict | None = None) -> dict:
    has_live_view = _has_ui_component(game_dir, "LiveView")
    has_config = _has_ui_component(game_dir, "ConfigForm")
    has_history = _has_ui_component(game_dir, "HistoryView")
    has_play = _has_ui_component(game_dir, "PlayView")
    return {
        "live_view": has_live_view,
        "custom_config": has_config,
        "custom_history": has_history,
        "interactive_play": has_play,
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
        metadata["ui"] = _detect_ui(game_dir, metadata)
        return metadata

    def get_game_metrics(self, name: str) -> dict:
        raw = self._load_yaml(self._game_dir(name) / "metrics.yaml")
        metrics_list = raw.get("metrics", [])
        if not isinstance(metrics_list, list):
            return {"metrics": []}
        from arena.metrics.catalog import build_metrics_list
        names = []
        overrides = {}
        for entry in metrics_list:
            if isinstance(entry, str):
                names.append(entry)
            elif isinstance(entry, dict) and "name" in entry:
                names.append(entry["name"])
                if "description" in entry and len(entry) > 1:
                    overrides[entry["name"]] = entry["description"]
        return {"metrics": build_metrics_list(names, overrides)}

    def get_game_prompts(self, name: str) -> dict:
        return self._load_yaml(self._game_dir(name) / "prompts.yaml")

    def render_observation(
        self,
        game_name: str,
        state: dict,
        config: dict,
        player_id: str,
        variant: str = "neutral",
    ) -> dict:
        """Render the system + turn prompts for a given player and game state."""
        prompts = self._load_yaml(self._game_dir(game_name) / "prompts.yaml")
        ctx = self._build_observation_context(game_name, state, config, player_id)

        system_src = prompts.get("system", "")
        if variant and variant != "neutral":
            variant_src = prompts.get("variants", {}).get(variant, "")
            if variant_src:
                system_src = variant_src.rstrip() + "\n\n" + system_src

        turn_src = self._pick_turn_template(game_name, state, prompts)

        return {
            "system": Template(system_src).render(**ctx).strip(),
            "turn": Template(turn_src).render(**ctx).strip(),
            "player_id": player_id,
            "variant": variant,
        }

    def _build_observation_context(
        self, game_name: str, state: dict, config: dict, player_id: str
    ) -> dict:
        ctx = {**config, **state}

        all_players = list(state.get("total_scores", {}).keys())
        opp_ids = [p for p in all_players if p != player_id]
        opp_id = opp_ids[0] if opp_ids else None
        total_scores = state.get("total_scores", {})

        messages = state.get("messages") or []
        inbox = [
            m for m in messages
            if m.get("recipient") in ("all", player_id) or m.get("sender") == player_id
        ]

        ctx.update({
            "player_id": player_id,
            "my_id": player_id,
            "opp_id": opp_id,
            "opp_ids": opp_ids,
            "my_score": total_scores.get(player_id, 0),
            "opp_score": total_scores.get(opp_id, 0) if opp_id else 0,
            "opp_scores": {p: total_scores.get(p, 0) for p in opp_ids},
            "score_a": total_scores.get("A", 0),
            "score_b": total_scores.get("B", 0),
            "total_scores": total_scores,
            "players": len(all_players),
            # Auto-injected inbox (#122): the observation carries the player's
            # visible mailbox messages directly, so agents no longer need to
            # spend a tool call polling get_mailbox every turn.
            "inbox": inbox,
        })

        if "round_total" in state:
            ctx.setdefault("rounds", state["round_total"])

        if "pot_a" in state and "pot_b" in state:
            ctx["my_pot"] = state["pot_a"] if player_id == "A" else state["pot_b"]
            ctx["opp_pot"] = state["pot_b"] if player_id == "A" else state["pot_a"]

        if "pending_offer" in state:
            offer = state.get("pending_offer") or 0.0
            total = state.get("total") or config.get("total") or 100.0
            ctx["offer"] = offer
            ctx["offer_fraction"] = offer / total if total else 0.0

        if "payoffs" in state and isinstance(state["payoffs"], dict):
            p = state["payoffs"]
            ctx.setdefault("payoff_stag_stag", p.get("stag_stag", 0))
            ctx.setdefault("payoff_hare_hare", p.get("hare_hare", 0))
            ctx.setdefault("payoff_stag_hare", p.get("stag_hare", 0))

        # Optional in-game exploitability signal (#135): a game's metrics extension
        # may define `exploitability_warning(state, player_id) -> str | None` to
        # surface a mid-game warning when an opponent's play is highly predictable.
        ext = self.metrics_extension(game_name)
        if ext is not None and hasattr(ext, "exploitability_warning"):
            warning = ext.exploitability_warning(state, player_id)
            if warning:
                ctx["exploitability_warning"] = warning

        return ctx

    def _pick_turn_template(self, game_name: str, state: dict, prompts: dict) -> str:
        phase = state.get("phase", "")
        if game_name == "ultimatum":
            if phase == "awaiting_proposal":
                return prompts.get("proposer_state", prompts.get("state", ""))
            return prompts.get("responder_state", prompts.get("state", ""))
        return prompts.get("state", prompts.get("turn", ""))

    def get_game_scenarios(self, name: str) -> list[dict]:
        game_dir = self._game_dir(name)
        namespace = game_dir.parent.name
        try:
            module = importlib.import_module(f"games.{namespace}.{name}.scenarios")
        except ImportError:
            return []
        scenarios = []
        for sid in getattr(module, "ALL_SCENARIOS", ()):
            scenario = module.get_scenario(sid)
            scenarios.append({
                "id": scenario.id,
                "name": scenario.name,
                "description": scenario.description,
                "cooperate_label": scenario.cooperate_label,
                "defect_label": scenario.defect_label,
                "system_prompt": scenario.system_prompt,
            })
        return scenarios

    def get_game_agents(self, name: str) -> dict:
        game_dir = self._game_dir(name)
        agents_yaml = game_dir / "agents.yaml"
        if agents_yaml.exists():
            return self._load_yaml(agents_yaml)
        return {"agents": []}

    def get_game_skill(self, name: str, structured: bool = False) -> str | dict:
        game_dir = self._game_dir(name)
        skill_path = game_dir / "skill.md"
        if not skill_path.exists():
            raise GameRegistryError(f"skill not found for game: {name}")
        raw = skill_path.read_text(encoding="utf-8")
        if not structured:
            return raw
        return _parse_skill_markdown(name, raw)

    def config_from_request(self, payload: dict):
        game = payload.get("game")
        if not game:
            raise GameRegistryError("experiment config must include game")
        module = self._game_module(game)
        return module.config_from_dict(payload)

    def game_from_config(self, config):
        module = self._game_module(config.game)
        return module.game_from_config(config)

    def metrics_extension(self, game_type: str):
        """
        Load the GameMetricsExtension for a game, or None if not defined.

        Imports the game's metrics.py submodule and returns the first class
        that inherits from GameMetricsExtension.
        """
        from arena.metrics.extension import GameMetricsExtension
        try:
            game_dir = self._game_dir(game_type)
        except GameRegistryError:
            return None
        namespace = game_dir.parent.name
        try:
            module = importlib.import_module(f"games.{namespace}.{game_type}.metrics")
        except ImportError:
            return None
        for name in dir(module):
            obj = getattr(module, name)
            if (
                isinstance(obj, type)
                and issubclass(obj, GameMetricsExtension)
                and obj is not GameMetricsExtension
            ):
                return obj()
        return None

    def get_metric_names(self, game_type: str) -> set[str]:
        """Return the set of metric names declared in a game's metrics.yaml."""
        try:
            data = self.get_game_metrics(game_type)
        except GameRegistryError:
            return set()
        metrics_list = data.get("metrics", [])
        if not isinstance(metrics_list, list):
            return set()
        names = set()
        for entry in metrics_list:
            if isinstance(entry, str):
                names.add(entry)
            elif isinstance(entry, dict) and "name" in entry:
                names.add(entry["name"])
        return names

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
