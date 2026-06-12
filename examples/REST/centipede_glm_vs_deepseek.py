"""
Centipede Game — GLM-5.1 vs DeepSeek V4 Pro.

Strictly sequential game: players alternate choosing TAKE or PASS.
System and turn prompts are served dynamically from the platform via get_observation().
"""
import asyncio
import os
import sys
import time
import json
from datetime import datetime, timezone

from openai import OpenAI

from nash_arena.client import ArenaClient
from games.core.centipede.config import config_from_dict

sys.stdout.reconfigure(line_buffering=True)

NASH_ARENA_BASE_URL = os.environ.get("NASH_ARENA_BASE_URL") or os.environ.get("ARENA_BASE_URL", "http://127.0.0.1:8000/api")
NASH_ARENA_API_KEY = os.environ["NASH_ARENA_API_KEY"]
OPENCODE_GO_API_BASE = "https://opencode.ai/zen/v1"
RESULTS_DIR = os.path.join(os.path.dirname(__file__), "..", "results")

_client = OpenAI(
    base_url=OPENCODE_GO_API_BASE,
    api_key=os.environ.get("OPENCODE_GO_API_KEY", "").strip(),
)

PLAYER_A_MODEL = "glm-5.1"
PLAYER_B_MODEL = "deepseek-v4-pro"
MODELS = {"A": PLAYER_A_MODEL, "B": PLAYER_B_MODEL}
MAX_STEPS = 8
INITIAL_POT_A = 4.0
INITIAL_POT_B = 1.0
GROWTH_FACTOR = 2.0


def parse_action(text):
    t = text.strip().lower()
    if "take" in t:
        return "take"
    return "pass"


def sync_llm_call(model, observation, extra_body=None):
    kwargs = dict(
        model=model,
        messages=[
            {"role": "system", "content": observation["system"]},
            {"role": "user", "content": observation["turn"]},
        ],
        max_tokens=32,
        temperature=0.7,
    )
    if extra_body:
        kwargs["extra_body"] = extra_body
    for attempt in range(2):
        try:
            t0 = time.time()
            content = _client.chat.completions.create(**kwargs).choices[0].message.content or ""
            action = parse_action(content)
            print(f"  [{model}] {time.time()-t0:.1f}s -> {action.upper()}")
            return action, None
        except Exception as e:
            print(f"  [{model}] attempt {attempt+1}/2: {str(e)[:80]}")
            time.sleep(5)
    return "pass", "LLM call failed"


