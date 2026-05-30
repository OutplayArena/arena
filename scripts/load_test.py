import argparse
import asyncio
import random
import sys
import time

import httpx

BALANCED = [20, 20, 20, 20, 20]
TOTAL_RESOURCES = 100
NUM_BATTLEFIELDS = 5
RETRY_MAX = 5


async def retry_request(fn, *args, **kwargs):
    for attempt in range(RETRY_MAX):
        try:
            resp = await fn(*args, **kwargs)
            resp.raise_for_status()
            return resp
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 429 and attempt < RETRY_MAX - 1:
                delay = (2 ** attempt) + random.uniform(0, 0.5)
                await asyncio.sleep(delay)
                continue
            raise


def greedy_move(history: list[dict]) -> list[int]:
    if not history:
        return list(BALANCED)

    last = history[-1]
    opponent = last["allocations"]["opponent"]
    allocation = [x + 1 for x in opponent]
    total = sum(allocation)

    while total > TOTAL_RESOURCES:
        idx = allocation.index(max(allocation))
        allocation[idx] -= 1
        total -= 1

    while total < TOTAL_RESOURCES:
        idx = allocation.index(min(allocation))
        allocation[idx] += 1
        total += 1

    return allocation


HEADERS = {"Host": "api.agent-arena.local"}


async def run_session(
    client: httpx.AsyncClient,
    base_url: str,
    session_idx: int,
    rounds: int,
    skip_mcp: bool = True,
) -> dict:
    try:
        payload = {
            "game": "blotto",
            "variant": "classic",
            "players": 2,
            "budget": [TOTAL_RESOURCES, TOTAL_RESOURCES],
            "battlefields": [
                {"id": f"battlefield_{i + 1}", "value": 1.0}
                for i in range(NUM_BATTLEFIELDS)
            ],
            "rounds": rounds,
            "seed": None,
        }

        url = f"{base_url}/api/experiment"
        if skip_mcp:
            url += "?skip_mcp=true"

        resp = await retry_request(
            client.post,
            url,
            json=payload,
            headers=HEADERS,
        )
        data = resp.json()
        session_id = data["session_id"]
        token_a = data["player_tokens"]["A"]
        token_b = data["player_tokens"]["B"]

        history_a = []
        history_b = []

        for _ in range(rounds):
            action_a = greedy_move(history_a)
            action_b = greedy_move(history_b)

            resp_a = await retry_request(
                client.post,
                f"{base_url}/api/session/{session_id}/action",
                json={"allocation": action_a},
                headers={"Authorization": f"Bearer {token_a}", **HEADERS},
            )

            resp_b = await retry_request(
                client.post,
                f"{base_url}/api/session/{session_id}/action",
                json={"allocation": action_b},
                headers={"Authorization": f"Bearer {token_b}", **HEADERS},
            )

            state = resp_b.json()
            last = state["history"][-1]
            history_a.append({
                "allocations": {
                    "opponent": last["allocations"]["B"],
                },
            })
            history_b.append({
                "allocations": {
                    "opponent": last["allocations"]["A"],
                },
            })

        resp = await retry_request(
            client.get, f"{base_url}/api/session/{session_id}/results", headers=HEADERS)
        resp.raise_for_status()
        results = resp.json()

        return {
            "session_idx": session_idx,
            "session_id": session_id,
            "status": "ok",
            "winner": results["winner"],
            "scores": results["total_scores"],
            "rounds_completed": len(results["history"]),
        }
    except Exception as exc:
        return {
            "session_idx": session_idx,
            "session_id": None,
            "status": "error",
            "error": str(exc),
        }


async def main():
    parser = argparse.ArgumentParser(description="Load test blotto with greedy agents")
    parser.add_argument(
        "--sessions", type=int, default=50,
        help="Number of concurrent sessions (default: 50)"
    )
    parser.add_argument(
        "--rounds", type=int, default=10,
        help="Number of rounds per session (default: 10)"
    )
    parser.add_argument(
        "--base-url", type=str,
        default="https://localhost:8443",
        help="Base URL of the API (default: https://localhost:8443)"
    )
    parser.add_argument(
        "--concurrency", type=int, default=10,
        help="Max concurrent sessions (default: 10)"
    )
    parser.add_argument(
        "--verify", action="store_true",
        help="Verify TLS certificate (default: skip verification)"
    )
    parser.add_argument(
        "--no-skip-mcp", action="store_true",
        help="Do NOT skip MCP server creation (creates K8s jobs per session)"
    )
    args = parser.parse_args()

    semaphore = asyncio.Semaphore(args.concurrency)

    async def bounded_run(idx: int) -> dict:
        async with semaphore:
            async with httpx.AsyncClient(verify=args.verify, timeout=120.0) as client:
                return await run_session(
                    client, args.base_url, idx, args.rounds,
                    skip_mcp=not args.no_skip_mcp,
                )

    print(f"Starting {args.sessions} sessions ({args.rounds} rounds each, "
          f"concurrency={args.concurrency}, skip_mcp={not args.no_skip_mcp})")
    print(f"Base URL: {args.base_url}")
    print("-" * 60)

    start = time.monotonic()
    tasks = [bounded_run(i) for i in range(args.sessions)]
    results = await asyncio.gather(*tasks)
    elapsed = time.monotonic() - start

    ok = [r for r in results if r["status"] == "ok"]
    errors = [r for r in results if r["status"] == "error"]

    print(f"\nDone in {elapsed:.1f}s")
    print(f"  OK:     {len(ok)}/{args.sessions}")
    print(f"  Errors: {len(errors)}/{args.sessions}")

    if ok:
        wins_a = sum(1 for r in ok if r["winner"] == "A")
        wins_b = sum(1 for r in ok if r["winner"] == "B")
        ties = sum(1 for r in ok if r["winner"] == "Tie")
        avg_score_a = sum(r["scores"]["A"] for r in ok) / len(ok)
        avg_score_b = sum(r["scores"]["B"] for r in ok) / len(ok)
        total_rounds = sum(r["rounds_completed"] for r in ok)

        print(f"  A wins: {wins_a}, B wins: {wins_b}, Ties: {ties}")
        print(f"  Avg score: A={avg_score_a:.1f}, B={avg_score_b:.1f}")
        print(f"  Total rounds completed: {total_rounds}")
        print(f"  Throughput: {args.sessions / elapsed:.1f} sessions/s, "
              f"{total_rounds / elapsed:.1f} rounds/s")

    if errors:
        print(f"\nErrors:")
        for r in errors:
            print(f"  [{r['session_idx']}] {r.get('error', 'unknown')[:120]}")

    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
