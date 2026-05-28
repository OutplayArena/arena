import pytest

from games.core.blotto.engine import BlottoGame
from games.core.blotto.config import BattlefieldConfig, BlottoExperimentConfig


def test_classic_config_has_platform_shape():
    config = BlottoExperimentConfig.classic(
        num_battlefields=3,
        total_resources=9,
        rounds=4,
        seed=42,
    )

    assert config.game == "blotto"
    assert config.variant == "classic"
    assert config.players == 2
    assert config.budget == [9, 9]
    assert config.rounds == 4
    assert config.seed == 42
    assert [field.id for field in config.battlefields] == [
        "battlefield_1",
        "battlefield_2",
        "battlefield_3",
    ]


def test_config_serializes_to_stable_dict():
    config = BlottoExperimentConfig.classic(
        num_battlefields=2,
        total_resources=10,
        rounds=3,
    )

    assert config.to_dict() == {
        "game": "blotto",
        "variant": "classic",
        "players": 2,
        "budget": [10, 10],
        "battlefields": [
            {"id": "battlefield_1", "value": 1.0},
            {"id": "battlefield_2", "value": 1.0},
        ],
        "rounds": 3,
        "seed": None,
    }


def test_config_hash_is_stable_for_equivalent_configs():
    config_a = BlottoExperimentConfig.classic(seed=7)
    config_b = BlottoExperimentConfig.classic(seed=7)

    assert config_a.config_hash() == config_b.config_hash()
    assert config_a.config_hash().startswith("sha256:")


def test_config_hash_changes_when_reproducible_inputs_change():
    config_a = BlottoExperimentConfig.classic(rounds=10, seed=7)
    config_b = BlottoExperimentConfig.classic(rounds=11, seed=7)
    config_c = BlottoExperimentConfig.classic(rounds=10, seed=8)

    assert config_a.config_hash() != config_b.config_hash()
    assert config_a.config_hash() != config_c.config_hash()


def test_config_hash_preserves_battlefield_order():
    config_a = BlottoExperimentConfig(
        game="blotto",
        variant="classic",
        players=2,
        budget=[10, 10],
        battlefields=[
            BattlefieldConfig(id="A", value=1.0),
            BattlefieldConfig(id="B", value=1.0),
        ],
        rounds=3,
    )
    config_b = BlottoExperimentConfig(
        game="blotto",
        variant="classic",
        players=2,
        budget=[10, 10],
        battlefields=[
            BattlefieldConfig(id="B", value=1.0),
            BattlefieldConfig(id="A", value=1.0),
        ],
        rounds=3,
    )

    assert config_a.config_hash() != config_b.config_hash()


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"game": "lotto"}, "game"),
        ({"variant": "general_lotto"}, "variant"),
        ({"players": 3}, "2 players"),
        ({"rounds": 0}, "rounds"),
        ({"budget": [10]}, "budget length"),
        ({"budget": [10, 9]}, "equal player budgets"),
        ({"budget": [10, True]}, "budgets must be integers"),
        ({"budget": [10, 0]}, "budgets must be positive"),
        ({"seed": True}, "seed"),
    ],
)
def test_config_validation_rejects_invalid_experiment_fields(kwargs, message):
    params = {
        "game": "blotto",
        "variant": "classic",
        "players": 2,
        "budget": [10, 10],
        "battlefields": [BattlefieldConfig(id="A", value=1.0)],
        "rounds": 3,
        "seed": None,
    }
    params.update(kwargs)

    with pytest.raises(ValueError, match=message):
        BlottoExperimentConfig(**params)


@pytest.mark.parametrize(
    ("field", "message"),
    [
        (lambda: BattlefieldConfig(id=""), "id"),
        (lambda: BattlefieldConfig(id="A", value=0), "positive"),
        (lambda: BattlefieldConfig(id="A", value=True), "number"),
    ],
)
def test_battlefield_validation_rejects_invalid_fields(field, message):
    with pytest.raises(ValueError, match=message):
        field()


def test_config_validation_rejects_duplicate_battlefield_ids():
    with pytest.raises(ValueError, match="unique"):
        BlottoExperimentConfig(
            game="blotto",
            variant="classic",
            players=2,
            budget=[10, 10],
            battlefields=[
                BattlefieldConfig(id="A", value=1.0),
                BattlefieldConfig(id="A", value=2.0),
            ],
            rounds=3,
        )


def test_blotto_game_from_config_uses_battlefields_and_budget():
    config = BlottoExperimentConfig.classic(
        num_battlefields=4,
        total_resources=12,
    )

    game = BlottoGame.from_config(config)

    assert game.num_battlefields == 4
    assert game.total_resources == 12
