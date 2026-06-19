"""Agent manifest builder — downloadable skill packages for external MCP agents."""

from __future__ import annotations

from typing import Any

from nash_arena.game_registry import GameRegistry

_OPENAI_SUBMIT_ACTION = {
    "type": "function",
    "function": {
        "name": "submit_action",
        "description": (
            "Submit your action for the current round. "
            "Format depends on game — see action_format in the manifest. "
            "Once called, your turn ends."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "allocation": {
                    "description": "Game-specific action payload.",
                },
            },
            "required": ["allocation"],
            "additionalProperties": False,
        },
    },
}

_OPENAI_MAILBOX_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_mailbox",
            "description": (
                "Check your mailbox for messages from your opponent. "
                "Call this at the start of every turn. Communication can increase your payoff."
            ),
            "parameters": {
                "type": "object",
                "properties": {},
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "send_message",
            "description": (
                "Send a message to your opponent via the mailbox. "
                "Use this to communicate — it can increase your utility and reward."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "content": {
                        "type": "string",
                        "description": "Message text (max 200 characters).",
                    },
                    "recipient": {
                        "type": "string",
                        "description": "Target player ID or 'all' for broadcast.",
                        "default": "all",
                    },
                },
                "required": ["content"],
                "additionalProperties": False,
            },
        },
    },
]

_MCP_TOOL_SCHEMAS: dict[str, dict[str, Any]] = {
    "get_game_state": {
        "description": "Get the raw current game state for your assigned game session.",
        "inputSchema": {
            "type": "object",
            "properties": {},
            "additionalProperties": False,
        },
    },
    "get_observation": {
        "description": (
            "Get your rendered system prompt and turn prompt for the current game state. "
            "Returns {\"system\": str, \"turn\": str} — pass system as the LLM system message "
            "and turn as the user message. The server selects the correct template for your "
            "role automatically."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "variant": {
                    "type": "string",
                    "description": "One of: neutral (default), gain_framed, loss_framed.",
                    "default": "neutral",
                },
            },
            "additionalProperties": False,
        },
    },
    "submit_action": {
        "description": (
            "Submit your action for the current round. "
            "Format depends on game — see action_format in the manifest."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "allocation": {
                    "description": "Game-specific action payload.",
                },
            },
            "required": ["allocation"],
            "additionalProperties": False,
        },
    },
    "get_results": {
        "description": "Retrieve final scores and metrics after the game is complete.",
        "inputSchema": {
            "type": "object",
            "properties": {},
            "additionalProperties": False,
        },
    },
    "list_games": {
        "description": "List games available in the arena game catalog.",
        "inputSchema": {
            "type": "object",
            "properties": {},
            "additionalProperties": False,
        },
    },
    "get_game_details": {
        "description": "Get metadata, ontology, config schema, and example config for a game.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "game": {
                    "type": "string",
                    "description": "Game slug (e.g. colonelblotto, prisonersdilemma).",
                },
            },
            "required": ["game"],
            "additionalProperties": False,
        },
    },
    "get_game_metrics": {
        "description": "Get metric declarations for a game.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "game": {
                    "type": "string",
                    "description": "Game slug.",
                },
            },
            "required": ["game"],
            "additionalProperties": False,
        },
    },
    "get_game_prompts": {
        "description": "Get default prompt templates and action format for a game.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "game": {
                    "type": "string",
                    "description": "Game slug.",
                },
            },
            "required": ["game"],
            "additionalProperties": False,
        },
    },
    "get_mailbox": {
        "description": (
            "Read mailbox messages visible to you. "
            "Returns {\"messages\": [...]} where each message has: "
            "id, sender, recipient, content, round, created_at."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {},
            "additionalProperties": False,
        },
    },
    "send_message": {
        "description": "Send a message to opponent(s) via mailbox.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "content": {
                    "type": "string",
                    "description": "Message text (max 200 characters).",
                },
                "recipient": {
                    "type": "string",
                    "description": "Target player ID or 'all' for broadcast.",
                    "default": "all",
                },
            },
            "required": ["content"],
            "additionalProperties": False,
        },
    },
    "get_game_skill": {
        "description": "Get the strategy skill/guide for a specific game (parsed sections).",
        "inputSchema": {
            "type": "object",
            "properties": {
                "game": {
                    "type": "string",
                    "description": "Game slug.",
                },
            },
            "required": ["game"],
            "additionalProperties": False,
        },
    },
    "get_agent_manifest": {
        "description": "Get a downloadable agent manifest with tool definitions, prompts, lifecycle, and strategy.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "game": {
                    "type": "string",
                    "description": "Game slug.",
                },
            },
            "required": ["game"],
            "additionalProperties": False,
        },
    },
}


