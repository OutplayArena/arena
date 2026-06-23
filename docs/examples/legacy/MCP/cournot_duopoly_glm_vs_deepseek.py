"""
Cournot Duopoly — GLM-5.1 vs DeepSeek V4 Pro via MCP.

═══ ORCHESTRATOR ════════════════════════════════════════════════════════════
Creates the game session and distributes player tokens.

═══ AGENTS ══════════════════════════════════════════════════════════════════
Each agent calls get_observation() → submit_action() via MCP.
"""
import asyncio
import os
import re
import sys
import time
import json
from datetime import datetime, timezone

from openai import OpenAI


from outplaylabs_arena_sdk import MCPAgent

from outplaylabs_arena_sdk import ArenaClient
from games.core.cournot_duopoly.config import config_from_dict

sys.stdout.reconfigure(line_buffering=True)

OUTPLAYLABS_ARENA_BASE_URL = os.environ.get("OUTPLAYLABS_ARENA_BASE_URL") or os.environ.get("ARENA_BASE_URL", "http://127.0.0.1:8000/api")
OUTPLAYLABS_ARENA_API_KEY  = os.environ["OUTPLAYLABS_ARENA_API_KEY"]
OPENCODE_API_BASE   = "https://opencode.ai/zen/v1"
RESULTS_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "results")

PLAYER_A_MODEL = "glm-5.1"
PLAYER_B_MODEL = "deepseek-v4-pro"
MODELS = {"A": PLAYER_A_MODEL, "B": PLAYER_B_MODEL}
NUM_ROUNDS   = 10
DEMAND_A     = 120.0
DEMAND_B     = 1.0
COST_PER_UNIT = 0.0
MAX_QUANTITY = 120.0
NASH_Q       = (DEMAND_A - COST_PER_UNIT) / (3 * DEMAND_B)

_llm = OpenAI(base_url=OPENCODE_API_BASE, api_key=os.environ.get("OPENCODE_GO_API_KEY", "").strip())


def parse_quantity(text):
    nums = re.findall(r"\d+(?:\.\d+)?", text)
    return max(0.0, min(float(nums[0]), MAX_QUANTITY)) if nums else NASH_Q


def call_llm(model, observation, extra_body=None):
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
            qty = parse_quantity(content)
            print(f"  [{model}] {time.time()-t0:.1f}s -> {qty:.1f}")
            return qty
        except Exception as e:
            print(f"  [{model}] attempt {attempt+1}/2: {str(e)[:80]}")
            time.sleep(5)
    return NASH_Q


async def agent_turn(player: str, agent: MCPAgent, extra_body=None):
    loop = asyncio.get_running_loop()
    obs  = await loop.run_in_executor(None, agent.get_observation)
    qty  = await loop.run_in_executor(None, call_llm, MODELS[player], obs, extra_body)
    return player, qty


async def run():
    _llm.api_key = os.environ.get("OPENCODE_GO_API_KEY", "").strip()

    print(f"=== Cournot Duopoly [MCP]: {PLAYER_A_MODEL} (A) vs {PLAYER_B_MODEL} (B) ===")
    print(f"P = {DEMAND_A} - {DEMAND_B}*(q1+q2)  Nash Q≈{NASH_Q:.0f}  Rounds: {NUM_ROUNDS}")
    print()

    # ── ORCHESTRATOR ──────────────────────────────────────────────────────────
    arena  = ArenaClient(OUTPLAYLABS_ARENA_BASE_URL)
    config = config_from_dict({
        "game": "cournot_duopoly", "players": 2, "rounds": NUM_ROUNDS,
        "demand_a": DEMAND_A, "demand_b": DEMAND_B,
        "cost_per_unit": COST_PER_UNIT, "max_quantity": MAX_QUANTITY,
        "seed": 42,
    })
    created = arena.create_experiment(
        config, agents={"A": PLAYER_A_MODEL, "B": PLAYER_B_MODEL}, api_key=OUTPLAYLABS_ARENA_API_KEY,
    )
    session_id    = created["session_id"]
    player_tokens = created["player_tokens"]

    print(f"Session : {session_id}")
    print(f"Token A : {player_tokens['A']}")
    print(f"Token B : {player_tokens['B']}")
    print()

    # ── AGENTS ────────────────────────────────────────────────────────────────
    agent_a = MCPAgent(player_tokens["A"], OUTPLAYLABS_ARENA_BASE_URL)
    agent_b = MCPAgent(player_tokens["B"], OUTPLAYLABS_ARENA_BASE_URL)

    no_thinking = {"thinking": {"type": "disabled"}}

    for round_idx in range(NUM_ROUNDS):
        round_num = round_idx + 1
        print(f"--- Round {round_num}/{NUM_ROUNDS} ---")

        if agent_a.get_game_state().get("phase") == "complete":
            break

        (_, q_a), (_, q_b) = await asyncio.gather(
            agent_turn("A", agent_a, no_thinking),
            agent_turn("B", agent_b, no_thinking),
        )

        agent_a.submit_action(q_a)
        agent_b.submit_action(q_b)

        state = agent_a.get_game_state()
        if state.get("history"):
            last      = state["history"][-1]
            quantities = last.get("quantities", last.get("actions", {}))
            payoffs    = last.get("payoffs", {})
            price      = last.get("price", 0)
            print(f"  Q: A={quantities.get('A',0):.1f}  B={quantities.get('B',0):.1f}  Price={price:.1f}")
            print(f"  Profit: A={payoffs.get('A',0):.1f}  B={payoffs.get('B',0):.1f}")
        print()

    results = agent_a.get_results()
    scores  = results.get("total_scores", {})
    winner  = results.get("winner", "Unknown")
    metrics = results.get("metrics", {})

    print("=" * 56)
    print(f"Winner: {MODELS.get(winner, 'Tie') + ' (' + winner + ')' if winner in MODELS else 'Tie'}")
    print(f"Final: A({PLAYER_A_MODEL})={scores.get('A',0):.1f}  B({PLAYER_B_MODEL})={scores.get('B',0):.1f}")
    print()
    print("─ Metrics ─")
    print(f"  Average payoff: A={metrics.get('average_payoff',{}).get('A',0):.1f}  B={metrics.get('average_payoff',{}).get('B',0):.1f}")
    print(f"  Nash gap: {metrics.get('nash_gap',0):.2f}  Social welfare: {metrics.get('social_welfare',0):.1f}")

    os.makedirs(RESULTS_DIR, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    path = os.path.join(RESULTS_DIR, f"cournot_mcp_{ts}.json")
    with open(path, "w") as f:
        json.dump({"game": "cournot_duopoly", "interface": "mcp", "session_id": session_id, "results": results}, f, indent=2, default=str)
    print(f"\nResults saved to {path}")


if __name__ == "__main__":
    asyncio.run(run())
