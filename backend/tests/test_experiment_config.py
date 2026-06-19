import pytest

from outplaylabs_arena.experiment_config import WandbConfig, split_runtime_config


def test_wandb_config_serializes_without_plaintext_api_key():
    config = WandbConfig(
        api_key="wandb-secret",
        entity="lab",
        project="arena-runs",
        run_name="run-1",
        tags=["blotto", "test"],
    )

    assert config.to_safe_dict() == {
        "api_key": "[redacted]",
        "entity": "lab",
        "project": "arena-runs",
        "run_name": "run-1",
        "tags": ["blotto", "test"],
    }


def test_split_runtime_config_removes_wandb_from_game_payload():
    payload = {
        "game": "blotto",
        "rounds": 1,
        "wandb": {
            "api_key": "wandb-secret",
            "project": "arena-runs",
            "tags": ["blotto"],
        },
    }

    game_payload, runtime_config = split_runtime_config(payload)

    assert game_payload == {"game": "blotto", "rounds": 1}
    assert runtime_config.wandb is not None
    assert runtime_config.wandb.api_key == "wandb-secret"
    assert runtime_config.to_safe_dict()["wandb"]["api_key"] == "[redacted]"
    assert "wandb" in payload


def test_split_runtime_config_defaults_to_no_wandb():
    game_payload, runtime_config = split_runtime_config({"game": "blotto"})

    assert game_payload == {"game": "blotto"}
    assert runtime_config.wandb is None
    assert runtime_config.to_safe_dict() == {"wandb": None}


@pytest.mark.parametrize(
    ("wandb", "message"),
    [
        ("bad", "object"),
        ({"api_key": "secret"}, "project"),
        ({"project": "arena-runs"}, "api_key"),
        ({"api_key": "", "project": "arena-runs"}, "api_key"),
        ({"api_key": "secret", "project": ""}, "project"),
        ({"api_key": "secret", "project": "arena-runs", "bad": True}, "unknown"),
        ({"api_key": "secret", "project": "arena-runs", "tags": [1]}, "tags"),
    ],
)
def test_split_runtime_config_rejects_invalid_wandb_config(wandb, message):
    with pytest.raises(ValueError, match=message):
        split_runtime_config({"game": "blotto", "wandb": wandb})
