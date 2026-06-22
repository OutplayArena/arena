import pytest

from arena.game_components.game_agent import GameAgent
from arena.game_components.game_config import GameConfig
from arena.game_engine import GameEngine
from arena.game_components.game_metrics import GameMetrics
from games.core.colonelblotto.agent import Agent, UniformAgent
from games.core.colonelblotto.config import ColonelBlottoExperimentConfig
from games.core.colonelblotto.engine import ColonelBlottoGame
from games.core.colonelblotto.metrics import ColonelBlottoMetrics


def test_base_contracts_are_abstract():
    with pytest.raises(TypeError):
        GameEngine()
    with pytest.raises(TypeError):
        GameAgent()
    with pytest.raises(TypeError):
        GameConfig()
    with pytest.raises(TypeError):
        GameMetrics()


def test_blotto_game_implements_engine_contract():
    assert isinstance(ColonelBlottoGame(num_battlefields=3, total_resources=10), GameEngine)


def test_blotto_support_classes_implement_base_contracts():
    assert isinstance(ColonelBlottoExperimentConfig.classic(), GameConfig)
    assert isinstance(Agent("base-agent"), GameAgent)
    assert isinstance(UniformAgent(), GameAgent)
    assert isinstance(ColonelBlottoMetrics(), GameMetrics)


def test_engine_contract_rejects_invalid_and_duplicate_actions():
    game = ColonelBlottoGame(num_battlefields=3, total_resources=10, num_rounds=2)
    state = game.initial_state()

    assert game.validate_player_action(state, "A", [10, 0, 0]) is True

    with pytest.raises(ValueError, match="invalid action"):
        game.validate_player_action(state, "A", [9, 0, 0])

    state = game.apply_action(state, "A", [10, 0, 0])
    with pytest.raises(ValueError, match="already submitted"):
        game.apply_action(state, "A", [10, 0, 0])


def test_engine_contract_full_game_reaches_terminal_results():
    game = ColonelBlottoGame(num_battlefields=3, total_resources=10, num_rounds=1)
    state = game.initial_state()

    assert state.phase == "awaiting_action"
    assert game.is_terminal(state) is False

    state = game.apply_action(state, "A", [10, 0, 0])
    state = game.apply_action(state, "B", [0, 5, 5])

    assert game.is_terminal(state) is True
    results = game.compute_results(state, session_id="s1", config_hash="sha256:test")
    assert results["winner"] == "B"
    assert results["session_id"] == "s1"
    assert results["config_hash"] == "sha256:test"
    assert results["history"]
    assert "metrics" in results
