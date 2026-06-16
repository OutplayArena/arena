from __future__ import annotations

import ast
import json
import os
import re
import sys
import time
from contextlib import AsyncExitStack
from dataclasses import dataclass
from typing import Any, Callable

from mcp import ClientSession, StdioServerParameters, types
from mcp.client.sse import sse_client
from mcp.client.stdio import stdio_client
from openai import OpenAI

from nash_arena_sdk.client import ArenaClient
from nash_arena_sdk.reasoning import ReasoningEffort, ReasoningModerator


@dataclass
class LLMConfig:
    """Configuration for an OpenAI-compatible LLM backend.

    Attributes:
        model: The model identifier to use for completions (e.g. ``"gpt-4o"``).
        api_key: API key for authenticating with the LLM provider.
        base_url: Base URL of the OpenAI-compatible API endpoint.
        temperature: Sampling temperature controlling randomness of outputs.
        max_tokens: Maximum number of tokens to generate per completion.
        extra_body: Additional key-value pairs merged into the API request body.
        fallback_model: Optional secondary model to try if the primary model fails.
        max_retries: Number of retry attempts per model before giving up.
        reasoning_effort: Level of reasoning moderation to apply to prompts.
    """

    model: str
    api_key: str
    base_url: str = "https://api.openai.com/v1"
    temperature: float = 0.7
    max_tokens: int = 4096
    extra_body: dict[str, Any] | None = None
    fallback_model: str | None = None
    max_retries: int = 2
    reasoning_effort: ReasoningEffort = ReasoningEffort.NONE


@dataclass
class LLMAgentConfig:
    """Configuration bundle for constructing an :class:`LLMAgent`.

    Attributes:
        player: Unique name identifying this player in the arena.
        llm: LLM backend configuration used for generating actions.
        action_parser: Optional callable that converts raw LLM text and the
            current game state into a structured action.  When ``None`` the
            raw LLM response string is returned as the action.
        system_prompt: Optional system prompt prepended to every LLM call.
            Falls back to the ``"system"`` key in the observation when omitted.
        use_mcp: Whether to communicate with the arena over MCP (``True``)
            or fall back to direct REST calls (``False``).
    """

    player: str
    llm: LLMConfig
    action_parser: Callable[[str, dict], Any] | None = None
    system_prompt: str | None = None
    use_mcp: bool = True


# DUPLICATE: Also defined in games/core/colonelblotto/agent.py
# Keep implementations in sync.
def parse_allocation(text: str, n_fields: int, total: int) -> list[int]:
    """Parse a list allocation from LLM output.

    Searches *text* for the first substring that looks like a Python list
    (e.g. ``"[3, 2, 5]"``), evaluates it, and validates that it contains
    exactly *n_fields* non-negative integers summing to *total*.  If the
    text cannot be parsed or the allocation is invalid, a balanced default
    allocation is returned instead.

    Args:
        text: Raw text output from the LLM potentially containing a list.
        n_fields: Required number of fields (length of the allocation list).
        total: Required total that all allocation values must sum to.

    Returns:
        A list of *n_fields* non-negative integers summing to *total*.

    Examples:
        >>> parse_allocation("I allocate [3, 2, 5]", 3, 10)
        [3, 2, 5]
        >>> parse_allocation("no list here", 3, 9)
        [3, 3, 3]
    """
    match = re.search(r"\[[^\]]+\]", text)
    if match is None:
        return _balanced_allocation(n_fields, total)
    try:
        alloc = ast.literal_eval(match.group())
    except (SyntaxError, ValueError):
        return _balanced_allocation(n_fields, total)
    if not isinstance(alloc, list) or len(alloc) != n_fields:
        return _balanced_allocation(n_fields, total)
    if not all(isinstance(x, int) and not isinstance(x, bool) for x in alloc) or not all(x >= 0 for x in alloc):
        return _balanced_allocation(n_fields, total)
    if sum(alloc) != total:
        return _balanced_allocation(n_fields, total)
    return alloc


