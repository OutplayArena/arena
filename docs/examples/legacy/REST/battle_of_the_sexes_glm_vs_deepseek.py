import asyncio
import os
import sys
import time
import json
from datetime import datetime, timezone

from openai import OpenAI

from outplaylabs_arena_sdk import ArenaClient
from games.core.battle_of_the_sexes.config import config_from_dict

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

OPTION_A = "opera"
OPTION_B = "football"
PAYOFF_PREFERRED_A = 3.0
PAYOFF_PREFERRED_B = 3.0
PAYOFF_NONPREFERRED = 2.0
PAYOFF_MISMATCH = 0.0


def parse_move(text):
    t = text.strip().lower()
    if OPTION_B in t:
        return OPTION_B
    return OPTION_A


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
            move = parse_move(content)
            print(f"  [{model}] {time.time()-t0:.1f}s -> {move}")
            return move, None
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

    print(f"=== Battle of the Sexes: {PLAYER_A_MODEL} (A) vs {PLAYER_B_MODEL} (B) ===")
    print(f"Options: {OPTION_A} (A's preference) vs {OPTION_B} (B's preference)")
    print(f"Rounds: {NUM_ROUNDS}")
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
        "game": "battle_of_the_sexes",
        "players": 2,
        "rounds": NUM_ROUNDS,
        "option_a_label": OPTION_A,
        "option_b_label": OPTION_B,
        "payoff_preferred_a": PAYOFF_PREFERRED_A,
        "payoff_preferred_b": PAYOFF_PREFERRED_B,
        "payoff_nonpreferred": PAYOFF_NONPREFERRED,
        "payoff_mismatch": PAYOFF_MISMATCH,
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
    coord_count = 0

    for round_idx in range(NUM_ROUNDS):
        round_num = round_idx + 1
        print(f"--- Round {round_num}/{NUM_ROUNDS} ---")

        state = player_a.get_state()
        if state.get("phase") == "complete":
            break

        (move_a, error_a), (move_b, error_b) = await asyncio.gather(
            llm_move("A", player_a, extra_body=no_thinking),
            llm_move("B", player_b, extra_body=no_thinking),
        )

        if error_a:
            move_a = OPTION_A
            print(f"  {PLAYER_A_MODEL} forfeit - using fallback: {move_a}")
        if error_b:
            move_b = OPTION_B
            print(f"  {PLAYER_B_MODEL} forfeit - using fallback: {move_b}")

        player_a.submit_action(move_a)
        player_b.submit_action(move_b)

        state_after = player_a.get_state()
        if state_after.get("history"):
            last = state_after["history"][-1]
            actions = last.get("actions", {})
            payoffs = last.get("payoffs", {})
            coordinated = actions.get("A") == actions.get("B")
            if coordinated:
                coord_count += 1
            result = "COORD" if coordinated else "MISS"
            print(f"  {PLAYER_A_MODEL}={actions.get('A','?')}  {PLAYER_B_MODEL}={actions.get('B','?')}  [{result}]")
            print(f"  Payoffs: A={payoffs.get('A', 0):.1f} B={payoffs.get('B', 0):.1f}")
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
    print(f"  Coordination rate: {coord_count}/{NUM_ROUNDS} = {coord_count/NUM_ROUNDS:.2f}")
    print(f"  Average payoff: A={metrics.get('average_payoff', {}).get('A', 0):.2f} B={metrics.get('average_payoff', {}).get('B', 0):.2f}")

    os.makedirs(RESULTS_DIR, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    result_file = os.path.join(RESULTS_DIR, f"bos_{PLAYER_A_MODEL}_vs_{PLAYER_B_MODEL}_{timestamp}.json")
    with open(result_file, "w") as f:
        json.dump({
            "game": "battle_of_the_sexes",
            "option_a": OPTION_A,
            "option_b": OPTION_B,
            "player_a": PLAYER_A_MODEL,
            "player_b": PLAYER_B_MODEL,
            "rounds": NUM_ROUNDS,
            "session_id": session_id,
            "results": results,
        }, f, indent=2, default=str)
    print(f"\nResults saved to {result_file}")


if __name__ == "__main__":
    asyncio.run(run_match())
