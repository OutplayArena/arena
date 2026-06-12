"""
Stag Hunt — GLM-5.1 vs DeepSeek V4 Pro via MCP.

═══ ORCHESTRATOR ════════════════════════════════════════════════════════════
Creates the game session and distributes player tokens to the agents.
In a real deployment this would be a tournament runner or game server.

═══ AGENTS ══════════════════════════════════════════════════════════════════
Each agent only knows its player_token and the arena URL.
It uses three MCP tools: get_observation() → submit_action() → get_results()
Prompts come entirely from the platform — no game logic lives here.

To wire a real Claude agent instead, configure MCP with:
  NASH_ARENA_KEY=<player_token>  NASH_ARENA_BASE_URL=<url>
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
from games.core.stag_hunt.config import config_from_dict

sys.stdout.reconfigure(line_buffering=True)

# ── Config ────────────────────────────────────────────────────────────────────
NASH_ARENA_BASE_URL = os.environ.get("NASH_ARENA_BASE_URL") or os.environ.get("ARENA_BASE_URL", "http://127.0.0.1:8000/api")
NASH_ARENA_API_KEY  = os.environ["NASH_ARENA_API_KEY"]
OPENCODE_API_BASE   = "https://opencode.ai/zen/v1"
RESULTS_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "results")

PLAYER_A_MODEL = "glm-5.1"
PLAYER_B_MODEL = "deepseek-v4-pro"
MODELS = {"A": PLAYER_A_MODEL, "B": PLAYER_B_MODEL}
NUM_ROUNDS = 10
PAYOFF_STAG_STAG, PAYOFF_HARE_HARE, PAYOFF_STAG_HARE = 4.0, 2.0, 0.0

_llm = OpenAI(base_url=OPENCODE_API_BASE, api_key=os.environ.get("OPENCODE_GO_API_KEY", "").strip())


def parse_move(text):
    return "hare" if "hare" in text.strip().lower() else "stag"


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
    return "hare"


async def agent_turn(player: str, agent: MCPAgent, extra_body=None):
    """One agent: fetch observation from platform, call LLM, return move."""
    loop = asyncio.get_running_loop()
    obs  = await loop.run_in_executor(None, agent.get_observation)
    move = await loop.run_in_executor(None, call_llm, MODELS[player], obs, extra_body)
    return player, move


async def run():
    _llm.api_key = os.environ.get("OPENCODE_GO_API_KEY", "").strip()

    print(f"=== Stag Hunt [MCP]: {PLAYER_A_MODEL} (A) vs {PLAYER_B_MODEL} (B) ===")
    print(f"Rounds: {NUM_ROUNDS}  Payoffs: SS={PAYOFF_STAG_STAG} HH={PAYOFF_HARE_HARE} SH={PAYOFF_STAG_HARE}")
    print()

    # ── ORCHESTRATOR: create session, hand out tokens ─────────────────────────
    arena  = ArenaClient(NASH_ARENA_BASE_URL)
    config = config_from_dict({
        "game": "stag_hunt", "variant": "classic", "players": 2,
        "rounds": NUM_ROUNDS,
        "payoff_stag_stag": PAYOFF_STAG_STAG,
        "payoff_hare_hare": PAYOFF_HARE_HARE,
        "payoff_stag_hare": PAYOFF_STAG_HARE,
        "seed": 42,
    })
    created = arena.create_experiment(
        config, agents={"A": PLAYER_A_MODEL, "B": PLAYER_B_MODEL}, api_key=NASH_ARENA_API_KEY,
    )
    session_id    = created["session_id"]
    player_tokens = created["player_tokens"]   # distribute these to agents

    print(f"Session : {session_id}")
    print(f"Token A : {player_tokens['A']}")
    print(f"Token B : {player_tokens['B']}")
    print()

    # ── AGENTS: each only knows its token ─────────────────────────────────────
    agent_a = MCPAgent(player_tokens["A"], NASH_ARENA_BASE_URL)
    agent_b = MCPAgent(player_tokens["B"], NASH_ARENA_BASE_URL)

    no_thinking = {"thinking": {"type": "disabled"}}
    stag_count  = {"A": 0, "B": 0}

    for round_idx in range(NUM_ROUNDS):
        round_num = round_idx + 1
        print(f"--- Round {round_num}/{NUM_ROUNDS} ---")

        if agent_a.get_game_state().get("phase") == "complete":
            break

        # Both agents fetch their observations and decide in parallel
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
            if actions.get("A") == "stag":
                stag_count["A"] += 1
            if actions.get("B") == "stag":
                stag_count["B"] += 1
            outcome = (
                "SS" if actions.get("A") == "stag" and actions.get("B") == "stag"
                else "HH" if actions.get("A") == "hare" and actions.get("B") == "hare"
                else "SH" if actions.get("A") == "stag" else "HS"
            )
            print(f"  {PLAYER_A_MODEL}={actions.get('A','?')}  {PLAYER_B_MODEL}={actions.get('B','?')}  [{outcome}]")
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
    print(f"  STAG rate: A={stag_count['A']/NUM_ROUNDS:.2f}  B={stag_count['B']/NUM_ROUNDS:.2f}")
    eq = metrics.get("equilibrium_selection_rate", {})
    print(f"  Pareto (SS): {eq.get('pareto',0):.2f}  Risk-dominant (HH): {eq.get('risk_dominant',0):.2f}")

    os.makedirs(RESULTS_DIR, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    path = os.path.join(RESULTS_DIR, f"stag_hunt_mcp_{ts}.json")
    with open(path, "w") as f:
        json.dump({"game": "stag_hunt", "interface": "mcp", "session_id": session_id, "results": results}, f, indent=2, default=str)
    print(f"\nResults saved to {path}")


if __name__ == "__main__":
    asyncio.run(run())
