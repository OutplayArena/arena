import asyncio
import json
import os
import sys
import re
import ast
import time
from contextlib import AsyncExitStack

import httpx
from mcp import ClientSession, StdioServerParameters, types
from mcp.client.stdio import stdio_client
from openai import OpenAI

from nash_arena.client import ArenaClient
from games.core.colonelblotto.config import ColonelBlottoExperimentConfig

sys.stdout.reconfigure(line_buffering=True)

NASH_ARENA_BASE_URL = os.environ.get("NASH_ARENA_BASE_URL") or os.environ.get("ARENA_BASE_URL", "http://127.0.0.1:8000/api")
OPENCODE_GO_API_BASE = "https://opencode.ai/zen/v1"

_client = OpenAI(
    base_url=OPENCODE_GO_API_BASE,
    api_key=(os.environ.get("OPENCODE_GO_API_KEY_2") or os.environ.get("OPENCODE_GO_API_KEY", "")).strip(),
)

LLM_MODEL = "mimo-v2.5"
FALLBACK_MODEL = "qwen3.6-plus"
NUM_BATTLEFIELDS = 5
TOTAL_RESOURCES = 100
NUM_ROUNDS = 5


def balanced_allocation(n, total):
    base = total // n
    alloc = [base] * n
    for i in range(total - sum(alloc)):
        alloc[i] += 1
    return alloc


def parse_allocation(text, n_fields, total_res):
    match = re.search(r"\[[^\]]+\]", text)
    if match is None:
        return balanced_allocation(n_fields, total_res)
    try:
        alloc = ast.literal_eval(match.group())
    except (SyntaxError, ValueError):
        return balanced_allocation(n_fields, total_res)
    if not isinstance(alloc, list) or len(alloc) != n_fields:
        return balanced_allocation(n_fields, total_res)
    if not all(isinstance(x, int) for x in alloc) or not all(x >= 0 for x in alloc):
        return balanced_allocation(n_fields, total_res)
    if sum(alloc) != total_res:
        return balanced_allocation(n_fields, total_res)
    return alloc


def build_prompt(state, player_label):
    history = state.get("history", [])
    round_num = state.get("round", 1)
    round_total = state.get("round_total", NUM_ROUNDS)
    total_scores = state.get("total_scores", {})

    lines = [
        f"R{round_num}/{round_total}. You={player_label}. Troops={TOTAL_RESOURCES}. "
        f"Fields={NUM_BATTLEFIELDS}. Scores A={total_scores.get('A', 0)} B={total_scores.get('B', 0)}.",
    ]
    if history:
        for h in history[-3:]:
            lines.append(
                f"R{h['round']}: A={h['allocations']['A']} B={h['allocations']['B']} -> {h['winner']}"
            )
    lines.append("Allocation:")
    return "\n".join(lines)


def sync_llm_call(model, system_msg, prompt):
    for attempt in range(2):
        try:
            t0 = time.time()
            completion = _client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": system_msg},
                    {"role": "user", "content": prompt},
                ],
                max_tokens=4096,
                temperature=0.7,
            )
            content = completion.choices[0].message.content or ""
            dt = time.time() - t0
            alloc = parse_allocation(content, NUM_BATTLEFIELDS, TOTAL_RESOURCES)
            print(f"  [{model}] {dt:.1f}s -> {alloc}")
            return alloc, None
        except Exception as e:
            msg = str(e)[:80]
            print(f"  [{model}] attempt {attempt+1}/2: {msg}")
            time.sleep(5)
    if model != FALLBACK_MODEL:
        print(f"  [{model}] FAILED — trying fallback model {FALLBACK_MODEL}")
        return sync_llm_call(FALLBACK_MODEL, system_msg, prompt)
    print(f"  [{model}] FAILED — forfeiting round")
    return None, "LLM call failed"


async def llm_allocate(model, prompt):
    system_msg = (
        f"You are playing the resource allocation game. "
        f"Distribute exactly {TOTAL_RESOURCES} troops across {NUM_BATTLEFIELDS} equal battlefields. "
        "Output ONLY a Python list of integers. No other text."
    )
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, sync_llm_call, model, system_msg, prompt)


def extract_tool_text(result):
    for item in result.content:
        if isinstance(item, types.TextContent):
            try:
                return json.loads(item.text)
            except json.JSONDecodeError:
                return {"raw": item.text}
    return {}


