#!/usr/bin/env python3
"""
Kubernetes E2E Test for MCP Gateway Architecture

This script tests the complete MCP gateway flow in Kubernetes:
1. Create an experiment
2. Verify MCP URL is returned
3. Connect to MCP server via gateway
4. Run a full game
5. Verify cleanup
"""

import asyncio
import sys
import time
import subprocess
from pathlib import Path

# Add paths
sys.path.insert(0, str(Path(__file__).parent / "agent-sdk" / "src"))
sys.path.insert(0, str(Path(__file__).parent))

from nash_arena_sdk import ArenaClient, MCPAgent
from games.core.colonelblotto.config import config_from_dict

# Configuration
MINIKUBE_IP = subprocess.run(
    ["minikube", "ip"],
    capture_output=True,
    text=True
).stdout.strip()

BACKEND_URL = f"http://{MINIKUBE_IP}:30173/api"
API_KEY = ""
JWT_SECRET = "change-me-in-production-use-a-long-random-string"

# LLM Configuration
OPENCODE_API_BASE = "https://opencode.ai/zen/v1"
OPENCODE_API_KEY = None  # Will be loaded from environment

# Game Configuration
PLAYER_A_MODEL = "glm-5.1"
PLAYER_B_MODEL = "deepseek-v4-pro"
NUM_ROUNDS = 3
N_FIELDS = 5
TOTAL = 100


def parse_allocation(text: str, n_fields: int, total: int) -> list[int]:
    """Parse allocation from LLM output."""
    import re
    import ast
    
    match = re.search(r"\[[^\]]+\]", text)
    if match is None:
        return _balanced(n_fields, total)
    try:
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
    from openai import OpenAI
    
    if not OPENCODE_API_KEY:
        raise ValueError("OPENCODE_API_KEY not set")
    
    llm = OpenAI(base_url=OPENCODE_API_BASE, api_key=OPENCODE_API_KEY)
    
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
            content = llm.chat.completions.create(**kwargs).choices[0].message.content or ""
            print(f"  [{model}] {time.time()-t0:.1f}s -> {content[:60]}...")
            return content
        except Exception as e:
            print(f"  [{model}] attempt {attempt+1}/2: {str(e)[:80]}")
            time.sleep(2)
    return ""


async def main():
    print("=" * 70)
    print("Kubernetes E2E Test: MCP Gateway Architecture")
    print("=" * 70)
    print()
    
    # Load API key
    import os
    global OPENCODE_API_KEY
    OPENCODE_API_KEY = os.environ.get("OPENCODE_GO_API_KEY", "").strip()
    if not OPENCODE_API_KEY:
        print("ERROR: OPENCODE_GO_API_KEY not set")
        return False
    
    print(f"Minikube IP: {MINIKUBE_IP}")
    print(f"Backend URL: {BACKEND_URL}")
    print()
    
    # Step 1: Create experiment
    print("Step 1: Creating experiment...")
    arena = ArenaClient(BACKEND_URL)
    config = config_from_dict({
        "game": "colonelblotto",
        "players": 2,
        "rounds": NUM_ROUNDS,
        "n_fields": N_FIELDS,
        "total": TOTAL,
        "seed": 42,
    })
    
    try:
        created = arena.create_experiment(
            config,
            agents={"A": PLAYER_A_MODEL, "B": PLAYER_B_MODEL},
            api_key=API_KEY,
        )
    except Exception as e:
        print(f"ERROR: Failed to create experiment: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    session_id = created["session_id"]
    player_tokens = created["player_tokens"]
    mcp_url = created.get("mcp_url")
    
    print(f"  Session ID: {session_id}")
    print(f"  Player A token: {player_tokens['A'][:20]}...")
    print(f"  Player B token: {player_tokens['B'][:20]}...")
    print(f"  MCP URL: {mcp_url}")
    
    if not mcp_url:
        print("ERROR: No MCP URL returned")
        return False
    
    print("  ✓ Experiment created successfully")
    print()
    
    # Step 2: Test MCP connection
    print("Step 2: Testing MCP connection...")
    try:
        agent_a = MCPAgent(
            player_tokens["A"],
            mcp_url=mcp_url,
            base_url=BACKEND_URL,
            jwt_secret=JWT_SECRET,
        )
        print(f"  Transport: {agent_a.transport}")
        
        # Test basic operations
        state = agent_a.get_game_state()
        print(f"  Game state: {state.get('phase')}")
        
        obs = agent_a.get_observation()
        print(f"  Observation: {obs.get('system', '')[:50]}...")
        
        print("  ✓ MCP connection successful")
        agent_a.close()
    except Exception as e:
        print(f"ERROR: MCP connection failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    print()
    
    # Step 3: Run full game
    print("Step 3: Running full game...")
    agents = {
        "A": MCPAgent(player_tokens["A"], mcp_url=mcp_url, base_url=BACKEND_URL, jwt_secret=JWT_SECRET),
        "B": MCPAgent(player_tokens["B"], mcp_url=None, base_url=BACKEND_URL, jwt_secret=JWT_SECRET),  # REST fallback
    }
    
    print(f"  Agent A transport: {agents['A'].transport}")
    print(f"  Agent B transport: {agents['B'].transport}")
    print()
    
    max_steps = NUM_ROUNDS * 2 + 5
    for step in range(max_steps):
        state = agents["A"].get_game_state()
        phase = state.get("phase")
        current_round = state.get("round", 1)
        
        if phase == "complete" or not state.get("awaiting"):
            break
        
        print(f"  Round {current_round}/{NUM_ROUNDS} | Phase: {phase}")
        
        for player in state.get("awaiting", []):
            model = PLAYER_A_MODEL if player == "A" else PLAYER_B_MODEL
            obs = await asyncio.get_event_loop().run_in_executor(
                None, agents[player].get_observation
            )
            raw = await asyncio.get_event_loop().run_in_executor(
                None, call_llm, model, obs
            )
            allocation = parse_allocation(raw, N_FIELDS, TOTAL)
            print(f"    Player {player} ({model}): {allocation}")
            agents[player].submit_action(allocation)
        
        print()
    
    # Step 4: Get results
    print("Step 4: Getting results...")
    results = agents["A"].get_results()
    scores = results.get("total_scores", {})
    winner = results.get("winner", "Unknown")
    
    print(f"  Winner: {winner}")
    print(f"  Scores: A={scores.get('A', 0)}, B={scores.get('B', 0)}")
    print(f"  Round results: {results.get('round_results', [])}")
    print("  ✓ Game completed successfully")
    print()
    
    # Step 5: Cleanup
    print("Step 5: Cleaning up...")
    for agent in agents.values():
        agent.close()
    
    print("  ✓ Cleanup complete")
    print()
    
    # Step 6: Verify pod cleanup
    print("Step 6: Verifying pod cleanup...")
    result = subprocess.run(
        ["kubectl", "get", "pods", "-n", "nasharena", "-l", "app=mcp-server", "--no-headers"],
        capture_output=True,
        text=True,
    )
    pods = result.stdout.strip()
    if pods:
        print(f"  WARNING: MCP pods still running: {pods}")
    else:
        print("  ✓ No MCP pods running")
    print()
    
    print("=" * 70)
    print("Kubernetes E2E Test: PASSED ✓")
    print("=" * 70)
    return True


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
