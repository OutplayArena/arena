import pytest

from nash_arena.reasoning import (
    MODEL_PROFILES,
    ReasoningConfig,
    ReasoningControlEngine,
    ReasoningEffort,
    ReasoningStrategy,
    build_api_params,
    build_system_prompt,
    get_limits,
)


class TestBuildApiParams:
    def test_none_effort_with_thinking_toggle(self):
        config = ReasoningConfig(effort=ReasoningEffort.NONE)
        params = build_api_params(config, "deepseek-v4-flash")
        assert params == {"thinking": {"type": "disabled"}}

    def test_none_effort_with_enable_thinking(self):
        config = ReasoningConfig(effort=ReasoningEffort.NONE)
        params = build_api_params(config, "qwen3.5-plus")
        assert params == {"enable_thinking": False}

    def test_none_effort_no_support(self):
        config = ReasoningConfig(effort=ReasoningEffort.NONE)
        params = build_api_params(config, "mimo-v2.5")
        assert params == {}

    def test_none_effort_unknown_model(self):
        config = ReasoningConfig(effort=ReasoningEffort.NONE)
        params = build_api_params(config, "unknown-model")
        assert params == {}

    def test_low_effort_with_reasoning_effort_support(self):
        config = ReasoningConfig(effort=ReasoningEffort.LOW)
        params = build_api_params(config, "deepseek-v4-flash")
        assert params == {"reasoning_effort": "low"}

    def test_low_effort_falls_back_to_thinking_toggle(self):
        config = ReasoningConfig(effort=ReasoningEffort.LOW)
        params = build_api_params(config, "deepseek-v4-pro")
        assert params == {"thinking": {"type": "disabled"}}

    def test_low_effort_falls_back_to_enable_thinking(self):
        config = ReasoningConfig(effort=ReasoningEffort.LOW)
        params = build_api_params(config, "qwen3.5-plus")
        assert params == {"enable_thinking": False}

    def test_medium_effort_returns_empty(self):
        config = ReasoningConfig(effort=ReasoningEffort.MEDIUM)
        params = build_api_params(config, "deepseek-v4-flash")
        assert params == {}

    def test_high_effort_returns_empty(self):
        config = ReasoningConfig(effort=ReasoningEffort.HIGH)
        params = build_api_params(config, "deepseek-v4-flash")
        assert params == {}


class TestBuildSystemPrompt:
    def test_none_effort_adds_hint(self):
        config = ReasoningConfig(effort=ReasoningEffort.NONE)
        result = build_system_prompt("Base prompt.", config, "deepseek-v4-flash")
        assert "NO time to think" in result

    def test_low_effort_adds_hint(self):
        config = ReasoningConfig(effort=ReasoningEffort.LOW)
        result = build_system_prompt("Base prompt.", config, "deepseek-v4-flash")
        assert "brief moment" in result

    def test_medium_effort_adds_hint(self):
        config = ReasoningConfig(effort=ReasoningEffort.MEDIUM)
        result = build_system_prompt("Base prompt.", config, "deepseek-v4-flash")
        assert "short assessment" in result

    def test_high_effort_adds_hint(self):
        config = ReasoningConfig(effort=ReasoningEffort.HIGH)
        result = build_system_prompt("Base prompt.", config, "deepseek-v4-flash")
        assert "analyze the situation thoroughly" in result

    def test_prompt_hint_disabled(self):
        config = ReasoningConfig(effort=ReasoningEffort.NONE, prompt_hint=False)
        result = build_system_prompt("Base prompt.", config, "deepseek-v4-flash")
        assert result == "Base prompt."

    def test_budget_prompt_strategy(self):
        config = ReasoningConfig(effort=ReasoningEffort.NONE)
        result = build_system_prompt("You are a General.", config, "glm-5.1")
        assert "NO time to think" in result

    def test_stubborn_strategy_no_hint(self):
        config = ReasoningConfig(effort=ReasoningEffort.NONE)
        result = build_system_prompt("You are a General.", config, "mimo-v2.5")
        assert result == "You are a General."


class TestGetLimits:
    def test_none_effort_limits(self):
        config = ReasoningConfig(effort=ReasoningEffort.NONE)
        limits = get_limits(config, "deepseek-v4-flash")
        assert limits["max_tokens"] == 512
        assert limits["timeout"] == 21.0

    def test_low_effort_limits(self):
        config = ReasoningConfig(effort=ReasoningEffort.LOW)
        limits = get_limits(config, "deepseek-v4-flash")
        assert limits["max_tokens"] == 1024
        assert limits["timeout"] == 28.0

    def test_medium_effort_limits(self):
        config = ReasoningConfig(effort=ReasoningEffort.MEDIUM)
        limits = get_limits(config, "deepseek-v4-flash")
        assert limits["max_tokens"] == 4096
        assert limits["timeout"] == 35.0

    def test_high_effort_limits(self):
        config = ReasoningConfig(effort=ReasoningEffort.HIGH)
        limits = get_limits(config, "deepseek-v4-flash")
        assert limits["max_tokens"] == 16384
        assert limits["timeout"] == 70.0

    def test_unknown_model_uses_default_baseline(self):
        config = ReasoningConfig(effort=ReasoningEffort.NONE)
        limits = get_limits(config, "unknown-model")
        assert limits["max_tokens"] == 512
        assert limits["timeout"] == 90.0

    def test_timeout_minimum_is_15(self):
        config = ReasoningConfig(effort=ReasoningEffort.NONE)
        limits = get_limits(config, "kimi-k2.5")
        assert limits["timeout"] >= 15.0


