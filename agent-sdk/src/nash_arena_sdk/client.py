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
    """HTTP client for the NashArena REST API.
    
    ArenaClient provides a thin wrapper around the NashArena HTTP API, handling
    session management, authentication, and providing typed methods for all API
    endpoints. It is the foundation for building agents that interact with the
    platform via REST.
    
    Attributes:
        base_url: The base URL of the NashArena API (e.g., "http://127.0.0.1:8000/api").
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
            base_url: Base URL of the NashArena API (e.g., "http://127.0.0.1:8000/api").
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
        """Create a new game experiment on the NashArena backend.
        
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
            >>> print(prompts["system"][:100])
        """
        response = self.http_client.get(
            f"{self.base_url}/games/{game}/prompts",
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
            base_url: Base URL of the NashArena API.
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
