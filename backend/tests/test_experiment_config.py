import pytest

from arena.experiment_config import WandbConfig, WandbRequestFields, split_runtime_config


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


def test_split_runtime_config_strips_wandb_fields_from_game_payload():
    payload = {
        "game": "blotto",
        "rounds": 1,
        "wandb_logging": True,
        "wandb_project": "arena-runs",
        "wandb_entity": "lab",
    }

    game_payload, wandb_fields = split_runtime_config(payload)

    assert game_payload == {"game": "blotto", "rounds": 1}
    assert wandb_fields.enabled is True
    assert wandb_fields.project == "arena-runs"
    assert wandb_fields.entity == "lab"
    # The original payload must not be mutated.
    assert "wandb_logging" in payload


def test_split_runtime_config_defaults_to_disabled():
    game_payload, wandb_fields = split_runtime_config({"game": "blotto"})

    assert game_payload == {"game": "blotto"}
    assert wandb_fields.enabled is False


def test_wandb_request_fields_default_project():
    fields = WandbRequestFields.from_payload({"wandb_logging": True})
    assert fields.enabled is True
    assert fields.project == "outplayarena"
    assert fields.entity is None
    assert fields.run_name is None


def test_wandb_request_fields_to_wandb_config():
    fields = WandbRequestFields.from_payload({
        "wandb_logging": True,
        "wandb_project": "my-project",
        "wandb_entity": "my-team",
        "wandb_run_name": "run-42",
        "wandb_tags": ["a", "b"],
    })

    config = fields.to_wandb_config(api_key="sk-test")
    assert config.api_key == "sk-test"
    assert config.project == "my-project"
    assert config.entity == "my-team"
    assert config.run_name == "run-42"
    assert config.tags == ["a", "b"]
    assert config.to_safe_dict()["api_key"] == "[redacted]"


def test_split_runtime_config_rejects_invalid_wandb_tags():
    with pytest.raises(ValueError, match="tags"):
        split_runtime_config({"game": "blotto", "wandb_logging": True, "wandb_tags": [1, 2]})


def test_split_runtime_config_rejects_invalid_entity_type():
    with pytest.raises(ValueError, match="entity"):
        split_runtime_config({"game": "blotto", "wandb_logging": True, "wandb_entity": 123})


def test_wandb_config_rejects_missing_api_key():
    with pytest.raises(ValueError, match="api_key"):
        WandbConfig(api_key="", project="p")


def test_wandb_config_rejects_missing_project():
    with pytest.raises(ValueError, match="project"):
        WandbConfig(api_key="secret", project="")