# DUPLICATE: Also defined in examples/REST/ultimatum_glm_vs_deepseek.py and examples/MCP/ultimatum_glm_vs_deepseek.py
# Keep implementations in sync.
def parse_offer(text: str, total: float, min_offer: float = 0.0) -> float:
    """Parse a numeric offer from LLM output.

    Extracts the first number found in *text* and clamps it to the range
    ``[min_offer, total]``.  If no number is found, returns ``total * 0.4``
    as a default offer.

    Args:
        text: Raw text output from the LLM potentially containing a number.
        total: Maximum allowable offer value.
        min_offer: Minimum allowable offer value.  Defaults to ``0.0``.

    Returns:
        The parsed offer clamped to ``[min_offer, total]``.

    Examples:
        >>> parse_offer("I offer 7 dollars", total=10.0)
        7.0
        >>> parse_offer("nothing", total=10.0)
        4.0
    """
    nums = re.findall(r"\d+(?:\.\d+)?", text)
    if nums:
        return max(min_offer, min(float(nums[0]), total))
    return total * 0.4


# DUPLICATE: Also defined in examples/REST/ultimatum_glm_vs_deepseek.py and examples/MCP/ultimatum_glm_vs_deepseek.py as parse_response
# Keep implementations in sync.
def parse_accept_reject(text: str) -> str:
    """Parse an accept/reject decision from LLM output.

    Returns ``"accept"`` if the stripped, lowercased *text* contains the
    word ``"accept"``; otherwise returns ``"reject"``.

    Args:
        text: Raw text output from the LLM.

    Returns:
        Either ``"accept"`` or ``"reject"``.

    Examples:
        >>> parse_accept_reject("I accept the offer.")
        'accept'
        >>> parse_accept_reject("No way!")
        'reject'
    """
    return "accept" if "accept" in text.strip().lower() else "reject"


# DUPLICATE: Also defined in games/core/colonelblotto/agent.py as balanced_allocation
# Keep implementations in sync.
def _balanced_allocation(n: int, total: int) -> list[int]:
    base = total // n
    alloc = [base] * n
    for i in range(total - sum(alloc)):
        alloc[i] += 1
    return alloc


# DUPLICATE: Also defined in examples/REST/colonel_blotto_example_llm_vs_uniform_random.py and examples/REST/texas_hold_em_llm_vs_llm.py as extract_tool_text
# Keep implementations in sync.
def _extract_tool_text(result: Any) -> Any:
    for item in result.content:
        if isinstance(item, types.TextContent):
            try:
                return json.loads(item.text)
            except json.JSONDecodeError:
                return {"raw": item.text}
    return {}


