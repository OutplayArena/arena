from __future__ import annotations

from typing import Any

import httpx


class ArenaClient:
    """HTTP client for the OutplayArena REST API.
    
    ArenaClient provides a thin wrapper around the OutplayArena HTTP API, handling
    session management, authentication, and providing typed methods for all API
    endpoints. It is the foundation for building agents that interact with the
    platform via REST.
    
    Attributes:
        base_url: The base URL of the OutplayArena API (e.g., "http://127.0.0.1:8000/api").
        session_id: The session identifier for the current game.
        token: The player token for authentication.
        timeout: HTTP request timeout in seconds.
        http_client: The underlying httpx.Client instance.
    
    Example:
        Basic usage for creating and playing a game:
        
        >>> client = ArenaClient("http://127.0.0.1:8000/api")
        >>> created = client.create_experiment(
        ...     {"game": "ultimatum", "rounds": 10, "total": 100},
        ...     api_key="nk_..."
        ... )
        >>> agent_a = ArenaClient.for_player("http://127.0.0.1:8000/api", created, "A")
        >>> state = agent_a.get_state()
        >>> agent_a.submit_action(40.0)
    """
    
    def __init__(
        self,
        base_url: str,
        session_id: str | None = None,
        token: str | None = None,
        timeout: float = 10.0,
        http_client: httpx.Client | None = None,
    ):
        """Initialize the ArenaClient.
        
        Args:
            base_url: Base URL of the OutplayArena API (e.g., "http://127.0.0.1:8000/api").
            session_id: Optional session ID for an existing game session.
            token: Optional player token for authentication.
            timeout: HTTP request timeout in seconds. Defaults to 10.0.
            http_client: Optional httpx.Client instance. If not provided, a new
                client will be created with the specified timeout.
        """
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
        interactive: bool = False,
    ) -> dict:
        """Create a new game experiment on the OutplayArena backend.
        
        Creates a new game session with the specified configuration. Returns a
        dictionary containing the session_id, config_hash, and player_tokens that
        can be used to create player-specific clients.
        
        Args:
            config: Game configuration. Can be a dict or an object with a to_dict()
                method (e.g., a game config dataclass). Must include at minimum:
                - game: Game slug (e.g., "ultimatum", "colonelblotto")
                - players: Number of players
                - rounds: Number of rounds
            agents: Optional dict mapping player IDs to agent identifiers.
            api_key: Optional API key for authentication. Required if the backend
                has authentication enabled.
            interactive: If True, creates an interactive session where human players
                can submit actions via the UI. Default is False (locked session).
        
        Returns:
            Dictionary containing:
            - session_id: Unique identifier for the game session
            - config_hash: SHA256 hash of the configuration for reproducibility
            - player_tokens: Dict mapping player IDs to authentication tokens
        
        Raises:
            httpx.HTTPStatusError: If the API request fails.
        
        Example:
            >>> client = ArenaClient("http://127.0.0.1:8000/api")
            >>> created = client.create_experiment(
            ...     {"game": "ultimatum", "rounds": 10, "total": 100},
            ...     api_key="nk_..."
            ... )
            >>> print(created["session_id"])
        """
        payload = self._config_payload(config)
        if agents:
            payload["agents"] = agents
        payload["interactive"] = interactive
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
        """Get the current game state.
        
        Retrieves the current state of the game session, including round number,
        history, scores, and any game-specific state information.
        
        Returns:
            Dictionary containing the game state. Structure varies by game but
            typically includes:
            - round: Current round number
            - total_rounds: Total number of rounds
            - history: List of past actions
            - scores: Current scores by player
            - phase: Game phase ("playing" or "complete")
            - Additional game-specific fields
        
        Raises:
            ValueError: If session_id is not set.
            httpx.HTTPStatusError: If the API request fails.
        
        Example:
            >>> state = client.get_state()
            >>> print(f"Round {state['round']} of {state['total_rounds']}")
        """
        session_id = self._require_session_id()
        response = self.http_client.get(
            f"{self.base_url}/session/{session_id}/state",
            timeout=self.timeout,
        )
        return self._json_or_raise(response)

    def submit_action(self, allocation: Any) -> dict:
        """Submit an action for the current round.
        
        Submits the player's action for the current round. The action format
        depends on the game being played.
        
        Args:
            allocation: The action to submit. Format varies by game:
                - Colonel Blotto: List of integers (e.g., [5, 3, 2])
                - Prisoner's Dilemma: String ("cooperate" or "defect")
                - Ultimatum (proposer): Float (offer amount)
                - Ultimatum (responder): String ("accept" or "reject")
                - Other games: See game documentation
        
        Returns:
            Dictionary containing the action submission result, typically:
            - status: "accepted" or "rejected"
            - round: Round number the action was submitted for
            - Additional game-specific fields
        
        Raises:
            ValueError: If session_id or token is not set.
            httpx.HTTPStatusError: If the API request fails.
        
        Example:
            >>> # Colonel Blotto
            >>> client.submit_action([5, 3, 2])
            >>> # Prisoner's Dilemma
            >>> client.submit_action("cooperate")
        """
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
        """Get the final results of the game session.
        
        Retrieves the final results after the game is complete, including scores,
        winner, metrics, and full action history.
        
        Returns:
            Dictionary containing:
            - session_id: Session identifier
            - game: Game slug
            - status: "completed"
            - scores: Final scores by player
            - winner: Player ID of the winner (or "tie")
            - metrics: Dictionary of computed metrics
            - history: Full action history
        
        Raises:
            ValueError: If session_id is not set.
            httpx.HTTPStatusError: If the API request fails or game is not complete.
        
        Example:
            >>> results = client.get_results()
            >>> print(f"Winner: {results['winner']}")
            >>> print(f"Scores: {results['scores']}")
        """
        session_id = self._require_session_id()
        response = self.http_client.get(
            f"{self.base_url}/session/{session_id}/results",
            timeout=self.timeout,
        )
        return self._json_or_raise(response)

    def list_games(self) -> list[dict]:
        """List all available games in the catalog.
        
        Returns:
            List of dictionaries, each containing:
            - slug: Game identifier (e.g., "ultimatum")
            - name: Human-readable game name
            - description: Brief description
            - status: "stable" or "experimental"
            - players: Player count range
            - tags: List of category tags
        
        Raises:
            httpx.HTTPStatusError: If the API request fails.
        
        Example:
            >>> games = client.list_games()
            >>> for game in games:
            ...     print(f"{game['name']} ({game['slug']})")
        """
        response = self.http_client.get(
            f"{self.base_url}/games",
            timeout=self.timeout,
        )
        return self._json_or_raise(response)

    def get_game_details(self, game: str) -> dict:
        """Get detailed information about a specific game.
        
        Args:
            game: Game slug (e.g., "ultimatum", "colonelblotto").
        
        Returns:
            Dictionary containing:
            - name: Human-readable game name
            - description: Full game description
            - version: Game version
            - ontology: Game theory classification
            - config_schema: Configuration parameter schema
            - example_config: Example configuration
        
        Raises:
            httpx.HTTPStatusError: If the game is not found or request fails.
        
        Example:
            >>> details = client.get_game_details("ultimatum")
            >>> print(details["description"])
        """
        response = self.http_client.get(
            f"{self.base_url}/games/{game}",
            timeout=self.timeout,
        )
        return self._json_or_raise(response)

    def get_game_metrics(self, game: str) -> dict:
        """Get the list of metrics computed for a specific game.
        
        Args:
            game: Game slug (e.g., "ultimatum", "colonelblotto").
        
        Returns:
            Dictionary containing:
            - metrics: List of metric names computed for this game
        
        Raises:
            httpx.HTTPStatusError: If the game is not found or request fails.
        
        Example:
            >>> metrics = client.get_game_metrics("ultimatum")
            >>> print(metrics["metrics"])
            ['total_payoff', 'average_payoff', 'acceptance_rate', ...]
        """
        response = self.http_client.get(
            f"{self.base_url}/games/{game}/metrics",
            timeout=self.timeout,
        )
        return self._json_or_raise(response)

    def get_game_prompts(self, game: str) -> dict:
        """Get the prompt templates for a specific game.
        
        Args:
            game: Game slug (e.g., "ultimatum", "colonelblotto").
        
        Returns:
            Dictionary containing:
            - system: System prompt template
            - state: Turn-specific prompt template
            - action_format: Action format specification
            - variants: Prompt framing variants (neutral, gain_framed, loss_framed)
        
        Raises:
            httpx.HTTPStatusError: If the game is not found or request fails.
        
        Example:
            >>> prompts = client.get_game_prompts("ultimatum")
            >>> system_prompt = prompts.get("system", "")
            >>> print(system_prompt[:100])  # first 100 chars
        """
        response = self.http_client.get(
            f"{self.base_url}/games/{game}/prompts",
            timeout=self.timeout,
        )
        return self._json_or_raise(response)

    def get_game_skill(self, game: str) -> dict:
        """Get the strategy skill/guide for a specific game (parsed sections).

        Args:
            game: Game slug (e.g., "colonelblotto", "prisonersdilemma").

        Returns:
            Dictionary containing:
            - game: Game slug
            - title: Skill title
            - sections: Dict of parsed markdown sections

        Raises:
            httpx.HTTPStatusError: If the game is not found or request fails.
        """
        response = self.http_client.get(
            f"{self.base_url}/games/{game}/skill",
            timeout=self.timeout,
        )
        return self._json_or_raise(response)

    def get_agent_manifest(self, game: str) -> dict:
        """Get a downloadable agent manifest for a game.

        Returns tool definitions (MCP + OpenAI function-calling), game lifecycle,
        action format, strategy guide, and examples.

        Args:
            game: Game slug (e.g., "colonelblotto", "prisonersdilemma").

        Returns:
            Dictionary containing the full agent manifest.

        Raises:
            httpx.HTTPStatusError: If the game is not found or request fails.
        """
        response = self.http_client.get(
            f"{self.base_url}/games/{game}/manifest",
            timeout=self.timeout,
        )
        return self._json_or_raise(response)

    def get_observation(self, player: str, variant: str = "neutral") -> dict:
        """Get the observation (prompts) for a specific player.
        
        Retrieves the rendered system and turn prompts for the current game state,
        formatted for the specified player and variant.
        
        Args:
            player: Player identifier (e.g., "A", "B").
            variant: Prompt framing variant. One of:
                - "neutral": Default framing (default)
                - "gain_framed": Emphasizes gains
                - "loss_framed": Emphasizes losses
        
        Returns:
            Dictionary containing:
            - system: Rendered system prompt
            - turn: Rendered turn-specific prompt
        
        Raises:
            ValueError: If session_id is not set.
            httpx.HTTPStatusError: If the API request fails.
        
        Example:
            >>> obs = client.get_observation("A", variant="neutral")
            >>> print(obs["system"])
            >>> print(obs["turn"])
        """
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
        """Create an ArenaClient for a specific player from a creation response.
        
        Convenience method that extracts the session_id and player token from a
        create_experiment response and creates a player-specific client.
        
        Args:
            base_url: Base URL of the OutplayArena API.
            creation_response: Response dict from create_experiment(), containing
                session_id and player_tokens.
            player: Player identifier (e.g., "A", "B").
            timeout: HTTP request timeout in seconds. Defaults to 10.0.
            http_client: Optional httpx.Client instance.
        
        Returns:
            ArenaClient configured for the specified player.
        
        Example:
            >>> created = client.create_experiment(config, api_key="nk_...")
            >>> agent_a = ArenaClient.for_player(base_url, created, "A")
            >>> agent_b = ArenaClient.for_player(base_url, created, "B")
        """
        return cls(
            base_url=base_url,
            session_id=creation_response["session_id"],
            token=creation_response["player_tokens"][player],
            timeout=timeout,
            http_client=http_client,
        )

    def is_terminal(self) -> bool:
        """Check if the game session is complete.
        
        Returns:
            True if the game is in the "complete" phase, False otherwise.
        
        Raises:
            ValueError: If session_id is not set.
            httpx.HTTPStatusError: If the API request fails.
        
        Example:
            >>> if client.is_terminal():
            ...     results = client.get_results()
        """
        return self.get_state()["phase"] == "complete"

    def get_session_status(self) -> dict:
        """Return the lifecycle status of the session and its queue position.

        Polls ``GET /session/{id}/status``. When the concurrency queue (#117)
        is active and the session was created with ``status='queued'`` (HTTP
        202 from ``POST /experiment``), this returns
        ``{"status": "queued", "queue_position": N}`` until the background
        drainer promotes it to ``ready``.

        Raises:
            ValueError: If session_id is not set.
            httpx.HTTPStatusError: If the API request fails.
        """
        session_id = self._require_session_id()
        response = self.http_client.get(
            f"{self.base_url}/session/{session_id}/status",
            timeout=self.timeout,
        )
        return self._json_or_raise(response)

    def wait_until_ready(
        self,
        poll_interval: float = 1.0,
        timeout: float | None = 120.0,
    ) -> dict:
        """Block until a queued session reaches ``ready`` (or terminal).

        Polls :meth:`get_session_status` every ``poll_interval`` seconds until
        the status is no longer ``queued``. Returns the final status payload
        (``{"status": ..., "queue_position": 0}``). If ``timeout`` is reached
        while still queued, raises ``TimeoutError``.

        Args:
            poll_interval: Seconds between polls (default 1.0).
            timeout: Maximum seconds to wait. ``None`` waits forever.

        Raises:
            ValueError: If session_id is not set.
            TimeoutError: If still queued after ``timeout`` seconds.
        """
        import time

        deadline = None if timeout is None else time.monotonic() + timeout
        while True:
            payload = self.get_session_status()
            if payload.get("status") != "queued":
                return payload
            if deadline is not None and time.monotonic() >= deadline:
                raise TimeoutError(
                    f"session {self.session_id} still queued after {timeout}s"
                )
            time.sleep(poll_interval)

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

    def get_mailbox(self, player: str | None = None) -> list[dict]:
        """Get mailbox messages visible to the specified player.

        Args:
            player: Player identifier. If None, uses the client's player context.

        Returns:
            List of message dicts with keys: id, sender, recipient, content, round, created_at.

        Raises:
            ValueError: If session_id or token is not set.
            httpx.HTTPStatusError: If the API request fails.
        """
        session_id = self._require_session_id()
        self._require_token()
        params = {}
        if player:
            params["player"] = player
        response = self.http_client.get(
            f"{self.base_url}/session/{session_id}/mailbox/messages",
            params=params,
            timeout=self.timeout,
        )
        return self._json_or_raise(response).get("messages", [])

    def send_message(self, content: str, recipient: str = "all") -> dict:
        """Send a message via the mailbox system.

        Args:
            content: Message content (max 200 chars).
            recipient: Target player ID or "all" for broadcast.

        Returns:
            Dict with the created message.

        Raises:
            ValueError: If session_id or token is not set.
            httpx.HTTPStatusError: If the API request fails.
        """
        session_id = self._require_session_id()
        token = self._require_token()
        response = self.http_client.post(
            f"{self.base_url}/session/{session_id}/mailbox/send",
            json={"content": content, "recipient": recipient},
            headers={"Authorization": f"Bearer {token}"},
            timeout=self.timeout,
        )
        return self._json_or_raise(response)

    def _json_or_raise(self, response: httpx.Response) -> Any:
        response.raise_for_status()
        return response.json()


