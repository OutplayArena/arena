from games.core.colonelblotto.config import ColonelBlottoExperimentConfig
from games.core.colonelblotto.engine import ColonelBlottoGame


def test_blotto_game_from_config_reaches_complete_state():
    config = ColonelBlottoExperimentConfig.classic(
        num_battlefields=3,
        total_resources=10,
        rounds=1,
        seed=42,
    )
    game = ColonelBlottoGame.from_config(config)
    state = game.initial_state()

    state = game.apply_action(state, "A", [10, 0, 0])
    state = game.apply_action(state, "B", [0, 5, 5])

    assert state.phase == "complete"
    assert game.compute_results(state)["winner"] == "B"