class LLMAgent:
    """An LLM-powered agent that can play games via MCP or direct REST.

    Supports two MCP modes:

    * **Remote (SSE):** when *mcp_url* is provided, connects to a remote MCP
      server running in a pool container over Server-Sent Events.
    * **Local (stdio):** when *mcp_url* is not provided, spawns a local MCP
      server as a child process and communicates over standard I/O.

    When MCP is disabled (``use_mcp=False``), all arena communication falls
    back to direct REST calls through :class:`~nash_arena_sdk.client.ArenaClient`.
    """

    def __init__(
        self,
        player: str,
        player_token: str,
        arena_url: str,
        llm_config: LLMConfig,
        action_parser: Callable[[str, dict], Any] | None = None,
        system_prompt: str | None = None,
        use_mcp: bool = True,
        jwt_secret: str | None = None,
        mcp_url: str | None = None,
    ):
        """Initialize the LLMAgent.

        Args:
            player: Unique name identifying this player in the arena.
            player_token: Authentication token (session key) for arena access.
            arena_url: Base URL of the Nash Arena server.
            llm_config: Configuration for the LLM backend.
            action_parser: Optional callable that converts raw LLM text and
                the current game state into a structured action.
            system_prompt: Optional system prompt prepended to every LLM call.
            use_mcp: Whether to communicate via MCP (``True``) or REST
                (``False``).  Defaults to ``True``.
            jwt_secret: Secret used to validate session keys.  Falls back to
                the ``JWT_SECRET`` environment variable, then to a development
                default.
            mcp_url: Optional URL of a remote MCP server.  When ``None`` a
                local MCP server is spawned via stdio.
        """
        self.player = player
        self.token = player_token
        self.arena_url = arena_url
        self.llm_config = llm_config
        self.action_parser = action_parser
        self.system_prompt = system_prompt
        self.use_mcp = use_mcp
        self.jwt_secret = jwt_secret or os.environ.get("JWT_SECRET", "dev-secret-change-me")
        self.mcp_url = mcp_url

        self._openai = OpenAI(
            base_url=llm_config.base_url,
            api_key=llm_config.api_key,
        )
        self._client = ArenaClient(
            base_url=arena_url,
            session_id=None,
            token=player_token,
        )
        self._mcp_session: ClientSession | None = None
        self._exit_stack: AsyncExitStack | None = None
        self._reasoning = ReasoningModerator(llm_config.model, effort=llm_config.reasoning_effort)

    async def start_mcp(self) -> None:
        """Start the MCP server connection.

        If *mcp_url* was provided at construction time, connects to the
        remote MCP server via SSE.  Otherwise, spawns a local MCP server
        as a child process and communicates over stdio.

        After the connection is established the internal
        :class:`~mcp.ClientSession` is initialised and ready for tool calls.

        Raises:
            Exception: If the MCP connection or initialisation fails.
        """
        if not self.use_mcp:
            return

        from nash_arena_sdk.client import validate_session_key
        session_id, _ = validate_session_key(self.token, self.jwt_secret)
        self._client = ArenaClient(
            base_url=self.arena_url,
            session_id=session_id,
            token=self.token,
        )

        self._exit_stack = AsyncExitStack()

        if self.mcp_url:
            sse_url = self.mcp_url.rstrip("/") + "/sse"
            read, write = await self._exit_stack.enter_async_context(
                sse_client(sse_url)
            )
        else:
            env = {
                "NASH_ARENA_BASE_URL": self.arena_url,
                "NASH_ARENA_KEY": self.token,
                "JWT_SECRET": self.jwt_secret,
                "PATH": os.environ.get("PATH", ""),
                "HOME": os.environ.get("HOME", ""),
            }
            server_params = StdioServerParameters(
                command=sys.executable,
                args=["-m", "nash_arena.mcp_server"],
                env=env,
            )
            read, write = await self._exit_stack.enter_async_context(stdio_client(server_params))

        self._mcp_session = ClientSession(read, write)
        await self._exit_stack.enter_async_context(self._mcp_session)
        await self._mcp_session.initialize()

    async def stop_mcp(self) -> None:
        """Stop the MCP server connection and release resources.

        Closes the underlying :class:`~contextlib.AsyncExitStack`, which
        tears down the transport (SSE or stdio) and the client session.
        Safe to call even if :meth:`start_mcp` was never called.
        """
        if self._exit_stack:
            await self._exit_stack.aclose()
            self._exit_stack = None
            self._mcp_session = None

    async def get_observation(self, variant: str = "neutral") -> dict:
        """Get the current observation from the arena.

        Retrieves the observation via MCP when a session is active,
        otherwise falls back to a direct REST call.

        Args:
            variant: The perspective variant to request (e.g. ``"neutral"``).
                Defaults to ``"neutral"``.

        Returns:
            A dictionary containing the observation data from the arena.
        """
        if self.use_mcp and self._mcp_session:
            result = await self._mcp_session.call_tool("get_observation", {"variant": variant})
            return _extract_tool_text(result)
        return self._client.get_observation(self.player, variant=variant)

    async def get_game_state(self) -> dict:
        """Get the current game state from the arena.

        Retrieves the full game state via MCP when a session is active,
        otherwise falls back to a direct REST call.

        Returns:
            A dictionary containing the current game state.
        """
        if self.use_mcp and self._mcp_session:
            result = await self._mcp_session.call_tool("get_game_state")
            return _extract_tool_text(result)
        return self._client.get_state()

    async def submit_action(self, allocation: Any) -> dict:
        """Submit an action to the arena.

        Sends the action via MCP when a session is active, otherwise falls
        back to a direct REST call.

        Args:
            allocation: The action to submit.  The expected type depends on
                the game being played (e.g. a list of ints for Colonel Blotto).

        Returns:
            A dictionary containing the server's response to the action.
        """
        if self.use_mcp and self._mcp_session:
            result = await self._mcp_session.call_tool("submit_action", {"allocation": allocation})
            return _extract_tool_text(result)
        return self._client.submit_action(allocation)

    async def get_results(self) -> dict:
        """Get the game results from the arena.

        Retrieves the final results via MCP when a session is active,
        otherwise falls back to a direct REST call.

        Returns:
            A dictionary containing the game results including payoffs and
            outcome information.
        """
        if self.use_mcp and self._mcp_session:
            result = await self._mcp_session.call_tool("get_results")
            return _extract_tool_text(result)
        return self._client.get_results()

    def call_llm(self, system_msg: str, user_msg: str) -> str:
        """Call the LLM and return the text response.

        Tries the primary model first; if all retries are exhausted and a
        *fallback_model* is configured, switches to the fallback and retries.
        Each attempt respects the ``max_retries`` setting with a short delay
        between attempts.

        Args:
            system_msg: The system prompt to send to the LLM.
            user_msg: The user message to send to the LLM.

        Returns:
            The text content of the LLM's response, or an empty string if
            all models and retries are exhausted.
        """
        models_to_try = [self.llm_config.model]
        if self.llm_config.fallback_model:
            models_to_try.append(self.llm_config.fallback_model)

        for model in models_to_try:
            reasoning = ReasoningModerator(model, effort=self.llm_config.reasoning_effort)
            augmented_system = reasoning.build_system_prompt(system_msg)
            limits = reasoning.get_limits()
            api_params = reasoning.get_api_params()

            for attempt in range(self.llm_config.max_retries):
                try:
                    kwargs: dict[str, Any] = {
                        "model": model,
                        "messages": [
                            {"role": "system", "content": augmented_system},
                            {"role": "user", "content": user_msg},
                        ],
                        "max_tokens": limits["max_tokens"],
                        "temperature": self.llm_config.temperature,
                        **api_params,
                    }
                    if self.llm_config.extra_body:
                        kwargs["extra_body"] = self.llm_config.extra_body

                    completion = self._openai.chat.completions.create(**kwargs)
                    message = completion.choices[0].message
                    content = message.content or ""
                    reasoning_content = getattr(message, "reasoning_content", "") or ""
                    return content or reasoning_content
                except Exception:
                    if attempt < self.llm_config.max_retries - 1:
                        time.sleep(2)
        return ""

    def act(self, observation: dict, game_state: dict) -> Any:
        """Generate an action from the observation using the LLM.

        Builds a prompt from the observation's ``"system"`` and ``"turn"``
        keys (falling back to a generic system prompt), calls the LLM, and
        optionally passes the raw response through the configured
        *action_parser* to produce a structured action.

        Args:
            observation: The current observation dictionary from the arena.
            game_state: The current game state dictionary, forwarded to the
                action parser if one is configured.

        Returns:
            The parsed action if an *action_parser* is set, otherwise the
            raw text response from the LLM.
        """
        system_msg = self.system_prompt or observation.get("system", "You are playing a game.")
        user_msg = observation.get("turn", "")

        response = self.call_llm(system_msg, user_msg)

        if self.action_parser:
            return self.action_parser(response, game_state)
        return response