class TestModelProfiles:
    def test_all_profiles_have_required_fields(self):
        for model_id, profile in MODEL_PROFILES.items():
            assert profile.model_id == model_id
            assert profile.provider
            assert isinstance(profile.supports_thinking_toggle, bool)
            assert isinstance(profile.supports_reasoning_effort, bool)
            assert isinstance(profile.supports_enable_thinking, bool)
            assert profile.baseline_response_time > 0


class TestReasoningControlEngine:
    def test_init_with_defaults(self):
        engine = ReasoningControlEngine("deepseek-v4-flash")
        assert engine.model_id == "deepseek-v4-flash"
        assert engine.effort == ReasoningEffort.NONE
        assert engine.config.prompt_hint is True

    def test_init_with_custom_effort(self):
        engine = ReasoningControlEngine("kimi-k2.5", effort=ReasoningEffort.HIGH)
        assert engine.effort == ReasoningEffort.HIGH

    def test_init_with_prompt_hint_disabled(self):
        engine = ReasoningControlEngine("glm-5.1", prompt_hint=False)
        assert engine.config.prompt_hint is False

    def test_from_config(self):
        config = ReasoningConfig(effort=ReasoningEffort.LOW, prompt_hint=False)
        engine = ReasoningControlEngine.from_config("deepseek-v4-pro", config)
        assert engine.model_id == "deepseek-v4-pro"
        assert engine.effort == ReasoningEffort.LOW
        assert engine.config.prompt_hint is False

    def test_strategy_property_api_control(self):
        engine = ReasoningControlEngine("deepseek-v4-flash")
        assert engine.strategy == ReasoningStrategy.API_CONTROL

    def test_strategy_property_budget_prompt(self):
        engine = ReasoningControlEngine("glm-5.1")
        assert engine.strategy == ReasoningStrategy.BUDGET_PROMPT

    def test_strategy_property_stubborn(self):
        engine = ReasoningControlEngine("mimo-v2.5")
        assert engine.strategy == ReasoningStrategy.STUBBORN

    def test_get_api_params_delegates(self):
        engine = ReasoningControlEngine("deepseek-v4-flash", effort=ReasoningEffort.NONE)
        params = engine.get_api_params()
        assert params == {"thinking": {"type": "disabled"}}

    def test_get_limits_delegates(self):
        engine = ReasoningControlEngine("deepseek-v4-flash", effort=ReasoningEffort.NONE)
        limits = engine.get_limits()
        assert limits["max_tokens"] == 512
        assert limits["timeout"] == 21.0

    def test_build_system_prompt_delegates(self):
        engine = ReasoningControlEngine("glm-5.1", effort=ReasoningEffort.NONE)
        result = engine.build_system_prompt("You are a General.")
        assert "NO time to think" in result

    def test_prepare_request_body_includes_model(self):
        engine = ReasoningControlEngine("deepseek-v4-flash")
        messages = [{"role": "user", "content": "test"}]
        body = engine.prepare_request_body(messages)
        assert body["model"] == "deepseek-v4-flash"

    def test_prepare_request_body_includes_messages(self):
        engine = ReasoningControlEngine("deepseek-v4-flash")
        messages = [
            {"role": "system", "content": "sys"},
            {"role": "user", "content": "usr"},
        ]
        body = engine.prepare_request_body(messages)
        assert body["messages"] == messages

    def test_prepare_request_body_includes_limits(self):
        engine = ReasoningControlEngine("deepseek-v4-flash", effort=ReasoningEffort.LOW)
        body = engine.prepare_request_body([])
        assert body["max_tokens"] == 1024

    def test_prepare_request_body_includes_api_params(self):
        engine = ReasoningControlEngine("deepseek-v4-flash", effort=ReasoningEffort.NONE)
        body = engine.prepare_request_body([])
        assert body["thinking"] == {"type": "disabled"}

    def test_prepare_request_body_custom_temperature(self):
        engine = ReasoningControlEngine("deepseek-v4-flash")
        body = engine.prepare_request_body([], temperature=0.5)
        assert body["temperature"] == 0.5

    def test_prepare_request_body_default_temperature(self):
        engine = ReasoningControlEngine("deepseek-v4-flash")
        body = engine.prepare_request_body([])
        assert body["temperature"] == 0.9

    def test_extract_response_text_content_only(self):
        engine = ReasoningControlEngine("deepseek-v4-flash")
        response_data = {
            "choices": [{"message": {"content": "[20,20,20,20,20]", "reasoning_content": None}}]
        }
        content, reasoning = engine.extract_response_text(response_data)
        assert content == "[20,20,20,20,20]"
        assert reasoning == ""

    def test_extract_response_text_reasoning_fallback(self):
        engine = ReasoningControlEngine("deepseek-v4-flash")
        response_data = {
            "choices": [{"message": {"content": "", "reasoning_content": "thinking..."}}]
        }
        content, reasoning = engine.extract_response_text(response_data)
        assert content == ""
        assert reasoning == "thinking..."

    def test_extract_response_text_both_present(self):
        engine = ReasoningControlEngine("deepseek-v4-flash")
        response_data = {
            "choices": [{"message": {"content": "[10,20,30,20,20]", "reasoning_content": "let me think"}}]
        }
        content, reasoning = engine.extract_response_text(response_data)
        assert content == "[10,20,30,20,20]"
        assert reasoning == "let me think"

    def test_extract_response_text_missing_fields(self):
        engine = ReasoningControlEngine("deepseek-v4-flash")
        response_data = {"choices": [{"message": {}}]}
        content, reasoning = engine.extract_response_text(response_data)
        assert content == ""
        assert reasoning == ""

    def test_profile_attribute_known_model(self):
        engine = ReasoningControlEngine("kimi-k2.5")
        assert engine.profile is not None
        assert engine.profile.provider == "moonshot"

    def test_profile_attribute_unknown_model(self):
        engine = ReasoningControlEngine("nonexistent-model")
        assert engine.profile is None
