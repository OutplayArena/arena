import base64
import binascii
import os
from typing import Any

import wandb
from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from arena.integrations.base_logger import BaseLogger


ENCRYPTION_KEY_ENV = "OUTPLAYARENA_WANDB_ENCRYPTION_KEY"


class WandbConfigError(ValueError):
    pass

def encryption_key_from_env() -> bytes:
    value = os.environ.get(ENCRYPTION_KEY_ENV)
    if not value:
        raise WandbConfigError(f"{ENCRYPTION_KEY_ENV} is required")

    try:
        key = bytes.fromhex(value)
    except ValueError as exc:
        raise WandbConfigError(f"{ENCRYPTION_KEY_ENV} must be hex") from exc

    if len(key) != 32:
        raise WandbConfigError(f"{ENCRYPTION_KEY_ENV} must be 32 bytes")

    return key


def encrypt_api_key(plaintext: str, key: bytes | None = None) -> str:
    if not isinstance(plaintext, str) or not plaintext.strip():
        raise WandbConfigError("wandb api key is required")

    aesgcm = AESGCM(key or encryption_key_from_env())
    nonce = os.urandom(12)
    ciphertext = aesgcm.encrypt(nonce, plaintext.encode("utf-8"), None)

    return base64.urlsafe_b64encode(nonce + ciphertext).decode("ascii")


def decrypt_api_key(encrypted: str, key: bytes | None = None) -> str:
    try:
        raw = base64.urlsafe_b64decode(encrypted.encode("ascii"))
    except (AttributeError, UnicodeEncodeError, binascii.Error) as exc:
        raise WandbConfigError("encrypted wandb api key is invalid") from exc

    if len(raw) <= 12:
        raise WandbConfigError("encrypted wandb api key is invalid")

    nonce = raw[:12]
    ciphertext = raw[12:]
    aesgcm = AESGCM(key or encryption_key_from_env())

    try:
        return aesgcm.decrypt(nonce, ciphertext, None).decode("utf-8")
    except (InvalidTag, UnicodeDecodeError) as exc:
        raise WandbConfigError("could not decrypt wandb api key") from exc


class WandbGameLogger(BaseLogger):
    def __init__(
        self,
        wandb_config,
        game_config,
        encrypted_api_key: str,
        agents: dict[str, str] | None = None,
    ):
        self.wandb_config = wandb_config
        self.game_config = game_config
        self.encrypted_api_key = encrypted_api_key
        self.agents = agents
        self._run = None

    # Start a W&B run using the decrypted session-scoped API key.
    def start(self):
        api_key = decrypt_api_key(self.encrypted_api_key)
        try:
            self._run = wandb.init(
                project=self.wandb_config.project,
                entity=self.wandb_config.entity,
                name=self.wandb_config.run_name,
                tags=list(self.wandb_config.tags or []),
                config=self._full_config_dict(),
                settings=wandb.Settings(_api_key=api_key),
            )
        finally:
            api_key = None
            del api_key

        return self

    def log_round(self, payload: dict[str, Any], step: int) -> None:
        if self._run is None:
            return
        self._run.log(payload, step=step)

    def log_terminal(self, payload: dict[str, Any]) -> None:
        if self._run is None:
            return
        self._run.log(payload)

    def finish(self) -> None:
        if self._run is None:
            return
        self._run.finish()
        self._run = None

    def _game_config_dict(self):
        if hasattr(self.game_config, "to_dict"):
            return self.game_config.to_dict()
        return self.game_config

    def _full_config_dict(self) -> dict[str, Any]:
        cfg = self._game_config_dict()
        if not isinstance(cfg, dict):
            cfg = {"config": cfg}
        return {**cfg, "agents": self.agents or {}}
