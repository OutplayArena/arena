"""
Test Docker MCP pool with 2 LLM agents playing Colonel Blotto (3 rounds).
Verifies MCP discovery works in Docker environment.
"""
import asyncio
import os
import re
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "agent-sdk", "src"))

from openai import OpenAI
from nash_arena_sdk import ArenaClient, MCPAgent
from games.core.colonelblotto.config import config_from_dict

# Docker deployment settings
# Get backend container IP dynamically (use the first network)
import subprocess
_backend_ips = subprocess.run(
    ["docker", "inspect", "docker-backend-1", "--format", "{{range .NetworkSettings.Networks}}{{.IPAddress}} {{end}}"],
    capture_output=True, text=True
).stdout.strip().split()
_backend_ip = _backend_ips[0] if _backend_ips else "127.0.0.1"
NASH_ARENA_BASE_URL = f"http://{_backend_ip}:8000/api"
NASH_ARENA_API_KEY = "nka_jYhmJ_GINGK48vcoUHKid_jCb1NH4cNXGZZCTsiEbak"
JWT_SECRET = "098991b0b02fbd9e54a89aa7eac3bbad864487a4234cb5eadf6bb3a207b8eb15"

# LLM settings
OPENCODE_API_BASE = "https://opencode.ai/zen/v1"
OPENCODE_API_KEY = os.environ.get("OPENCODE_GO_API_KEY", "").strip()

PLAYER_A_MODEL = "glm-5.1"
PLAYER_B_MODEL = "deepseek-v4-pro"
NUM_ROUNDS = 3
N_FIELDS = 5
TOTAL = 100

_llm = OpenAI(base_url=OPENCODE_API_BASE, api_key=OPENCODE_API_KEY)


def parse_allocation(text: str, n_fields: int, total: int) -> list[int]:
    """Parse allocation from LLM output."""
    match = re.search(r"\[[^\]]+\]", text)
    if match is None:
        return _balanced(n_fields, total)
    try:
        import ast
        alloc = ast.literal_eval(match.group())
    except (SyntaxError, ValueError):
        return _balanced(n_fields, total)
    if not isinstance(alloc, list) or len(alloc) != n_fields:
        return _balanced(n_fields, total)
    if not all(isinstance(x, int) and not isinstance(x, bool) for x in alloc) or not all(x >= 0 for x in alloc):
        return _balanced(n_fields, total)
    if sum(alloc) != total:
        return _balanced(n_fields, total)
    return alloc


def _balanced(n: int, total: int) -> list[int]:
    base = total // n
    alloc = [base] * n
    for i in range(total - sum(alloc)):
        alloc[i] += 1
    return alloc


def call_llm(model: str, observation: dict) -> str:
    """Call LLM and return raw text."""
    kwargs = dict(
        model=model,
        messages=[
            {"role": "system", "content": observation["system"]},
            {"role": "user", "content": observation["turn"]},
        ],
        max_tokens=128,
        temperature=0.7,
    )
    for attempt in range(2):
        try:
            t0 = time.time()
            content = _llm.chat.completions.create(**kwargs).choices[0].message.content or ""
            print(f"  [{model}] {time.time()-t0:.1f}s -> {content[:60]}...")
            return content
        except Exception as e:
            print(f"  [{model}] attempt {attempt+1}/2: {str(e)[:80]}")
            time.sleep(2)
    return ""


