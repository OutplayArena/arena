from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class WandbConfig:
    api_key: str
    project: str
    entity: str | None = None
    run_name: str | None = None
    tags: list[str] | None = None

    def __post_init__(self):
        if not isinstance(self.api_key, str) or not self.api_key.strip():
            raise ValueError("wandb api_key must be a non-empty string")
        if not isinstance(self.project, str) or not self.project.strip():
            raise ValueError("wandb project must be a non-empty string")
        if self.entity is not None and not isinstance(self.entity, str):
            raise ValueError("wandb entity must be a string or None")
        if self.run_name is not None and not isinstance(self.run_name, str):
            raise ValueError("wandb run_name must be a string or None")
        if self.tags is not None and not all(isinstance(tag, str) for tag in self.tags):
            raise ValueError("wandb tags must be strings")

    # Return W&B metadata without exposing the plaintext API key.
    def to_safe_dict(self):
        return {
            "project": self.project,
            "entity": self.entity,
            "run_name": self.run_name,
            "tags": list(self.tags or []),
            "api_key": "[redacted]",
        }


@dataclass(frozen=True)
class ExperimentRuntimeConfig:
    wandb: WandbConfig | None = None

    # Return runtime metadata safe enough for logs, responses, and tests.
    def to_safe_dict(self):
        return {
            "wandb": self.wandb.to_safe_dict() if self.wandb else None,
        }


# Split platform runtime config from game-specific experiment config.
def split_runtime_config(payload: dict[str, Any]) -> tuple[dict[str, Any], ExperimentRuntimeConfig]:
    game_payload = dict(payload)
    wandb_data = game_payload.pop("wandb", None)
    wandb = _wandb_from_dict(wandb_data) if wandb_data is not None else None
    return game_payload, ExperimentRuntimeConfig(wandb=wandb)


def _wandb_from_dict(data: Any) -> WandbConfig:
    if not isinstance(data, dict):
        raise ValueError("wandb config must be an object")

    allowed_keys = {"api_key", "project", "entity", "run_name", "tags"}
    extra_keys = set(data) - allowed_keys
    if extra_keys:
        extra = ", ".join(sorted(extra_keys))
        raise ValueError(f"unknown wandb config fields: {extra}")

    try:
        return WandbConfig(
            api_key=data["api_key"],
            project=data["project"],
            entity=data.get("entity"),
            run_name=data.get("run_name"),
            tags=list(data.get("tags") or []),
        )
    except KeyError as exc:
        raise ValueError(f"wandb config missing required field: {exc.args[0]}") from exc
