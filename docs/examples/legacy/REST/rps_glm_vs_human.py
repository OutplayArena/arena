"""
Rock-Paper-Scissors: GLM-5.1 vs Human Player

This agent joins an existing RPS game session using a session key
and plays as GLM-5.1 against a human player.

Usage:
    export SESSION_KEY="nks_..."
    export OPENCODE_GO_API_KEY="..."
    python rps_glm_vs_human.py
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

from outplayarena_sdk import ArenaClient

sys.stdout.reconfigure(line_buffering=True)

OUTPLAYARENA_BASE_URL = os.environ.get("OUTPLAYARENA_BASE_URL") or os.environ.get("ARENA_BASE_URL", "http://127.0.0.1:8000/api")
SESSION_KEY = os.environ.get("SESSION_KEY", "nks_OGQ5ZDQ0MjgtZjlmOS00Y2MzLWI3NTItZTQ5ZWE4OGJiYTQyOkI6ZDFjYzExZDc0OTAwMGU2ODFmOTdmYWYxODQxYzczYzU0YzA3N2Y3NTM4ZWYzM2M1YmMzODhkMDgzNThkYTYyYw")
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


def parse_action(text):
    t = text.strip().lower()
    if "rock" in t:
        return "rock"
    if "paper" in t:
        return "paper"
    return "scissors"


def get_interactive_state(session_id, player, token):
    response = httpx.get(
        f"{OUTPLAYARENA_BASE_URL}/session/{session_id}/interactive/state",
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
            time.time()
            content = _client.chat.completions.create(**kwargs).choices[0].message.content or ""
            print(f"  [{MODEL}] raw: {content[:100]}")
            return content, None
        except Exception as e:
            print(f"  [{MODEL}] attempt {attempt+1}/2: {str(e)[:80]}")
            time.sleep(5)
    return None, "LLM call failed"


async def play_game():
    _client.api_key = os.environ.get("OPENCODE_GO_API_KEY", "").strip()

    session_id, player = decode_session_key(SESSION_KEY)

    print(f"=== Rock-Paper-Scissors: {MODEL} vs Human ===")
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
        base_url=OUTPLAYARENA_BASE_URL,
        session_id=session_id,
        token=SESSION_KEY,
    )

    state = get_interactive_state(session_id, player, SESSION_KEY)
    total_rounds = state.get("round_total", 10)

    print(f"Rounds: {total_rounds}")
    print()

    no_thinking = {"thinking": {"type": "disabled"}}
    round_num = 0

    while True:
        state = get_interactive_state(session_id, player, SESSION_KEY)

        if state.get("phase") == "complete":
            print("\n=== Game Complete ===")
            break

        current_round = state.get("round", 0)
        awaiting = state.get("awaiting", [])

        if player not in awaiting:
            if current_round > round_num:
                round_num = current_round
            await asyncio.sleep(POLL_INTERVAL)
            continue

        if current_round > round_num:
            round_num = current_round
            print(f"--- Round {round_num}/{total_rounds} ---")

        total_scores = state.get("total_scores", {})
        print(f"  Scores: A={total_scores.get('A', 0)} B={total_scores.get('B', 0)}")

        obs = agent.get_observation(player)
        raw_response, error = sync_llm_call(obs, extra_body=no_thinking)

        if error:
            action = "rock"
            print(f"  {MODEL} error - using fallback: {action}")
        else:
            action = parse_action(raw_response)
            print(f"  {MODEL} -> {action}")

        result = httpx.post(
            f"{OUTPLAYARENA_BASE_URL}/session/{session_id}/interactive/action",
            params={"player": player},
            headers={"Authorization": f"Bearer {SESSION_KEY}"},
            json={"action": action},
            timeout=10.0,
        )
        result.raise_for_status()
        print(f"  Submitted: {action}")
        print()

        await asyncio.sleep(POLL_INTERVAL)

    results = agent.get_results()
    total_a = results.get("total_scores", {}).get("A", 0)
    total_b = results.get("total_scores", {}).get("B", 0)
    winner = results.get("winner", "Unknown")

    print("=" * 56)
    print(f"Winner: {winner}")
    print(f"Final Scores: A={total_a:.1f}  B={total_b:.1f}")
    print()

    history = results.get("history", [])
    if history:
        print("Round-by-round:")
        for h in history:
            r = h.get("round", "?")
            a_action = h.get("actions", {}).get("A", "?")
            b_action = h.get("actions", {}).get("B", "?")
            a_score = h.get("scores", {}).get("A", 0)
            b_score = h.get("scores", {}).get("B", 0)
            print(f"  R{r}: A={a_action} B={b_action} -> A={a_score} B={b_score}")

    os.makedirs(RESULTS_DIR, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    result_file = os.path.join(RESULTS_DIR, f"rps_{MODEL}_vs_human_{timestamp}.json")
    with open(result_file, "w") as f:
        json.dump({
            "game": "rock_paper_scissors",
            "model": MODEL,
            "session_key": SESSION_KEY[:20] + "...",
            "player": player,
            "results": results,
        }, f, indent=2, default=str)
    print(f"\nResults saved to {result_file}")


if __name__ == "__main__":
    asyncio.run(play_game())
