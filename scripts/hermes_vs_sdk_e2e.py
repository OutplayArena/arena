"""
Hermes vs NashArena SDK — end-to-end Colonel Blotto game.

Launches the hermes-agent harness (with an on-the-fly skill + MCP config)
as Player A and a NashArena SDK MCPAgent as Player B. Both play a multi-round
Colonel Blotto game through NashArena's MCP server.

Usage:
    python scripts/hermes_vs_sdk_e2e.py

Environment:
    E2E_BACKEND_URL   - backend REST API (default http://192.168.49.2:30391/api)
    E2E_MCP_URL       - MCP endpoint (default http://192.168.49.2:30391/mcp)
    HERMES_BIN        - path to hermes binary (default ~/.hermes/hermes-agent/venv/bin/hermes)

Requires:
    - minikube cluster with nasharena deployed
    - hermes-agent installed at ~/.hermes/hermes-agent/
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import threading
import time
import uuid
from pathlib import Path
from typing import Any

import httpx
import yaml

# Add SDK to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "agent-sdk" / "src"))
from nash_arena_sdk.mcp_client import MCPClient  # noqa: E402

# ── Configuration ────────────────────────────────────────────────────────────

BACKEND_URL = os.environ.get("E2E_BACKEND_URL", "http://192.168.49.2:30391/api")
MCP_URL = os.environ.get("E2E_MCP_URL", "http://192.168.49.2:30391/mcp")
HERMES_BIN = os.environ.get(
    "HERMES_BIN",
    os.path.expanduser("~/.hermes/hermes-agent/venv/bin/hermes"),
)
HERMES_TIMEOUT = int(os.environ.get("HERMES_TIMEOUT", "300"))
GAME_ROUNDS = int(os.environ.get("HERMES_GAME_ROUNDS", "3"))
GAME_N_FIELDS = int(os.environ.get("HERMES_N_FIELDS", "5"))
GAME_TOTAL = int(os.environ.get("HERMES_TOTAL_BUDGET", "100"))

# ── Helpers (mirror test_mcp_e2e.py pattern) ─────────────────────────────────

def _kubectl_exec(script: str) -> str:
    namespace = os.environ.get("E2E_NAMESPACE", "nasharena")
    result = subprocess.run(
        [
            "kubectl", "exec", "-n", namespace,
            "deployment/nasharena-backend", "--",
            "python3", "-c", script,
        ],
        capture_output=True, text=True, timeout=30,
    )
    if result.returncode != 0:
        raise RuntimeError(f"kubectl exec failed:\n{result.stderr}")
    return result.stdout.strip()


def _create_test_user() -> tuple[str, str]:
    uid = str(uuid.uuid4())
    email = f"e2e-hermes-{uid[:8]}@test.local"
    output = _kubectl_exec(f"""
import asyncio
from uuid import UUID
from nash_arena.db import async_session
from nash_arena.models.user import User
from nash_arena.auth.jwt import create_access_token

async def main():
    user_id = UUID("{uid}")
    async with async_session() as db:
        db.add(User(id=user_id, email="{email}", name="E2E Hermes Test", provider="e2e", provider_user_id="{uid}"))
        await db.commit()
    print("{uid}" + "|" + create_access_token("{uid}"))

asyncio.run(main())
""")
    user_id, token = output.split("|", 1)
    return user_id, f"Bearer {token}"


def _delete_test_user(user_id: str) -> None:
    _kubectl_exec(f"""
import asyncio
from nash_arena.db import async_session
from nash_arena.models.user import User
from sqlalchemy import delete

async def main():
    async with async_session() as db:
        await db.execute(delete(User).where(User.id == "{user_id}"))
        await db.commit()

asyncio.run(main())
""")


# ── Skill builder ────────────────────────────────────────────────────────────

def _build_skill_content(manifest: dict) -> str:
    """Build a hermes SKILL.md from the NashArena agent manifest."""
    tools_lines: list[str] = []
    for t in manifest.get("tools", []):
        name = t["name"]
        desc = t.get("description", "")
        params = t.get("inputSchema", {}).get("properties", {})
        param_str = ", ".join(
            f"{p}: {info.get('type', 'any')}" for p, info in params.items()
        )
        tools_lines.append(
            f"- `mcp_nasharena_{name}({param_str})` — {desc}"
        )

    skill = manifest.get("skill", {})
    sections = skill.get("sections", {})
    lifecycle = manifest.get("game_lifecycle", {})
    action_fmt = manifest.get("action_format", {})

    return f"""---
name: nasharena-colonel-blotto
description: "Play Colonel Blotto on NashArena using MCP tools"
version: 1.0.0
author: nasharena
tags: [nasharena, game-theory, colonel-blotto, strategy]
---

