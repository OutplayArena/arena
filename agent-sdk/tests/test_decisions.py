"""Strict benchmark decisions retain SDK parser proposals without executing defaults."""

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from outplayarena_sdk.agents.games.prisonersdilemma import PrisonersDilemmaAgent
from outplayarena_sdk.agents.games.rock_paper_scissors import RockPaperScissorsAgent
from outplayarena_sdk.agents.games.stag_hunt import StagHuntAgent
from outplayarena_sdk.base import BaseAgent, LLMConfig


def response(text: str) -> SimpleNamespace:
    """Build a model response including auditable provider and usage metadata."""
    return SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content=text))],
        model="provider-model-version",
        id="response-1",
        usage=SimpleNamespace(prompt_tokens=20, completion_tokens=1, total_tokens=21),
    )


def agent(cls: type = RockPaperScissorsAgent) -> BaseAgent:
    """Use a registered game agent without connecting an Arena server."""
    return cls(
        "A",
        "opaque-token",
        "http://offline.invalid",
        LLMConfig("test-model", "secret", max_retries=0, timeout=12),
        session_id="local-session",
        use_mcp=False,
    )


@pytest.mark.parametrize(
    "cls,choices,text",
    [
        (RockPaperScissorsAgent, ("rock", "paper", "scissors"), " PAPER \n"),
        (PrisonersDilemmaAgent, ("cooperate", "defect"), "DEFECT"),
        (StagHuntAgent, ("stag", "hare"), "stag"),
    ],
)
def test_existing_agents_and_audit_without_network(
    cls: type, choices: tuple, text: str
) -> None:
    sdk = agent(cls)
    observation = {
        "system": "Game rules and payoff table",
        "turn": "Round 1; no completed history",
    }
    with patch("outplayarena_sdk.base.OpenAI") as client:
        decision = sdk.decide_once(
            observation, {}, choices, completion=lambda messages: response(text)
        )
    client.assert_not_called()
    assert decision["action"] == text.strip().lower()
    assert decision["parse_status"] == "valid"
    assert decision["raw_response"] == text
    assert decision["fallback_used"] is False
    assert decision["messages"][1]["content"] == observation["turn"]
    assert "Tools and communication are disabled" in decision["messages"][0]["content"]
    assert decision["reported_model"] == "provider-model-version"
    assert decision["usage"]["total_tokens"] == 21
    assert "secret" not in str(decision)


@pytest.mark.parametrize(
    "text", ["", "nonsense", "rock or paper", "I choose scissors.", '"rock"']
)
def test_invalid_response_never_executes_parser_default(text: str) -> None:
    sdk = agent()
    decision = sdk.decide_once(
        {"turn": "Round 1"}, {}, sdk.OPTIONS, completion=lambda messages: response(text)
    )
    assert decision["action"] is None
    assert decision["parse_status"] == "invalid"
    assert decision["fallback_used"] is False
    assert decision["parser_proposed_action"] == sdk.parse_action(text, {})
    assert sdk.parse_action("nonsense", {}) == "rock"


def test_uses_existing_sdk_completion_client_with_explicit_retry_and_timeout() -> None:
    sdk = agent()
    with patch("outplayarena_sdk.base.OpenAI") as client:
        client.return_value.chat.completions.create.return_value = response("rock")
        result = sdk.decide_once({"turn": "Round 1"}, {}, sdk.OPTIONS)
    client.assert_called_once_with(
        base_url=sdk.llm_config.base_url, api_key="secret", max_retries=0, timeout=12
    )
    call = client.return_value.chat.completions.create.call_args.kwargs
    assert call["messages"] == result["messages"]
    assert "tools" not in call
    assert call["model"] == "test-model"


def test_legacy_default_timeout_is_preserved() -> None:
    sdk = agent()
    sdk.llm_config.timeout = None
    with patch("outplayarena_sdk.base.OpenAI") as client:
        sdk._ensure_openai()
    assert "timeout" not in client.call_args.kwargs


def test_bad_choices_and_provider_failure() -> None:
    sdk = agent()
    for choices in ((), ("rock", "rock"), (1,), ("",), ("Rock",), (" rock",)):
        with pytest.raises(ValueError):
            sdk.decide_once({"turn": "x"}, {}, choices, completion=MagicMock())
    with pytest.raises(RuntimeError):
        sdk.decide_once(
            {"turn": "x"},
            {},
            sdk.OPTIONS,
            completion=MagicMock(side_effect=RuntimeError("provider failed")),
        )