async def run_match():
    nash_api_key = os.environ["NASH_ARENA_API_KEY"]
    opencode_api_key = os.environ.get("OPENCODE_GO_API_KEY_2") or os.environ["OPENCODE_GO_API_KEY"]
    _client.api_key = opencode_api_key.strip()

    print(f"=== {LLM_MODEL} (LLM/MCP) vs Uniform Agent ===")
    print(f"Battlefields: {NUM_BATTLEFIELDS}, Troops: {TOTAL_RESOURCES}, Rounds: {NUM_ROUNDS}")
    print()

    print("Warming up LLM API...")
    try:
        t0 = time.time()
        completion = _client.chat.completions.create(
            model=LLM_MODEL,
            messages=[
                {"role": "system", "content": "You are helpful."},
                {"role": "user", "content": "Say 'ready'"},
            ],
            max_tokens=256,
            temperature=0,
        )
        content = completion.choices[0].message.content or ""
        print(f"  warmup OK ({len(content)} chars, {time.time() - t0:.1f}s)")
    except Exception as e:
        print(f"  warmup failed ({e}), continuing anyway")

    arena = ArenaClient(NASH_ARENA_BASE_URL)
    config = ColonelBlottoExperimentConfig.classic(
        num_battlefields=NUM_BATTLEFIELDS,
        total_resources=TOTAL_RESOURCES,
        rounds=NUM_ROUNDS,
        seed=42,
    )
    created = arena.create_experiment(config, agents={"A": LLM_MODEL, "B": "UniformAgent"}, api_key=nash_api_key)
    session_id = created["session_id"]
    key_a = created["player_tokens"]["A"]
    key_b = created["player_tokens"]["B"]
    print(f"Session: {session_id}")
    print(f"LLM key (A): {key_a}")
    print(f"Uniform key (B): {key_b}")
    print()

    async with AsyncExitStack() as exit_stack:
        print("Starting MCP server for LLM agent (Player A)...")
        env = {
            "NASH_ARENA_BASE_URL": NASH_ARENA_BASE_URL,
            "NASH_ARENA_KEY": key_a,
        }
        server_params = StdioServerParameters(
            command=sys.executable,
            args=["-m", "nash_arena.mcp_server"],
            env=env,
        )
        read, write = await exit_stack.enter_async_context(stdio_client(server_params))
        mcp_a = ClientSession(read, write)
        await exit_stack.enter_async_context(mcp_a)
        await mcp_a.initialize()

        arena_b = ArenaClient.for_player(NASH_ARENA_BASE_URL, created, "B")
        print("Both players ready.\n")

        for round_idx in range(NUM_ROUNDS):
            round_num = round_idx + 1

            state_result = await mcp_a.call_tool("get_game_state")
            state = extract_tool_text(state_result)

            if state.get("phase") == "complete":
                break

            prompt_a = build_prompt(state, "A")
            alloc_a, error_a = await llm_allocate(LLM_MODEL, prompt_a)

            alloc_b = balanced_allocation(NUM_BATTLEFIELDS, TOTAL_RESOURCES)

            if error_a:
                httpx.post(
                    f"{NASH_ARENA_BASE_URL}/session/{session_id}/action",
                    headers={"Authorization": f"Bearer {key_a}"},
                    json={"allocation": [], "forfeit": True},
                )
            else:
                await mcp_a.call_tool("submit_action", {"allocation": alloc_a})
            arena_b.submit_action(alloc_b)

            state_b = arena_b.get_state()
            if state_b.get("history"):
                last = state_b["history"][-1]
                forfeit_flag = " FORFEIT" if error_a else ""
                print(
                    f"Round {round_num:2d}: "
                    f"LLM={alloc_a if not error_a else 'FAILED'} Uniform={alloc_b} -> "
                    f"A={last['scores']['A']:.1f} B={last['scores']['B']:.1f} winner={last['winner']}"
                    f"{forfeit_flag}"
                )
            else:
                print(f"Round {round_num:2d}: LLM={alloc_a} Uniform={alloc_b} (resolving...)")

        results = arena_b.get_results()

    total_a = results.get("total_scores", {}).get("A", 0)
    total_b = results.get("total_scores", {}).get("B", 0)
    winner = results.get("winner", "Unknown")

    print()
    print("=" * 56)
    winner_label = f"LLM ({LLM_MODEL})" if winner == "A" else "UniformAgent" if winner == "B" else "Tie"
    print(f"Winner: {winner_label}")
    print(f"Final: A({LLM_MODEL})={total_a:.1f}  B(Uniform)={total_b:.1f}")
    print(f"URL: http://localhost:5173/play/colonelblotto/{session_id}")


if __name__ == "__main__":
    asyncio.run(run_match())
