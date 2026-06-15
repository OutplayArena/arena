from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from nash_arena_sdk.client import ArenaClient
from nash_arena_sdk.llm_agent import LLMAgent, LLMConfig


@dataclass
class AgentSpec:
    """Specification for an agent in a game."""
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
    """Configuration for the game orchestrator."""
    game: str
    config: dict[str, Any]
    agents: dict[str, AgentSpec]
    arena_url: str = "http://127.0.0.1:8000/api"
    arena_api_key: str | None = None
    jwt_secret: str | None = None
    max_steps: int | None = None
    verbose: bool = True


class GameOrchestrator:
    """Orchestrates a game session between multiple agents."""

    def __init__(self, config: OrchestratorConfig):
        self.config = config
        self.arena = ArenaClient(config.arena_url)
        self.agents: dict[str, LLMAgent | Any] = {}
        self.session_id: str | None = None
        self.player_tokens: dict[str, str] = {}
        self.mcp_url: str | None = None

    async def setup(self) -> dict:
        """Create the experiment and set up agents."""
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
        """Run the game loop until completion."""
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
        first_agent = next(iter(self.agents.values()))
        if isinstance(first_agent, LLMAgent):
            return await first_agent.get_game_state()
        return first_agent.get_game_state()

    async def _get_results(self) -> dict:
        first_agent = next(iter(self.agents.values()))
        if isinstance(first_agent, LLMAgent):
            return await first_agent.get_results()
        return first_agent.get_results()

    async def _process_turn(self, state: dict) -> None:
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
