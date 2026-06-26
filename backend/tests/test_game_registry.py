from pathlib import Path
import importlib.util

import pytest

from arena.game_registry import (
    CATALOG_ROOT,
    GameRegistry,
    GameRegistryError,
    _detect_ui,
    _has_ui_component,
    _parse_skill_markdown,
)
from arena.manifest import build_agent_manifest
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


def test_registry_loads_blotto_skill_structured():
    skill = GameRegistry().get_game_skill("colonelblotto", structured=True)

    assert skill["game"] == "colonelblotto"
    assert skill["title"] == "Colonel Blotto Skill"
    assert "sections" in skill
    sections = skill["sections"]
    assert "objective" in sections
    assert "action_format" in sections
    assert "rules" in sections
    assert "strategy_hints" in sections
    assert "awaiting" in sections["required_tool_flow"]


def test_registry_loads_pd_skill_structured():
    skill = GameRegistry().get_game_skill("prisonersdilemma", structured=True)

    assert skill["game"] == "prisonersdilemma"
    sections = skill["sections"]
    assert "objective" in sections
    assert "action_format" in sections
    assert "strategy_notes" in sections
    assert "cooperate" in sections["action_format"].lower()


def test_registry_skill_missing_game():
    with pytest.raises(GameRegistryError, match="game not found"):
        GameRegistry().get_game_skill("nonexistent", structured=True)


def test_build_agent_manifest_colonelblotto():
    manifest = build_agent_manifest("colonelblotto")

    assert manifest["platform"] == "outplaylabs-arena"
    assert manifest["manifest_version"] == "1.0"
    assert manifest["game"] == "colonelblotto"
    assert manifest["game_metadata"]["name"] == "Colonel Blotto"
    assert "auth" in manifest
    assert manifest["auth"]["type"] == "bearer"
    assert manifest["auth"]["key_prefix"] == "nks_"
    assert len(manifest["tools"]) == 12
    tool_names = [t["name"] for t in manifest["tools"]]
    assert "get_game_state" in tool_names
    assert "submit_action" in tool_names
    assert "get_game_skill" in tool_names
    assert "get_agent_manifest" in tool_names
    assert len(manifest["openai_tools"]) == 3
    assert "action_format" in manifest
    assert "game_lifecycle" in manifest
    assert "skill" in manifest
    assert manifest["skill"]["title"] == "Colonel Blotto Skill"


def test_build_agent_manifest_pd():
    manifest = build_agent_manifest("prisonersdilemma")

    assert manifest["game"] == "prisonersdilemma"
    assert manifest["game_metadata"]["name"] == "Prisoner's Dilemma"
    assert manifest["skill"]["sections"]["strategy_notes"] != ""
    assert len(manifest["openai_tools"]) == 3


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
    # Game-specific modules must live under games/, not in arena directly
    assert importlib.util.find_spec("arena.config") is None
    assert importlib.util.find_spec("arena.engine") is None
    assert importlib.util.find_spec("arena.agent") is None
    # arena.metrics is intentionally present — it's the game-agnostic
    # metrics infrastructure. Blotto-specific logic lives in games/core/colonelblotto/metrics.py
    assert importlib.util.find_spec("arena.metrics") is not None
    assert importlib.util.find_spec("arena.metrics.blotto") is None


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


def test_registry_config_from_request_without_game_raises():
    with pytest.raises(GameRegistryError, match="must include game"):
        GameRegistry().config_from_request({})


def test_registry_get_game_agents_returns_dict_with_agents():
    agents = GameRegistry().get_game_agents("ultimatum")
    assert "agents" in agents
    assert isinstance(agents["agents"], list)


def test_registry_get_game_agents_returns_empty_when_no_yaml(tmp_path: Path):
    (tmp_path / "core").mkdir()
    game_dir = tmp_path / "core" / "no_agents_game"
    game_dir.mkdir()
    (game_dir / "game.yaml").write_text(
        'name: no-agents\nversion: "1.0"\nstatus: stable\n',
        encoding="utf-8",
    )
    agents = GameRegistry(tmp_path).get_game_agents("no_agents_game")
    assert agents == {"agents": []}


def test_registry_get_metric_names_blotto():
    names = GameRegistry().get_metric_names("colonelblotto")
    assert isinstance(names, set)
    assert "total_payoff" in names


