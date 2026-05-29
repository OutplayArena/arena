from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Literal


class ReasoningEffort(str, Enum):
    NONE = "none"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class ReasoningStrategy(str, Enum):
    API_CONTROL = "api_control"
    BUDGET_PROMPT = "budget_prompt"
    STUBBORN = "stubborn"


@dataclass(frozen=True)
class ModelProfile:
    model_id: str
    provider: str
    supports_thinking_toggle: bool
    supports_reasoning_effort: bool
    supports_enable_thinking: bool
    baseline_response_time: float
    preferred_strategy: ReasoningStrategy = ReasoningStrategy.API_CONTROL


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
        baseline_response_time=1.0,
        preferred_strategy=ReasoningStrategy.API_CONTROL,
    ),
    "kimi-k2.6": ModelProfile(
        model_id="kimi-k2.6",
        provider="moonshot",
        supports_thinking_toggle=True,
        supports_reasoning_effort=False,
        supports_enable_thinking=False,
        baseline_response_time=1.0,
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
    effort: ReasoningEffort = ReasoningEffort.NONE
    prompt_hint: bool = True


_BUDGET_PROMPTS: dict[ReasoningEffort, str] = {
    ReasoningEffort.NONE: (
        "You have NO time to think. Respond immediately with ONLY the list. "
        "No analysis, no strategy discussion."
    ),
    ReasoningEffort.LOW: (
        "You have a brief moment. Think in at most 1 sentence, then output the list."
    ),
    ReasoningEffort.MEDIUM: (
        "You have time for a short assessment. Think in 2-3 sentences, then output the list."
    ),
    ReasoningEffort.HIGH: (
        "Take your time to analyze the situation thoroughly before outputting the list."
    ),
}


def get_strategy(model_id: str) -> ReasoningStrategy:
    profile = MODEL_PROFILES.get(model_id)
    if profile is None:
        return ReasoningStrategy.STUBBORN
    return profile.preferred_strategy


def build_api_params(config: ReasoningConfig, model_id: str) -> dict:
    profile = MODEL_PROFILES.get(model_id)
    if profile is None:
        return {}

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
    if not config.prompt_hint:
        return base_prompt

    profile = MODEL_PROFILES.get(model_id)
    if profile is None:
        return base_prompt

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
    """Get token and timeout limits based on config and model."""
    profile = MODEL_PROFILES.get(model_id)
    baseline = profile.baseline_response_time if profile else 30.0

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


class ReasoningControlEngine:
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
        self.profile = MODEL_PROFILES.get(model_id)

    @classmethod
    def from_config(
        cls, model_id: str, config: ReasoningConfig
    ) -> "ReasoningControlEngine":
        """Create engine from existing ReasoningConfig."""
        return cls(
            model_id, effort=config.effort, prompt_hint=config.prompt_hint
        )

    @property
    def strategy(self) -> ReasoningStrategy:
        """Get the reasoning strategy for this model."""
        return get_strategy(self.model_id)

    @property
    def effort(self) -> ReasoningEffort:
        """Get the current effort level."""
        return self.config.effort

    def get_api_params(self) -> dict:
        """Get provider-specific API parameters."""
        return build_api_params(self.config, self.model_id)

    def get_limits(self) -> dict[str, float | int]:
        """Get token and timeout limits."""
        return get_limits(self.config, self.model_id)

    def build_system_prompt(self, base_prompt: str) -> str:
        """Build system prompt with reasoning budget instructions."""
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
