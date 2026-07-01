import secrets

import pytest

from games.core.colonelblotto.config import ColonelBlottoExperimentConfig
from arena.experiment_config import WandbConfig
from arena.integrations import wandb_logger
from arena.integrations.wandb_logger import (
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
    assert calls[0]["settings"].kwargs == {"api_key": "wandb-secret"}


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


def test_wandb_game_logger_log_terminal_noops_before_start(monkeypatch):
    logger = make_logger(monkeypatch)

    logger.log_terminal({"final/winner": "A"})  # _run is None → should not raise

    assert logger._run is None


def test_wandb_game_logger_run_meta_returns_none_before_start(monkeypatch):
    logger = make_logger(monkeypatch)

    assert logger.run_meta is None


def test_wandb_game_logger_full_config_dict_wraps_non_dict_config(monkeypatch):
    """When game_config is not a dict (and has no to_dict), it is wrapped."""
    raw_key = secrets.token_bytes(32)
    monkeypatch.setenv(ENCRYPTION_KEY_ENV, raw_key.hex())
    encrypted = encrypt_api_key("wandb-secret", key=raw_key)
    config = WandbConfig(api_key="wandb-secret", project="p")
    logger = WandbGameLogger(config, game_config="raw-string", encrypted_api_key=encrypted)

    full = logger._full_config_dict()

    assert full["config"] == "raw-string"
    assert "agents" in full


class FakeRunForComplete:
    """Fake wandb.Run that records log calls and supports finish()."""

    def __init__(self, run_id="run-complete"):
        self.id = run_id
        self.name = "complete-run"
        self.entity = "lab"
        self.project = "arena-runs"
        self.url = "https://wandb.ai/lab/arena-runs/runs/run-complete"
        self.logged = []
        self.finished = False

    def log(self, payload, step=None):
        self.logged.append({"payload": payload, "step": step})

    def finish(self):
        self.finished = True


def test_log_complete_session_logs_all_rounds_and_terminal(monkeypatch):
    fake_run = FakeRunForComplete()
    monkeypatch.setattr(wandb_logger.wandb, "init", lambda **kwargs: fake_run)
    monkeypatch.setattr(wandb_logger.wandb, "Settings", FakeSettings)
    logger = make_logger(monkeypatch)

    round_payloads = [
        ({"round": 1, "scores/A": 1, "scores/B": 2}, 1),
        ({"round": 2, "scores/A": 3, "scores/B": 0}, 2),
    ]
    terminal_payload = {"final/winner": "A", "final/total_scores/A": 4}

    logger.log_complete_session(round_payloads, terminal_payload)

    assert len(fake_run.logged) == 3
    assert fake_run.logged[0] == {"payload": {"round": 1, "scores/A": 1, "scores/B": 2}, "step": 1}
    assert fake_run.logged[1] == {"payload": {"round": 2, "scores/A": 3, "scores/B": 0}, "step": 2}
    assert fake_run.logged[2] == {"payload": {"final/winner": "A", "final/total_scores/A": 4}, "step": None}
    assert fake_run.finished is True


def test_log_complete_session_returns_run_meta(monkeypatch):
    fake_run = FakeRunForComplete()
    monkeypatch.setattr(wandb_logger.wandb, "init", lambda **kwargs: fake_run)
    monkeypatch.setattr(wandb_logger.wandb, "Settings", FakeSettings)
    logger = make_logger(monkeypatch)

    result = logger.log_complete_session([], {"final/winner": "A"})

    assert result is not None
    assert result["run_id"] == fake_run.id
    assert result["run_name"] == fake_run.name
    assert result["entity"] == fake_run.entity
    assert result["project"] == fake_run.project
    assert result["url"] == fake_run.url


def test_log_complete_session_always_finishes_run(monkeypatch):
    """Even if logging a payload raises, finish() must still be called."""
    fake_run = FakeRunForComplete()

    def exploding_log(payload, step=None):
        raise RuntimeError("simulated log failure")

    fake_run.log = exploding_log
    monkeypatch.setattr(wandb_logger.wandb, "init", lambda **kwargs: fake_run)
    monkeypatch.setattr(wandb_logger.wandb, "Settings", FakeSettings)
    logger = make_logger(monkeypatch)

    with pytest.raises(RuntimeError, match="simulated log failure"):
        logger.log_complete_session([({}, 1)], {})

    assert fake_run.finished is True


def test_log_complete_session_decrypts_key_before_init(monkeypatch):
    """wandb.init must receive the plaintext api_key inside Settings."""
    init_calls = []
    fake_run = FakeRunForComplete()

    def capturing_init(**kwargs):
        init_calls.append(kwargs)
        return fake_run

    monkeypatch.setattr(wandb_logger.wandb, "init", capturing_init)
    monkeypatch.setattr(wandb_logger.wandb, "Settings", FakeSettings)
    logger = make_logger(monkeypatch)

    logger.log_complete_session([], {"final/winner": "A"})

    assert init_calls[0]["settings"].kwargs == {"api_key": "wandb-secret"}
