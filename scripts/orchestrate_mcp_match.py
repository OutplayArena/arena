import asyncio
import json
import os
import sys
import re
import ast
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from contextlib import AsyncExitStack

import httpx
from mcp import ClientSession, StdioServerParameters, types
from mcp.client.stdio import stdio_client

from nash_arena.client import ArenaClient
from games.core.blotto.config import BlottoExperimentConfig

sys.stdout.reconfigure(line_buffering=True)

LLM_EXECUTOR = ThreadPoolExecutor(max_workers=2)

ARENA_BASE_URL = os.environ.get("ARENA_BASE_URL", "http://127.0.0.1:8000")
INTERNAL_API_TOKEN = os.environ.get("NASH_ARENA_INTERNAL_API_TOKEN", "").strip()
OPENCODE_GO_API_KEY = os.environ.get("OPENCODE_GO_API_KEY", "").strip()
OPENCODE_GO_API_BASE = "https://opencode.ai/zen/go/v1"

PLAYER_A_MODEL = "deepseek-v4-pro"
PLAYER_B_MODEL = "glm-5.1"

NUM_BATTLEFIELDS = 5
TOTAL_RESOURCES = 100
NUM_ROUNDS = 20


def balanced_allocation(num_battlefields, total_resources):
    base = total_resources // num_battlefields
    allocation = [base] * num_battlefields
    for i in range(total_resources - sum(allocation)):
        allocation[i] += 1
    return allocation


def parse_allocation(text, num_battlefields, total_resources):
    match = re.search(r"\[[^\]]+\]", text)
    if match is None:
        return balanced_allocation(num_battlefields, total_resources)
    try:
        allocation = ast.literal_eval(match.group())
    except (SyntaxError, ValueError):
        return balanced_allocation(num_battlefields, total_resources)
    if not isinstance(allocation, list):
        return balanced_allocation(num_battlefields, total_resources)
    if len(allocation) != num_battlefields:
        return balanced_allocation(num_battlefields, total_resources)
    if not all(isinstance(x, int) and not isinstance(x, bool) for x in allocation):
        return balanced_allocation(num_battlefields, total_resources)
    if not all(x >= 0 for x in allocation):
        return balanced_allocation(num_battlefields, total_resources)
    if sum(allocation) != total_resources:
        return balanced_allocation(num_battlefields, total_resources)
    return allocation


def build_prompt(state, player_label):
    history = state.get("history", [])
    round_num = state.get("round", 1)
    round_total = state.get("round_total", NUM_ROUNDS)
    total_scores = state.get("total_scores", {})

    lines = [
        f"Blotto R{round_num}/{round_total}. You={player_label}. Troops=100. Fields=5. Scores A={total_scores.get('A', 0)} B={total_scores.get('B', 0)}.",
    ]

    if history:
        for h in history[-3:]:
            lines.append(
                f"R{h['round']}: A={h['allocations']['A']} B={h['allocations']['B']} → {h['winner']}"
            )

    lines.append("Allocation:")
    return "\n".join(lines)


def _sync_llm_call(model, system_msg, prompt):
    fallback = balanced_allocation(NUM_BATTLEFIELDS, TOTAL_RESOURCES)

    for attempt in range(5):
        try:
            t0 = time.time()
            resp = httpx.post(
                f"{OPENCODE_GO_API_BASE}/chat/completions",
                headers={
                    "Authorization": f"Bearer {OPENCODE_GO_API_KEY}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": model,
                    "messages": [
                        {"role": "system", "content": system_msg},
                        {"role": "user", "content": prompt},
                    ],
                    "max_tokens": 16384,
                    "temperature": 0.7,
                },
                timeout=300.0,
            )

            if resp.status_code == 429:
                wait = 30 * (attempt + 1)
                print(f"  [{model}] 429 rate limited, waiting {wait}s...")
                time.sleep(wait)
                continue

            resp.raise_for_status()
            data = resp.json()
            dt = time.time() - t0

            choice = data["choices"][0]
            message = choice["message"]
            finish = choice.get("finish_reason")
            content = message.get("content") or ""
            reasoning = message.get("reasoning_content") or ""

            text = content if content.strip() else reasoning
            alloc = parse_allocation(text, NUM_BATTLEFIELDS, TOTAL_RESOURCES)
            is_fallback = alloc == fallback and not content.strip()

            print(
                f"  [{model}] {dt:.1f}s finish={finish} "
                f"content={repr(content)[:60] or '(empty)'} "
                f"→ {alloc}"
                + (" (from reasoning)" if not content.strip() and reasoning else "")
                + (" (FALLBACK)" if is_fallback else "")
            )
            return alloc, text

        except (httpx.ReadTimeout, httpx.ConnectTimeout) as exc:
            print(f"  [{model}] timeout attempt {attempt+1}/5")

    print(f"  [{model}] all retries exhausted, using uniform allocation")
    return fallback, ""


async def llm_allocate(model, prompt):
    system_msg = (
        "You play Colonel Blotto. "
        "Distribute exactly 100 troops across 5 equal battlefields. "
        "Output ONLY a Python list like [30,25,20,15,10]. "
        "No other text."
    )
    loop = asyncio.get_running_loop()
    alloc, text = await loop.run_in_executor(
        LLM_EXECUTOR, _sync_llm_call, model, system_msg, prompt
    )
    return alloc, text


