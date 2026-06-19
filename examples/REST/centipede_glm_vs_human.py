"""
Centipede: GLM-5.1 vs Human Player

This agent joins an existing Centipede game session using a session key
and plays as GLM-5.1 against a human player.

Usage:
    export SESSION_KEY="nks_..."
    export OPENCODE_GO_API_KEY="..."
    python centipede_glm_vs_human.py
"""

import asyncio
import base64
import os
import sys
import time
import json
from datetime import datetime, timezone

import httpx
from openai import OpenAI

from outplaylabs_arena_sdk import ArenaClient

sys.stdout.reconfigure(line_buffering=True)

OUTPLAYLABS_ARENA_BASE_URL = os.environ.get("OUTPLAYLABS_ARENA_BASE_URL") or os.environ.get("ARENA_BASE_URL", "http://127.0.0.1:8000/api")
SESSION_KEY = os.environ.get("SESSION_KEY", "nks_YjA1ZGU2NGItNGZiZi00ZWVmLWJkZjktODVkMjliYjcyYTk3OkI6MDE5OTIyZWRlZmFkZGZlMWZhMTFjZDhmN2I5OGFjOTNiYjk5YjEyODg1ZTlhNGY4ZmY5OTNjOTQ3NzMzYzAwNQ")
OPENCODE_GO_API_BASE = "https://opencode.ai/zen/v1"
RESULTS_DIR = os.path.join(os.path.dirname(__file__), "..", "results")

_client = OpenAI(
    base_url=OPENCODE_GO_API_BASE,
    api_key=os.environ.get("OPENCODE_GO_API_KEY", "").strip(),
)

MODEL = "glm-5.1"
POLL_INTERVAL = 2.0


def decode_session_key(key):
    payload = key[4:]
    payload += "=" * (4 - len(payload) % 4)
    decoded = base64.urlsafe_b64decode(payload).decode()
    parts = decoded.split(":")
    return parts[0], parts[1]


def parse_move(text):
    t = text.strip().lower()
    if "take" in t:
        return "take"
    return "pass"


def get_interactive_state(session_id, player, token):
    response = httpx.get(
        f"{OUTPLAYLABS_ARENA_BASE_URL}/session/{session_id}/interactive/state",
        params={"player": player},
        headers={"Authorization": f"Bearer {token}"},
        timeout=10.0,
    )
    response.raise_for_status()
    return response.json()


def sync_llm_call(observation, extra_body=None):
    kwargs = dict(
        model=MODEL,
        messages=[
            {"role": "system", "content": observation["system"]},
            {"role": "user", "content": observation["turn"]},
        ],
        max_tokens=64,
        temperature=0.7,
    )
    if extra_body:
        kwargs["extra_body"] = extra_body
    for attempt in range(2):
        try:
            t0 = time.time()
            content = _client.chat.completions.create(**kwargs).choices[0].message.content or ""
            move = parse_move(content)
            print(f"  [{MODEL}] {time.time()-t0:.1f}s -> {move}")
            return move, None
        except Exception as e:
            print(f"  [{MODEL}] attempt {attempt+1}/2: {str(e)[:80]}")
            time.sleep(5)
    return None, "LLM call failed"


async def play_game():
    _client.api_key = os.environ.get("OPENCODE_GO_API_KEY", "").strip()

    session_id, player = decode_session_key(SESSION_KEY)

    print(f"=== Centipede: {MODEL} vs Human ===")
    print(f"Connected as player: {player}")
    print(f"Session: {session_id}")
    print()

    print("Warming up LLM API...")
    try:
        t0 = time.time()
        _client.chat.completions.create(
            model=MODEL, messages=[{"role": "user", "content": "Say 'ready'"}],
            max_tokens=16, temperature=0,
        )
        print(f"  [{MODEL}] warmup OK ({time.time() - t0:.1f}s)")
    except Exception as e:
        print(f"  [{MODEL}] warmup failed ({e}), continuing anyway")
    print()

    agent = ArenaClient(
        base_url=OUTPLAYLABS_ARENA_BASE_URL,
        session_id=session_id,
        token=SESSION_KEY,
    )

    no_thinking = {"thinking": {"type": "disabled"}}
    last_step = 0

    while True:
        state = get_interactive_state(session_id, player, SESSION_KEY)

        if state.get("phase") == "complete":
            print("\n=== Game Complete ===")
            break

        step = state.get("step", 0)
        max_steps = state.get("max_steps", 0)
        awaiting = state.get("awaiting", [])
        pot_a = state.get("pot_a", 0)
        pot_b = state.get("pot_b", 0)
        current = state.get("current_player", "?")

        if step > last_step:
            last_step = step
            print(f"--- Step {step}/{max_steps} | Pots: A={pot_a:.0f} B={pot_b:.0f} | Waiting on: {current} ---")

        if player not in awaiting:
            await asyncio.sleep(POLL_INTERVAL)
            continue

        obs = agent.get_observation(player)
        move, error = sync_llm_call(obs, extra_body=no_thinking)

        if error:
            move = "pass"
            print(f"  {MODEL} error - using fallback: {move}")

        agent.submit_action(move)
        print(f"  Action submitted: {move}")
        print()

        await asyncio.sleep(POLL_INTERVAL)

    results = agent.get_results()
    total_a = results.get("total_scores", {}).get("A", 0)
    total_b = results.get("total_scores", {}).get("B", 0)
    winner = results.get("winner", "Unknown")
    ended_by = results.get("game_ended_by", "?")
    history = results.get("history", [])

    print("=" * 56)
    print(f"Winner: {winner}")
    print(f"Final: A={total_a:.1f}  B={total_b:.1f}")
    print(f"Game ended by: {ended_by}")
    print()

    print("─ History ─")
    for entry in history:
        print(f"  Step {entry.get('step', '?')}: Player {entry.get('player', '?')} -> {entry.get('action', '?')}")

    os.makedirs(RESULTS_DIR, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    result_file = os.path.join(RESULTS_DIR, f"centipede_{MODEL}_vs_human_{timestamp}.json")
    with open(result_file, "w") as f:
        json.dump({
            "game": "centipede",
            "model": MODEL,
            "session_key": SESSION_KEY[:20] + "...",
            "player": player,
            "results": results,
        }, f, indent=2, default=str)
    print(f"\nResults saved to {result_file}")


if __name__ == "__main__":
    asyncio.run(play_game())
