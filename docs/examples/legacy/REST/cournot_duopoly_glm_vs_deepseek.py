import asyncio
import os
import re
import sys
import time
import json
from datetime import datetime, timezone

from openai import OpenAI

from outplaylabs_arena_sdk import ArenaClient
from games.core.cournot_duopoly.config import config_from_dict

sys.stdout.reconfigure(line_buffering=True)

OUTPLAYLABS_ARENA_BASE_URL = os.environ.get("OUTPLAYLABS_ARENA_BASE_URL") or os.environ.get("ARENA_BASE_URL", "http://127.0.0.1:8000/api")
OUTPLAYLABS_ARENA_API_KEY = os.environ["OUTPLAYLABS_ARENA_API_KEY"]
OPENCODE_GO_API_BASE = "https://opencode.ai/zen/v1"
RESULTS_DIR = os.path.join(os.path.dirname(__file__), "..", "results")

_client = OpenAI(
    base_url=OPENCODE_GO_API_BASE,
    api_key=os.environ.get("OPENCODE_GO_API_KEY", "").strip(),
)

PLAYER_A_MODEL = "glm-5.1"
PLAYER_B_MODEL = "deepseek-v4-pro"
MODELS = {"A": PLAYER_A_MODEL, "B": PLAYER_B_MODEL}
NUM_ROUNDS = 10

DEMAND_A = 120.0
DEMAND_B = 1.0
COST_PER_UNIT = 0.0
MAX_QUANTITY = 120.0
NASH_Q = (DEMAND_A - COST_PER_UNIT) / (3 * DEMAND_B)
COLLUSIVE_Q = (DEMAND_A - COST_PER_UNIT) / (4 * DEMAND_B)


def parse_quantity(text, max_q=MAX_QUANTITY):
    numbers = re.findall(r"\d+(?:\.\d+)?", text)
    if numbers:
        return max(0.0, min(float(numbers[0]), max_q))
    return NASH_Q


def sync_llm_call(model, observation, extra_body=None):
    kwargs = dict(
        model=model,
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
            quantity = parse_quantity(content)
            print(f"  [{model}] {time.time()-t0:.1f}s -> {quantity:.1f}")
            return quantity, None
        except Exception as e:
            print(f"  [{model}] attempt {attempt+1}/2: {str(e)[:80]}")
            time.sleep(5)
    return None, "LLM call failed"


async def llm_move(player_label, arena_client, extra_body=None):
    loop = asyncio.get_running_loop()
    obs = await loop.run_in_executor(None, arena_client.get_observation, player_label)
    model = MODELS[player_label]
    return await loop.run_in_executor(None, sync_llm_call, model, obs, extra_body)


async def run_match():
    _client.api_key = os.environ.get("OPENCODE_GO_API_KEY", "").strip()

    print(f"=== Cournot Duopoly: {PLAYER_A_MODEL} (A) vs {PLAYER_B_MODEL} (B) ===")
    print(f"Market: P = {DEMAND_A} - {DEMAND_B}*(q1+q2), cost={COST_PER_UNIT}, max_q={MAX_QUANTITY}")
    print(f"Nash Q: {NASH_Q:.0f}  Collusive Q: {COLLUSIVE_Q:.0f}  Rounds: {NUM_ROUNDS}")
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

    arena = ArenaClient(OUTPLAYLABS_ARENA_BASE_URL)
    config = config_from_dict({
        "game": "cournot_duopoly",
        "players": 2,
        "rounds": NUM_ROUNDS,
        "demand_a": DEMAND_A,
        "demand_b": DEMAND_B,
        "cost_per_unit": COST_PER_UNIT,
        "max_quantity": MAX_QUANTITY,
        "seed": 42,
    })
    created = arena.create_experiment(
        config,
        agents={"A": PLAYER_A_MODEL, "B": PLAYER_B_MODEL},
        api_key=OUTPLAYLABS_ARENA_API_KEY,
    )
    session_id = created["session_id"]
    print(f"Session: {session_id}")
    print()

    player_a = ArenaClient.for_player(OUTPLAYLABS_ARENA_BASE_URL, created, "A")
    player_b = ArenaClient.for_player(OUTPLAYLABS_ARENA_BASE_URL, created, "B")

    no_thinking = {"thinking": {"type": "disabled"}}

    for round_idx in range(NUM_ROUNDS):
        round_num = round_idx + 1
        print(f"--- Round {round_num}/{NUM_ROUNDS} ---")

        state = player_a.get_state()
        if state.get("phase") == "complete":
            break

        (q_a, error_a), (q_b, error_b) = await asyncio.gather(
            llm_move("A", player_a, extra_body=no_thinking),
            llm_move("B", player_b, extra_body=no_thinking),
        )

        if error_a:
            q_a = NASH_Q
            print(f"  {PLAYER_A_MODEL} forfeit - using Nash fallback: {q_a}")
        if error_b:
            q_b = NASH_Q
            print(f"  {PLAYER_B_MODEL} forfeit - using Nash fallback: {q_b}")

        player_a.submit_action(q_a)
        player_b.submit_action(q_b)

        state_after = player_a.get_state()
        if state_after.get("history"):
            last = state_after["history"][-1]
            quantities = last.get("quantities", last.get("actions", {}))
            payoffs = last.get("payoffs", {})
            price = last.get("price", 0)
            print(f"  Q: A={quantities.get('A',0):.1f}  B={quantities.get('B',0):.1f}  Price={price:.1f}")
            print(f"  Profit: A={payoffs.get('A', 0):.1f}  B={payoffs.get('B', 0):.1f}")
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
    print(f"  Average payoff: A={metrics.get('average_payoff', {}).get('A', 0):.1f}  B={metrics.get('average_payoff', {}).get('B', 0):.1f}")
    print(f"  Nash gap: {metrics.get('nash_gap', 0):.2f}")
    print(f"  Social welfare: {metrics.get('social_welfare', 0):.1f}")

    os.makedirs(RESULTS_DIR, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    result_file = os.path.join(RESULTS_DIR, f"cournot_{PLAYER_A_MODEL}_vs_{PLAYER_B_MODEL}_{timestamp}.json")
    with open(result_file, "w") as f:
        json.dump({
            "game": "cournot_duopoly",
            "player_a": PLAYER_A_MODEL,
            "player_b": PLAYER_B_MODEL,
            "rounds": NUM_ROUNDS,
            "demand_a": DEMAND_A,
            "demand_b": DEMAND_B,
            "cost_per_unit": COST_PER_UNIT,
            "session_id": session_id,
            "results": results,
        }, f, indent=2, default=str)
    print(f"\nResults saved to {result_file}")


if __name__ == "__main__":
    asyncio.run(run_match())
