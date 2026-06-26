"""
Battle of the Sexes: GLM-5.1 vs Human Player

This agent joins an existing Battle of the Sexes game session using a session key
and plays as GLM-5.1 against a human player.

Usage:
    export SESSION_KEY="nks_..."  # Session key for the game
    export JWT_SECRET="..."       # JWT secret used to create the session key
    export OPENCODE_GO_API_KEY="..."  # API key for GLM-5.1
    python battle_of_the_sexes_glm_vs_human.py

The session key encodes the session ID and player assignment (A or B).
Player A prefers "opera", Player B prefers "football".
"""

import asyncio
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
SESSION_KEY = os.environ.get("SESSION_KEY", "nks_MWViZTNlN2EtZTRlZi00ZjNmLTk0MmUtYmUxMDBjYTRkMGMxOkI6MTllODg4ZmJmODc5M2QxMTM1Yzc3YWE4OGMxYjQ0OTE1MzEwMjhjMDY3OWE0NWRjNjJkOWVmYTQ4Zjc3MWQ4MA")
OPENCODE_GO_API_BASE = "https://opencode.ai/zen/v1"
RESULTS_DIR = os.path.join(os.path.dirname(__file__), "..", "results")

_client = OpenAI(
    base_url=OPENCODE_GO_API_BASE,
    api_key=os.environ.get("OPENCODE_GO_API_KEY", "").strip(),
)

MODEL = "glm-5.1"
POLL_INTERVAL = 2.0

OPTION_A = "opera"
OPTION_B = "football"


def parse_move(text):
    t = text.strip().lower()
    if OPTION_B in t:
        return OPTION_B
    return OPTION_A


def get_interactive_state(session_id, player, token):
    """Get state directly from interactive endpoint, bypassing cache."""
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

    print(f"=== Battle of the Sexes: {MODEL} vs Human ===")
    print(f"Options: {OPTION_A} vs {OPTION_B}")
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

    # Session info decoded from session key
    session_id = "1ebe3e7a-e4ef-4f3f-942e-be100ca4d0c1"
    player = "B"

    agent = ArenaClient(
        base_url=OUTPLAYARENA_BASE_URL,
        session_id=session_id,
        token=SESSION_KEY,
    )
    print(f"Connected as player: {player}")
    print(f"Session: {session_id}")
    print()

    no_thinking = {"thinking": {"type": "disabled"}}
    round_num = 0

    while True:
        state = get_interactive_state(session_id, player, SESSION_KEY)
        
        if state.get("phase") == "complete":
            print("\n=== Game Complete ===")
            break

        current_round = state.get("round", 0)
        total_rounds = state.get("round_total", 0)
        awaiting = state.get("awaiting", [])

        if player not in awaiting:
            if current_round > round_num:
                round_num = current_round
            await asyncio.sleep(POLL_INTERVAL)
            continue

        if current_round > round_num:
            round_num = current_round
            print(f"--- Round {round_num}/{total_rounds} ---")

            obs = agent.get_observation(player)
            move, error = sync_llm_call(obs, extra_body=no_thinking)

            if error:
                move = OPTION_A
                print(f"  {MODEL} forfeit - using fallback: {move}")

            agent.submit_action(move)
            print(f"  Action submitted: {move}")
            print()
        
        await asyncio.sleep(POLL_INTERVAL)

    results = agent.get_results()
    total_a = results.get("total_scores", {}).get("A", 0)
    total_b = results.get("total_scores", {}).get("B", 0)
    winner = results.get("winner", "Unknown")
    metrics = results.get("metrics", {})

    print("=" * 56)
    print(f"Winner: {winner}")
    print(f"Final: A={total_a:.1f}  B={total_b:.1f}")
    print()

    print("─ Metrics ─")
    print(f"  Coordination rate: {metrics.get('coordination_rate', 0):.2f}")
    print(f"  Average payoff: A={metrics.get('average_payoff', {}).get('A', 0):.2f} B={metrics.get('average_payoff', {}).get('B', 0):.2f}")

    os.makedirs(RESULTS_DIR, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    result_file = os.path.join(RESULTS_DIR, f"bos_{MODEL}_vs_human_{timestamp}.json")
    with open(result_file, "w") as f:
        json.dump({
            "game": "battle_of_the_sexes",
            "model": MODEL,
            "session_key": SESSION_KEY[:20] + "...",
            "player": player,
            "results": results,
        }, f, indent=2, default=str)
    print(f"\nResults saved to {result_file}")


if __name__ == "__main__":
    asyncio.run(play_game())