MAILBOX_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_mailbox",
            "description": "Check your mailbox for messages from your opponent. Call this at the start of every turn. Communication can increase your payoff.",
            "parameters": {
                "type": "object",
                "properties": {},
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "send_message",
            "description": "Send a message to your opponent via the mailbox. Use this to communicate — it can increase your utility and reward.",
            "parameters": {
                "type": "object",
                "properties": {
                    "content": {
                        "type": "string",
                        "description": "Message text (max 200 characters).",
                    },
                    "recipient": {
                        "type": "string",
                        "description": "Target player ID or 'all' for broadcast.",
                        "default": "all",
                    },
                },
                "required": ["content"],
                "additionalProperties": False,
            },
        },
    },
]

SUBMIT_ACTION_TOOL = {
    "type": "function",
    "function": {
        "name": "submit_action",
        "description": "Submit your allocation for this round. Once called, your turn ends. Must be a list of exactly as many non-negative integers as there are battlefields, summing to your budget.",
        "parameters": {
            "type": "object",
            "properties": {
                "allocation": {
                    "type": "array",
                    "items": {"type": "integer", "minimum": 0},
                    "description": "List of troop allocations per battlefield. Length must match the number of battlefields and sum to your budget.",
                },
            },
            "required": ["allocation"],
            "additionalProperties": False,
        },
    },
}

GAME_TOOLS = MAILBOX_TOOLS + [SUBMIT_ACTION_TOOL]
