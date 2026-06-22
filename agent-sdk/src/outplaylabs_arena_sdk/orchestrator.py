from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from outplaylabs_arena_sdk.client import ArenaClient
from outplaylabs_arena_sdk.llm_agent import LLMAgent, LLMConfig


@dataclass
class AgentSpec:
    """Specification for configuring a single agent participating in a game.

    Encapsulates all parameters needed to instantiate either an LLM-backed agent
    or a custom user-supplied agent.  When ``model`` is provided the orchestrator
    will automatically create an :class:`~outplaylabs_arena_sdk.llm_agent.LLMAgent`;
    otherwise a pre-built ``agent`` instance must be supplied.

    Attributes:
        player: The player identifier that this agent will use in the arena
            (e.g. ``"player_0"``).
        model: The LLM model identifier to use (e.g. ``"gpt-4"``).  When
            ``None`` and no custom ``agent`` is given, the orchestrator will
            skip automatic agent creation for this player.
        api_key: API key for the LLM provider.  Falls back to the provider's
            default environment variable when ``None``.
        base_url: Base URL of the LLM-compatible API endpoint.
        temperature: Sampling temperature for the LLM.  Higher values produce
            more diverse outputs.
        max_tokens: Maximum number of tokens the LLM may generate per request.
        extra_body: Additional key-value pairs merged into every LLM request
            body.
        fallback_model: Model identifier to retry with when the primary
            ``model`` is unavailable.
        action_parser: Optional callable that converts raw LLM text output and
            the current game state dict into a structured action object.
        system_prompt: Optional system prompt prepended to every LLM
            conversation.
        use_mcp: Whether to enable Model Context Protocol tool-use for this
            agent.
        agent: A pre-built custom agent instance.  When provided, ``model``
            and all LLM-related fields are ignored.
    """

    player: str
    model: str | None = None
    api_key: str | None = None
    base_url: str = "https://api.openai.com/v1"
    temperature: float = 0.7
    max_tokens: int = 4096
    extra_body: dict[str, Any] | None = None
    fallback_model: str | None = None
    action_parser: Callable[[str, dict], Any] | None = None
    system_prompt: str | None = None
    use_mcp: bool = True
    agent: Any = None

    def to_llm_config(self) -> LLMConfig:
        """Convert this specification into an :class:`LLMConfig`.

        Returns:
            An :class:`~outplaylabs_arena_sdk.llm_agent.LLMConfig` populated with the
            LLM-related fields from this spec.  ``model`` defaults to
            ``"gpt-4"`` and ``api_key`` defaults to ``""`` when not set.

        Examples:
            >>> spec = AgentSpec(player="p0", model="gpt-4o", api_key="sk-...")
            >>> cfg = spec.to_llm_config()
            >>> cfg.model
            'gpt-4o'
        """
        return LLMConfig(
            model=self.model or "gpt-4",
            api_key=self.api_key or "",
            base_url=self.base_url,
            temperature=self.temperature,
            max_tokens=self.max_tokens,
            extra_body=self.extra_body,
            fallback_model=self.fallback_model,
        )


@dataclass
class OrchestratorConfig:
    """Top-level configuration for a :class:`GameOrchestrator` session.

    Bundles together the game parameters, per-agent specifications, and arena
    connection details needed to create an experiment and run a complete game
    loop.

    Attributes:
        game: The name of the game to play (e.g. ``"colonel_blotto"``).
        config: Game-specific configuration dict forwarded to the arena's
            experiment-creation endpoint.
        agents: Mapping of player identifiers to their :class:`AgentSpec`
            definitions.
        arena_url: Base URL of the OutplayLabs Arena HTTP API.
        arena_api_key: Optional API key used when creating the experiment on
            the arena server.
        jwt_secret: Optional shared secret used for JWT-based agent
            authentication.
        max_steps: Maximum number of game-loop iterations before the session
            is forcibly terminated.  ``None`` means the orchestrator's default
            (currently 1000).
        verbose: When ``True``, per-turn progress messages are printed to
            stdout.

    Examples:
        >>> cfg = OrchestratorConfig(
        ...     game="colonel_blotto",
        ...     config={"n_fields": 5, "total_troops": 100},
        ...     agents={
        ...         "player_0": AgentSpec(player="player_0", model="gpt-4o"),
        ...         "player_1": AgentSpec(player="player_1", model="gpt-4o-mini"),
        ...     },
        ... )
    """

    game: str
    config: dict[str, Any]
    agents: dict[str, AgentSpec]
    arena_url: str = "http://127.0.0.1:8000/api"
    arena_api_key: str | None = None
    jwt_secret: str | None = None
    max_steps: int | None = None
    verbose: bool = True