def extract_tool_text(result):
    for item in result.content:
        if isinstance(item, types.TextContent):
            try:
                return json.loads(item.text)
            except json.JSONDecodeError:
                return {"raw": item.text}
    return {}


async def create_player_session(player, session_id, token, exit_stack):
    env = {
        "ARENA_BASE_URL": ARENA_BASE_URL,
        "ARENA_SESSION_ID": session_id,
        "ARENA_SESSION_TOKEN": token,
        "NASH_ARENA_INTERNAL_API_TOKEN": INTERNAL_API_TOKEN,
    }
    server_params = StdioServerParameters(
        command=sys.executable,
        args=["-m", "nash_arena.mcp_server"],
        env=env,
    )
    read_stream, write_stream = await exit_stack.enter_async_context(
        stdio_client(server_params)
    )
    session = ClientSession(read_stream, write_stream)
    await exit_stack.enter_async_context(session)
    await session.initialize()
    return session


async def run_match():
    if not OPENCODE_GO_API_KEY:
        print("ERROR: OPENCODE_GO_API_KEY environment variable is required")
        sys.exit(1)
    if not INTERNAL_API_TOKEN:
        print("ERROR: NASH_ARENA_INTERNAL_API_TOKEN environment variable is required")
        sys.exit(1)

    print("Creating arena session...")
    arena = ArenaClient(ARENA_BASE_URL, internal_api_token=INTERNAL_API_TOKEN)
    config = BlottoExperimentConfig.classic(
        num_battlefields=NUM_BATTLEFIELDS,
        total_resources=TOTAL_RESOURCES,
        rounds=NUM_ROUNDS,
        seed=42,
    )
    created = arena.create_experiment(config)
    session_id = created["session_id"]
    token_a = created["player_tokens"]["A"]
    token_b = created["player_tokens"]["B"]
    print(f"Session: {session_id}")
    print(f"Player A ({PLAYER_A_MODEL}) vs Player B ({PLAYER_B_MODEL})")
    print(f"Config: {NUM_BATTLEFIELDS} battlefields, {TOTAL_RESOURCES} troops, {NUM_ROUNDS} rounds")
    print()

    async with AsyncExitStack() as exit_stack:
        print("Starting MCP server for Player A...")
        mcp_a = await create_player_session("A", session_id, token_a, exit_stack)
        print("Starting MCP server for Player B...")
        mcp_b = await create_player_session("B", session_id, token_b, exit_stack)
        print("Both MCP servers ready.")
        print()

        full_history = []

        for round_idx in range(NUM_ROUNDS):
            round_num = round_idx + 1

            state_result = await mcp_a.call_tool("get_game_state")
            state = extract_tool_text(state_result)

            if state.get("phase") == "complete":
                break

            prompt_a = build_prompt(state, "A")
            prompt_b = build_prompt(state, "B")

            (alloc_a, raw_a), (alloc_b, raw_b) = await asyncio.gather(
                llm_allocate(PLAYER_A_MODEL, prompt_a),
                llm_allocate(PLAYER_B_MODEL, prompt_b),
            )

            action_a_result = await mcp_a.call_tool(
                "submit_action", {"allocation": alloc_a}
            )
            action_a_resp = extract_tool_text(action_a_result)

            action_b_result = await mcp_b.call_tool(
                "submit_action", {"allocation": alloc_b}
            )
            action_b_resp = extract_tool_text(action_b_result)

            latest_state = action_a_resp if action_a_resp.get("history") else action_b_resp
            round_history = latest_state.get("history", [])
            if round_history:
                last = round_history[-1]
                a_score = last["scores"]["A"]
                b_score = last["scores"]["B"]
                winner = last["winner"]
                full_history.append(last)
                print(
                    f"Round {round_num:2d}: "
                    f"A={alloc_a} B={alloc_b} → "
                    f"A={a_score:.1f} B={b_score:.1f} winner={winner}"
                )
            else:
                print(f"Round {round_num:2d}: A={alloc_a} B={alloc_b} (resolving...)")

        results_result = await mcp_a.call_tool("get_results")
        results = extract_tool_text(results_result)

    total_a = results.get("total_scores", {}).get("A", 0)
    total_b = results.get("total_scores", {}).get("B", 0)
    winner = results.get("winner", "Unknown")
    metrics = results.get("metrics", {})

    print()
    print("=" * 50)
    winner_label = (
        f"Player A ({PLAYER_A_MODEL})"
        if winner == "A"
        else f"Player B ({PLAYER_B_MODEL})"
        if winner == "B"
        else "Tie"
    )
    print(f"Winner: {winner_label}")
    print(f"Final score: A={total_a:.1f}  B={total_b:.1f}")
    if metrics:
        print(f"Metrics: {json.dumps(metrics, indent=2)}")

    output = {
        "session_id": session_id,
        "config": {
            "num_battlefields": NUM_BATTLEFIELDS,
            "total_resources": TOTAL_RESOURCES,
            "num_rounds": NUM_ROUNDS,
            "seed": 42,
        },
        "player_a": {"model": PLAYER_A_MODEL, "label": "A"},
        "player_b": {"model": PLAYER_B_MODEL, "label": "B"},
        "total_scores": {"A": total_a, "B": total_b},
        "winner": winner,
        "history": full_history,
        "metrics": metrics,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"results_{ts}.json"
    with open(filename, "w") as f:
        json.dump(output, f, indent=2)
    print(f"\nResults saved to {filename}")


if __name__ == "__main__":
    asyncio.run(run_match())
