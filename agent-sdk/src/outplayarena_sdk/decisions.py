"""Auditable single-response decisions using the existing SDK model client."""

from collections.abc import Callable, Sequence
from copy import deepcopy
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from outplayarena_sdk.base import BaseAgent


def decision_messages(observation: dict, choices: Sequence[str]) -> list[dict]:
    """Construct the exact plain-text prompts, including strict action instructions."""
    if (
        not choices
        or any(
            not isinstance(a, str) or not a or a != a.strip().lower() for a in choices
        )
        or len(set(choices)) != len(choices)
    ):
        raise ValueError("choices must contain canonical action strings")
    messages = [
        {
            "role": "system",
            "content": observation.get("system", "")
            + "\n"
            + "Tools and communication are disabled for this decision. Return exactly one of: "
            + ", ".join(choices)
            + ".",
        },
        {"role": "user", "content": observation["turn"]},
    ]
    return messages


def decide_once(
    agent: "BaseAgent",
    observation: dict,
    state: dict,
    choices: Sequence[str],
    completion: Callable[[list[dict]], Any] | None = None,
) -> dict:
    """Make one plain-text decision, rejecting implicit parser fallbacks.

    Args:
        agent: An existing per-game SDK agent.
        observation: Game observation containing system and turn prompts.
        state: Past-only public state used by the game's action parser.
        choices: Canonical allowed actions for strict benchmark validation.
        completion: Optional injected completion for offline testing.

    Returns:
        Exact messages, raw text, parser proposal, strict action validity,
        and available provider response metadata. Invalid text has no action.
    """
    messages = decision_messages(observation, choices)
    agent.on_observation(deepcopy(observation), deepcopy(state))
    if completion is None:
        agent._ensure_openai()
        completion = agent._call_llm_plain
    response = completion(deepcopy(messages))
    raw = response.choices[0].message.content
    raw = raw if isinstance(raw, str) else ""
    proposal = agent.parse_action(raw, deepcopy(state))
    canonical = raw.strip().lower()
    valid = canonical in choices and proposal == canonical
    usage = getattr(response, "usage", None)
    tokens = {
        key: value
        for key in ("prompt_tokens", "completion_tokens", "total_tokens")
        if isinstance((value := getattr(usage, key, None)), int) and value >= 0
    }
    decision = {
        "messages": messages,
        "raw_response": raw,
        "parser_proposed_action": proposal,
        "action": canonical if valid else None,
        "parse_status": "valid" if valid else "invalid",
        "fallback_used": False,
        "response_id": getattr(response, "id", None),
        "reported_model": getattr(response, "model", None),
        "usage": tokens,
    }
    if valid:
        agent.on_action_decision(canonical, raw)
    return decision
