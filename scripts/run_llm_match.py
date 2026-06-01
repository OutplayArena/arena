import asyncio
import json
import os
import sys
import re
import ast
import time
from contextlib import AsyncExitStack
from datetime import datetime, timezone

import httpx
from mcp import ClientSession, StdioServerParameters, types
from mcp.client.stdio import stdio_client

sys.stdout.reconfigure(line_buffering=True)

SESSION_ID = "36467ed8-e176-4865-9a21-fb3451c96906"
KEY_A = "nks_MzY0NjdlZDgtZTE3Ni00ODY1LTlhMjEtZmIzNDUxYzk2OTA2OkE6NzcwNmM3Y2Y5NzFkMWJhNTZjMzIzYjZlNmNkY2ZhOGQ4ZDJkOTA2MTUzYWFmYmNhMTQxNmIxNDIwMDI4N2M1ZA"
KEY_B = "nks_MzY0NjdlZDgtZTE3Ni00ODY1LTlhMjEtZmIzNDUxYzk2OTA2OkI6N2ZlY2E3OWYwM2MzNTM2MDRiNGMwYmViNWU1NzJmZDI3NTNiYWMwMDBlYTE0OTIxYTYzZjI1ZGJkZjExMjk2Nw"
NASH_ARENA_BASE_URL = os.environ.get("NASH_ARENA_BASE_URL", "http://127.0.0.1:8000/api")
OPENCODE_GO_API_KEY = os.environ.get("OPENCODE_GO_API_KEY_2", "").strip()
OPENCODE_GO_API_BASE = "https://opencode.ai/zen/v1"

PLAYER_A_MODEL = "glm-5.1"
PLAYER_A_TEMP = 0.4
PLAYER_A_BASE = "https://opencode.ai/zen/v1"
PLAYER_B_MODEL = "glm-5.1"
PLAYER_B_TEMP = 0.9
PLAYER_B_BASE = "https://opencode.ai/zen/v1"
NUM_BATTLEFIELDS = 5
TOTAL_RESOURCES = 100
NUM_ROUNDS = 3


def balanced(nf, tr):
    base = tr // nf
    alloc = [base] * nf
    for i in range(tr - sum(alloc)):
        alloc[i] += 1
    return alloc


def parse(text, nf, tr):
    m = re.search(r"\[[^\]]+\]", text)
    if m is None:
        return balanced(nf, tr)
    try:
        alloc = ast.literal_eval(m.group())
    except Exception:
        return balanced(nf, tr)
    if not isinstance(alloc, list) or len(alloc) != nf:
        return balanced(nf, tr)
    if not all(isinstance(x, int) and not isinstance(x, bool) for x in alloc):
        return balanced(nf, tr)
    if not all(x >= 0 for x in alloc) or sum(alloc) != tr:
        return balanced(nf, tr)
    return alloc


def build_prompt(state, player_label):
    history = state.get("history", [])
    rn = state.get("round", 1)
    rt = state.get("round_total", NUM_ROUNDS)
    ts = state.get("total_scores", {})
    lines = [
        f"R{rn}/{rt}. You={player_label}. Troops=100. Fields=5. "
        f"Scores A={ts.get('A',0)} B={ts.get('B',0)}."
    ]
    if history:
        for h in history[-3:]:
            lines.append(f"R{h['round']}: A={h['allocations']['A']} B={h['allocations']['B']} -> {h['winner']}")
    lines.append("Allocation:")
    return "\n".join(lines)


async def _async_llm_call(model, system, prompt, api_base, temperature):
    fallback = balanced(NUM_BATTLEFIELDS, TOTAL_RESOURCES)
    for attempt in range(5):
        try:
            t0 = time.time()
            async with httpx.AsyncClient(http2=False) as client:
                resp = await client.post(
                    f"{api_base}/chat/completions",
                    headers={
                        "Authorization": f"Bearer {OPENCODE_GO_API_KEY}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": model,
                        "messages": [
                            {"role": "system", "content": system},
                            {"role": "user", "content": prompt},
                        ],
                        "max_tokens": 16384,
                        "temperature": temperature,
                    },
                    timeout=300.0,
                )
            if resp.status_code == 429:
                wait = 30 * (attempt + 1)
                print(f"  [{model}] rate limited, waiting {wait}s...")
                await asyncio.sleep(wait)
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
            alloc = parse(text, NUM_BATTLEFIELDS, TOTAL_RESOURCES)
            print(
                f"  [{model}] {dt:.1f}s finish={finish} "
                f"content={repr(content[:60])} -> {alloc}"
                + (" (from reasoning)" if not content.strip() and reasoning else "")
                + (" (FALLBACK)" if alloc == fallback and not content.strip() else "")
            )
            return alloc, text
        except (httpx.ReadTimeout, httpx.ConnectTimeout):
            print(f"  [{model}] timeout attempt {attempt+1}/5")
    print(f"  [{model}] all retries exhausted, using balanced")
    return fallback, ""


