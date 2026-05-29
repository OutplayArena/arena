import httpx


class ArenaClient:
    def __init__(
        self,
        base_url,
        session_id=None,
        token=None,
        timeout=10.0,
        http_client=None,
        game_api_prefix: str = "/api/game",
        internal_api_token: str | None = None,
    ):
        self.base_url = base_url.rstrip("/")
        self.session_id = session_id
        self.token = token
        self.timeout = timeout
        self.http_client = http_client or httpx.Client(timeout=timeout)
        self.game_api_prefix = game_api_prefix.rstrip("/")
        self.internal_api_token = internal_api_token

    def create_experiment(self, config):
        response = self.http_client.post(
            f"{self.base_url}{self._game_path('/experiment')}",
            headers=self._internal_headers(),
            json=self._config_payload(config),
            timeout=self.timeout,
        )
        return self._json_or_raise(response)

    def get_state(self):
        session_id = self._require_session_id()
        response = self.http_client.get(
            f"{self.base_url}{self._game_path(f'/session/{session_id}/state')}",
            headers=self._internal_headers(),
            timeout=self.timeout,
        )
        return self._json_or_raise(response)

    def submit_action(self, allocation):
        session_id = self._require_session_id()
        token = self._require_token()
        response = self.http_client.post(
            f"{self.base_url}{self._game_path(f'/session/{session_id}/action')}",
            headers={
                **self._internal_headers(),
                "Authorization": f"Bearer {token}",
            },
            json={"allocation": allocation},
            timeout=self.timeout,
        )
        return self._json_or_raise(response)

    def get_results(self):
        session_id = self._require_session_id()
        response = self.http_client.get(
            f"{self.base_url}{self._game_path(f'/session/{session_id}/results')}",
            headers=self._internal_headers(),
            timeout=self.timeout,
        )
        return self._json_or_raise(response)

    def list_games(self):
        response = self.http_client.get(
            f"{self.base_url}/games",
            timeout=self.timeout,
        )
        return self._json_or_raise(response)

    def get_game_details(self, game):
        response = self.http_client.get(
            f"{self.base_url}/games/{game}",
            timeout=self.timeout,
        )
        return self._json_or_raise(response)

    def get_game_metrics(self, game):
        response = self.http_client.get(
            f"{self.base_url}/games/{game}/metrics",
            timeout=self.timeout,
        )
        return self._json_or_raise(response)

    def get_game_prompts(self, game):
        response = self.http_client.get(
            f"{self.base_url}/games/{game}/prompts",
            timeout=self.timeout,
        )
        return self._json_or_raise(response)

    def get_game_skill(self, game):
        response = self.http_client.get(
            f"{self.base_url}/games/{game}/skill",
            timeout=self.timeout,
        )
        return self._json_or_raise(response)

    @classmethod
    def for_player(
        cls,
        base_url,
        creation_response,
        player,
        timeout=10.0,
        http_client=None,
        game_api_prefix: str = "/api/game",
        internal_api_token: str | None = None,
    ):
        return cls(
            base_url=base_url,
            session_id=creation_response["session_id"],
            token=creation_response["player_tokens"][player],
            timeout=timeout,
            http_client=http_client,
            game_api_prefix=game_api_prefix,
            internal_api_token=internal_api_token,
        )

    def is_terminal(self):
        return self.get_state()["phase"] == "complete"

    def _require_session_id(self):
        if not self.session_id:
            raise ValueError("session_id is required")
        return self.session_id

    def _require_token(self):
        if not self.token:
            raise ValueError("token is required")
        return self.token

    def _config_payload(self, config):
        if hasattr(config, "to_dict"):
            return config.to_dict()
        return config

    def _json_or_raise(self, response):
        response.raise_for_status()
        return response.json()

    def _game_path(self, path: str) -> str:
        return f"{self.game_api_prefix}{path}"

    def _internal_headers(self) -> dict[str, str]:
        if not self.internal_api_token:
            return {}
        return {"X-Nash-Arena-Internal-Token": self.internal_api_token}
