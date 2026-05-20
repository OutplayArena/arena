import ast
import json
import mimetypes
import os
import re
import secrets
import threading
from concurrent.futures import ThreadPoolExecutor
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlencode, urlparse
from urllib.request import Request, urlopen

from agent import GreedyAgent, LLMAgent, LiteLLMAgent, RandomAgent
from api import BlottoGame


ROOT = Path(__file__).resolve().parent
STATIC_ROOT = ROOT / "static"

AGENTS = ["uniform", "random", "greedy", "llm-local", "llm-api"]
DEFAULT_LLM_MODEL = "Qwen/Qwen2.5-0.5B-Instruct"
DEFAULT_API_MODEL = "opencode/go"


class ParameterizedUniformAgent:
    def __init__(self, num_battlefields, total_resources):
        self.name = "UniformAgent"
        self.num_battlefields = num_battlefields
        self.total_resources = total_resources

    def act(self, history):
        base = self.total_resources // self.num_battlefields
        allocation = [base] * self.num_battlefields
        for index in range(self.total_resources - sum(allocation)):
            allocation[index] += 1
        return allocation


class ParameterizedGreedyAgent(GreedyAgent):
    def act(self, history):
        if len(history) == 0:
            return ParameterizedUniformAgent(
                self.num_battlefields,
                self.total_resources,
            ).act([])
        return super().act(history)


class ParameterizedLLMAgent(LLMAgent):
    def build_prompt(self, history):
        return f"""
You are playing Colonel Blotto.

Rules:
- There are {self.num_battlefields} battlefields.
- You have exactly {self.total_resources} troops.
- Return only a Python list of {self.num_battlefields} nonnegative integers.
- The list must sum to {self.total_resources}.
- Do not explain.

History:
{history}

Your allocation:
"""

    def parse_allocation(self, text):
        match = re.search(r"\[[^\]]+\]", text)
        if match is None:
            return ParameterizedUniformAgent(
                self.num_battlefields,
                self.total_resources,
            ).act([])

        try:
            allocation = ast.literal_eval(match.group())
        except (SyntaxError, ValueError):
            return ParameterizedUniformAgent(
                self.num_battlefields,
                self.total_resources,
            ).act([])

        if (
            isinstance(allocation, list)
            and len(allocation) == self.num_battlefields
            and all(isinstance(x, int) for x in allocation)
            and all(x >= 0 for x in allocation)
            and sum(allocation) == self.total_resources
        ):
            return allocation

        return ParameterizedUniformAgent(
            self.num_battlefields,
            self.total_resources,
        ).act([])


class ParameterizedLiteLLMAgent(LiteLLMAgent):
    pass


def search_huggingface_models(query, limit=8):
    params = urlencode(
        {
            "search": query or "text-generation",
            "pipeline_tag": "text-generation",
            "sort": "downloads",
            "direction": "-1",
            "limit": str(limit),
        }
    )
    request = Request(
        f"https://huggingface.co/api/models?{params}",
        headers={
            "Accept": "application/json",
            "User-Agent": "blotto-visualizer/1.0",
        },
    )

    hf_token = os.environ.get("HF_TOKEN") or os.environ.get("HUGGINGFACEHUB_API_TOKEN")
    if hf_token:
        request.add_header("Authorization", f"Bearer {hf_token}")

    with urlopen(request, timeout=12) as response:
        models = json.loads(response.read().decode("utf-8"))

    results = []
    for model in models:
        model_id = model.get("id")
        if not model_id:
            continue
        results.append(
            {
                "id": model_id,
                "pipeline_tag": model.get("pipeline_tag"),
                "downloads": model.get("downloads", 0),
                "likes": model.get("likes", 0),
                "tags": (model.get("tags") or [])[:8],
            }
        )
    return results


def make_agent(agent_key, num_battlefields, total_resources, model_name=None):
    if agent_key == "uniform":
        return ParameterizedUniformAgent(num_battlefields, total_resources)
    if agent_key == "random":
        return RandomAgent(num_battlefields, total_resources)
    if agent_key == "greedy":
        return ParameterizedGreedyAgent(num_battlefields, total_resources)
    if agent_key == "llm-local":
        return ParameterizedLLMAgent(
            num_battlefields,
            total_resources,
            model_name=model_name or DEFAULT_LLM_MODEL,
        )
    if agent_key == "llm-api":
        return ParameterizedLiteLLMAgent(
            num_battlefields,
            total_resources,
            model_name=model_name or DEFAULT_API_MODEL,
        )
    raise ValueError(f"Unknown agent: {agent_key}")