def test_registry_get_metric_names_unknown_game_returns_empty_set():
    assert GameRegistry().get_metric_names("does-not-exist") == set()


def test_registry_metrics_extension_returns_object_or_none():
    ext = GameRegistry().metrics_extension("colonelblotto")
    assert ext is not None
    assert hasattr(ext, "metrics_for_match") or hasattr(ext, "name") or hasattr(ext, "__class__")


def test_registry_metrics_extension_unknown_game_returns_none():
    assert GameRegistry().metrics_extension("does-not-exist") is None


def test_registry_list_games_includes_ultimatum():
    slugs = {g["slug"] for g in GameRegistry().list_games()}
    assert "ultimatum" in slugs


def test_parse_skill_markdown_parses_sections():
    md = (
        "# Colonel Blotto\n\n"
        "## Objective\n\nWin more battlefields.\n\n"
        "## Action Format\n\n"
        "Use submit_action.\n"
    )
    parsed = _parse_skill_markdown("colonelblotto", md)
    assert parsed["title"] == "Colonel Blotto"
    assert "objective" in parsed["sections"]
    assert "action_format" in parsed["sections"]
    assert "Win more battlefields" in parsed["sections"]["objective"]


def test_parse_skill_markdown_with_no_h2_defaults_to_introduction():
    md = "# Untitled\n\nJust some text.\n"
    parsed = _parse_skill_markdown("test", md)
    assert "introduction" in parsed["sections"]
    assert "Just some text" in parsed["sections"]["introduction"]


def test_detect_ui_returns_dict_with_all_keys(tmp_path: Path):
    result = _detect_ui(tmp_path)
    assert set(result.keys()) == {
        "live_view", "custom_config", "custom_history", "interactive_play"
    }
    assert all(value is False for value in result.values())


def test_detect_ui_finds_existing_components(tmp_path: Path):
    (tmp_path / "ui").mkdir()
    (tmp_path / "ui" / "LiveView.tsx").write_text("// live")
    (tmp_path / "ui" / "PlayView.tsx").write_text("// play")
    result = _detect_ui(tmp_path)
    assert result["live_view"] is True
    assert result["interactive_play"] is True
    assert result["custom_config"] is False


def test_has_ui_component_returns_true_for_existing(tmp_path: Path):
    (tmp_path / "ui").mkdir()
    (tmp_path / "ui" / "HistoryView.tsx").write_text("// hist")
    assert _has_ui_component(tmp_path, "HistoryView") is True
    assert _has_ui_component(tmp_path, "LiveView") is False


def test_summary_extracts_metadata_fields():
    metadata = {
        "name": "Test",
        "version": "1.0",
        "status": "stable",
        "description": "A test game",
        "tags": ["x", "y"],
        "players": {"min": 2, "max": 4},
        "ontology": {"timing": "single_round"},
    }
    result = GameRegistry()._summary(metadata, "test")
    assert result["name"] == "Test"
    assert result["slug"] == "test"
    assert result["version"] == "1.0"
    assert result["status"] == "stable"
    assert result["tags"] == ["x", "y"]
    assert result["players"] == {"min": 2, "max": 4}


def test_summary_uses_empty_defaults():
    metadata = {"name": "Bare"}
    result = GameRegistry()._summary(metadata, "bare")
    assert result["version"] is None
    assert result["status"] is None
    assert result["description"] is None
    assert result["tags"] == []
    assert result["players"] == {}
    assert result["ontology"] == {}


def test_render_observation_blotto_neutral():
    registry = GameRegistry()
    state = {
        "total_scores": {"A": 1, "B": 2},
        "round_total": 3,
        "round": 1,
        "budgets": {"A": 10, "B": 10},
        "battlefields": [
            {"id": "f1", "value": 1.0},
            {"id": "f2", "value": 1.0},
            {"id": "f3", "value": 1.0},
        ],
        "history": [],
    }
    config = {"game": "colonelblotto"}
    result = registry.render_observation("colonelblotto", state, config, "A", "neutral")
    assert result["player_id"] == "A"
    assert result["variant"] == "neutral"
    assert "system" in result
    assert "turn" in result