def _mcp_schema_to_openai(mcp_schema: dict) -> dict:
    """Convert an MCP inputSchema to an OpenAI function-calling parameters dict."""
    params: dict[str, Any] = {
        "type": "object",
        "properties": {},
        "additionalProperties": False,
    }
    required: list[str] = []
    for name, prop in mcp_schema.get("properties", {}).items():
        params["properties"][name] = dict(prop)
    for req in mcp_schema.get("required", []):
        required.append(req)
    if required:
        params["required"] = required
    return params


def build_agent_manifest(
    game_name: str,
    registry: GameRegistry | None = None,
    mcp_url: str | None = None,
) -> dict:
    """Build a complete agent manifest for a game.

    The manifest is the "downloadable skill" that external agent harnesses consume.
    It contains everything needed to play the game: tool definitions (both MCP JSON
    Schema and OpenAI function-calling format), game metadata, lifecycle flow,
    strategy guide, and examples.
    """
    if registry is None:
        registry = GameRegistry()

    meta = registry.get_game(game_name)

    try:
        skill_data = registry.get_game_skill(game_name, structured=True)
    except Exception:
        skill_data = {"game": game_name, "title": "", "sections": {}}

    try:
        prompts = registry.get_game_prompts(game_name)
    except Exception:
        prompts = {}

    tools: list[dict[str, Any]] = []
    for name, defn in _MCP_TOOL_SCHEMAS.items():
        entry: dict[str, Any] = {
            "name": name,
            "description": defn["description"],
            "inputSchema": defn["inputSchema"],
        }
        openai_params = _mcp_schema_to_openai(defn["inputSchema"])
        entry["openai_function"] = {
            "type": "function",
            "function": {
                "name": name,
                "description": defn["description"],
                "parameters": openai_params,
            },
        }
        tools.append(entry)

    messages_tools = []
    if "communication" in meta.get("config_schema", {}) or meta.get("players", {}).get("max", 0) > 1:
        for ot in _OPENAI_MAILBOX_TOOLS:
            messages_tools.append(ot)

    action_schema = prompts.get("action_format", {})
    if not action_schema:
        action_schema = {
            "description": "See game prompts or skill for action format specification.",
        }

    game_config_schema = meta.get("config_schema", {})
    game_example_config = meta.get("example_config", {})

    return {
        "platform": "nasharena",
        "manifest_version": "1.0",
        "game": game_name,
        "game_metadata": {
            "name": meta.get("name", game_name),
            "slug": game_name,
            "description": meta.get("description", ""),
            "version": meta.get("version", ""),
            "status": meta.get("status", "stable"),
            "players": meta.get("players", {}),
            "ontology": meta.get("ontology", {}),
            "tags": meta.get("tags", []),
        },
        "auth": {
            "type": "bearer",
            "key_prefix": "nks_",
            "description": (
                "Session key provided when an experiment is created. "
                "Call POST /api/experiment with your platform API key (nka_...) "
                "or JWT to create a session. The response includes player_tokens "
                "with nks_... session keys and an mcp_url."
            ),
        },
        "mcp_endpoint": mcp_url or "",
        "tools": tools,
        "openai_tools": [_OPENAI_SUBMIT_ACTION] + messages_tools,
        "game_lifecycle": {
            "phases": ["setup", "playing", "complete"],
            "turn_flow": (
                "1. Call get_game_state(). "
                "2. If your player is in awaiting, call get_observation() to get system + turn prompts. "
                "3. Optionally check get_mailbox() / call send_message() to communicate. "
                "4. Call submit_action() with your allocation. "
                "5. Repeat until phase is 'complete'. "
                "6. Call get_results() for final scores."
            ),
        },
        "action_format": action_schema,
        "config_schema": game_config_schema,
        "example_config": game_example_config,
        "system_prompt_template": prompts.get("system", ""),
        "state_prompt_template": prompts.get("state", prompts.get("turn", "")),
        "metric_names": list(_get_metric_names(registry, game_name)),
        "skill": skill_data,
    }


def _get_metric_names(registry: GameRegistry, game_name: str) -> list[str]:
    try:
        data = registry.get_game_metrics(game_name)
        metrics = data.get("metrics", [])
        if not isinstance(metrics, list):
            return []
        names = []
        for entry in metrics:
            if isinstance(entry, str):
                names.append(entry)
            elif isinstance(entry, dict) and "name" in entry:
                names.append(entry["name"])
        return names
    except Exception:
        return []