async def main():
    print("=" * 60)
    print("Docker MCP Pool Test: Colonel Blotto (3 rounds)")
    print(f"Player A: {PLAYER_A_MODEL}")
    print(f"Player B: {PLAYER_B_MODEL}")
    print(f"Arena: {NASH_ARENA_BASE_URL}")
    print("=" * 60)
    print()

    # Create experiment
    arena = ArenaClient(NASH_ARENA_BASE_URL)
    config = config_from_dict({
        "game": "colonelblotto",
        "players": 2,
        "rounds": NUM_ROUNDS,
        "n_fields": N_FIELDS,
        "total": TOTAL,
        "seed": 42,
    })

    print("Creating experiment...")
    created = arena.create_experiment(
        config,
        agents={"A": PLAYER_A_MODEL, "B": PLAYER_B_MODEL},
        api_key=NASH_ARENA_API_KEY,
    )
    session_id = created["session_id"]
    player_tokens = created["player_tokens"]
    mcp_url = created.get("mcp_url")
    print(f"Session: {session_id}")
    print(f"Token A: {player_tokens['A'][:20]}...")
    print(f"Token B: {player_tokens['B'][:20]}...")
    print(f"MCP URL: {mcp_url}")

    # Resolve MCP container IP from Docker DNS (since host can't resolve container names)
    if mcp_url:
        import re as _re
        container_name = _re.search(r"http://([^:]+)", mcp_url).group(1)
        try:
            result = subprocess.run(
                ["docker", "inspect", "-f", "{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}", container_name],
                capture_output=True, text=True
            )
            mcp_ip = result.stdout.strip()
            if mcp_ip:
                mcp_url = mcp_url.replace(container_name, mcp_ip)
                print(f"MCP URL (resolved): {mcp_url}")
        except Exception:
            pass
    print()

    # Create MCP agents
    # Note: The current MCP pool design spawns one container per experiment with player A's token.
    # Player A uses MCP, Player B uses REST (fallback) since the MCP server is bound to player A.
    # In a production setup, each player would get their own MCP container.
    agents = {
        "A": MCPAgent(player_tokens["A"], mcp_url=mcp_url, base_url=NASH_ARENA_BASE_URL),
        "B": MCPAgent(player_tokens["B"], mcp_url=None, base_url=NASH_ARENA_BASE_URL),  # REST fallback
    }

    print(f"Agent A transport: {agents['A'].transport}")
    print(f"Agent B transport: {agents['B'].transport}")
    print()

    # Game loop
    max_steps = NUM_ROUNDS * 2 + 5
    for step in range(max_steps):
        state = agents["A"].get_game_state()
        phase = state.get("phase")
        current_round = state.get("round", 1)

        if phase == "complete" or not state.get("awaiting"):
            break

        print(f"--- Round {current_round}/{NUM_ROUNDS} | Phase: {phase} ---")

        for player in state.get("awaiting", []):
            print(f"Player {player} ({PLAYER_A_MODEL if player == 'A' else PLAYER_B_MODEL}) acting...")
            obs = await asyncio.get_event_loop().run_in_executor(
                None, agents[player].get_observation
            )
            model = PLAYER_A_MODEL if player == "A" else PLAYER_B_MODEL
            raw = await asyncio.get_event_loop().run_in_executor(
                None, call_llm, model, obs
            )
            allocation = parse_allocation(raw, N_FIELDS, TOTAL)
            print(f"  Allocation: {allocation}")
            agents[player].submit_action(allocation)

        print()

    # Get results
    print("=" * 60)
    print("Game Complete!")
    results = agents["A"].get_results()
    scores = results.get("total_scores", {})
    winner = results.get("winner", "Unknown")

    print(f"Winner: {winner}")
    print(f"Scores: A={scores.get('A', 0)}, B={scores.get('B', 0)}")
    print(f"Round results: {results.get('round_results', [])}")
    print()

    # Clean up MCP connections
    for agent in agents.values():
        agent.close()

    # Check MCP pool status via backend logs
    print("Checking Docker MCP pool status...")
    result = subprocess.run(
        ["docker", "compose", "-f", "backend/docker/docker-compose.yml", "logs", "--tail=30", "backend"],
        capture_output=True, text=True, cwd=os.path.dirname(__file__) + "/../.."
    )
    mcp_logs = [line for line in result.stdout.split("\n") if "mcp" in line.lower() or "pool" in line.lower()]
    if mcp_logs:
        print("MCP-related logs:")
        for line in mcp_logs[-10:]:
            print(f"  {line}")
    else:
        print("  (No MCP-specific logs found in recent output)")

    print()
    print("Test complete!")


if __name__ == "__main__":
    asyncio.run(main())
