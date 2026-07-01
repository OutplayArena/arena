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
    """Platform-level runtime options extracted from the experiment request.

    wandb: fully-resolved WandbConfig (api_key populated server-side from the
    user's stored encrypted credential, never passed in the request).
    """

    wandb: WandbConfig | None = None

    # Return runtime metadata safe enough for logs, responses, and tests.
    def to_safe_dict(self):
        return {
            "wandb": self.wandb.to_safe_dict() if self.wandb else None,
        }


# Flat W&B fields accepted on the experiment-creation request.
# api_key is intentionally absent — it is always resolved server-side from
# the user's stored encrypted credential (WandbCredential table).
_WANDB_REQUEST_FIELDS = frozenset(
    {"wandb_logging", "wandb_project", "wandb_entity", "wandb_run_name", "wandb_tags"}
)


def split_runtime_config(
    payload: dict[str, Any],
) -> tuple[dict[str, Any], "WandbRequestFields"]:
    """Strip W&B logging fields out of the raw request payload.

    Returns (game_payload, wandb_fields) where game_payload is safe to pass
    to GAME_REGISTRY.config_from_request and wandb_fields carries the caller's
    W&B preferences (no api_key — resolved later from the credential store).
    """
    game_payload = {k: v for k, v in payload.items() if k not in _WANDB_REQUEST_FIELDS}
    return game_payload, WandbRequestFields.from_payload(payload)


@dataclass(frozen=True)
class WandbRequestFields:
    """Parsed W&B preferences from the raw request — api_key is never here."""

    enabled: bool = False
    project: str = "outplayarena"
    entity: str | None = None
    run_name: str | None = None
    tags: list[str] | None = None

    @classmethod
    def from_payload(cls, payload: dict[str, Any]) -> "WandbRequestFields":
        enabled = bool(payload.get("wandb_logging", False))
        if not enabled:
            return cls()

        project = payload.get("wandb_project") or "outplayarena"
        entity = payload.get("wandb_entity") or None
        run_name = payload.get("wandb_run_name") or None
        raw_tags = payload.get("wandb_tags")
        tags = list(raw_tags) if isinstance(raw_tags, (list, tuple)) else None

        if not isinstance(project, str):
            raise ValueError("wandb_project must be a string")
        if entity is not None and not isinstance(entity, str):
            raise ValueError("wandb_entity must be a string")
        if run_name is not None and not isinstance(run_name, str):
            raise ValueError("wandb_run_name must be a string")
        if tags is not None and not all(isinstance(t, str) for t in tags):
            raise ValueError("wandb_tags must be a list of strings")

        return cls(enabled=True, project=project, entity=entity, run_name=run_name, tags=tags)

    def to_wandb_config(self, api_key: str) -> WandbConfig:
        """Build a WandbConfig from the stored (decrypted) api_key + these fields."""
        return WandbConfig(
            api_key=api_key,
            project=self.project,
            entity=self.entity,
            run_name=self.run_name,
            tags=self.tags,
        )