# Colonel Blotto on NashArena

You are playing Colonel Blotto through NashArena's MCP server.
All MCP tools are prefixed `mcp_nasharena_`.

## Objective
{sections.get('objective', 'Win more battlefields than your opponent.')}

## Available MCP Tools

{chr(10).join(tools_lines)}

## Game Lifecycle

{lifecycle.get('turn_flow', '1. Check get_game_state. 2. Get observation. 3. Submit action. 4. Repeat.')}

## Action Format

```json
{json.dumps(action_fmt, indent=2)}
```

## Rules
{sections.get('rules', 'Use MCP tools only. Follow the action format.')}

## Strategy Hints
{sections.get('strategy_hints', sections.get('strategy_notes', 'Balance between concentrating and spreading forces.'))}

## Critical Instructions
- ALL tools are called as `mcp_nasharena_<tool_name>`
- Start by calling `mcp_nasharena_get_game_state` to see the current state
- When it's your turn (you appear in `awaiting`), call `mcp_nasharena_get_observation` then `mcp_nasharena_submit_action`
- If you're NOT in `awaiting`, call `mcp_nasharena_get_game_state` again
- Keep playing until `mcp_nasharena_get_game_state` shows `phase: complete`
- Then call `mcp_nasharena_get_results` for final scores
"""


# ── Hermes setup ─────────────────────────────────────────────────────────────

def _setup_hermes_home(
    mcp_url: str,
    session_key: str,
    skill_content: str,
) -> str:
    """Create a temporary hermes home with NashArena MCP config and skill.

    Merges the real hermes config (model/provider settings) with our
    NashArena MCP config so the agent can connect to both its LLM and
    the game server.
    """
    hermes_home = tempfile.mkdtemp(prefix="hermes_nasharena_")

    # Load the real hermes config for model/provider settings
    real_home = os.environ.get("HERMES_HOME", os.path.expanduser("~/.hermes"))
    real_config_path = Path(real_home) / "config.yaml"
    if real_config_path.exists():
        base_config = yaml.safe_load(real_config_path.read_text(encoding="utf-8")) or {}
    else:
        base_config = {}

    # Merge: keep real config, add/override MCP servers
    base_config.setdefault("mcp_servers", {})
    base_config["mcp_servers"]["nasharena"] = {
        "url": mcp_url,
        "headers": {"Authorization": f"Bearer {session_key}"},
        "timeout": 120,
    }

    config_path = Path(hermes_home) / "config.yaml"
    config_path.write_text(yaml.dump(base_config), encoding="utf-8")

    # Copy skills directory if it exists (for any built-in skills)
    real_skills = Path(real_home) / "skills"
    if real_skills.exists():
        import shutil
        shutil.copytree(real_skills, Path(hermes_home) / "skills", symlinks=True, dirs_exist_ok=True)

    # Write our NashArena skill
    skill_dir = Path(hermes_home) / "skills" / "nasharena-colonel-blotto"
    skill_dir.mkdir(parents=True, exist_ok=True)
    (skill_dir / "SKILL.md").write_text(skill_content, encoding="utf-8")

    return hermes_home


def _hermes_oneshot_prompt(player: str, rounds: int, n_fields: int, total: int) -> str:
    """Build the oneshot prompt that tells hermes to play autonomously."""
    return (
        f"You are Player {player} in a Colonel Blotto game on NashArena. "
        f"The game has {rounds} rounds, {n_fields} battlefields, and you have {total} troops per round.\n\n"
        f"CRITICAL RULE: DO NOT write any text responses. ONLY make tool calls. "
        f"Never ask if you should continue — just do it. "
        f"Never describe what you see — just act on it. "
        f"The ONLY time you may write text is when the game is complete to report the final scores.\n\n"
        f"Loop these steps silently until the game ends:\n"
        f"1. Call mcp_nasharena_get_game_state\n"
        f"2. If phase is complete → call mcp_nasharena_get_results, then output the scores and stop.\n"
        f"3. If your player ID ({player}) is in awaiting → call mcp_nasharena_get_observation, "
        f"then immediately call mcp_nasharena_submit_action with your allocation.\n"
        f"4. If NOT in awaiting → go back to step 1.\n\n"
        f"Use strategic allocations. You have {total} troops across {n_fields} battlefields. "
        f"Play ALL {rounds} rounds without stopping."
    )


# ── SDK counterpart ──────────────────────────────────────────────────────────

def _run_sdk_player(
    mcp_url: str,
    session_key: str,
    player: str,
    n_fields: int,
    total: int,
    result_holder: dict,
) -> None:
    """SDK agent that plays as the counterpart using even-split strategy."""
    try:
        with MCPClient(mcp_url, session_key) as client:
            while True:
                state = client.get_game_state()
                if state.get("phase") == "complete":
                    result_holder["results"] = client.get_results()
                    result_holder["completed"] = True
                    return

                if player in state.get("awaiting", []):
                    client.get_observation()
                    # Simple even-split strategy
                    base = total // n_fields
                    remainder = total % n_fields
                    allocation = [base + (1 if i < remainder else 0) for i in range(n_fields)]
                    client.submit_action(allocation)

                time.sleep(0.3)
    except Exception as exc:
        result_holder["error"] = str(exc)


# ── Main orchestrator ────────────────────────────────────────────────────────

def run_hermes_vs_sdk(
    backend_url: str | None = None,
    mcp_url: str | None = None,
    bearer_token: str | None = None,
    rounds: int | None = None,
    n_fields: int | None = None,
    total: int | None = None,
) -> dict[str, Any]:
    """Run a full hermes vs SDK Colonel Blotto game.

    Returns a dict with keys: session_id, hermes_rc, hermes_stdout,
    hermes_stderr, results, sdk_results, error.
    """
    backend_url = backend_url or BACKEND_URL
    mcp_url = mcp_url or MCP_URL
    rounds = rounds or GAME_ROUNDS
    n_fields = n_fields or GAME_N_FIELDS
    total = total or GAME_TOTAL

    # 1. Create test user and session
    user_id, bearer = None, bearer_token
    if bearer is None:
        user_id, bearer = _create_test_user()

    try:
        with httpx.Client(base_url=backend_url, timeout=30.0) as api:
            resp = api.post(
                "/experiment",
                json={
                    "game": "colonelblotto",
                    "players": 2,
                    "n_fields": n_fields,
                    "total": total,
                    "rounds": rounds,
                    "seed": 42,
                },
                headers={"Authorization": bearer},
            )
            resp.raise_for_status()
            data = resp.json()
            session_id = data["session_id"]
            token_a = data["player_tokens"]["A"]
            token_b = data["player_tokens"]["B"]
            mcp_url_val = data.get("mcp_url", mcp_url)

            # 2. Fetch manifest
            manifest_resp = api.get("/games/colonelblotto/manifest")
            manifest_resp.raise_for_status()
            manifest = manifest_resp.json()

    except Exception as exc:
        if user_id:
            _delete_test_user(user_id)
        return {"error": f"Session creation failed: {exc}"}

    # 3. Build skill and hermes home
    skill_content = _build_skill_content(manifest)
    hermes_home = _setup_hermes_home(mcp_url_val, token_a, skill_content)

    # 4. Launch both agents
    sdk_result: dict[str, Any] = {}
    sdk_thread = threading.Thread(
        target=_run_sdk_player,
        args=(mcp_url_val, token_b, "B", n_fields, total, sdk_result),
        daemon=True,
    )
    sdk_thread.start()
    time.sleep(0.5)  # Give SDK agent a head start to connect

    # 5. Launch hermes
    prompt = _hermes_oneshot_prompt("A", rounds, n_fields, total)
    env = os.environ.copy()
    env["HERMES_HOME"] = hermes_home

    try:
        hermes_proc = subprocess.run(
            [HERMES_BIN, "-z", prompt, "--skills", "nasharena-colonel-blotto", "--cli"],
            env=env,
            capture_output=True,
            text=True,
            timeout=HERMES_TIMEOUT,
        )
    except subprocess.TimeoutExpired:
        return {
            "session_id": session_id,
            "error": f"Hermes timed out after {HERMES_TIMEOUT}s",
        }

    # 6. Wait for SDK agent
    sdk_thread.join(timeout=30)

    # 7. Fetch final results
    final_results = None
    try:
        with MCPClient(mcp_url_val, token_a) as client:
            final_results = client.get_results()
    except Exception as exc:
        final_results = {"error": str(exc)}

    # 8. Cleanup
    if user_id:
        _delete_test_user(user_id)

    return {
        "session_id": session_id,
        "hermes_rc": hermes_proc.returncode,
        "hermes_stdout": hermes_proc.stdout[-2000:] if hermes_proc.stdout else "",
        "hermes_stderr": hermes_proc.stderr[-2000:] if hermes_proc.stderr else "",
        "results": final_results,
        "sdk_results": sdk_result.get("results"),
        "sdk_completed": sdk_result.get("completed", False),
        "error": sdk_result.get("error"),
    }


# ── CLI entrypoint ───────────────────────────────────────────────────────────

if __name__ == "__main__":
    result = run_hermes_vs_sdk()
    print(json.dumps({k: v for k, v in result.items() if k != "hermes_stderr"}, indent=2))
    if result.get("hermes_stderr"):
        print("\n# Hermes stderr (last 2000 chars):")
        print(result["hermes_stderr"])
