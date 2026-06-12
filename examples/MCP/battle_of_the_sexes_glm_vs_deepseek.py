"""
Battle of the Sexes — GLM-5.1 vs DeepSeek V4 Pro via MCP.

═══ ORCHESTRATOR ════════════════════════════════════════════════════════════
Creates the game session and distributes player tokens.

═══ AGENTS ══════════════════════════════════════════════════════════════════
Each agent calls get_observation() → submit_action() via MCP.
No game-specific prompt logic lives here — it's all in prompts.yaml.
"""
import asyncio
import os
import sys
import time
import json
from datetime import datetime, timezone

from openai import OpenAI

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from MCP._agent import MCPAgent

from nash_arena.client import ArenaClient
from games.core.battle_of_the_sexes.config import config_from_dict

sys.stdout.reconfigure(line_buffering=True)

NASH_ARENA_BASE_URL = os.environ.get("NASH_ARENA_BASE_URL") or os.environ.get("ARENA_BASE_URL", "http://127.0.0.1:8000/api")
NASH_ARENA_API_KEY  = os.environ["NASH_ARENA_API_KEY"]
OPENCODE_API_BASE   = "https://opencode.ai/zen/v1"
RESULTS_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "results")

PLAYER_A_MODEL = "glm-5.1"
PLAYER_B_MODEL = "deepseek-v4-pro"
MODELS = {"A": PLAYER_A_MODEL, "B": PLAYER_B_MODEL}
NUM_ROUNDS = 10
OPTION_A, OPTION_B = "opera", "football"

_llm = OpenAI(base_url=OPENCODE_API_BASE, api_key=os.environ.get("OPENCODE_GO_API_KEY", "").strip())


def parse_move(text):
    return OPTION_B if OPTION_B in text.strip().lower() else OPTION_A


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
            move = parse_move(content)
            print(f"  [{model}] {time.time()-t0:.1f}s -> {move}")
            return move
        except Exception as e:
            print(f"  [{model}] attempt {attempt+1}/2: {str(e)[:80]}")
            time.sleep(5)
    return OPTION_A


async def agent_turn(player: str, agent: MCPAgent, extra_body=None):
    loop = asyncio.get_running_loop()
    obs  = await loop.run_in_executor(None, agent.get_observation)
    move = await loop.run_in_executor(None, call_llm, MODELS[player], obs, extra_body)
    return player, move


async def run():
    _llm.api_key = os.environ.get("OPENCODE_GO_API_KEY", "").strip()

    print(f"=== Battle of the Sexes [MCP]: {PLAYER_A_MODEL} (A) vs {PLAYER_B_MODEL} (B) ===")
    print(f"Options: {OPTION_A} (A's preference) vs {OPTION_B} (B's preference)  Rounds: {NUM_ROUNDS}")
    print()

    # ── ORCHESTRATOR ──────────────────────────────────────────────────────────
    arena  = ArenaClient(NASH_ARENA_BASE_URL)
    config = config_from_dict({
        "game": "battle_of_the_sexes", "players": 2, "rounds": NUM_ROUNDS,
        "option_a_label": OPTION_A, "option_b_label": OPTION_B,
        "payoff_preferred_a": 3.0, "payoff_preferred_b": 3.0,
        "payoff_nonpreferred": 2.0, "payoff_mismatch": 0.0,
        "seed": 42,
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
    agent_a = MCPAgent(player_tokens["A"], NASH_ARENA_BASE_URL)
    agent_b = MCPAgent(player_tokens["B"], NASH_ARENA_BASE_URL)

    no_thinking = {"thinking": {"type": "disabled"}}
    coord_count = 0

    for round_idx in range(NUM_ROUNDS):
        round_num = round_idx + 1
        print(f"--- Round {round_num}/{NUM_ROUNDS} ---")

        if agent_a.get_game_state().get("phase") == "complete":
            break

        (_, move_a), (_, move_b) = await asyncio.gather(
            agent_turn("A", agent_a, no_thinking),
            agent_turn("B", agent_b, no_thinking),
        )

        agent_a.submit_action(move_a)
        agent_b.submit_action(move_b)

        state = agent_a.get_game_state()
        if state.get("history"):
            last    = state["history"][-1]
            actions = last.get("actions", {})
            payoffs = last.get("payoffs", {})
            coordinated = actions.get("A") == actions.get("B")
            if coordinated: coord_count += 1
            print(f"  {PLAYER_A_MODEL}={actions.get('A','?')}  {PLAYER_B_MODEL}={actions.get('B','?')}  [{'COORD' if coordinated else 'MISS'}]")
            print(f"  Payoffs: A={payoffs.get('A',0):.1f} B={payoffs.get('B',0):.1f}")
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
    print(f"  Coordination rate: {coord_count}/{NUM_ROUNDS} = {coord_count/NUM_ROUNDS:.2f}")
    print(f"  Average payoff: A={metrics.get('average_payoff',{}).get('A',0):.2f} B={metrics.get('average_payoff',{}).get('B',0):.2f}")

    os.makedirs(RESULTS_DIR, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    path = os.path.join(RESULTS_DIR, f"bos_mcp_{ts}.json")
    with open(path, "w") as f:
        json.dump({"game": "battle_of_the_sexes", "interface": "mcp", "session_id": session_id, "results": results}, f, indent=2, default=str)
    print(f"\nResults saved to {path}")


if __name__ == "__main__":
    asyncio.run(run())
