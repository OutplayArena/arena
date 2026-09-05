"""OpenAI function-calling definitions for the backend tools an agent can invoke.

The LLM is given these tools during the per-turn sub-loop inside
:meth:`BaseAgent._decide_with_tools`. Each tool corresponds to one of the
backend's MCP/REST endpoints:

* :func:`get_observation_tool` &mdash; render system + turn prompts.
* :func:`get_game_state_tool` &mdash; raw public state (awaiting, scores, ...).
* :func:`send_message_tool` &mdash; write to inbox. The inbox itself is no longer
  a callable tool (#122): it is auto-injected into the observation returned by
  ``get_observation``/``get_game_state``, so agents don't spend tool-call budget
  polling for messages that haven't changed.
* :func:`submit_action_tool` &mdash; commit the turn's action.

The agent also needs to *commit* an action at the end of a turn. The
``submit_action`` tool is the one that ends the loop.  Per-turn budget
(default 4) prevents runaway tool-call sequences.

These schemas are intentionally narrow: the LLM should not see
discovery tools (``list_games``, ``get_game_details``, etc.) during a
turn &mdash; those are used for one-shot setup, not for the
back-and-forth of a single move.
"""
from __future__ import annotations

from typing import Any


def get_observation_tool() -> dict[str, Any]:
    return {
        "type": "function",
        "function": {
            "name": "get_observation",
            "description": (
                "Fetch the rendered system prompt and turn prompt for your "
                "current game state. Call this at the start of every turn to "
                "know what to do."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "variant": {
                        "type": "string",
                        "enum": ["neutral", "gain_framed", "loss_framed"],
                        "description": "Prompt framing variant.",
                        "default": "neutral",
                    },
                },
                "required": [],
                "additionalProperties": False,
            },
        },
    }


def get_game_state_tool() -> dict[str, Any]:
    return {
        "type": "function",
        "function": {
            "name": "get_game_state",
            "description": (
                "Fetch the raw current game state. Returns: phase, round, "
                "awaiting (list of player IDs whose turn it is), total_scores, "
                "history, and game-specific fields."
            ),
            "parameters": {
                "type": "object",
                "properties": {},
                "required": [],
                "additionalProperties": False,
            },
        },
    }


def send_message_tool() -> dict[str, Any]:
    return {
        "type": "function",
        "function": {
            "name": "send_message",
            "description": (
                "Send a message to your opponent (or broadcast). Max 200 "
                "characters. Use strategically: honest signals or decoys."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "content": {
                        "type": "string",
                        "description": "Message text (max 200 characters).",
                        "maxLength": 200,
                    },
                    "recipient": {
                        "type": "string",
                        "description": "Target player ID or 'all'.",
                        "default": "all",
                    },
                },
                "required": ["content"],
                "additionalProperties": False,
            },
        },
    }


def submit_action_tool(action_format_hint: str) -> dict[str, Any]:
    """Schema for ``submit_action`` parameterized by the per-game action format.

    Args:
        action_format_hint: Short description of the expected action format,
            injected into the tool's description so the LLM knows what to
            produce. Per-game agents pass their game-specific hint here.
    """
    return {
        "type": "function",
        "function": {
            "name": "submit_action",
            "description": (
                "Commit your action for this round. This ends your turn. "
                f"Expected format: {action_format_hint}"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "allocation": {
                        "description": (
                            "Your action. Structure depends on the game "
                            "(see hint above)."
                        ),
                    },
                },
                "required": ["allocation"],
                "additionalProperties": False,
            },
        },
    }


def build_backend_tools(action_format_hint: str) -> list[dict[str, Any]]:
    """Return the list of tool definitions for the per-turn sub-loop."""
    return [
        get_observation_tool(),
        get_game_state_tool(),
        send_message_tool(),
        submit_action_tool(action_format_hint),
    ]


__all__ = [
    "build_backend_tools",
    "get_observation_tool",
    "get_game_state_tool",
    "send_message_tool",
    "submit_action_tool",
]