class GameOrchestrator:
    """Orchestrates a complete game session between multiple agents.

    Manages the full lifecycle of an arena experiment: creating the experiment
    on the server, instantiating and wiring up agents (including optional MCP
    tool-use), running the turn-based game loop until completion or step-limit,
    collecting final results, and tearing down agent resources.

    Typical usage::

        config = OrchestratorConfig(game="colonel_blotto", config={...}, agents={...})
        orchestrator = GameOrchestrator(config)
        results = await orchestrator.run()
    """

    def __init__(self, config: OrchestratorConfig):
        """Initialise the orchestrator with the given configuration.

        Args:
            config: An :class:`OrchestratorConfig` describing the game, agents,
                and arena connection details.
        """
        self.config = config
        self.arena = ArenaClient(config.arena_url)
        self.agents: dict[str, LLMAgent | Any] = {}
        self.session_id: str | None = None
        self.player_tokens: dict[str, str] = {}
        self.mcp_url: str | None = None

    async def setup(self) -> dict:
        """Create the arena experiment and initialise all agents.

        Contacts the arena server to create a new experiment, stores the
        returned session metadata, and then instantiates an agent for each
        player defined in the configuration.  For :class:`AgentSpec` entries
        that specify a ``model``, an :class:`~outplaylabs_arena_sdk.llm_agent.LLMAgent`
        is created and its MCP connection (if enabled) is started.  Entries
        that supply a pre-built ``agent`` are used as-is.

        Returns:
            The raw experiment-creation response dict from the arena server,
            containing at least ``"session_id"``, ``"player_tokens"``, and
            optionally ``"mcp_url"``.

        Examples:
            >>> orchestrator = GameOrchestrator(config)
            >>> info = await orchestrator.setup()
            >>> info["session_id"]
            'abc123...'
        """
        created = self.arena.create_experiment(
            self.config.config,
            agents={p: spec.model or "unknown" for p, spec in self.config.agents.items()},
            api_key=self.config.arena_api_key,
        )
        self.session_id = created["session_id"]
        self.player_tokens = created["player_tokens"]
        self.mcp_url = created.get("mcp_url")

        jwt_secret = self.config.jwt_secret
        for player, spec in self.config.agents.items():
            token = self.player_tokens[player]
            if spec.agent is not None:
                self.agents[player] = spec.agent
            elif spec.model:
                agent = LLMAgent(
                    player=player,
                    player_token=token,
                    arena_url=self.config.arena_url,
                    llm_config=spec.to_llm_config(),
                    action_parser=spec.action_parser,
                    system_prompt=spec.system_prompt,
                    use_mcp=spec.use_mcp,
                    jwt_secret=jwt_secret,
                    mcp_url=self.mcp_url,
                )
                if spec.use_mcp and self.mcp_url:
                    await agent.start_mcp()
                self.agents[player] = agent

        return created

    async def run(self) -> dict:
        """Run the full game loop from setup through to final results.

        Calls :meth:`setup` to create the experiment and initialise agents,
        then repeatedly polls the game state and dispatches turns to the
        appropriate agents until the game phase is ``"complete"``, no players
        are awaiting a turn, or ``max_steps`` is reached.  After the loop
        finishes, final results are fetched and all MCP connections are torn
        down.

        Returns:
            A dict containing the final game results as returned by the arena
            server (typically including per-player scores and outcome data).

        Examples:
            >>> results = await orchestrator.run()
            >>> results["winner"]
            'player_0'
        """
        await self.setup()

        max_steps = self.config.max_steps or 1000
        step = 0

        while step < max_steps:
            state = await self._get_state()
            phase = state.get("phase")

            if phase == "complete" or not state.get("awaiting"):
                break

            await self._process_turn(state)
            step += 1

        results = await self._get_results()

        for agent in self.agents.values():
            if isinstance(agent, LLMAgent):
                await agent.stop_mcp()

        return results

    async def _get_state(self) -> dict:
        """Fetch the current game state from the arena via the first agent.

        Returns:
            A dict representing the current game state, including at least
            ``"phase"`` and ``"awaiting"`` keys.
        """
        first_agent = next(iter(self.agents.values()))
        if isinstance(first_agent, LLMAgent):
            return await first_agent.get_game_state()
        return first_agent.get_game_state()

    async def _get_results(self) -> dict:
        """Fetch the final game results from the arena via the first agent.

        Returns:
            A dict containing the final game results (scores, outcomes, etc.).
        """
        first_agent = next(iter(self.agents.values()))
        if isinstance(first_agent, LLMAgent):
            return await first_agent.get_results()
        return first_agent.get_results()

    async def _process_turn(self, state: dict) -> None:
        """Dispatch actions for every player currently awaiting a turn.

        For each player listed in ``state["awaiting"]``, retrieves the latest
        observation, computes an action via the player's agent, and submits it
        to the arena.  Supports both :class:`~outplaylabs_arena_sdk.llm_agent.LLMAgent`
        (async) and arbitrary custom agent (sync) interfaces.

        Args:
            state: The current game state dict, as returned by
                :meth:`_get_state`.
        """
        awaiting = state.get("awaiting", [])
        if not awaiting:
            return

        for player in awaiting:
            if player not in self.agents:
                continue
            agent = self.agents[player]

            if isinstance(agent, LLMAgent):
                obs = await agent.get_observation()
                action = agent.act(obs, state)
                await agent.submit_action(action)
            else:
                obs = agent.get_observation()
                try:
                    action = agent.act(obs, state)
                except TypeError:
                    action = agent.act(obs)
                agent.submit_action(action)

            if self.config.verbose:
                print(f"  Player {player} acted")