async def llm_call(model, system, prompt, api_base, temperature):
    return await _async_llm_call(model, system, prompt, api_base, temperature)


def extract(result):
    for item in result.content:
        if isinstance(item, types.TextContent):
            try:
                return json.loads(item.text)
            except json.JSONDecodeError:
                return {"raw": item.text}
    return {}


async def make_mcp(player, key, stack):
    env = {"NASH_ARENA_BASE_URL": NASH_ARENA_BASE_URL, "NASH_ARENA_KEY": key}
    params = StdioServerParameters(
        command=sys.executable, args=["-m", "nash_arena.mcp_server"], env=env
    )
    read, write = await stack.enter_async_context(stdio_client(params))
    session = ClientSession(read, write)
    await stack.enter_async_context(session)
    await session.initialize()
    return session


async def main():
    if not OPENCODE_GO_API_KEY:
        print("ERROR: OPENCODE_GO_API_KEY is required")
        sys.exit(1)

    print(f"Session: {SESSION_ID}")
    print(f"Player A model: {PLAYER_A_MODEL}")
    print(f"Player B model: {PLAYER_B_MODEL}")
    print(f"Config: {NUM_BATTLEFIELDS} fields, {TOTAL_RESOURCES} troops, {NUM_ROUNDS} rounds\n")

    async with AsyncExitStack() as stack:
        print("Starting MCP server for Player A...")
        mcp_a = await make_mcp("A", KEY_A, stack)
        print("Starting MCP server for Player B...")
        mcp_b = await make_mcp("B", KEY_B, stack)
        print("MCP servers ready.\n")

        history = []

        for ri in range(NUM_ROUNDS):
            rn = ri + 1
            sr = await mcp_a.call_tool("get_game_state")
            state = extract(sr)
            if state.get("phase") == "complete":
                break

            pa = build_prompt(state, "A")
            pb = build_prompt(state, "B")

            (aa, _) = await llm_call(PLAYER_A_MODEL, "Output ONLY a Python list like [30,25,20,15,10]. Distribute exactly 100 troops across 5 equal battlefields.", pa, PLAYER_A_BASE, PLAYER_A_TEMP)
            (ab, _) = await llm_call(PLAYER_B_MODEL, "Output ONLY a Python list like [30,25,20,15,10]. Distribute exactly 100 troops across 5 equal battlefields.", pb, PLAYER_B_BASE, PLAYER_B_TEMP)

            ar = await mcp_a.call_tool("submit_action", {"allocation": aa})
            br = await mcp_b.call_tool("submit_action", {"allocation": ab})
            latest = extract(br)
            rhist = latest.get("history", [])
            rh = rhist[-1] if rhist else {}
            if rh:
                history.append(rh)
                print(f"R{rn:2d}: A={aa} B={ab} -> {rh.get('winner')}  scores A={rh.get('scores',{}).get('A',0)} B={rh.get('scores',{}).get('B',0)}")
            else:
                print(f"R{rn:2d}: A={aa} B={ab} (resolving)")

        rr = await mcp_a.call_tool("get_results")
        results = extract(rr)

    ta = results.get("total_scores", {}).get("A", 0)
    tb = results.get("total_scores", {}).get("B", 0)
    winner = results.get("winner", "?")
    print(f"\nFinal: A={ta} B={tb} winner={winner}")
    print("MCP servers destroyed (AsyncExitStack cleaned up).")

    out = {
        "session_id": SESSION_ID,
        "player_a": {"model": PLAYER_A_MODEL},
        "player_b": {"model": PLAYER_B_MODEL},
        "total_scores": {"A": ta, "B": tb},
        "winner": winner,
        "history": history,
        "metrics": results.get("metrics", {}),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    fn = f"results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(fn, "w") as f:
        json.dump(out, f, indent=2)
    print(f"Saved to {fn}")


if __name__ == "__main__":
    asyncio.run(main())