async def run_match():
    _client.api_key = os.environ.get("OPENCODE_GO_API_KEY", "").strip()

    print(f"=== Centipede Game: {PLAYER_A_MODEL} (A) vs {PLAYER_B_MODEL} (B) ===")
    print(f"Max steps: {MAX_STEPS}  Initial pots: A={INITIAL_POT_A}, B={INITIAL_POT_B}  Growth: ×{GROWTH_FACTOR}")
    print(f"Backward induction predicts: TAKE on step 1 (A)")
    print()

    print("Warming up LLM APIs...")
    for model in [PLAYER_A_MODEL, PLAYER_B_MODEL]:
        try:
            t0 = time.time()
            _client.chat.completions.create(
                model=model, messages=[{"role": "user", "content": "Say 'ready'"}],
                max_tokens=16, temperature=0,
            )
            print(f"  [{model}] warmup OK ({time.time() - t0:.1f}s)")
        except Exception as e:
            print(f"  [{model}] warmup failed ({e}), continuing anyway")
    print()

    arena = ArenaClient(NASH_ARENA_BASE_URL)
    config = config_from_dict({
        "game": "centipede",
        "players": 2,
        "max_steps": MAX_STEPS,
        "initial_pot_a": INITIAL_POT_A,
        "initial_pot_b": INITIAL_POT_B,
        "growth_factor": GROWTH_FACTOR,
        "seed": 42,
    })
    created = arena.create_experiment(
        config,
        agents={"A": PLAYER_A_MODEL, "B": PLAYER_B_MODEL},
        api_key=NASH_ARENA_API_KEY,
    )
    session_id = created["session_id"]
    print(f"Session: {session_id}")
    print()

    player_a = ArenaClient.for_player(NASH_ARENA_BASE_URL, created, "A")
    player_b = ArenaClient.for_player(NASH_ARENA_BASE_URL, created, "B")
    clients = {"A": player_a, "B": player_b}

    no_thinking = {"thinking": {"type": "disabled"}}
    pass_count = 0
    total_steps = 0
    loop = asyncio.get_running_loop()

    for _ in range(MAX_STEPS + 1):
        state = player_a.get_state()
        if state.get("phase") == "complete":
            break
        if not state.get("awaiting"):
            break

        current_player = state.get("current_player", "A")
        pot_a = state.get("pot_a", INITIAL_POT_A)
        pot_b = state.get("pot_b", INITIAL_POT_B)
        step_num = len(state.get("history", [])) + 1

        print(f"--- Step {step_num}/{MAX_STEPS} · {MODELS[current_player]} ({current_player}) ---")
        print(f"  Pots: A={pot_a:.1f}  B={pot_b:.1f}")

        obs = await loop.run_in_executor(None, clients[current_player].get_observation, current_player)
        action, error = await loop.run_in_executor(
            None, sync_llm_call, MODELS[current_player], obs, no_thinking
        )
        if error:
            action = "pass"
            print(f"  FAILED - using fallback: {action}")

        clients[current_player].submit_action(action)
        total_steps += 1
        if action == "pass":
            pass_count += 1

        if action == "take":
            print(f"  {MODELS[current_player]} TAKEs — game over!")
            print()
            break
        else:
            print(f"  PASSed — pots grow to A={pot_a * GROWTH_FACTOR:.1f}  B={pot_b * GROWTH_FACTOR:.1f}")
            print()

    results = player_a.get_results()
    total_a = results.get("total_scores", {}).get("A", 0)
    total_b = results.get("total_scores", {}).get("B", 0)
    winner = results.get("winner", "Unknown")
    metrics = results.get("metrics", {})

    print("=" * 56)
    winner_label = (
        f"{PLAYER_A_MODEL} (A)" if winner == "A"
        else f"{PLAYER_B_MODEL} (B)" if winner == "B"
        else "Tie"
    )
    print(f"Winner: {winner_label}")
    print(f"Final: A({PLAYER_A_MODEL})={total_a:.1f}  B({PLAYER_B_MODEL})={total_b:.1f}")
    print()

    print("─ Metrics ─")
    print(f"  Steps played: {total_steps}/{MAX_STEPS}  ({pass_count} passed, {total_steps - pass_count} took)")
    print(f"  Cooperation depth: {pass_count}/{MAX_STEPS} = {pass_count/MAX_STEPS:.2f}")
    bi_adherence = metrics.get("backward_induction_adherence", {})
    print(f"  Backward induction adherence: A={bi_adherence.get('A', 0):.2f}  B={bi_adherence.get('B', 0):.2f}")

    os.makedirs(RESULTS_DIR, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    result_file = os.path.join(RESULTS_DIR, f"centipede_{PLAYER_A_MODEL}_vs_{PLAYER_B_MODEL}_{timestamp}.json")
    with open(result_file, "w") as f:
        json.dump({
            "game": "centipede",
            "player_a": PLAYER_A_MODEL,
            "player_b": PLAYER_B_MODEL,
            "max_steps": MAX_STEPS,
            "initial_pot_a": INITIAL_POT_A,
            "initial_pot_b": INITIAL_POT_B,
            "growth_factor": GROWTH_FACTOR,
            "session_id": session_id,
            "results": results,
        }, f, indent=2, default=str)
    print(f"\nResults saved to {result_file}")


if __name__ == "__main__":
    asyncio.run(run_match())
