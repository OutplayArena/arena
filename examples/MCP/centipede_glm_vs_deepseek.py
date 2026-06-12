"""
Centipede Game — GLM-5.1 vs DeepSeek V4 Pro via MCP.

═══ ORCHESTRATOR ════════════════════════════════════════════════════════════
Creates the game session and distributes player tokens.

═══ AGENTS ══════════════════════════════════════════════════════════════════
Strictly sequential: only the current player's agent acts each step.
The agent calls get_observation() — the platform returns the correct state
(current pots, step number, history). No game logic in this script.
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
from games.core.centipede.config import config_from_dict

sys.stdout.reconfigure(line_buffering=True)

NASH_ARENA_BASE_URL = os.environ.get("NASH_ARENA_BASE_URL") or os.environ.get("ARENA_BASE_URL", "http://127.0.0.1:8000/api")
NASH_ARENA_API_KEY  = os.environ["NASH_ARENA_API_KEY"]
OPENCODE_API_BASE   = "https://opencode.ai/zen/v1"
RESULTS_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "results")

PLAYER_A_MODEL = "glm-5.1"
PLAYER_B_MODEL = "deepseek-v4-pro"
MODELS         = {"A": PLAYER_A_MODEL, "B": PLAYER_B_MODEL}
MAX_STEPS      = 8
INITIAL_POT_A  = 4.0
INITIAL_POT_B  = 1.0
GROWTH_FACTOR  = 2.0

_llm = OpenAI(base_url=OPENCODE_API_BASE, api_key=os.environ.get("OPENCODE_GO_API_KEY", "").strip())


def parse_action(text):
    return "take" if "take" in text.strip().lower() else "pass"


def call_llm(model, observation, extra_body=None):
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
            action = parse_action(content)
            print(f"  [{model}] {time.time()-t0:.1f}s -> {action.upper()}")
            return action
        except Exception as e:
            print(f"  [{model}] attempt {attempt+1}/2: {str(e)[:80]}")
            time.sleep(5)
    return "pass"


async def run():
    _llm.api_key = os.environ.get("OPENCODE_GO_API_KEY", "").strip()
    loop = asyncio.get_running_loop()

    print(f"=== Centipede Game [MCP]: {PLAYER_A_MODEL} (A) vs {PLAYER_B_MODEL} (B) ===")
    print(f"Max steps: {MAX_STEPS}  Initial pots: A={INITIAL_POT_A}, B={INITIAL_POT_B}  Growth: ×{GROWTH_FACTOR}")
    print(f"Backward induction predicts: TAKE on step 1 (A)")
    print()

    # ── ORCHESTRATOR ──────────────────────────────────────────────────────────
    arena  = ArenaClient(NASH_ARENA_BASE_URL)
    config = config_from_dict({
        "game": "centipede", "players": 2,
        "max_steps": MAX_STEPS,
        "initial_pot_a": INITIAL_POT_A, "initial_pot_b": INITIAL_POT_B,
        "growth_factor": GROWTH_FACTOR,
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
    agents = {"A": MCPAgent(player_tokens["A"], NASH_ARENA_BASE_URL),
              "B": MCPAgent(player_tokens["B"], NASH_ARENA_BASE_URL)}

    no_thinking = {"thinking": {"type": "disabled"}}
    pass_count  = 0
    total_steps = 0

    for _ in range(MAX_STEPS + 1):
        state          = agents["A"].get_game_state()
        phase          = state.get("phase")
        current_player = state.get("current_player", "A")

        if phase == "complete" or not state.get("awaiting"):
            break

        pot_a    = state.get("pot_a", INITIAL_POT_A)
        pot_b    = state.get("pot_b", INITIAL_POT_B)
        step_num = len(state.get("history", [])) + 1

        print(f"--- Step {step_num}/{MAX_STEPS} · {MODELS[current_player]} ({current_player}) ---")
        print(f"  Pots: A={pot_a:.1f}  B={pot_b:.1f}")

        # Only the current player's agent acts
        obs    = await loop.run_in_executor(None, agents[current_player].get_observation)
        action = await loop.run_in_executor(None, call_llm, MODELS[current_player], obs, no_thinking)

        agents[current_player].submit_action(action)
        total_steps += 1
        if action == "pass":
            pass_count += 1
            print(f"  PASSed — pots grow to A={pot_a*GROWTH_FACTOR:.1f}  B={pot_b*GROWTH_FACTOR:.1f}")
        else:
            print(f"  {MODELS[current_player]} TAKEs — game over!")
        print()

        if action == "take":
            break

    results = agents["A"].get_results()
    scores  = results.get("total_scores", {})
    winner  = results.get("winner", "Unknown")
    metrics = results.get("metrics", {})

    print("=" * 56)
    print(f"Winner: {MODELS.get(winner, 'Tie') + ' (' + winner + ')' if winner in MODELS else 'Tie'}")
    print(f"Final: A({PLAYER_A_MODEL})={scores.get('A',0):.1f}  B({PLAYER_B_MODEL})={scores.get('B',0):.1f}")
    print()
    print("─ Metrics ─")
    print(f"  Steps played: {total_steps}/{MAX_STEPS}  ({pass_count} passed, {total_steps-pass_count} took)")
    print(f"  Cooperation depth: {pass_count}/{MAX_STEPS} = {pass_count/MAX_STEPS:.2f}")
    bi = metrics.get("backward_induction_adherence", {})
    print(f"  Backward induction adherence: A={bi.get('A',0):.2f}  B={bi.get('B',0):.2f}")

    os.makedirs(RESULTS_DIR, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    path = os.path.join(RESULTS_DIR, f"centipede_mcp_{ts}.json")
    with open(path, "w") as f:
        json.dump({"game": "centipede", "interface": "mcp", "session_id": session_id, "results": results}, f, indent=2, default=str)
    print(f"\nResults saved to {path}")


if __name__ == "__main__":
    asyncio.run(run())