def test_render_observation_with_unknown_variant_falls_back_to_neutral():
    registry = GameRegistry()
    state = {
        "total_scores": {"A": 1, "B": 2},
        "round_total": 3,
        "round": 1,
        "budgets": {"A": 10, "B": 10},
        "battlefields": [
            {"id": "f1", "value": 1.0},
            {"id": "f2", "value": 1.0},
            {"id": "f3", "value": 1.0},
        ],
        "history": [],
    }
    config = {"game": "colonelblotto"}
    result = registry.render_observation(
        "colonelblotto", state, config, "A", "unknown_variant"
    )
    assert result["variant"] == "unknown_variant"


def test_build_observation_context_includes_pot_fields():
    registry = GameRegistry()
    state = {
        "total_scores": {"A": 1, "B": 2},
        "pot_a": 10,
        "pot_b": 8,
        "round_total": 3,
    }
    config = {"game": "ultimatum"}
    ctx = registry._build_observation_context("ultimatum", state, config, "A")
    assert ctx["my_pot"] == 10
    assert ctx["opp_pot"] == 8
    assert ctx["players"] == 2
    assert ctx["score_a"] == 1
    assert ctx["score_b"] == 2
    assert ctx["rounds"] == 3


def test_build_observation_context_includes_payoff_fields():
    registry = GameRegistry()
    state = {
        "total_scores": {"A": 1, "B": 2},
        "payoffs": {"stag_stag": 5, "hare_hare": 3, "stag_hare": 1},
    }
    config = {"game": "staghunt"}
    ctx = registry._build_observation_context("staghunt", state, config, "A")
    assert ctx["payoff_stag_stag"] == 5
    assert ctx["payoff_hare_hare"] == 3
    assert ctx["payoff_stag_hare"] == 1


def test_build_observation_context_with_pending_offer():
    registry = GameRegistry()
    state = {
        "total_scores": {"A": 0, "B": 0},
        "pending_offer": 30.0,
    }
    config = {"total": 100.0}
    ctx = registry._build_observation_context("ultimatum", state, config, "A")
    assert ctx["offer"] == 30.0
    assert abs(ctx["offer_fraction"] - 0.3) < 1e-9


def test_pick_turn_template_ultimatum_proposer_phase():
    registry = GameRegistry()
    prompts = {
        "state": "generic state",
        "proposer_state": "you are the proposer",
        "responder_state": "you are the responder",
    }
    result = registry._pick_turn_template(
        "ultimatum", {"phase": "awaiting_proposal"}, prompts
    )
    assert result == "you are the proposer"


def test_pick_turn_template_ultimatum_responder_phase():
    registry = GameRegistry()
    prompts = {
        "state": "generic state",
        "proposer_state": "you are the proposer",
        "responder_state": "you are the responder",
    }
    result = registry._pick_turn_template(
        "ultimatum", {"phase": "awaiting_response"}, prompts
    )
    assert result == "you are the responder"


def test_pick_turn_template_non_ultimatum_uses_state():
    registry = GameRegistry()
    prompts = {"state": "the state", "turn": "the turn"}
    result = registry._pick_turn_template(
        "colonelblotto", {"phase": "play"}, prompts
    )
    assert result == "the state"


def test_pick_turn_template_non_ultimatum_falls_back_to_turn():
    registry = GameRegistry()
    prompts = {"turn": "the turn"}
    result = registry._pick_turn_template(
        "colonelblotto", {"phase": "play"}, prompts
    )
    assert result == "the turn"


def test_get_game_scenarios_for_game_with_scenarios_module():
    scenarios = GameRegistry().get_game_scenarios("ultimatum")
    assert isinstance(scenarios, list)
    if scenarios:
        first = scenarios[0]
        assert "id" in first
        assert "name" in first
        assert "description" in first


def test_get_game_scenarios_for_game_without_scenarios_module(tmp_path: Path):
    (tmp_path / "core").mkdir()
    game_dir = tmp_path / "core" / "no_scenarios"
    game_dir.mkdir()
    (game_dir / "game.yaml").write_text(
        'name: no-scenarios\nversion: "1.0"\nstatus: stable\n',
        encoding="utf-8",
    )
    assert GameRegistry(tmp_path).get_game_scenarios("no_scenarios") == []
