from pathlib import Path
import importlib.util

import pytest

from nash_arena.game_registry import CATALOG_ROOT, GameRegistry, GameRegistryError
from games.core.colonelblotto.engine import ColonelBlottoGame


def test_registry_catalog_root_points_to_top_level_games_directory():
    assert CATALOG_ROOT.name == "games"
    assert (CATALOG_ROOT / "core" / "colonelblotto" / "game.yaml").exists()


def test_registry_lists_blotto():
    games = GameRegistry().list_games()
    slugs = [g["slug"] for g in games]

    assert "colonelblotto" in slugs
    blotto = next(g for g in games if g["slug"] == "colonelblotto")
    assert blotto["players"] == {"min": 2, "max": 2}
    assert "resource-allocation" in blotto["tags"]


def test_registry_lists_rps_and_prisonersdilemma():
    games = GameRegistry().list_games()
    slugs = [g["slug"] for g in games]

    assert "rock_paper_scissors" in slugs, f"rock_paper_scissors not in {slugs}"
    assert "prisonersdilemma" in slugs, f"prisonersdilemma not in {slugs}"


def test_registry_loads_blotto_details_metrics_and_prompts():
    registry = GameRegistry()

    details = registry.get_game("colonelblotto")
    metrics = registry.get_game_metrics("colonelblotto")
    prompts = registry.get_game_prompts("colonelblotto")

    assert details["name"] == "Colonel Blotto"
    assert details["example_config"]["game"] == "colonelblotto"
    assert {metric["name"] for metric in metrics["metrics"]} >= {
        "total_payoff",
        "allocation_concentration",
    }
    assert prompts["action_format"]["type"] == "json_array"


def test_registry_loads_blotto_skill():
    skill = GameRegistry().get_game_skill("colonelblotto")

    assert "Colonel Blotto" in skill
    assert "MCP tools" in skill
    assert "submit_action" in skill
    assert "Do not call REST endpoints directly." in skill


def test_registry_builds_blotto_config_and_game_from_catalog():
    registry = GameRegistry()

    config = registry.config_from_request(
        {
            "game": "colonelblotto",
            "variant": "classic",
            "players": 2,
            "budget": [10, 10],
            "battlefields": [
                {"id": "left", "value": 1.0},
                {"id": "right", "value": 1.0},
            ],
            "rounds": 2,
            "seed": 42,
        }
    )
    game = registry.game_from_config(config)

    assert config.game == "colonelblotto"
    assert game.num_battlefields == 2
    assert isinstance(game, ColonelBlottoGame)


def test_arena_package_does_not_own_blotto_specific_modules():
    # Game-specific modules must live under games/, not in nash_arena directly
    assert importlib.util.find_spec("nash_arena.config") is None
    assert importlib.util.find_spec("nash_arena.engine") is None
    assert importlib.util.find_spec("nash_arena.agent") is None
    # nash_arena.metrics is intentionally present — it's the game-agnostic
    # metrics infrastructure. Blotto-specific logic lives in games/core/colonelblotto/metrics.py
    assert importlib.util.find_spec("nash_arena.metrics") is not None
    assert importlib.util.find_spec("nash_arena.metrics.blotto") is None


def test_registry_rejects_unknown_game():
    with pytest.raises(GameRegistryError, match="game not found"):
        GameRegistry().get_game("missing")


def test_registry_can_load_from_custom_catalog(tmp_path: Path):
    game_dir = tmp_path / "community" / "mini"
    game_dir.mkdir(parents=True)
    (tmp_path / "core").mkdir()
    (game_dir / "game.yaml").write_text(
        """
name: mini
version: "0.1.0"
status: stable
description: Mini game.
tags: [test]
players: {min: 2, max: 4}
ontology: {timing: single_round}
""".strip(),
        encoding="utf-8",
    )

    assert GameRegistry(tmp_path).list_games()[0]["name"] == "mini"
