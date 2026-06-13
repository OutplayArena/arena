"""Reasoning control module for LLM agents in the Nash Arena SDK.

Provides enums, dataclasses, and utility functions for managing model-specific
reasoning behaviour, including effort levels, strategy selection, API parameter
construction, and system prompt augmentation.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from enum import Enum


class ReasoningEffort(str, Enum):
    """Enumeration of reasoning effort levels available to agents.

    Controls how much computational budget a model should devote to
    chain-of-thought reasoning before producing a final answer.

    Values:
        NONE: No reasoning; respond immediately with no deliberation.
        LOW: Minimal reasoning; brief internal deliberation.
        MEDIUM: Moderate reasoning; short assessment before responding.
        HIGH: Extensive reasoning; thorough analysis before responding.
    """

    NONE = "none"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class ReasoningStrategy(str, Enum):
    """Enumeration of strategies used to control model reasoning behaviour.

    Each strategy corresponds to a different mechanism for constraining or
    directing the reasoning process of an LLM.

    Values:
        API_CONTROL: The model exposes a dedicated API parameter (e.g.
            ``reasoning_effort``, ``thinking``) to set the reasoning budget.
        BUDGET_PROMPT: The model responds to prompt-level instructions that
            describe the desired amount of deliberation.
        STUBBORN: The model does not respond to any reasoning moderation
            attempts and always uses extensive reasoning regardless of
            configuration.
    """

    API_CONTROL = "api_control"
    BUDGET_PROMPT = "budget_prompt"
    STUBBORN = "stubborn"


@dataclass(frozen=True)
class ModelProfile:
    """Immutable profile describing the reasoning capabilities of a specific LLM.

    Each profile captures which reasoning-control mechanisms a model supports
    and which strategy should be preferred when interacting with it.

    Attributes:
        model_id: Unique identifier for the model (e.g. ``"deepseek-v4-flash"``).
        provider: Name of the model provider (e.g. ``"openai"``, ``"anthropic"``).
        supports_thinking_toggle: Whether the model accepts a ``thinking``
            parameter to enable or disable its internal reasoning trace.
        supports_reasoning_effort: Whether the model accepts a
            ``reasoning_effort`` parameter (e.g. ``"low"``, ``"medium"``).
        supports_enable_thinking: Whether the model accepts an
            ``enable_thinking`` boolean parameter.
        baseline_response_time: Expected baseline response time in seconds for
            the model under normal load, used to compute dynamic timeouts.
        preferred_strategy: The reasoning strategy that works best for this
            model. Defaults to ``ReasoningStrategy.API_CONTROL``.
    """

    model_id: str
    provider: str
    supports_thinking_toggle: bool
    supports_reasoning_effort: bool
    supports_enable_thinking: bool
    baseline_response_time: float
    preferred_strategy: ReasoningStrategy = ReasoningStrategy.API_CONTROL


DEFAULT_MODEL_PROFILE = ModelProfile(
    model_id="unknown",
    provider="unknown",
    supports_thinking_toggle=False,
    supports_reasoning_effort=False,
    supports_enable_thinking=False,
    baseline_response_time=30.0,
    preferred_strategy=ReasoningStrategy.BUDGET_PROMPT,
)


# Registry of known model profiles keyed by model identifier.
#
# Maps model IDs (e.g. "deepseek-v4-flash", "gpt-5") to their corresponding
# :class:`ModelProfile` instances. Used by :func:`get_model_profile` to look
# up capability information at runtime.
MODEL_PROFILES: dict[str, ModelProfile] = {
    "deepseek-v4-flash": ModelProfile(
        model_id="deepseek-v4-flash",
        provider="deepseek",
        supports_thinking_toggle=True,
        supports_reasoning_effort=True,
        supports_enable_thinking=False,
        baseline_response_time=7.0,
        preferred_strategy=ReasoningStrategy.API_CONTROL,
    ),
    "deepseek-v4-pro": ModelProfile(
        model_id="deepseek-v4-pro",
        provider="deepseek",
        supports_thinking_toggle=True,
        supports_reasoning_effort=False,
        supports_enable_thinking=False,
        baseline_response_time=14.0,
        preferred_strategy=ReasoningStrategy.API_CONTROL,
    ),
    "glm-5.1": ModelProfile(
        model_id="glm-5.1",
        provider="zhipu",
        supports_thinking_toggle=False,
        supports_reasoning_effort=False,
        supports_enable_thinking=False,
        baseline_response_time=4.0,
        preferred_strategy=ReasoningStrategy.BUDGET_PROMPT,
    ),
    "glm-5": ModelProfile(
        model_id="glm-5",
        provider="zhipu",
        supports_thinking_toggle=False,
        supports_reasoning_effort=False,
        supports_enable_thinking=False,
        baseline_response_time=4.0,
        preferred_strategy=ReasoningStrategy.BUDGET_PROMPT,
    ),
    "kimi-k2.5": ModelProfile(
        model_id="kimi-k2.5",
        provider="moonshot",
        supports_thinking_toggle=True,
        supports_reasoning_effort=False,
        supports_enable_thinking=False,
        baseline_response_time=5.0,
        preferred_strategy=ReasoningStrategy.API_CONTROL,
    ),
    "kimi-k2.6": ModelProfile(
        model_id="kimi-k2.6",
        provider="moonshot",
        supports_thinking_toggle=True,
        supports_reasoning_effort=False,
        supports_enable_thinking=False,
        baseline_response_time=5.0,
        preferred_strategy=ReasoningStrategy.API_CONTROL,
    ),
    "minimax-m2.7": ModelProfile(
        model_id="minimax-m2.7",
        provider="minimax",
        supports_thinking_toggle=True,
        supports_reasoning_effort=False,
        supports_enable_thinking=False,
        baseline_response_time=5.0,
        preferred_strategy=ReasoningStrategy.API_CONTROL,
    ),
    "minimax-m2.5": ModelProfile(
        model_id="minimax-m2.5",
        provider="minimax",
        supports_thinking_toggle=True,
        supports_reasoning_effort=False,
        supports_enable_thinking=False,
        baseline_response_time=5.0,
        preferred_strategy=ReasoningStrategy.API_CONTROL,
    ),
    "mimo-v2.5": ModelProfile(
        model_id="mimo-v2.5",
        provider="xiaomi",
        supports_thinking_toggle=False,
        supports_reasoning_effort=False,
        supports_enable_thinking=False,
        baseline_response_time=8.0,
        preferred_strategy=ReasoningStrategy.STUBBORN,
    ),
    "mimo-v2.5-pro": ModelProfile(
        model_id="mimo-v2.5-pro",
        provider="xiaomi",
        supports_thinking_toggle=False,
        supports_reasoning_effort=False,
        supports_enable_thinking=False,
        baseline_response_time=12.0,
        preferred_strategy=ReasoningStrategy.STUBBORN,
    ),
    "qwen3.5-plus": ModelProfile(
        model_id="qwen3.5-plus",
        provider="alibaba",
        supports_thinking_toggle=False,
        supports_reasoning_effort=False,
        supports_enable_thinking=True,
        baseline_response_time=86.0,
        preferred_strategy=ReasoningStrategy.API_CONTROL,
    ),
    "qwen3.6-plus": ModelProfile(
        model_id="qwen3.6-plus",
        provider="alibaba",
        supports_thinking_toggle=False,
        supports_reasoning_effort=False,
        supports_enable_thinking=True,
        baseline_response_time=86.0,
        preferred_strategy=ReasoningStrategy.API_CONTROL,
    ),
    "qwen3.7-max": ModelProfile(
        model_id="qwen3.7-max",
        provider="alibaba",
        supports_thinking_toggle=False,
        supports_reasoning_effort=False,
        supports_enable_thinking=True,
        baseline_response_time=120.0,
        preferred_strategy=ReasoningStrategy.API_CONTROL,
    ),
    # ── OpenAI ────────────────────────────────────────────────
    "o4-mini": ModelProfile(
        model_id="o4-mini",
        provider="openai",
        supports_thinking_toggle=False,
        supports_reasoning_effort=True,
        supports_enable_thinking=False,
        baseline_response_time=5.0,
        preferred_strategy=ReasoningStrategy.API_CONTROL,
    ),
    "o3-mini": ModelProfile(
        model_id="o3-mini",
        provider="openai",
        supports_thinking_toggle=False,
        supports_reasoning_effort=True,
        supports_enable_thinking=False,
        baseline_response_time=8.0,
        preferred_strategy=ReasoningStrategy.API_CONTROL,
    ),
    "o3": ModelProfile(
        model_id="o3",
        provider="openai",
        supports_thinking_toggle=False,
        supports_reasoning_effort=True,
        supports_enable_thinking=False,
        baseline_response_time=15.0,
        preferred_strategy=ReasoningStrategy.API_CONTROL,
    ),
    "gpt-4o": ModelProfile(
        model_id="gpt-4o",
        provider="openai",
        supports_thinking_toggle=False,
        supports_reasoning_effort=False,
        supports_enable_thinking=False,
        baseline_response_time=2.0,
        preferred_strategy=ReasoningStrategy.BUDGET_PROMPT,
    ),
    "gpt-4o-mini": ModelProfile(
        model_id="gpt-4o-mini",
        provider="openai",
        supports_thinking_toggle=False,
        supports_reasoning_effort=False,
        supports_enable_thinking=False,
        baseline_response_time=1.0,
        preferred_strategy=ReasoningStrategy.BUDGET_PROMPT,
    ),
    "gpt-4.1": ModelProfile(
        model_id="gpt-4.1",
        provider="openai",
        supports_thinking_toggle=False,
        supports_reasoning_effort=False,
        supports_enable_thinking=False,
        baseline_response_time=3.0,
        preferred_strategy=ReasoningStrategy.BUDGET_PROMPT,
    ),
    "gpt-4.1-mini": ModelProfile(
        model_id="gpt-4.1-mini",
        provider="openai",
        supports_thinking_toggle=False,
        supports_reasoning_effort=False,
        supports_enable_thinking=False,
        baseline_response_time=1.5,
        preferred_strategy=ReasoningStrategy.BUDGET_PROMPT,
    ),
    "gpt-5": ModelProfile(
        model_id="gpt-5",
        provider="openai",
        supports_thinking_toggle=False,
        supports_reasoning_effort=True,
        supports_enable_thinking=False,
        baseline_response_time=8.0,
        preferred_strategy=ReasoningStrategy.API_CONTROL,
    ),
    "gpt-5-mini": ModelProfile(
        model_id="gpt-5-mini",
        provider="openai",
        supports_thinking_toggle=False,
        supports_reasoning_effort=True,
        supports_enable_thinking=False,
        baseline_response_time=3.0,
        preferred_strategy=ReasoningStrategy.API_CONTROL,
    ),
    "gpt-5-nano": ModelProfile(
        model_id="gpt-5-nano",
        provider="openai",
        supports_thinking_toggle=False,
        supports_reasoning_effort=True,
        supports_enable_thinking=False,
        baseline_response_time=1.0,
        preferred_strategy=ReasoningStrategy.API_CONTROL,
    ),
    # ── Anthropic ─────────────────────────────────────────────
    "claude-sonnet-4-20250514": ModelProfile(
        model_id="claude-sonnet-4-20250514",
        provider="anthropic",
        supports_thinking_toggle=True,
        supports_reasoning_effort=False,
        supports_enable_thinking=False,
        baseline_response_time=3.0,
        preferred_strategy=ReasoningStrategy.API_CONTROL,
    ),
    "claude-sonnet-4-6": ModelProfile(
        model_id="claude-sonnet-4-6",
        provider="anthropic",
        supports_thinking_toggle=True,
        supports_reasoning_effort=False,
        supports_enable_thinking=False,
        baseline_response_time=2.5,
        preferred_strategy=ReasoningStrategy.API_CONTROL,
    ),
    "claude-opus-4-20250514": ModelProfile(
        model_id="claude-opus-4-20250514",
        provider="anthropic",
        supports_thinking_toggle=True,
        supports_reasoning_effort=False,
        supports_enable_thinking=False,
        baseline_response_time=8.0,
        preferred_strategy=ReasoningStrategy.API_CONTROL,
    ),
    "claude-opus-4-7": ModelProfile(
        model_id="claude-opus-4-7",
        provider="anthropic",
        supports_thinking_toggle=True,
        supports_reasoning_effort=False,
        supports_enable_thinking=False,
        baseline_response_time=6.0,
        preferred_strategy=ReasoningStrategy.API_CONTROL,
    ),
    "claude-haiku-3-5": ModelProfile(
        model_id="claude-haiku-3-5",
        provider="anthropic",
        supports_thinking_toggle=True,
        supports_reasoning_effort=False,
        supports_enable_thinking=False,
        baseline_response_time=1.0,
        preferred_strategy=ReasoningStrategy.API_CONTROL,
    ),
    # ── Google ────────────────────────────────────────────────
    "gemini-2.5-pro": ModelProfile(
        model_id="gemini-2.5-pro",
        provider="google",
        supports_thinking_toggle=True,
        supports_reasoning_effort=False,
        supports_enable_thinking=False,
        baseline_response_time=5.0,
        preferred_strategy=ReasoningStrategy.API_CONTROL,
    ),
    "gemini-2.5-flash": ModelProfile(
        model_id="gemini-2.5-flash",
        provider="google",
        supports_thinking_toggle=True,
        supports_reasoning_effort=False,
        supports_enable_thinking=False,
        baseline_response_time=2.0,
        preferred_strategy=ReasoningStrategy.API_CONTROL,
    ),
    # ── Meta ──────────────────────────────────────────────────
    "llama-4-maverick": ModelProfile(
        model_id="llama-4-maverick",
        provider="meta",
        supports_thinking_toggle=False,
        supports_reasoning_effort=False,
        supports_enable_thinking=False,
        baseline_response_time=2.0,
        preferred_strategy=ReasoningStrategy.BUDGET_PROMPT,
    ),
    "llama-4-scout": ModelProfile(
        model_id="llama-4-scout",
        provider="meta",
        supports_thinking_toggle=False,
        supports_reasoning_effort=False,
        supports_enable_thinking=False,
        baseline_response_time=1.0,
        preferred_strategy=ReasoningStrategy.BUDGET_PROMPT,
    ),
    # ── Mistral ───────────────────────────────────────────────
    "mistral-large-2605": ModelProfile(
        model_id="mistral-large-2605",
        provider="mistral",
        supports_thinking_toggle=False,
        supports_reasoning_effort=False,
        supports_enable_thinking=False,
        baseline_response_time=3.0,
        preferred_strategy=ReasoningStrategy.BUDGET_PROMPT,
    ),
    # ── Cohere ────────────────────────────────────────────────
    "command-r-plus": ModelProfile(
        model_id="command-r-plus",
        provider="cohere",
        supports_thinking_toggle=False,
        supports_reasoning_effort=False,
        supports_enable_thinking=False,
        baseline_response_time=2.0,
        preferred_strategy=ReasoningStrategy.BUDGET_PROMPT,
    ),
}


@dataclass(frozen=True)
class ReasoningConfig:
    """User-facing configuration for reasoning behaviour in a single request.

    Combines the desired effort level with an option to include prompt-level
    hints that guide the model's deliberation budget.

    Attributes:
        effort: The reasoning effort level to apply. Defaults to
            ``ReasoningEffort.NONE``.
        prompt_hint: Whether to append prompt-level budget instructions to
            the system prompt. Defaults to ``True``.
    """

    effort: ReasoningEffort = ReasoningEffort.NONE
    prompt_hint: bool = True


_BUDGET_PROMPTS: dict[ReasoningEffort, str] = {
    ReasoningEffort.NONE: (
        "You have NO time to think. Respond immediately with ONLY the list. "
        "No analysis, no strategy discussion."
    ),
    ReasoningEffort.LOW: (
        "You have a brief moment. Think in at most 2 sentence, then output the list."
    ),
    ReasoningEffort.MEDIUM: (
        "You have time for a short assessment. Think in 5-10 sentences, then output the list."
    ),
    ReasoningEffort.HIGH: (
        "Take your time to analyze the situation thoroughly before outputting the list."
    ),
}

def get_model_profile(model_id: str) -> ModelProfile:
    """Look up the :class:`ModelProfile` for a given model identifier.

    If the model is not found in :data:`MODEL_PROFILES`, a default profile is
    returned with the supplied *model_id* substituted in.

    Args:
        model_id: Unique model identifier (e.g. ``"deepseek-v4-flash"``).

    Returns:
        The matching :class:`ModelProfile`, or a default profile if the model
        is unknown.
    """
    profile = MODEL_PROFILES.get(model_id)
    if profile is not None:
        return profile
    return replace(DEFAULT_MODEL_PROFILE, model_id=model_id)


def get_strategy(model_id: str) -> ReasoningStrategy:
    """Return the preferred reasoning strategy for a given model.

    Convenience wrapper around :func:`get_model_profile` that extracts only
    the :attr:`ModelProfile.preferred_strategy` field.

    Args:
        model_id: Unique model identifier (e.g. ``"gpt-5"``).

    Returns:
        The :class:`ReasoningStrategy` preferred for the model.
    """
    profile = get_model_profile(model_id)
    return profile.preferred_strategy


def build_api_params(config: ReasoningConfig, model_id: str) -> dict:
    """Build provider-specific API parameters for reasoning control.

    Translates the high-level :class:`ReasoningConfig` into the concrete
    keyword arguments expected by a model provider's chat-completion API,
    based on the model's supported capabilities.

    Args:
        config: The desired reasoning configuration.
        model_id: Unique model identifier used to look up the model profile.

    Returns:
        A dict of API parameters to merge into the request body. May be empty
        if the model does not support any reasoning-control parameters or if
        the strategy is ``BUDGET_PROMPT`` or ``STUBBORN``.
    """
    profile = get_model_profile(model_id)
    strategy = profile.preferred_strategy

    if strategy == ReasoningStrategy.BUDGET_PROMPT:
        return {}

    if strategy == ReasoningStrategy.STUBBORN:
        return {}

    if config.effort == ReasoningEffort.NONE:
        if profile.supports_thinking_toggle:
            return {"thinking": {"type": "disabled"}}
        if profile.supports_enable_thinking:
            return {"enable_thinking": False}
        if profile.supports_reasoning_effort:
            return {"reasoning_effort": "none"}
        return {}

    if config.effort == ReasoningEffort.LOW:
        if profile.supports_reasoning_effort:
            return {"reasoning_effort": "low"}
        if profile.supports_thinking_toggle:
            return {"thinking": {"type": "disabled"}}
        if profile.supports_enable_thinking:
            return {"enable_thinking": False}
        return {}

    return {}


def build_system_prompt(base_prompt: str, config: ReasoningConfig, model_id: str) -> str:
    """Augment a base system prompt with reasoning-budget instructions.

    Appends effort-level guidance to *base_prompt* when the model's strategy
    is ``BUDGET_PROMPT`` or when prompt hints are applicable. Returns the
    original prompt unchanged for ``STUBBORN`` models or when
    :attr:`ReasoningConfig.prompt_hint` is ``False``.

    Args:
        base_prompt: The original system prompt text.
        config: The desired reasoning configuration.
        model_id: Unique model identifier used to look up the model profile.

    Returns:
        The system prompt, potentially augmented with budget instructions.
    """
    if not config.prompt_hint:
        return base_prompt

    profile = get_model_profile(model_id)
    strategy = profile.preferred_strategy

    if strategy == ReasoningStrategy.BUDGET_PROMPT:
        budget_instruction = _BUDGET_PROMPTS.get(config.effort, "")
        if budget_instruction:
            return f"{base_prompt} {budget_instruction}"
        return base_prompt

    if strategy == ReasoningStrategy.STUBBORN:
        return base_prompt

    hint = _BUDGET_PROMPTS.get(config.effort, "")
    if not hint:
        return base_prompt
    return f"{base_prompt} {hint}"


def get_limits(config: ReasoningConfig, model_id: str) -> dict[str, float | int]:
    """Compute token and timeout limits based on config and model profile.

    Maps the current reasoning effort to a maximum token count and derives a
    dynamic timeout by multiplying the model's baseline response time by an
    effort-dependent factor.

    Args:
        config: The desired reasoning configuration.
        model_id: Unique model identifier used to look up the model profile.

    Returns:
        A dict with keys ``"max_tokens"`` (int) and ``"timeout"`` (float,
        in seconds, with a minimum of 15.0).
    """
    profile = get_model_profile(model_id)
    baseline = profile.baseline_response_time

    limits: dict[ReasoningEffort, tuple[int, float]] = {
        ReasoningEffort.NONE: (512, 3.0),
        ReasoningEffort.LOW: (1024, 4.0),
        ReasoningEffort.MEDIUM: (4096, 5.0),
        ReasoningEffort.HIGH: (16384, 10.0),
    }

    max_tokens, timeout_mult = limits[config.effort]
    return {
        "max_tokens": max_tokens,
        "timeout": max(baseline * timeout_mult, 15.0),
    }


class ReasoningModerator:
    """
    Unified reasoning control engine for LLM agents.

    Encapsulates model-specific reasoning control logic, providing a clean
    interface for preparing API requests and extracting responses.
    """

    def __init__(
        self,
        model_id: str,
        effort: ReasoningEffort = ReasoningEffort.NONE,
        prompt_hint: bool = True,
    ):
        """
        Initialize reasoning control engine.

        Args:
            model_id: Model identifier (e.g., "deepseek-v4-flash")
            effort: Reasoning effort level
            prompt_hint: Whether to add prompt-level instructions
        """
        self.model_id = model_id
        self.config = ReasoningConfig(effort=effort, prompt_hint=prompt_hint)
        self.profile = get_model_profile(model_id)

    @classmethod
    def from_config(
        cls, model_id: str, config: ReasoningConfig
    ) -> "ReasoningModerator":
        """Create a :class:`ReasoningModerator` from an existing config.

        Args:
            model_id: Model identifier (e.g. ``"deepseek-v4-flash"``).
            config: A :class:`ReasoningConfig` instance providing effort and
                prompt-hint settings.

        Returns:
            A new :class:`ReasoningModerator` initialised with the given
            parameters.
        """
        return cls(
            model_id, effort=config.effort, prompt_hint=config.prompt_hint
        )

    @property
    def strategy(self) -> ReasoningStrategy:
        """Return the preferred reasoning strategy for this moderator's model.

        Returns:
            The :class:`ReasoningStrategy` associated with the model profile.
        """
        return get_strategy(self.model_id)

    @property
    def effort(self) -> ReasoningEffort:
        """Return the current reasoning effort level.

        Returns:
            The :class:`ReasoningEffort` set on this moderator's config.
        """
        return self.config.effort

    def get_api_params(self) -> dict:
        """Build provider-specific API parameters for reasoning control.

        Delegates to :func:`build_api_params` using this moderator's config
        and model.

        Returns:
            A dict of API parameters to merge into the request body.
        """
        return build_api_params(self.config, self.model_id)

    def get_limits(self) -> dict[str, float | int]:
        """Compute token and timeout limits for the current configuration.

        Delegates to :func:`get_limits` using this moderator's config and
        model.

        Returns:
            A dict with ``"max_tokens"`` (int) and ``"timeout"`` (float,
            seconds).
        """
        return get_limits(self.config, self.model_id)

    def build_system_prompt(self, base_prompt: str) -> str:
        """Augment a base system prompt with reasoning-budget instructions.

        Delegates to :func:`build_system_prompt` using this moderator's
        config and model.

        Args:
            base_prompt: The original system prompt text.

        Returns:
            The system prompt, potentially augmented with budget
            instructions.
        """
        return build_system_prompt(base_prompt, self.config, self.model_id)

    def prepare_request_body(
        self, messages: list[dict], temperature: float = 0.9
    ) -> dict:
        """
        Prepare complete API request body.

        Args:
            messages: List of message dicts with role and content
            temperature: Sampling temperature

        Returns:
            Complete request body ready to send
        """
        limits = self.get_limits()
        return {
            "model": self.model_id,
            "messages": messages,
            "max_tokens": limits["max_tokens"],
            "temperature": temperature,
            **self.get_api_params(),
        }

    def extract_response_text(self, response_data: dict) -> tuple[str, str]:
        """
        Extract content and reasoning text from API response.

        Args:
            response_data: Parsed JSON response from API

        Returns:
            Tuple of (content, reasoning_content)
        """
        choice = response_data["choices"][0]
        message = choice["message"]
        content = message.get("content") or ""
        reasoning = message.get("reasoning_content") or ""
        return content, reasoning
