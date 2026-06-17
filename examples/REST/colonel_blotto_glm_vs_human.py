import asyncio
import base64
import os
import sys
import time
import json
import ast
import re
from datetime import datetime, timezone

import httpx
from openai import OpenAI

from nash_arena_sdk import ArenaClient

sys.stdout.reconfigure(line_buffering=True)

NASH_ARENA_BASE_URL = os.environ.get("NASH_ARENA_BASE_URL") or os.environ.get("ARENA_BASE_URL", "http://127.0.0.1:8000/api")
SESSION_KEY = os.environ.get("SESSION_KEY", "nks_NDVhMmEzZGItNGZiNC00YmJiLWFkYzUtOGMyYzRjYzJmZjM0OkI6ZjU4ZDgzNjk5MWQzMTczODhmZmZkYTlkMGNhYjBmNDBhYmUzM2MyMGY2ZjcxNDI5NDcwZWIwMjQ4NzNjZjQ4Mw")
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


def get_interactive_state(session_id, player, token):
    response = httpx.get(
        f"{NASH_ARENA_BASE_URL}/session/{session_id}/interactive/state",
        params={"player": player},
        headers={"Authorization": f"Bearer {token}"},
        timeout=10.0,
    )
    response.raise_for_status()
    return response.json()


def balanced_allocation(n, total):
    base = total // n
    alloc = [base] * n
    for i in range(total - sum(alloc)):
        alloc[i] += 1
    return alloc


def parse_allocation(text, n_fields, total_res):
    match = re.search(r"\[[^\]]+\]", text)
    if match is None:
        return balanced_allocation(n_fields, total_res)
    try:
        alloc = ast.literal_eval(match.group())
    except (SyntaxError, ValueError):
        return balanced_allocation(n_fields, total_res)
    if not isinstance(alloc, list) or len(alloc) != n_fields:
        return balanced_allocation(n_fields, total_res)
    if not all(isinstance(x, int) and not isinstance(x, bool) for x in alloc) or not all(x >= 0 for x in alloc):
        return balanced_allocation(n_fields, total_res)
    if sum(alloc) != total_res:
        return balanced_allocation(n_fields, total_res)
    return alloc


def sync_llm_call(observation, extra_body=None):
    kwargs = dict(
        model=MODEL,
        messages=[
            {"role": "system", "content": observation["system"]},
            {"role": "user", "content": observation["turn"]},
        ],
        max_tokens=4096,
        temperature=0.7,
    )
    if extra_body:
        kwargs["extra_body"] = extra_body
    for attempt in range(2):
        try:
            t0 = time.time()
            content = _client.chat.completions.create(**kwargs).choices[0].message.content or ""
            print(f"  [{MODEL}] raw: {content[:200]}")
            return content, None
        except Exception as e:
            print(f"  [{MODEL}] attempt {attempt+1}/2: {str(e)[:80]}")
            time.sleep(5)
    return None, "LLM call failed"


async def play_game():
    _client.api_key = os.environ.get("OPENCODE_GO_API_KEY", "").strip()

    session_id, player = decode_session_key(SESSION_KEY)

    print(f"=== Colonel Blotto: {MODEL} vs Human ===")
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
        base_url=NASH_ARENA_BASE_URL,
        session_id=session_id,
        token=SESSION_KEY,
    )

    state = get_interactive_state(session_id, player, SESSION_KEY)
    num_battlefields = state.get("num_battlefields", 5)
    total_resources = state.get("total_resources", 100)
    total_rounds = state.get("round_total", 10)

    print(f"Connected as player: {player}")
    print(f"Session: {session_id}")
    print(f"Battlefields: {num_battlefields}, Troops: {total_resources}, Rounds: {total_rounds}")
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
        budget = state.get("budgets", {}).get(player, total_resources)
        if str(budget) not in obs["turn"]:
            obs["turn"] = obs["turn"].replace(
                "Your budget is .",
                f"Your budget is {budget}.",
            )
        if player not in obs["system"]:
            obs["system"] = obs["system"].replace(
                "as player .",
                f"as player {player}.",
            )
        obs["system"] += (
            f"\nYou have {total_resources} troops to distribute across "
            f"{num_battlefields} battlefields. "
            f"Return ONLY a JSON list of {num_battlefields} non-negative integers "
            f"that sums to exactly {total_resources}. No explanation."
        )
        raw_response, error = sync_llm_call(obs, extra_body=no_thinking)

        if error:
            alloc = balanced_allocation(num_battlefields, total_resources)
            print(f"  {MODEL} error - using balanced fallback: {alloc}")
        else:
            alloc = parse_allocation(raw_response, num_battlefields, total_resources)
            print(f"  {MODEL} -> {alloc}")

        result = agent.submit_action(alloc)
        print(f"  Submitted: {alloc}")
        print()

        await asyncio.sleep(POLL_INTERVAL)

    results = agent.get_results()
    total_a = results.get("total_scores", {}).get("A", 0)
    total_b = results.get("total_scores", {}).get("B", 0)
    winner = results.get("winner", "Unknown")

    print("=" * 56)
    print(f"Winner: {winner}")
    print(f"Final: A={total_a:.1f}  B={total_b:.1f}")
    print()

    history = results.get("history", [])
    if history:
        print("Round-by-round:")
        for h in history:
            r = h.get("round", "?")
            a_alloc = h.get("allocations", {}).get("A", [])
            b_alloc = h.get("allocations", {}).get("B", [])
            h_scores = h.get("scores", {})
            h_winner = h.get("winner", "?")
            print(f"  R{r}: A={a_alloc} B={b_alloc} -> {h_winner} (A={h_scores.get('A', 0):.1f} B={h_scores.get('B', 0):.1f})")

    os.makedirs(RESULTS_DIR, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    result_file = os.path.join(RESULTS_DIR, f"blotto_{MODEL}_vs_human_{timestamp}.json")
    with open(result_file, "w") as f:
        json.dump({
            "game": "colonelblotto",
            "model": MODEL,
            "session_key": SESSION_KEY[:20] + "...",
            "player": player,
            "results": results,
        }, f, indent=2, default=str)
    print(f"\nResults saved to {result_file}")


if __name__ == "__main__":
    asyncio.run(play_game())
