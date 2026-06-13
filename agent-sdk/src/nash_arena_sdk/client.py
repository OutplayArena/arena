from __future__ import annotations

import hashlib
import hmac
import base64
from typing import Any

import httpx


SESSION_KEY_PREFIX = "nks_"

# DUPLICATE: Also defined in backend/nash_arena/auth/session_key.py
# Keep implementations in sync. The SDK version accepts secret as a parameter
# since it cannot import the backend's module-level JWT_SECRET constant.


# DUPLICATE: Also defined in backend/nash_arena/auth/session_key.py
# Keep implementations in sync. The SDK version accepts secret as a parameter
# since it cannot import the backend's module-level JWT_SECRET constant.
def validate_session_key(key: str, secret: str) -> tuple[str, str]:
    if not key or not key.startswith(SESSION_KEY_PREFIX):
        raise ValueError("invalid session key")

    encoded = key[len(SESSION_KEY_PREFIX):]
    padding = 4 - (len(encoded) % 4)
    if padding != 4:
        encoded += "=" * padding
    try:
        token = base64.urlsafe_b64decode(encoded).decode("utf-8")
    except (ValueError, UnicodeDecodeError):
        raise ValueError("invalid session key")

    parts = token.split(":")
    if len(parts) != 3:
        raise ValueError("invalid session key")
    session_id, player, sig = parts

    payload = f"{session_id}:{player}"
    secret_hash = hashlib.sha256(secret.encode("utf-8")).digest()
    expected = hmac.new(secret_hash, payload.encode("utf-8"), hashlib.sha256).hexdigest()

    import secrets as _secrets
    if not _secrets.compare_digest(sig, expected):
        raise ValueError("invalid session key")

    return session_id, player


# DUPLICATE: Also defined in backend/nash_arena/client.py
# Keep implementations in sync. The SDK version adds type annotations.
class ArenaClient:
    def __init__(
        self,
        base_url: str,
        session_id: str | None = None,
        token: str | None = None,
        timeout: float = 10.0,
        http_client: httpx.Client | None = None,
    ):
        self.base_url = base_url.rstrip("/")
        self.session_id = session_id
        self.token = token
        self.timeout = timeout
        self.http_client = http_client or httpx.Client(timeout=timeout)

    def create_experiment(
        self,
        config: Any,
        agents: dict[str, str] | None = None,
        api_key: str | None = None,
    ) -> dict:
        payload = self._config_payload(config)
        if agents:
            payload["agents"] = agents
        headers = {}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        response = self.http_client.post(
            f"{self.base_url}/experiment",
            json=payload,
            headers=headers,
            timeout=self.timeout,
        )
        return self._json_or_raise(response)

    def get_state(self) -> dict:
        session_id = self._require_session_id()
        response = self.http_client.get(
            f"{self.base_url}/session/{session_id}/state",
            timeout=self.timeout,
        )
        return self._json_or_raise(response)

    def submit_action(self, allocation: Any) -> dict:
        session_id = self._require_session_id()
        token = self._require_token()
        response = self.http_client.post(
            f"{self.base_url}/session/{session_id}/action",
            headers={"Authorization": f"Bearer {token}"},
            json={"allocation": allocation},
            timeout=self.timeout,
        )
        return self._json_or_raise(response)

    def get_results(self) -> dict:
        session_id = self._require_session_id()
        response = self.http_client.get(
            f"{self.base_url}/session/{session_id}/results",
            timeout=self.timeout,
        )
        return self._json_or_raise(response)

    def list_games(self) -> list[dict]:
        response = self.http_client.get(
            f"{self.base_url}/games",
            timeout=self.timeout,
        )
        return self._json_or_raise(response)

    def get_game_details(self, game: str) -> dict:
        response = self.http_client.get(
            f"{self.base_url}/games/{game}",
            timeout=self.timeout,
        )
        return self._json_or_raise(response)

    def get_game_metrics(self, game: str) -> dict:
        response = self.http_client.get(
            f"{self.base_url}/games/{game}/metrics",
            timeout=self.timeout,
        )
        return self._json_or_raise(response)

    def get_game_prompts(self, game: str) -> dict:
        response = self.http_client.get(
            f"{self.base_url}/games/{game}/prompts",
            timeout=self.timeout,
        )
        return self._json_or_raise(response)

    def get_observation(self, player: str, variant: str = "neutral") -> dict:
        session_id = self._require_session_id()
        response = self.http_client.get(
            f"{self.base_url}/session/{session_id}/observation",
            params={"player": player, "variant": variant},
            timeout=self.timeout,
        )
        return self._json_or_raise(response)

    @classmethod
    def for_player(
        cls,
        base_url: str,
        creation_response: dict,
        player: str,
        timeout: float = 10.0,
        http_client: httpx.Client | None = None,
    ) -> ArenaClient:
        return cls(
            base_url=base_url,
            session_id=creation_response["session_id"],
            token=creation_response["player_tokens"][player],
            timeout=timeout,
            http_client=http_client,
        )

    def is_terminal(self) -> bool:
        return self.get_state()["phase"] == "complete"

    def _require_session_id(self) -> str:
        if not self.session_id:
            raise ValueError("session_id is required")
        return self.session_id

    def _require_token(self) -> str:
        if not self.token:
            raise ValueError("token is required")
        return self.token

    def _config_payload(self, config: Any) -> dict:
        if hasattr(config, "to_dict"):
            return config.to_dict()
        return config

    def _json_or_raise(self, response: httpx.Response) -> Any:
        response.raise_for_status()
        return response.json()
