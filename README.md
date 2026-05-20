# blotto

Colonel Blotto game simulation with heuristic and LLM-powered agents.

## Installation

```bash
pip install -e .
```

The `transformers` library will pull in PyTorch automatically. A GPU is recommended but not required when using LLM agents.

## Agents

| Agent      | Description                                                          |
| ---------- | -------------------------------------------------------------------- |
| `uniform`  | Distributes troops evenly across all battlefields                     |
| `random`   | Random (but valid) troop allocation                                   |
| `greedy`   | Copies the opponent's last move and adds one troop to each battlefield |
| `llm-local`      | Uses a local HuggingFace text-generation model to decide allocations  |
| `llm-api`  | Uses an OpenAI-compatible API (via litellm) to decide allocations     |

## Running experiments from the command line

```bash
python run_experiment.py --agent_a uniform --agent_b random --rounds 10
```

Available agent choices: `uniform`, `random`, `greedy`, `llm`, `llm-api`.

## Running the visualizer

Start the web server:

```bash
python server.py
```

Then open **http://127.0.0.1:8000** in your browser. The visualizer lets you pick two agents (including LLM agents with selectable HuggingFace models), set game parameters, and watch the match play out round by round.

### LLM model discovery

The visualizer includes a model search backed by the Hugging Face API. Set the `HF_TOKEN` environment variable for higher rate limits:

```bash
export HF_TOKEN=hf_...
python server.py
```

### API-based LLM agent

The `llm-api` agent uses [litellm](https://github.com/BerriAI/litellm) to call any OpenAI-compatible endpoint. Configure it via environment variables:

```bash
export LLM_API_BASE="http://127.0.0.1:11434/v1"
export LLM_MODEL="opencode/go"
python server.py
```
