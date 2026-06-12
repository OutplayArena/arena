"""
Ultimatum Game — GLM-5.1 vs DeepSeek V4 Pro via MCP.

═══ ORCHESTRATOR ════════════════════════════════════════════════════════════
Creates the game session and distributes player tokens.

═══ AGENTS ══════════════════════════════════════════════════════════════════
Sequential game: the server tracks whose turn it is (proposer vs responder).
Each agent calls get_observation() — the platform automatically returns the
correct template (proposer_state or responder_state) for the current phase.
No phase-detection logic needed here.
"""
import asyncio
import os
import re
import sys
import time
import json
from datetime import datetime, timezone

from openai import OpenAI

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from MCP._agent import MCPAgent

from nash_arena.client import ArenaClient
from games.core.ultimatum.config import config_from_dict

sys.stdout.reconfigure(line_buffering=True)

NASH_ARENA_BASE_URL = os.environ.get("NASH_ARENA_BASE_URL") or os.environ.get("ARENA_BASE_URL", "http://127.0.0.1:8000/api")
NASH_ARENA_API_KEY  = os.environ["NASH_ARENA_API_KEY"]
OPENCODE_API_BASE   = "https://opencode.ai/zen/v1"
RESULTS_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "results")

PLAYER_A_MODEL = "glm-5.1"
PLAYER_B_MODEL = "deepseek-v4-pro"
MODELS = {"A": PLAYER_A_MODEL, "B": PLAYER_B_MODEL}
NUM_ROUNDS = 10
TOTAL      = 100.0
MIN_OFFER  = 1.0

_llm = OpenAI(base_url=OPENCODE_API_BASE, api_key=os.environ.get("OPENCODE_GO_API_KEY", "").strip())


def parse_offer(text):
    nums = re.findall(r"\d+(?:\.\d+)?", text)
    return max(MIN_OFFER, min(float(nums[0]), TOTAL)) if nums else TOTAL * 0.4


def parse_response(text):
    return "accept" if "accept" in text.strip().lower() else "reject"


def call_llm_offer(model, observation, extra_body=None):
    kwargs = dict(
        model=model,
        messages=[
            {"role": "system", "content": observation["system"]},
            {"role": "user",   "content": observation["turn"]},
        ],
        max_tokens=64, temperature=0.7,
    )
    if extra_body:
        kwargs["extra_body"] = extra_body
    for attempt in range(2):
        try:
            t0 = time.time()
            content = _llm.chat.completions.create(**kwargs).choices[0].message.content or ""
            offer = parse_offer(content)
            print(f"  [{model}] {time.time()-t0:.1f}s -> offer {offer:.0f}")
            return offer
        except Exception as e:
            print(f"  [{model}] attempt {attempt+1}/2: {str(e)[:80]}")
            time.sleep(5)
    return TOTAL * 0.4


def call_llm_response(model, observation, extra_body=None):
    kwargs = dict(
        model=model,
        messages=[
            {"role": "system", "content": observation["system"]},
            {"role": "user",   "content": observation["turn"]},
        ],
        max_tokens=32, temperature=0.7,
    )
    if extra_body:
        kwargs["extra_body"] = extra_body
    for attempt in range(2):
        try:
            t0 = time.time()
            content = _llm.chat.completions.create(**kwargs).choices[0].message.content or ""
            resp = parse_response(content)
            print(f"  [{model}] {time.time()-t0:.1f}s -> {resp}")
            return resp
        except Exception as e:
            print(f"  [{model}] attempt {attempt+1}/2: {str(e)[:80]}")
            time.sleep(5)
    return "reject"


