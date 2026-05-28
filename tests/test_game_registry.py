from pathlib import Path
import importlib.util

import pytest

from arena.game_registry import CATALOG_ROOT, GameRegistry, GameRegistryError
from games.core.blotto.engine import BlottoGame


def test_registry_catalog_root_points_to_top_level_games_directory():
    assert CATALOG_ROOT.name == "games"
    assert (CATALOG_ROOT / "core" / "blotto" / "game.yaml").exists()


def test_registry_lists_blotto():
    games = GameRegistry().list_games()

    assert [game["name"] for game in games] == ["blotto"]
    assert games[0]["players"] == {"min": 2, "max": 2}
    assert "resource-allocation" in games[0]["tags"]


def test_registry_loads_blotto_details_metrics_and_prompts():
    registry = GameRegistry()

    details = registry.get_game("blotto")
    metrics = registry.get_game_metrics("blotto")
    prompts = registry.get_game_prompts("blotto")

    assert details["name"] == "blotto"
    assert details["example_config"]["game"] == "blotto"
    assert {metric["name"] for metric in metrics["metrics"]} >= {
        "total_payoff",
        "allocation_concentration",
    }
    assert prompts["action_format"]["type"] == "json_array"


def test_registry_builds_blotto_config_and_game_from_catalog():
    registry = GameRegistry()

    config = registry.config_from_request(
        {
            "game": "blotto",
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

    assert config.game == "blotto"
    assert game.num_battlefields == 2
    assert isinstance(game, BlottoGame)


def test_arena_package_does_not_own_blotto_specific_modules():
    assert importlib.util.find_spec("arena.config") is None
    assert importlib.util.find_spec("arena.engine") is None
    assert importlib.util.find_spec("arena.metrics") is None
    assert importlib.util.find_spec("arena.agent") is None


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