def simulate_match(
    agent_a_key,
    agent_b_key,
    num_rounds,
    num_battlefields,
    total_resources,
    llm_model_a=None,
    llm_model_b=None,
    run_id=None,
):
    if agent_a_key not in AGENTS:
        raise ValueError(f"Unknown agent_a: {agent_a_key}")
    if agent_b_key not in AGENTS:
        raise ValueError(f"Unknown agent_b: {agent_b_key}")

    game = BlottoGame(
        num_battlefields=num_battlefields,
        total_resources=total_resources,
    )
    agent_a = make_agent(agent_a_key, num_battlefields, total_resources, llm_model_a)
    agent_b = make_agent(agent_b_key, num_battlefields, total_resources, llm_model_b)

    history_a = []
    history_b = []
    full_history = []
    total_score_a = 0
    total_score_b = 0

    for round_idx in range(num_rounds):
        with ThreadPoolExecutor(max_workers=2) as executor:
            future_a = executor.submit(agent_a.act, history_a)
            future_b = executor.submit(agent_b.act, history_b)
            action_a = future_a.result()
            action_b = future_b.result()

        result = game.play_round(action_a, action_b)

        total_score_a += result["score_a"]
        total_score_b += result["score_b"]

        full_history.append(
            {
                "round": round_idx + 1,
                "agent_a": agent_a_key,
                "agent_b": agent_b_key,
                "llm_model_a": llm_model_a if agent_a_key in ("llm-local", "llm-api") else None,
                "llm_model_b": llm_model_b if agent_b_key in ("llm-local", "llm-api") else None,
                "num_battlefields": num_battlefields,
                "total_resources": total_resources,
                "action_a": action_a,
                "action_b": action_b,
                "score_a": result["score_a"],
                "score_b": result["score_b"],
                "total_score_a": total_score_a,
                "total_score_b": total_score_b,
                "winner": result["winner"],
            }
        )

        history_a.append(
            {
                "own_action": action_a,
                "opponent_action": action_b,
                "own_score": result["score_a"],
                "oppoenent_score": result["score_b"],
                "winner": result["winner"],
            }
        )
        history_b.append(
            {
                "own_action": action_b,
                "opponent_action": action_a,
                "own_score": result["score_b"],
                "oppoenent_score": result["score_a"],
                "winner": result["winner"],
            }
        )

        if run_id:
            RUNS[run_id] = {
                "status": "running",
                "round": round_idx + 1,
                "total_rounds": num_rounds,
                "total_score_a": total_score_a,
                "total_score_b": total_score_b,
            }

    if total_score_a > total_score_b:
        match_winner = "agent_a"
    elif total_score_b > total_score_a:
        match_winner = "agent_b"
    else:
        match_winner = "Tie"

    return {
        "agent_a": agent_a_key,
        "agent_b": agent_b_key,
        "llm_model_a": llm_model_a if agent_a_key in ("llm-local", "llm-api") else None,
        "llm_model_b": llm_model_b if agent_b_key in ("llm-local", "llm-api") else None,
        "num_rounds": num_rounds,
        "num_battlefields": num_battlefields,
        "total_resources": total_resources,
        "total_score_a": total_score_a,
        "total_score_b": total_score_b,
        "match_winner": match_winner,
        "history": full_history,
    }


RUNS = {}


def _run_async(run_id, *sim_args, **sim_kwargs):
    try:
        result = simulate_match(*sim_args, run_id=run_id, **sim_kwargs)
        RUNS[run_id] = {"status": "done", "result": result}
    except Exception as exc:
        RUNS[run_id] = {"status": "error", "error": str(exc)}


class BlottoHandler(SimpleHTTPRequestHandler):
    def end_headers(self):
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        if path == "/api/agents":
            self.send_json({"agents": AGENTS})
            return
        if path == "/api/huggingface-models":
            params = parse_qs(parsed.query)
            query = (params.get("q") or [""])[0].strip()
            limit = min(20, max(1, int((params.get("limit") or ["8"])[0])))
            try:
                self.send_json({"models": search_huggingface_models(query, limit)})
            except Exception as exc:
                self.send_json({"error": str(exc)}, status=502)
            return
        if path.startswith("/api/run/"):
            run_id = path.split("/api/run/", 1)[1]
            run = RUNS.get(run_id)
            if run is None:
                self.send_json({"error": "not found"}, status=404)
                return
            self.send_json(run)
            return

        if path == "/":
            path = "/index.html"

        self.serve_static(path)

    def do_POST(self):
        path = urlparse(self.path).path
        if path != "/api/run-experiment":
            self.send_error(404, "Not found")
            return

        try:
            length = int(self.headers.get("Content-Length", "0"))
            payload = json.loads(self.rfile.read(length) or b"{}")
            agent_a = payload.get("agent_a")
            agent_b = payload.get("agent_b")
            num_rounds = int(payload.get("num_rounds", 10))
            num_battlefields = int(payload.get("num_battlefields", 5))
            total_resources = int(payload.get("total_resources", 100))
            llm_model_a = payload.get("llm_model_a") or (
                DEFAULT_API_MODEL if agent_a == "llm-api" else DEFAULT_LLM_MODEL
            )
            llm_model_b = payload.get("llm_model_b") or (
                DEFAULT_API_MODEL if agent_b == "llm-api" else DEFAULT_LLM_MODEL
            )

            if num_rounds < 1 or num_rounds > 50:
                raise ValueError("num_rounds must be between 1 and 50")
            if num_battlefields < 1 or num_battlefields > 12:
                raise ValueError("num_battlefields must be between 1 and 12")
            if total_resources < num_battlefields or total_resources > 1000:
                raise ValueError("total_resources must be between num_battlefields and 1000")

            run_id = secrets.token_hex(8)
            RUNS[run_id] = {"status": "running"}
            threading.Thread(
                target=_run_async,
                args=(run_id, agent_a, agent_b, num_rounds, num_battlefields, total_resources),
                kwargs={"llm_model_a": llm_model_a, "llm_model_b": llm_model_b},
                daemon=True,
            ).start()
            self.send_json({"run_id": run_id, "status": "running"})
        except Exception as exc:
            self.send_json({"error": str(exc)}, status=400)

    def serve_static(self, request_path):
        target = (STATIC_ROOT / request_path.lstrip("/")).resolve()
        if STATIC_ROOT not in target.parents and target != STATIC_ROOT:
            self.send_error(403, "Forbidden")
            return
        if not target.exists() or not target.is_file():
            self.send_error(404, "Not found")
            return

        content_type = mimetypes.guess_type(target.name)[0] or "application/octet-stream"
        data = target.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def send_json(self, payload, status=200):
        data = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


def main():
    server = ThreadingHTTPServer(("127.0.0.1", 8000), BlottoHandler)
    print("Blotto visualizer running at http://127.0.0.1:8000")
    server.serve_forever()


if __name__ == "__main__":
    main()
