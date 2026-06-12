"""
Public Goods Game — GLM-5.1 vs DeepSeek V4 Pro (plus two more LLM instances).

This uses 4 players: A and C are GLM-5.1, B and D are DeepSeek V4 Pro.
All 4 submit contributions simultaneously each round.
System and turn prompts are served dynamically from the platform.
"""
import asyncio
import os
import re
import sys
import time
import json
from datetime import datetime, timezone

from openai import OpenAI

from nash_arena.client import ArenaClient
from games.core.public_goods.config import config_from_dict

sys.stdout.reconfigure(line_buffering=True)

NASH_ARENA_BASE_URL = os.environ.get("NASH_ARENA_BASE_URL") or os.environ.get("ARENA_BASE_URL", "http://127.0.0.1:8000/api")
NASH_ARENA_API_KEY = os.environ["NASH_ARENA_API_KEY"]
OPENCODE_GO_API_BASE = "https://opencode.ai/zen/v1"
RESULTS_DIR = os.path.join(os.path.dirname(__file__), "..", "results")

_client = OpenAI(
    base_url=OPENCODE_GO_API_BASE,
    api_key=os.environ.get("OPENCODE_GO_API_KEY", "").strip(),
)

PLAYER_MODELS = {
    "A": "glm-5.1",
    "B": "deepseek-v4-pro",
    "C": "glm-5.1",
    "D": "deepseek-v4-pro",
}
NUM_PLAYERS = 4
NUM_ROUNDS = 10
ENDOWMENT = 10.0
MULTIPLIER = 2.0


def parse_contribution(text, endowment=ENDOWMENT):
    numbers = re.findall(r"\d+(?:\.\d+)?", text)
    if numbers:
        return max(0.0, min(float(numbers[0]), endowment))
    return endowment / 2.0


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
            contribution = parse_contribution(content)
            print(f"  [{model}/no-think] {time.time()-t0:.1f}s -> contribute {contribution:.1f}")
            return contribution, None
        except Exception as e:
            print(f"  [{model}] attempt {attempt+1}/2: {str(e)[:80]}")
            time.sleep(5)
    return None, "LLM call failed"


async def llm_move(player_label, arena_client, extra_body=None):
    loop = asyncio.get_running_loop()
    obs = await loop.run_in_executor(None, arena_client.get_observation, player_label)
    model = PLAYER_MODELS[player_label]
    return player_label, await loop.run_in_executor(None, sync_llm_call, model, obs, extra_body)


async def run_match():
    _client.api_key = os.environ.get("OPENCODE_GO_API_KEY", "").strip()

    print(f"=== Public Goods Game: {NUM_PLAYERS} players ===")
    for pid, model in PLAYER_MODELS.items():
        print(f"  Player {pid}: {model}")
    print(f"Endowment={ENDOWMENT}, Multiplier={MULTIPLIER}, Rounds={NUM_ROUNDS}")
    print()

    print("Warming up LLM APIs...")
    seen_models = set()
    for model in PLAYER_MODELS.values():
        if model in seen_models:
            continue
        seen_models.add(model)
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
        "game": "public_goods",
        "variant": "classic",
        "players": NUM_PLAYERS,
        "rounds": NUM_ROUNDS,
        "endowment": ENDOWMENT,
        "multiplier": MULTIPLIER,
        "seed": 42,
    })
    created = arena.create_experiment(
        config,
        agents={pid: model for pid, model in PLAYER_MODELS.items()},
        api_key=NASH_ARENA_API_KEY,
    )
    session_id = created["session_id"]
    print(f"Session: {session_id}")
    print()

    players = {
        pid: ArenaClient.for_player(NASH_ARENA_BASE_URL, created, pid)
        for pid in PLAYER_MODELS
    }

    no_thinking = {"thinking": {"type": "disabled"}}

    for round_idx in range(NUM_ROUNDS):
        round_num = round_idx + 1
        print(f"--- Round {round_num}/{NUM_ROUNDS} ---")

        state = players["A"].get_state()
        if state.get("phase") == "complete":
            break

        llm_results = await asyncio.gather(*[
            llm_move(pid, players[pid], extra_body=no_thinking)
            for pid in PLAYER_MODELS
        ])

        contributions = {}
        for pid, (contrib, error) in llm_results:
            if error:
                contrib = ENDOWMENT / 2.0
                print(f"  Player {pid} FAILED - using fallback: {contrib}")
            contributions[pid] = contrib

        for pid, client in players.items():
            client.submit_action(contributions[pid])

        state_after = players["A"].get_state()
        if state_after.get("history"):
            last = state_after["history"][-1]
            contribs = last.get("contributions", {})
            pool = last.get("pool", 0)
            share = last.get("share", 0)
            payoffs = last.get("round_payoffs", last.get("payoffs", {}))
            contribs_str = "  ".join(f"{p}={contribs.get(p,0):.1f}" for p in PLAYER_MODELS)
            print(f"  Contributions: {contribs_str}")
            print(f"  Pool={pool:.1f} → each gets +{share:.1f}")
            payoffs_str = "  ".join(f"{p}={payoffs.get(p,0):.1f}" for p in PLAYER_MODELS)
            print(f"  Payoffs: {payoffs_str}")
        print()

    results = players["A"].get_results()
    total_scores = results.get("total_scores", {})
    winner = results.get("winner", "Unknown")
    metrics = results.get("metrics", {})

    print("=" * 56)
    best = max(total_scores, key=lambda p: total_scores[p]) if total_scores else "?"
    print(f"Winner: Player {best} ({PLAYER_MODELS.get(best, '?')})")
    for pid, model in PLAYER_MODELS.items():
        print(f"  {pid} ({model}): {total_scores.get(pid, 0):.1f}")
    print()

    print("─ Metrics ─")
    avg_contrib = metrics.get("avg_contribution", {})
    contrib_rate = metrics.get("contribution_rate", {})
    print("  Avg contribution / rate per player:")
    for pid, model in PLAYER_MODELS.items():
        print(f"    {pid} ({model}): {avg_contrib.get(pid, 0):.1f} tokens  ({contrib_rate.get(pid, 0)*100:.0f}% of endowment)")
    print(f"  Avg pool per round: {metrics.get('avg_pool', 0):.1f}")
    print(f"  Free rider rounds: {metrics.get('free_rider_count', 0)}")
    print(f"  Average payoff: " + "  ".join(f"{p}={metrics.get('average_payoff',{}).get(p,0):.1f}" for p in PLAYER_MODELS))

    os.makedirs(RESULTS_DIR, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    result_file = os.path.join(RESULTS_DIR, f"public_goods_{NUM_PLAYERS}p_{timestamp}.json")
    with open(result_file, "w") as f:
        json.dump({
            "game": "public_goods",
            "num_players": NUM_PLAYERS,
            "players": PLAYER_MODELS,
            "rounds": NUM_ROUNDS,
            "endowment": ENDOWMENT,
            "multiplier": MULTIPLIER,
            "session_id": session_id,
            "results": results,
        }, f, indent=2, default=str)
    print(f"\nResults saved to {result_file}")


if __name__ == "__main__":
    asyncio.run(run_match())
