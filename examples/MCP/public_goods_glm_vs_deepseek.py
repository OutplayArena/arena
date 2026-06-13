"""
Public Goods Game — 4 players via MCP (A+C = GLM-5.1, B+D = DeepSeek V4 Pro).

═══ ORCHESTRATOR ════════════════════════════════════════════════════════════
Creates the 4-player session and distributes tokens to each agent.

═══ AGENTS ══════════════════════════════════════════════════════════════════
Each of the 4 agents independently calls get_observation() → submit_action().
All 4 move simultaneously each round.
"""
import asyncio
import os
import re
import sys
import time
import json
from datetime import datetime, timezone

from openai import OpenAI


from nash_arena_sdk import MCPAgent

from nash_arena_sdk import ArenaClient
from games.core.public_goods.config import config_from_dict

sys.stdout.reconfigure(line_buffering=True)

NASH_ARENA_BASE_URL = os.environ.get("NASH_ARENA_BASE_URL") or os.environ.get("ARENA_BASE_URL", "http://127.0.0.1:8000/api")
NASH_ARENA_API_KEY  = os.environ["NASH_ARENA_API_KEY"]
OPENCODE_API_BASE   = "https://opencode.ai/zen/v1"
RESULTS_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "results")

PLAYER_MODELS = {"A": "glm-5.1", "B": "deepseek-v4-pro", "C": "glm-5.1", "D": "deepseek-v4-pro"}
NUM_ROUNDS = 10
ENDOWMENT  = 10.0
MULTIPLIER = 2.0

_llm = OpenAI(base_url=OPENCODE_API_BASE, api_key=os.environ.get("OPENCODE_GO_API_KEY", "").strip())


def parse_contribution(text):
    nums = re.findall(r"\d+(?:\.\d+)?", text)
    return max(0.0, min(float(nums[0]), ENDOWMENT)) if nums else ENDOWMENT / 2.0


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
            contrib = parse_contribution(content)
            print(f"  [{model}/no-think] {time.time()-t0:.1f}s -> contribute {contrib:.1f}")
            return contrib
        except Exception as e:
            print(f"  [{model}] attempt {attempt+1}/2: {str(e)[:80]}")
            time.sleep(5)
    return ENDOWMENT / 2.0


async def agent_turn(player: str, agent: MCPAgent, extra_body=None):
    loop   = asyncio.get_running_loop()
    obs    = await loop.run_in_executor(None, agent.get_observation)
    contrib = await loop.run_in_executor(None, call_llm, PLAYER_MODELS[player], obs, extra_body)
    return player, contrib


async def run():
    _llm.api_key = os.environ.get("OPENCODE_GO_API_KEY", "").strip()

    print("=== Public Goods Game [MCP]: 4 players ===")
    for pid, model in PLAYER_MODELS.items():
        print(f"  Player {pid}: {model}")
    print(f"Endowment={ENDOWMENT}, Multiplier={MULTIPLIER}, Rounds={NUM_ROUNDS}")
    print()

    # ── ORCHESTRATOR ──────────────────────────────────────────────────────────
    arena  = ArenaClient(NASH_ARENA_BASE_URL)
    config = config_from_dict({
        "game": "public_goods", "variant": "classic",
        "players": len(PLAYER_MODELS), "rounds": NUM_ROUNDS,
        "endowment": ENDOWMENT, "multiplier": MULTIPLIER,
        "seed": 42,
    })
    created = arena.create_experiment(
        config, agents=PLAYER_MODELS, api_key=NASH_ARENA_API_KEY,
    )
    session_id    = created["session_id"]
    player_tokens = created["player_tokens"]

    print(f"Session : {session_id}")
    for pid, tok in player_tokens.items():
        print(f"Token {pid} : {tok}")
    print()

    # ── AGENTS ────────────────────────────────────────────────────────────────
    agents = {pid: MCPAgent(player_tokens[pid], NASH_ARENA_BASE_URL) for pid in PLAYER_MODELS}

    no_thinking = {"thinking": {"type": "disabled"}}

    for round_idx in range(NUM_ROUNDS):
        round_num = round_idx + 1
        print(f"--- Round {round_num}/{NUM_ROUNDS} ---")

        if agents["A"].get_game_state().get("phase") == "complete":
            break

        # All 4 agents decide simultaneously
        results_list = await asyncio.gather(*[
            agent_turn(pid, agents[pid], no_thinking) for pid in PLAYER_MODELS
        ])
        contributions = {pid: contrib for pid, contrib in results_list}

        for pid, agent in agents.items():
            agent.submit_action(contributions[pid])

        state = agents["A"].get_game_state()
        if state.get("history"):
            last    = state["history"][-1]
            contribs = last.get("contributions", {})
            pool    = last.get("pool", 0)
            share   = last.get("share", 0)
            payoffs = last.get("round_payoffs", last.get("payoffs", {}))
            print("  Contributions: " + "  ".join(f"{p}={contribs.get(p,0):.1f}" for p in PLAYER_MODELS))
            print(f"  Pool={pool:.1f} → each gets +{share:.1f}")
            print("  Payoffs: " + "  ".join(f"{p}={payoffs.get(p,0):.1f}" for p in PLAYER_MODELS))
        print()

    results = agents["A"].get_results()
    scores  = results.get("total_scores", {})
    metrics = results.get("metrics", {})
    best    = max(scores, key=lambda p: scores[p]) if scores else "?"

    print("=" * 56)
    print(f"Winner: Player {best} ({PLAYER_MODELS.get(best,'?')})")
    for pid, model in PLAYER_MODELS.items():
        print(f"  {pid} ({model}): {scores.get(pid,0):.1f}")
    print()
    print("─ Metrics ─")
    avg_contrib  = metrics.get("avg_contribution", {})
    contrib_rate = metrics.get("contribution_rate", {})
    for pid, model in PLAYER_MODELS.items():
        print(f"  {pid} ({model}): {avg_contrib.get(pid,0):.1f} tokens  ({contrib_rate.get(pid,0)*100:.0f}%)")
    print(f"  Avg pool: {metrics.get('avg_pool',0):.1f}  Free rider rounds: {metrics.get('free_rider_count',0)}")

    os.makedirs(RESULTS_DIR, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    path = os.path.join(RESULTS_DIR, f"public_goods_mcp_{ts}.json")
    with open(path, "w") as f:
        json.dump({"game": "public_goods", "interface": "mcp", "session_id": session_id, "results": results}, f, indent=2, default=str)
    print(f"\nResults saved to {path}")


if __name__ == "__main__":
    asyncio.run(run())
