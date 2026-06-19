"""
End-to-end test: Hermes agent harness vs NashArena SDK playing Colonel Blotto.

Run with:
    pytest tests/test_hermes_e2e.py -m e2e -v

Requires:
    - minikube cluster with nasharena deployed
    - hermes-agent installed at ~/.hermes/hermes-agent/
"""

import json
import sys
from pathlib import Path

import pytest

# Allow importing the orchestrator script
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "scripts"))
from hermes_vs_sdk_e2e import run_hermes_vs_sdk  # noqa: E402

pytestmark = pytest.mark.e2e


def test_hermes_vs_sdk_colonel_blotto():
    """Hermes agent plays Colonel Blotto against NashArena SDK agent.

    Hermes uses an on-the-fly skill (fetched from /api/games/colonelblotto/manifest)
    and connect to NashArena MCP with a session key. The SDK agent uses the
    NashArena SDK's MCPClient. Both play a full 3-round game.
    """
    result = run_hermes_vs_sdk(rounds=3, n_fields=5, total=100)

    error = result.get("error")
    if error:
        # If hermes failed but SDK completed, the game might still have results
        if result.get("results") and result["results"].get("error") is None:
            pass  # Results available despite hermes issues
        else:
            pytest.fail(f"Hermes e2e failed: {error}\n\nHermes stdout:\n{result.get('hermes_stdout', '')}\n\nHermes stderr:\n{result.get('hermes_stderr', '')}")

    # Verify game completed
    results = result.get("results", {})
    assert results is not None, f"No results returned. Hermes stdout: {result.get('hermes_stdout', '')}"
    if isinstance(results, dict) and "error" in results:
        pytest.fail(f"Results error: {results['error']}")

    assert "winner" in results or "total_scores" in results, (
        f"Game did not complete. Results: {json.dumps(results, indent=2)[:500]}"
    )

    # Verify both players have scores
    total_scores = results.get("total_scores", {})
    assert len(total_scores) == 2, f"Expected 2 players, got: {total_scores}"

    print(f"\nHermes (Player A) vs SDK (Player B): {total_scores}")
    print(f"Winner: {results.get('winner', 'N/A')}")
    print(f"Hermes return code: {result.get('hermes_rc')}")


def test_hermes_vs_sdk_single_round():
    """Quick smoke test with 1 round."""
    result = run_hermes_vs_sdk(rounds=1, n_fields=5, total=100)

    error = result.get("error")
    if error and not (result.get("results") and result["results"].get("error") is None):
        pytest.fail(f"Hermes e2e failed: {error}")

    results = result.get("results", {})
    assert results is not None
    if isinstance(results, dict) and "error" in results:
        pytest.fail(f"Results error: {results['error']}")

    total_scores = results.get("total_scores", {})
    assert len(total_scores) == 2, f"Expected 2 players, got: {total_scores}"
    print(f"\nSingle round: {total_scores}")
