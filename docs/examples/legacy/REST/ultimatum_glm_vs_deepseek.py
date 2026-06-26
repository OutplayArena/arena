"""
Ultimatum Game — GLM-5.1 vs DeepSeek V4 Pro.

Sequential game: roles (proposer/responder) alternate each round.
System and turn prompts are served dynamically from the platform via get_observation().
The server selects proposer_state or responder_state based on the current phase.
"""
import asyncio
import os
import re
import sys
import time
import json
from datetime import datetime, timezone

from openai import OpenAI

from outplayarena_sdk import ArenaClient
from games.core.ultimatum.config import config_from_dict

sys.stdout.reconfigure(line_buffering=True)

OUTPLAYARENA_BASE_URL = os.environ.get("OUTPLAYARENA_BASE_URL") or os.environ.get("ARENA_BASE_URL", "http://127.0.0.1:8000/api")
OUTPLAYARENA_API_KEY = os.environ["OUTPLAYARENA_API_KEY"]
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
TOTAL = 100.0
MIN_OFFER = 1.0


def parse_offer(text, total=TOTAL, min_offer=MIN_OFFER):
    numbers = re.findall(r"\d+(?:\.\d+)?", text)
    if numbers:
        return max(min_offer, min(float(numbers[0]), total))
    return total * 0.4


def parse_response(text):
    t = text.strip().lower()
    if "accept" in t:
        return "accept"
    return "reject"


def sync_llm_call_offer(model, observation, extra_body=None):
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
            offer = parse_offer(content)
            print(f"  [{model}] {time.time()-t0:.1f}s -> offer {offer:.0f}")
            return offer, None
        except Exception as e:
            print(f"  [{model}] attempt {attempt+1}/2: {str(e)[:80]}")
            time.sleep(5)
    return TOTAL * 0.4, "LLM call failed"


def sync_llm_call_response(model, observation, extra_body=None):
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
            response = parse_response(content)
            print(f"  [{model}] {time.time()-t0:.1f}s -> {response}")
            return response, None
        except Exception as e:
            print(f"  [{model}] attempt {attempt+1}/2: {str(e)[:80]}")
            time.sleep(5)
    return "reject", "LLM call failed"


async def run_match():
    _client.api_key = os.environ.get("OPENCODE_GO_API_KEY", "").strip()

    print(f"=== Ultimatum Game: {PLAYER_A_MODEL} (A) vs {PLAYER_B_MODEL} (B) ===")
    print(f"Total={TOTAL:.0f}, MinOffer={MIN_OFFER:.0f}, Rounds={NUM_ROUNDS}")
    print("Roles alternate each round. Round 1: A proposes, B responds.")
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

    arena = ArenaClient(OUTPLAYARENA_BASE_URL)
    config = config_from_dict({
        "game": "ultimatum",
        "players": 2,
        "rounds": NUM_ROUNDS,
        "total": TOTAL,
        "min_offer": MIN_OFFER,
        "seed": 42,
    })
    created = arena.create_experiment(
        config,
        agents={"A": PLAYER_A_MODEL, "B": PLAYER_B_MODEL},
        api_key=OUTPLAYARENA_API_KEY,
    )
    session_id = created["session_id"]
    print(f"Session: {session_id}")
    print()

    player_a = ArenaClient.for_player(OUTPLAYARENA_BASE_URL, created, "A")
    player_b = ArenaClient.for_player(OUTPLAYARENA_BASE_URL, created, "B")
    clients = {"A": player_a, "B": player_b}

    no_thinking = {"thinking": {"type": "disabled"}}
    accept_count = 0
    round_count = 0

    max_steps = NUM_ROUNDS * 2 + 5
    step = 0
    loop = asyncio.get_running_loop()

    while step < max_steps:
        state = player_a.get_state()
        phase = state.get("phase")

        if phase == "complete":
            break
        if not state.get("awaiting"):
            break

        current_round = state.get("round", 1)

        if phase == "awaiting_proposal":
            proposer = state.get("proposer", "A")
            print(f"--- Round {current_round}/{NUM_ROUNDS} · {MODELS[proposer]} ({proposer}) proposes ---")
            obs = await loop.run_in_executor(None, clients[proposer].get_observation, proposer)
            offer, error = await loop.run_in_executor(
                None, sync_llm_call_offer, MODELS[proposer], obs, no_thinking
            )
            if error:
                offer = TOTAL * 0.4
                print(f"  FAILED - using fallback offer: {offer:.0f}")
            clients[proposer].submit_action(offer)
            round_count = current_round

        elif phase == "awaiting_response":
            responder = state.get("responder", "B")
            pending_offer = state.get("pending_offer", 0.0) or 0.0
            offer_pct = pending_offer / TOTAL * 100 if TOTAL else 0
            print(f"  {MODELS[responder]} ({responder}) responds to offer {pending_offer:.0f} ({offer_pct:.0f}%)")
            obs = await loop.run_in_executor(None, clients[responder].get_observation, responder)
            response, error = await loop.run_in_executor(
                None, sync_llm_call_response, MODELS[responder], obs, no_thinking
            )
            if error:
                response = "accept"
                print(f"  FAILED - using fallback: {response}")
            clients[responder].submit_action(response)

            state_after = player_a.get_state()
            if state_after.get("history"):
                last = state_after["history"][-1]
                accepted = last.get("accepted", False)
                payoffs = last.get("payoffs", {})
                if accepted:
                    accept_count += 1
                status = "ACCEPTED ✓" if accepted else "REJECTED ✗"
                print(f"  {status} | Payoffs: A={payoffs.get('A', 0):.1f} B={payoffs.get('B', 0):.1f}")
            print()

        step += 1

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
    print(f"  Acceptance rate: {accept_count}/{round_count} = {accept_count/max(round_count,1):.2f}")
    avg_offer_frac = metrics.get("avg_offer_fraction", 0)
    print(f"  Avg offer fraction: {avg_offer_frac*100:.0f}%  (={avg_offer_frac*TOTAL:.1f} / {TOTAL:.0f})")
    print(f"  API acceptance rate: {metrics.get('acceptance_rate', 0):.2f}")
    fairness = metrics.get("offer_fairness_index", 0)
    print(f"  Offer fairness index (0=equal, 1=proposer takes all): {fairness:.2f}")
    print(f"  Average payoff: A={metrics.get('average_payoff', {}).get('A', 0):.1f}  B={metrics.get('average_payoff', {}).get('B', 0):.1f}")

    os.makedirs(RESULTS_DIR, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    result_file = os.path.join(RESULTS_DIR, f"ultimatum_{PLAYER_A_MODEL}_vs_{PLAYER_B_MODEL}_{timestamp}.json")
    with open(result_file, "w") as f:
        json.dump({
            "game": "ultimatum",
            "player_a": PLAYER_A_MODEL,
            "player_b": PLAYER_B_MODEL,
            "rounds": NUM_ROUNDS,
            "total": TOTAL,
            "min_offer": MIN_OFFER,
            "session_id": session_id,
            "results": results,
        }, f, indent=2, default=str)
    print(f"\nResults saved to {result_file}")


if __name__ == "__main__":
    asyncio.run(run_match())