async def run():
    _llm.api_key = os.environ.get("OPENCODE_GO_API_KEY", "").strip()
    loop = asyncio.get_running_loop()

    print(f"=== Ultimatum Game [MCP]: {PLAYER_A_MODEL} (A) vs {PLAYER_B_MODEL} (B) ===")
    print(f"Total={TOTAL:.0f}  MinOffer={MIN_OFFER:.0f}  Rounds={NUM_ROUNDS}")
    print()

    # ── ORCHESTRATOR ──────────────────────────────────────────────────────────
    arena  = ArenaClient(NASH_ARENA_BASE_URL)
    config = config_from_dict({
        "game": "ultimatum", "players": 2, "rounds": NUM_ROUNDS,
        "total": TOTAL, "min_offer": MIN_OFFER, "seed": 42,
    })
    created = arena.create_experiment(
        config, agents={"A": PLAYER_A_MODEL, "B": PLAYER_B_MODEL}, api_key=NASH_ARENA_API_KEY,
    )
    session_id    = created["session_id"]
    player_tokens = created["player_tokens"]

    print(f"Session : {session_id}")
    print(f"Token A : {player_tokens['A']}")
    print(f"Token B : {player_tokens['B']}")
    print()

    # ── AGENTS ────────────────────────────────────────────────────────────────
    agents = {"A": MCPAgent(player_tokens["A"], NASH_ARENA_BASE_URL),
              "B": MCPAgent(player_tokens["B"], NASH_ARENA_BASE_URL)}

    no_thinking  = {"thinking": {"type": "disabled"}}
    accept_count = 0
    round_count  = 0
    max_steps    = NUM_ROUNDS * 2 + 5

    for step in range(max_steps):
        state = agents["A"].get_game_state()
        phase = state.get("phase")

        if phase == "complete" or not state.get("awaiting"):
            break

        current_round = state.get("round", 1)

        if phase == "awaiting_proposal":
            proposer = state.get("proposer", "A")
            print(f"--- Round {current_round}/{NUM_ROUNDS} · {MODELS[proposer]} ({proposer}) proposes ---")
            obs   = await loop.run_in_executor(None, agents[proposer].get_observation)
            offer = await loop.run_in_executor(None, call_llm_offer, MODELS[proposer], obs, no_thinking)
            agents[proposer].submit_action(offer)
            round_count = current_round

        elif phase == "awaiting_response":
            responder    = state.get("responder", "B")
            pending_offer = state.get("pending_offer", 0.0) or 0.0
            print(f"  {MODELS[responder]} ({responder}) responds to offer {pending_offer:.0f} ({pending_offer/TOTAL*100:.0f}%)")
            # get_observation() automatically returns responder_state with offer filled in
            obs      = await loop.run_in_executor(None, agents[responder].get_observation)
            response = await loop.run_in_executor(None, call_llm_response, MODELS[responder], obs, no_thinking)
            agents[responder].submit_action(response)

            state_after = agents["A"].get_game_state()
            if state_after.get("history"):
                last     = state_after["history"][-1]
                accepted = last.get("accepted", False)
                payoffs  = last.get("payoffs", {})
                if accepted:
                    accept_count += 1
                print(f"  {'ACCEPTED ✓' if accepted else 'REJECTED ✗'} | Payoffs: A={payoffs.get('A',0):.1f} B={payoffs.get('B',0):.1f}")
            print()

    results = agents["A"].get_results()
    scores  = results.get("total_scores", {})
    winner  = results.get("winner", "Unknown")
    metrics = results.get("metrics", {})

    print("=" * 56)
    print(f"Winner: {MODELS.get(winner, 'Tie') + ' (' + winner + ')' if winner in MODELS else 'Tie'}")
    print(f"Final: A({PLAYER_A_MODEL})={scores.get('A',0):.1f}  B({PLAYER_B_MODEL})={scores.get('B',0):.1f}")
    print()
    print("─ Metrics ─")
    print(f"  Acceptance rate: {accept_count}/{round_count} = {accept_count/max(round_count,1):.2f}")
    avg_frac = metrics.get("avg_offer_fraction", 0)
    print(f"  Avg offer: {avg_frac*100:.0f}%  ({avg_frac*TOTAL:.1f} / {TOTAL:.0f})")
    print(f"  Fairness index: {metrics.get('offer_fairness_index', 0):.2f}")

    os.makedirs(RESULTS_DIR, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    path = os.path.join(RESULTS_DIR, f"ultimatum_mcp_{ts}.json")
    with open(path, "w") as f:
        json.dump({"game": "ultimatum", "interface": "mcp", "session_id": session_id, "results": results}, f, indent=2, default=str)
    print(f"\nResults saved to {path}")


if __name__ == "__main__":
    asyncio.run(run())
