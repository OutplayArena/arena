import secrets

import pytest

from games.core.colonelblotto.config import ColonelBlottoExperimentConfig
from nash_arena.experiment_config import WandbConfig
from nash_arena.integrations import wandb_logger
from nash_arena.integrations.wandb_logger import (
    ENCRYPTION_KEY_ENV,
    WandbGameLogger,
    WandbConfigError,
    decrypt_api_key,
    encrypt_api_key,
    encryption_key_from_env,
)


def test_encrypt_decrypt_api_key_round_trip():
    key = secrets.token_bytes(32)

    encrypted = encrypt_api_key("wandb-secret", key=key)

    assert decrypt_api_key(encrypted, key=key) == "wandb-secret"


def test_encrypted_api_key_does_not_contain_plaintext():
    key = secrets.token_bytes(32)

    encrypted = encrypt_api_key("wandb-secret", key=key)

    assert "wandb-secret" not in encrypted
    assert encrypted != "wandb-secret"


def test_encryption_key_from_env_loads_32_byte_hex_key(monkeypatch):
    raw_key = secrets.token_bytes(32)
    monkeypatch.setenv(ENCRYPTION_KEY_ENV, raw_key.hex())

    assert encryption_key_from_env() == raw_key


def test_encryption_key_from_env_rejects_missing_key(monkeypatch):
    monkeypatch.delenv(ENCRYPTION_KEY_ENV, raising=False)

    with pytest.raises(WandbConfigError, match="required"):
        encryption_key_from_env()


def test_encryption_key_from_env_rejects_non_hex_key(monkeypatch):
    monkeypatch.setenv(ENCRYPTION_KEY_ENV, "not-hex")

    with pytest.raises(WandbConfigError, match="hex"):
        encryption_key_from_env()


def test_encryption_key_from_env_rejects_wrong_length_key(monkeypatch):
    monkeypatch.setenv(ENCRYPTION_KEY_ENV, secrets.token_bytes(16).hex())

    with pytest.raises(WandbConfigError, match="32 bytes"):
        encryption_key_from_env()


def test_decrypt_api_key_rejects_wrong_key():
    encrypted = encrypt_api_key("wandb-secret", key=secrets.token_bytes(32))

    with pytest.raises(WandbConfigError, match="could not decrypt"):
        decrypt_api_key(encrypted, key=secrets.token_bytes(32))


def test_encrypt_api_key_rejects_empty_plaintext_key():
    with pytest.raises(WandbConfigError, match="required"):
        encrypt_api_key("", key=secrets.token_bytes(32))


def test_decrypt_api_key_rejects_invalid_ciphertext():
    with pytest.raises(WandbConfigError, match="invalid"):
        decrypt_api_key("bad", key=secrets.token_bytes(32))


class FakeRun:
    def __init__(self):
        self.logged = []
        self.finished = False

    def log(self, payload, step=None):
        self.logged.append({"payload": payload, "step": step})

    def finish(self):
        self.finished = True


class FakeSettings:
    def __init__(self, **kwargs):
        self.kwargs = kwargs


def make_logger(monkeypatch):
    raw_key = secrets.token_bytes(32)
    monkeypatch.setenv(ENCRYPTION_KEY_ENV, raw_key.hex())
    encrypted = encrypt_api_key("wandb-secret", key=raw_key)
    config = WandbConfig(
        api_key="wandb-secret",
        project="arena-runs",
        entity="lab",
        run_name="run-1",
        tags=["blotto"],
    )
    game_config = ColonelBlottoExperimentConfig.classic(
        num_battlefields=2,
        total_resources=10,
        rounds=3,
        seed=42,
    )
    return WandbGameLogger(config, game_config, encrypted)


def test_wandb_game_logger_start_initializes_run(monkeypatch):
    calls = []
    fake_run = FakeRun()

    def fake_init(**kwargs):
        calls.append(kwargs)
        return fake_run

    monkeypatch.setattr(wandb_logger.wandb, "init", fake_init)
    monkeypatch.setattr(wandb_logger.wandb, "Settings", FakeSettings)
    logger = make_logger(monkeypatch)

    assert logger.start() is logger

    assert calls[0]["project"] == "arena-runs"
    assert calls[0]["entity"] == "lab"
    assert calls[0]["name"] == "run-1"
    assert calls[0]["tags"] == ["blotto"]
    assert calls[0]["config"]["game"] == "colonelblotto"
    assert calls[0]["settings"].kwargs == {"_api_key": "wandb-secret"}


def test_wandb_game_logger_log_round_noops_before_start(monkeypatch):
    logger = make_logger(monkeypatch)

    logger.log_round({"scores/A": 1}, step=1)

    assert logger._run is None


def test_wandb_game_logger_log_round_sends_payload_after_start(monkeypatch):
    fake_run = FakeRun()
    monkeypatch.setattr(wandb_logger.wandb, "init", lambda **kwargs: fake_run)
    monkeypatch.setattr(wandb_logger.wandb, "Settings", FakeSettings)
    logger = make_logger(monkeypatch).start()

    logger.log_round({"scores/A": 1}, step=1)

    assert fake_run.logged == [{"payload": {"scores/A": 1}, "step": 1}]


def test_wandb_game_logger_log_terminal_sends_payload_after_start(monkeypatch):
    fake_run = FakeRun()
    monkeypatch.setattr(wandb_logger.wandb, "init", lambda **kwargs: fake_run)
    monkeypatch.setattr(wandb_logger.wandb, "Settings", FakeSettings)
    logger = make_logger(monkeypatch).start()

    logger.log_terminal({"final/winner": "A"})

    assert fake_run.logged == [{"payload": {"final/winner": "A"}, "step": None}]


def test_wandb_game_logger_finish_noops_before_start(monkeypatch):
    logger = make_logger(monkeypatch)

    logger.finish()

    assert logger._run is None


def test_wandb_game_logger_finish_closes_run(monkeypatch):
    fake_run = FakeRun()
    monkeypatch.setattr(wandb_logger.wandb, "init", lambda **kwargs: fake_run)
    monkeypatch.setattr(wandb_logger.wandb, "Settings", FakeSettings)
    logger = make_logger(monkeypatch).start()

    logger.finish()

    assert fake_run.finished is True
    assert logger._run is None
