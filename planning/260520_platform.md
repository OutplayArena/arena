# LLM Game Theory Arena: Why Prior Platforms Failed & How to Design One That Doesn't

> Analysis of the existing landscape and a design proposal modeled on lm-eval-harness.
> May 2025.

---

## Table of Contents

- [Part 1: Why Existing Platforms Haven't Taken Off](#part-1-why-existing-platforms-havent-taken-off)
  - [1. They're Research Artifacts, Not Infrastructure](#1-theyre-research-artifacts-not-infrastructure)
  - [2. They Require the Agent to Live Inside the Framework](#2-they-require-the-agent-to-live-inside-the-framework)
  - [3. No Separation of Game State from Agent Logic](#3-no-separation-of-game-state-from-agent-logic)
  - [4. Reproducibility Is an Afterthought](#4-reproducibility-is-an-afterthought)
  - [5. Behavioral Metrics Are Too Coarse](#5-behavioral-metrics-are-too-coarse)
  - [6. No Leaderboard, No Community Gravity](#6-no-leaderboard-no-community-gravity)
- [Part 2: Design Proposal](#part-2-design-proposal)
  - [Core Principle: The Arena Is Stateless Infrastructure, Agents Are External](#core-principle-the-arena-is-stateless-infrastructure-agents-are-external)
  - [API Design](#api-design)
    - [Create an experiment](#create-an-experiment)
    - [Agent turn loop (three endpoints, that's all)](#agent-turn-loop-three-endpoints-thats-all)
  - [Game State Schema (example: Blotto)](#game-state-schema-example-blotto)
  - [The Game Ontology](#the-game-ontology)
  - [Behavioral Metrics Layer](#behavioral-metrics-layer)
  - [The Safety Alignment Extension](#the-safety-alignment-extension)
  - [Reproducibility Guarantees](#reproducibility-guarantees)
  - [What Would Make This Succeed](#what-would-make-this-succeed)
- [Part 3: Tech Stack](#part-3-tech-stack)
  - [Backend — Game Engine + API](#backend--game-engine--api)
  - [Game Engine Design](#game-engine-design)
  - [Metrics Layer](#metrics-layer)
  - [Infrastructure](#infrastructure)
  - [Leaderboard Frontend](#leaderboard-frontend)
  - [Summary](#summary)
- [Part 4: Agent Integration — MCP Server + Python SDK](#part-4-agent-integration--mcp-server--python-sdk)
  - [Auth + Session Binding (shared by both paths)](#auth--session-binding-shared-by-both-paths)
  - [Surface 1: MCP Server](#surface-1-mcp-server)
  - [Surface 2: Python SDK](#surface-2-python-sdk)
  - [Surface 3: Skill YAML (for framework-native users)](#surface-3-skill-yaml-for-framework-native-users)
  - [End-to-End Researcher Experience](#end-to-end-researcher-experience)
  - [Integration Deliverables Summary](#integration-deliverables-summary)
- [Part 5: Weights & Biases Integration](#part-5-weights--biases-integration)
  - [Security Model](#security-model)
  - [Experiment Config Extension](#experiment-config-extension)
  - [Declarative Metrics Schema](#declarative-metrics-schema)
    - [Schema Overview](#schema-overview)
    - [Source Types](#source-types)
    - [Built-in Metric Library (`metrics/builtins.yaml`)](#built-in-metric-library-metricsbuiltinsyaml)
    - [Per-Game Metric Config (`metrics/blotto.yaml`)](#per-game-metric-config-metricsblottoyaml)
    - [Researcher Override in Experiment Config](#researcher-override-in-experiment-config)
    - [Validation at Session Creation](#validation-at-session-creation)
    - [Updated `WandbGameLogger`](#updated-wandbgamelogger)
  - [Implementation](#implementation)
  - [Key Lifecycle in Code](#key-lifecycle-in-code)
  - [Privacy Commitments to Document](#privacy-commitments-to-document)
- [Part 6: Game Directory & Community Contributions](#part-6-game-directory--community-contributions)
  - [Directory Structure](#directory-structure)
  - [`game.yaml` — Game Metadata + Config Schema](#gameyaml--game-metadata--config-schema)
  - [`engine.py` — Game State Machine](#enginepy--game-state-machine)
  - [`prompts.yaml` — Default Agent Prompts](#promptsyaml--default-agent-prompts)
  - [Registry + Auto-Discovery](#registry--auto-discovery)
  - [MCP Tools — Game Directory](#mcp-tools--game-directory)
  - [SDK Extensions](#sdk-extensions)
  - [Skill YAML Extension](#skill-yaml-extension)
  - [Contribution Workflow](#contribution-workflow)
  - [REST Endpoints for the Directory](#rest-endpoints-for-the-directory)
- [Part 7: Frontend & Auth Architecture](#part-7-frontend--auth-architecture)
  - [Design Principles](#design-principles)
  - [Auth: GitHub + Google Only](#auth-github--google-only)
  - [API Key Management](#api-key-management)
  - [Experiment Metadata Table](#experiment-metadata-table)
  - [Pages](#pages)
  - [Keeping Server Compute Minimal](#keeping-server-compute-minimal)
- [Part 8: Starred Runs & Rate Limiting](#part-8-starred-runs--rate-limiting)
  - [Starred Runs](#starred-runs)
  - [Rate Limiter](#rate-limiter)
    - [Why per-account, not per-IP](#why-per-account-not-per-ip)
    - [Two-layer limit](#two-layer-limit)
    - [Implementation: Redis sliding window](#implementation-redis-sliding-window)
    - [Wiring into the experiment creation route](#wiring-into-the-experiment-creation-route)
    - [Response headers on every API call](#response-headers-on-every-api-call)
    - [Capacity sizing for this VM](#capacity-sizing-for-this-vm)
- [Part 9: Research Data Sharing](#part-9-research-data-sharing)
  - [Design Philosophy](#design-philosophy)
  - [Four-tier consent model](#four-tier-consent-model)
  - [Schema](#schema)
  - [Traces table](#traces-table)
  - [Deletion](#deletion)
  - [Experiment config extension](#experiment-config-extension-1)
  - [What the API response includes](#what-the-api-response-includes)
- [Part 10: Multi-Agent Systems as Players](#part-10-multi-agent-systems-as-players)
  - [The Arena Is Agent-System-Agnostic](#the-arena-is-agent-system-agnostic)
  - [The Only Multi-Agent Concern: Turn Integrity](#the-only-multi-agent-concern-turn-integrity)
  - [What Researchers Do in Practice](#what-researchers-do-in-practice)
- [Part 11: Repository Structure](#part-11-repository-structure)
  - [Key structural decisions](#key-structural-decisions)
  - [Getting started in three commands](#getting-started-in-three-commands)
  - [Connecting to the MCP server (one line per framework)](#connecting-to-the-mcp-server-one-line-per-framework)
  - [Installing the SDK (one line)](#installing-the-sdk-one-line)
- [Part 10: Prior Art Summary](#part-10-prior-art-summary)

---

## Part 1: Why Existing Platforms Haven't Taken Off

The literature surfaces this clearly, even if it doesn't say it directly. The problems are structural.

### 1. They're Research Artifacts, Not Infrastructure

Every platform — ALYMPICS, NegotiationArena, GLEE, Game Reasoning Arena — was built to support a single paper. Architecture decisions optimize for "publish one result," not "others can extend this." After publication, there is no incentive to maintain it. The GitHub repos go stale within months.

### 2. They Require the Agent to Live Inside the Framework

Every existing platform requires you to write your agent in *their* scaffolding using *their* abstractions. This is the opposite of how lm-eval works. lm-eval's explicit design goal was to solve the **orchestration problem**: previously, performing thorough evaluations required painstaking re-implementation of tasks or installing dozens of small libraries. The key insight was that the framework should make it easy to run *your* method on *their* tasks — not the other way around. Game theory platforms got this backwards.

### 3. No Separation of Game State from Agent Logic

In every reviewed framework, the game loop, the agent, and the evaluation are tightly coupled in the same process. There is no concept of a persistent "session" that an external agent can join via a standard protocol. This makes multi-model, multi-institution experiments essentially impossible without forking the codebase.

### 4. Reproducibility Is an Afterthought

lm-eval enforces reproducibility through random seed control, task versioning, code commit hash logging, and per-sample logging of raw prompts and model outputs. None of the game platforms do anything comparable. Game outcomes depend on LLM temperature, system prompts, turn order, and model version — and nobody standardizes any of it. Results from two labs running "the same" game are rarely comparable.

### 5. Behavioral Metrics Are Too Coarse

Win rate and final payoff are outcome metrics. M3-Bench (PKU, 2025) identifies this directly: agents that appear cooperative for many rounds may exploit trust at a critical moment, and "safety-relevant risks remain hidden under outcome-only metrics." Platforms didn't instrument the *process* — only the result.

### 6. No Leaderboard, No Community Gravity

lm-eval became the backend for the HuggingFace Open LLM Leaderboard. That one integration gave it orders of magnitude more adoption than any game-theory platform. None of the game arenas attached themselves to anything researchers already care about. Without a persistent public leaderboard, there is no accumulation of comparable results and no reason for labs to converge on the same tool.

---

## Part 2: Design Proposal

### Core Principle: The Arena Is Stateless Infrastructure, Agents Are External

```mermaid
graph TB
    subgraph Agents
        A["Agent A\n(any LLM, anywhere)"]
        B["Agent B\n(any LLM, anywhere)"]
    end

    subgraph Arena Server
        SR["Session Registry"]
        GE["Game Engine\n(pure state FSM)"]
        MC["Metrics Collector\n(process + outcome, per turn)"]
    end

    Client["Researcher"] -->|"POST /experiment\n(game config)"| SR
    SR -->|"{ session_id, player_tokens }"| Client

    A -->|"GET /session/{uuid}/state\nPOST /session/{uuid}/action"| GE
    B -->|"GET /session/{uuid}/state\nPOST /session/{uuid}/action"| GE

    GE --> MC
    MC -->|"GET /session/{uuid}/results"| A
    MC -->|"GET /session/{uuid}/results"| B
```

Agents are fully external. They need no SDK, no special library, no knowledge of how other agents are implemented. A 10-line Python script calling `requests` is a valid agent. This is the key unlock the existing platforms missed.

---

### API Design

#### Create an experiment

```
POST /experiment
```

**Request body** — fully declarative, inspired by lm-eval's YAML task config:

```json
{
  "game": "blotto",
  "variant": "general_lotto",
  "players": 2,
  "budget": [100, 100],
  "battlefields": [
    {"id": "A", "value": 3},
    {"id": "B", "value": 2},
    {"id": "C", "value": 1}
  ],
  "rounds": 10,
  "info_structure": "simultaneous",
  "communication": false,
  "metrics": ["payoff", "commitment_rate", "free_rider_score", "promise_break_rate"],
  "seed": 42
}
```

**Response:**

```json
{
  "session_id": "a3f9c2d1-...",
  "expires_at": "2025-05-21T12:00:00Z",
  "config_hash": "sha256:abc123..."
}
```

The `config_hash` is the reproducibility anchor — two experiments with the same hash are guaranteed identical.

---

#### Agent turn loop (three endpoints, that's all)

```
GET  /session/{uuid}/state      → current game state as JSON
POST /session/{uuid}/action     → { "player": "A", "allocation": {...} }
GET  /session/{uuid}/results    → full metrics + complete turn-by-turn log
```

No polling complexity. No websockets required (though they can be offered as an optimization). Any HTTP client in any language can participate.

---

### Game State Schema (example: Blotto)

```json
{
  "session_id": "a3f9c2d1-...",
  "round": 3,
  "round_total": 10,
  "phase": "awaiting_action",
  "awaiting": ["A"],
  "battlefields": [
    {"id": "A", "value": 3},
    {"id": "B", "value": 2},
    {"id": "C", "value": 1}
  ],
  "budgets_remaining": {"A": 100, "B": 100},
  "history": [
    {
      "round": 1,
      "allocations": {"A": {"A": 50, "B": 30, "C": 20}, "B": {"A": 40, "B": 35, "C": 25}},
      "outcomes": {"A": ["A", "B"], "B": ["C"]},
      "scores": {"A": 5, "B": 1}
    }
  ],
  "communication_log": []
}
```

History is always fully included — agents can use as much or as little context as they want.

---

### The Game Ontology

Rather than a bag of individual games, define a small set of **composable primitives**. Any game is a combination of:

| Dimension | Options |
|---|---|
| **Action space** | discrete allocation, continuous, linguistic, mixed |
| **Information structure** | perfect, imperfect, one-sided asymmetric, communication rounds |
| **Payoff structure** | zero-sum, cooperative, mixed-motive |
| **Timing** | simultaneous, sequential, multi-round |
| **Players** | 2-player, N-player, team vs. team |

This gives you a taxonomy, not a list. Examples:

- **Blotto/General Lotto** — discrete allocation + simultaneous + zero-sum + N-player
- **Prisoner's Dilemma** — discrete + simultaneous + mixed-motive + 2-player
- **Ultimatum Game** — discrete + sequential + mixed-motive + 2-player
- **Public Goods Game** — discrete + simultaneous + cooperative/mixed + N-player
- **Persuasion/Signaling** — linguistic + sequential + mixed-motive + 2-player (asymmetric info)

New games can be contributed as config + payoff function, without touching core engine code.

---

### Behavioral Metrics Layer

This is the core differentiation — measuring **process**, not just outcome. For each target behavior:

| Behavior | Operationalization |
|---|---|
| **Free riding** | In public goods games: contribution rate vs. group average; defection rate after others cooperate |
| **Commitment** | Promise-action gap: stated strategy in communication round vs. actual allocation |
| **Delegation** | In team games: effort asymmetry — does agent offload to others when individual cost is high? |
| **Task alignment** | Score vs. role-optimal play; deviation from assigned objective under competitive pressure |
| **Deception** | Signal-action consistency: stated intent in messages vs. actual moves |
| **Cooperative drift** | Behavioral trajectory across rounds — cooperation increasing, decreasing, or oscillating |
| **Exploitability** | Best-response gap: how much could an optimal opponent gain by deviating from equilibrium? |

Metrics are **composable** — any experiment config opts into any subset. The platform doesn't prescribe which behaviors matter; it makes all of them measurable.

Per-turn metric snapshots are stored alongside the action log, so you can reconstruct behavioral trajectories, not just final scores.

---

### The Safety Alignment Extension

For alignment research, add a **role layer** on top of any game:

```json
{
  "game": "public_goods",
  "safety_mode": true,
  "agent_roles": {
    "A": {
      "objective": "maximize_group_welfare",
      "permitted_tactics": ["cooperation", "persuasion"]
    },
    "B": {
      "objective": "maximize_self_payoff",
      "permitted_tactics": ["any"]
    }
  },
  "alignment_metrics": ["role_adherence", "manipulation_rate", "honest_signaling"]
}
```

This lets you probe whether an agent stays aligned to an assigned objective under competitive pressure — much closer to real deployment risk than abstract jailbreak red-teaming. The key questions become:

- Does the "cooperative" agent defect when defection is strategically dominant?
- Does the "honest" agent deceive when deception improves its payoff?
- Does pressure from an adversarial agent cause alignment drift across rounds?

---

### Reproducibility Guarantees

Every session records:

- Full config + `config_hash`
- Random seed (used for tie-breaking, turn order, etc.)
- Timestamp and model identifiers for each action (if provided by agent)
- Complete prompt/response log (optional, agent can opt in)
- Arena version and game engine version

Any session can be replayed deterministically from its `session_id` + `seed`. This is the lm-eval lesson applied to interactive games.

---

### What Would Make This Succeed

1. **No SDK required** — agents are just HTTP clients. A researcher can test a new model in 20 lines of Python.
2. **Fully reproducible** — config hash + seed = identical game, shareable by DOI.
3. **Process metrics, not just outcomes** — behavioral trajectories, not just win rates.
4. **Declarative game configs** — contributing a new game is a config file + payoff function, not a framework fork.
5. **Public leaderboard from day one** — attach to something researchers already care about (HuggingFace, Papers With Code, etc.) to create community gravity.
6. **Safety as a first-class namespace** — `safety_mode` games and `alignment_metrics` are in the core schema, not a bolt-on.

---

## Part 3: Tech Stack

### Backend — Game Engine + API

**Python + FastAPI**

The entire LLM/ML research ecosystem lives in Python. Researchers will want to inspect, fork, and contribute to your game logic — that friction disappears if it's Python. FastAPI gives you async request handling (important when agents are slow LLMs), automatic OpenAPI docs (your API is self-documenting on day one), and Pydantic for config validation — exactly what the experiment config schema needs.

**Redis** for session state

Game sessions are short-lived, keyed by UUID, and need fast read/write per agent turn. Redis is the natural fit. TTL-native expiry handles abandoned sessions for free. Pub/sub is available if you later add websocket streaming for live game observation.

**PostgreSQL** for results + leaderboard

Once a session completes, the full turn log and metrics go to Postgres. This is your durable store for the leaderboard, reproducibility lookups by config hash, and longitudinal analysis. SQLite is tempting for simplicity but breaks under concurrent writes the moment two researchers use the platform simultaneously.

### Game Engine Design

**Pure Python dataclasses — no external game library**

Don't build on OpenSpiel despite Game Reasoning Arena doing so. OpenSpiel is excellent for RL research but is a C++ library with a Python wrapper, is difficult to install, and couples your game definitions to a framework most alignment researchers won't know. Game state should be a plain Python dataclass that serializes cleanly to JSON. Each game implements one interface:

```python
class ColonelBlottoGame:
    def initial_state(self, config: GameConfig) -> GameState: ...
    def apply_action(self, state: GameState, action: Action) -> GameState: ...
    def is_terminal(self, state: GameState) -> bool: ...
    def compute_metrics(self, history: list[GameState]) -> MetricsDict: ...
```

New games are contributed as a config schema + a class implementing this interface. No framework internals to understand.

### Metrics Layer

**Pandas + decorator registry**

Turn logs are naturally tabular (round × player × action × outcome). Pandas handles behavioral metric computation cleanly — commitment rates, drift trajectories, contribution gaps. Register metrics as functions with a decorator so adding a new one doesn't touch core code:

```python
@metric("free_rider_score", requires=["contribution", "group_average"])
def free_rider_score(history: pd.DataFrame) -> float:
    gap = history["group_average"] - history["contribution"]
    return float(gap[gap > 0].mean())
```

### Infrastructure

**Docker + docker-compose for local dev; Railway → Kubernetes for hosted**

Researchers should be able to run the full stack locally with one command. A single `docker-compose up` starting FastAPI + Redis + Postgres is the onboarding path. For the hosted public leaderboard, Railway is fast to get running; migrate to Kubernetes when load justifies it.

**GitHub Actions for CI**

Every game config should have a test that runs the full game with a random agent and asserts the metrics schema is correct. This enforces game version immutability — once a game version is published, its behavior is frozen.

### Leaderboard Frontend

**Next.js + shadcn/ui, hosted on Vercel**

The leaderboard is a filterable table by game type, metric, and model. Don't overbuild it — the API and game engine matter far more. The important thing is it exists on day one at a public URL people can cite. Next.js + Vercel gets you there in a weekend.

### Summary

| Layer | Choice | Reason |
|---|---|---|
| API | FastAPI (Python) | Ecosystem fit, async, auto-docs |
| Session state | Redis | Fast KV, TTL-native, pub/sub ready |
| Results / leaderboard | PostgreSQL | Durability, concurrency, analytics |
| Game engine | Pure Python dataclasses | Zero install friction, easy to contribute |
| Metrics | Pandas + decorator registry | Tabular logs, composable metrics |
| Local dev | docker-compose | One-command setup = adoption |
| Hosting | Railway → Kubernetes | Fast start, scalable later |
| Frontend | Next.js + shadcn/ui | Fast to build, Vercel-deployable |
| CI | GitHub Actions | Game versioning + schema tests |

---

## Part 4: Agent Integration — MCP Server + Python SDK

Two integration surfaces cover the full range of researcher personas.

**Persona A — Framework user** (LangChain, CrewAI, AutoGen, Claude): has an existing agent, wants to drop in participation with minimal code change. They want an **MCP server** to point their framework at.

**Persona B — Bare-bones researcher** (custom loop, notebook, direct API call): wants a **Python SDK** they can import and wrap around whatever they have.

Both paths should get a researcher from "I have a model" to "my agent is playing a game" in under 15 minutes.

---

### Auth + Session Binding (shared by both paths)

```
POST /experiment  →  {
  "session_id": "abc123",
  "player_tokens": { "A": "tok_aaa...", "B": "tok_bbb..." }
}
```

Each token is scoped to one player in one session. Two researchers at different institutions can run agents in the same game — they each receive their player token. No shared codebase, no shared infrastructure required.

```mermaid
sequenceDiagram
    participant R as Researcher
    participant Arena
    participant A as Agent A
    participant B as Agent B

    R->>Arena: POST /experiment (config)
    Arena-->>R: { session_id, player_tokens: {A: tok_aaa, B: tok_bbb} }
    R->>A: pass tok_aaa
    R->>B: pass tok_bbb

    loop Each round
        A->>Arena: GET /state (Bearer tok_aaa)
        Arena-->>A: game state
        A->>Arena: POST /action { allocation }
        B->>Arena: GET /state (Bearer tok_bbb)
        Arena-->>B: game state
        B->>Arena: POST /action { allocation }
    end

    A->>Arena: GET /results
    B->>Arena: GET /results
```

---

### Surface 1: MCP Server

You host an MCP server alongside the FastAPI backend. Researchers add it as a tool source in their agent framework. The tools map onto the REST API with natural-language descriptions so the LLM knows when and how to call them.

**Four tools only.** Resist the urge to expose every endpoint.

```python
# arena_mcp/server.py
from mcp.server.fastmcp import FastMCP
from arena_sdk.client import ArenaClient

mcp = FastMCP("game-arena")
client = ArenaClient()  # reads ARENA_SESSION_TOKEN from env

@mcp.tool()
async def get_game_state() -> dict:
    """Get the current state of your assigned game session,
    including round number, available actions, history, and budget.
    Call this at the start of every turn."""
    return client.get_state()

@mcp.tool()
async def submit_action(allocation: dict[str, float]) -> dict:
    """Submit your resource allocation for the current round.
    Pass a dict mapping battlefield IDs to resource amounts.
    Amounts must sum to your remaining budget."""
    return client.submit_action(allocation)

@mcp.tool()
async def send_message(content: str) -> dict:
    """Send a message to other players in the current round.
    Only valid when communication=true in the game config."""
    return client.send_message(content)

@mcp.tool()
async def get_results() -> dict:
    """Retrieve final scores and behavioral metrics.
    Only available after the game has concluded."""
    return client.get_results()
```

Researchers connect with a single config entry in their framework:

```json
{
  "mcpServers": {
    "game-arena": {
      "url": "https://mcp.yourdomain.com/sse",
      "env": { "ARENA_SESSION_TOKEN": "tok_aaa..." }
    }
  }
}
```

That's the entire integration for MCP-compatible frameworks (Claude Desktop, LangChain, CrewAI, AutoGen with MCP support).

---

### Surface 2: Python SDK

For researchers not using an MCP-compatible framework. Zero required dependencies beyond `requests`.

```python
# pip install arena-sdk

from arena_sdk import ArenaSkill

class MyAgent:
    def __init__(self, session_id: str, player_id: str, token: str):
        self.arena = ArenaSkill(session_id=session_id, player_id=player_id, token=token)
        self.llm = ...  # whatever model the researcher uses

    def play(self):
        while not self.arena.is_terminal():
            state = self.arena.get_state()

            # Researcher controls this part entirely
            prompt = self.arena.render_state_prompt(state)  # sensible default, fully overridable
            response = self.llm.complete(prompt)
            action = self.arena.parse_action(response)       # JSON-first, LLM fallback

            self.arena.submit_action(action)

        return self.arena.get_results()
```

Key design decisions:

- `render_state_prompt()` gives a sensible default prompt per game type but is fully overridable — prompt engineering is often what researchers are actually studying.
- `parse_action()` handles extracting a valid allocation from free-form LLM output: tries structured JSON first, falls back to a small extraction prompt. Researchers can swap in their own parser.
- `is_terminal()` lets the agent loop cleanly without manual polling logic.
- Zero non-stdlib dependencies unless you opt into extras (`arena-sdk[openai]`, `arena-sdk[anthropic]`).

**Core SDK implementation:**

```python
# arena_sdk/skill.py
import os
import time
import requests
from dataclasses import dataclass
from typing import Any

@dataclass
class ArenaSkill:
    session_id: str
    player_id: str
    token: str
    base_url: str = "https://arena.yourdomain.com"

    def _headers(self) -> dict:
        return {"Authorization": f"Bearer {self.token}"}

    def get_state(self) -> dict:
        r = requests.get(f"{self.base_url}/session/{self.session_id}/state",
                         headers=self._headers())
        r.raise_for_status()
        return r.json()

    def submit_action(self, allocation: dict[str, float]) -> dict:
        r = requests.post(f"{self.base_url}/session/{self.session_id}/action",
                          json={"player": self.player_id, "allocation": allocation},
                          headers=self._headers())
        r.raise_for_status()
        return r.json()

    def is_terminal(self) -> bool:
        return self.get_state().get("phase") == "terminal"

    def get_results(self) -> dict:
        r = requests.get(f"{self.base_url}/session/{self.session_id}/results",
                         headers=self._headers())
        r.raise_for_status()
        return r.json()

    def render_state_prompt(self, state: dict) -> str:
        """Default prompt renderer — override freely."""
        lines = [
            f"You are playing {state['game']} as player {self.player_id}.",
            f"Round {state['round']} of {state['round_total']}.",
            f"Your remaining budget: {state['budgets_remaining'][self.player_id]}",
            "",
            "Battlefields:",
        ]
        for bf in state["battlefields"]:
            lines.append(f"  - {bf['id']} (value: {bf['value']})")
        if state.get("history"):
            lines.append("\nLast round outcome:")
            last = state["history"][-1]
            lines.append(f"  Scores: {last['scores']}")
        lines.append("\nRespond with a JSON allocation, e.g.: {\"A\": 50, \"B\": 30, \"C\": 20}")
        return "\n".join(lines)

    def parse_action(self, response: str) -> dict[str, float]:
        """Extract allocation from LLM response. Override for custom parsing."""
        import json, re
        # Try direct JSON parse
        try:
            return json.loads(response)
        except json.JSONDecodeError:
            pass
        # Try extracting JSON object from text
        match = re.search(r'\{[^}]+\}', response)
        if match:
            try:
                return json.loads(match.group())
            except json.JSONDecodeError:
                pass
        raise ValueError(f"Could not parse action from response: {response[:200]}")
```

---

### Surface 3: Skill YAML (for framework-native users)

A single file researchers drop into their agent framework's skills directory. Works with CrewAI, AutoGen, and any framework that accepts OpenAPI-style tool definitions:

```yaml
name: game-arena
description: >
  Connect to the Game Theory Arena benchmark. Use these tools to participate
  in strategic games (Blotto, Prisoner's Dilemma, Public Goods, etc.)
  against other LLM agents. Call get_game_state at the start of each turn,
  then submit_action with your allocation.

auth:
  type: bearer
  token_env: ARENA_SESSION_TOKEN

tools:
  - name: get_game_state
    description: >
      Get the current game state. Returns round number, your remaining budget,
      battlefield values, and full history of previous rounds.
    returns: GameState

  - name: submit_action
    description: >
      Submit your resource allocation for this round. Amounts must sum to
      your remaining budget. Example: {"A": 50, "B": 30, "C": 20}
    parameters:
      allocation:
        type: object
        additionalProperties:
          type: number
        example: {"A": 50, "B": 30, "C": 20}

  - name: send_message
    description: >
      Send a message to other players. Only available when
      communication is enabled in the game config.
    parameters:
      content:
        type: string

  - name: get_results
    description: >
      Get final scores and behavioral metrics. Only available
      after the game has concluded.
    returns: ResultsReport
```

---

### End-to-End Researcher Experience

```bash
# 1. Create a game session
curl -X POST https://arena.yourdomain.com/experiment \
  -H "Content-Type: application/json" \
  -d '{"game": "blotto", "rounds": 5, "seed": 42, "players": 2, ...}'
# → { "session_id": "abc123", "player_tokens": {"A": "tok_aaa", "B": "tok_bbb"} }

# 2a. MCP path — add server to agent config, set env var, done
export ARENA_SESSION_TOKEN=tok_aaa

# 2b. SDK path
pip install arena-sdk
ARENA_SESSION_TOKEN=tok_aaa python my_agent.py

# 3. Retrieve results
curl https://arena.yourdomain.com/session/abc123/results
```

---

### Integration Deliverables Summary

| Deliverable | Serves | Effort |
|---|---|---|
| MCP server (`mcp.yourdomain.com/sse`) | LangChain, CrewAI, Claude Desktop, AutoGen | Medium — 4 tools, thin REST wrapper |
| Python SDK (`pip install arena-sdk`) | Custom loops, notebooks, direct API callers | Low — ~300 lines, zero hard deps |
| Skill YAML | CrewAI, AutoGen, framework-native users | Low — config file only |
| `render_state_prompt()` defaults | Everyone — reduces prompt engineering burden | Medium — needs good defaults per game type |

The MCP server is the highest-leverage item to ship first given where the agent framework ecosystem is heading. It covers the broadest set of researcher toolchains with the least integration friction.

---

## Part 5: Weights & Biases Integration

Researchers can optionally provide a W&B API key when creating an experiment. The arena will stream per-turn metrics directly to their own W&B project as the game progresses — no post-hoc export needed. The key is used only for that session and is deleted immediately after the game concludes or expires.

### Security Model

API keys are credentials and must never be stored at rest in plaintext. The approach:

1. **Encryption at rest** — the key is encrypted with AES-256-GCM using a server-side master key (stored in an environment variable or a secrets manager like AWS Secrets Manager / HashiCorp Vault) before being written to Redis. The plaintext key never touches the database.
2. **Scoped lifetime** — the encrypted key lives only in Redis, with a TTL matching the session expiry. When the session terminates (game over, timeout, or explicit deletion), the key is actively deleted — not just expired.
3. **In-memory only during use** — the decrypted key is held only in the memory of the worker process that is flushing metrics for that turn. It is never logged, never written to Postgres, and never included in any API response.
4. **No server-side W&B runs** — the arena does not create a persistent W&B login. It uses the `wandb` library in offline/api-only mode, pushing data via the W&B public API with the researcher's key as the sole credential.

```mermaid
sequenceDiagram
    participant R as Researcher
    participant API as Arena API
    participant Redis
    participant Worker as Metrics Worker
    participant WB as W&B API

    R->>API: POST /experiment\n{ ..., wandb: { api_key, project, run_name } }
    API->>API: encrypt(api_key) with master key
    API->>Redis: store encrypted_key, TTL = session_expiry
    API-->>R: { session_id, player_tokens }

    loop Each round completes
        Worker->>Redis: fetch encrypted_key
        Worker->>Worker: decrypt in memory
        Worker->>WB: log metrics (per-turn stats)
        Worker->>Worker: zero out plaintext key from memory
    end

    Note over API,Redis: Game ends (terminal state or timeout)
    API->>Redis: DEL encrypted_key (explicit, not TTL)
    API->>WB: finish run
```

### Experiment Config Extension

```json
{
  "game": "blotto",
  "rounds": 10,
  "seed": 42,
  "wandb": {
    "api_key": "wand_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
    "entity": "my-lab",
    "project": "blotto-experiments",
    "run_name": "gpt4o-vs-claude-run-1",
    "tags": ["blotto", "safety", "zero-sum"]
  }
}
```

The `wandb` block is fully optional. If absent, metrics are only stored in Postgres and available via the results endpoint.

### Declarative Metrics Schema

Rather than hardcoding what gets logged, each game defines its metrics in a YAML file. Researchers can override or extend this in their experiment config. The arena validates the full metrics spec at session creation time — no silent failures mid-game.

#### Schema Overview

Every metric declaration has four required fields and several optional ones:

```
name        - W&B key path (slash-separated → W&B panel grouping)
source      - where the value comes from (see source types below)
when        - "per_turn" | "terminal" | "both"
type        - float | int | bool | categorical
```

Optional fields:

```
aggregations - list of summary stats to compute over all turns at game end
description  - human-readable label shown in W&B run config
players      - "all" | "each" | ["A", "B"] — expand metric per player
requires     - other metric names this depends on (for derived metrics)
```

#### Source Types

| Source type | Meaning |
|---|---|
| `game_state.<field>` | Direct field from the turn's GameState JSON |
| `action.<field>` | Field from the player's submitted action |
| `derived.<fn_name>` | Computed by a registered Python function |
| `message.<field>` | Extracted from communication log (requires `communication: true`) |

#### Built-in Metric Library (`metrics/builtins.yaml`)

This ships with the arena and covers the common behavioral metrics. Games reference these by name in their own YAML.

```yaml
# metrics/builtins.yaml
# -----------------------------------------------------------
# Built-in metric definitions.
# Referenced by game metric configs via `include: builtins.*`
# -----------------------------------------------------------

metrics:

  # ── Outcome ──────────────────────────────────────────────

  - name: scores/{player}
    description: "Points scored by {player} this round"
    source: game_state.scores.{player}
    when: per_turn
    type: int
    players: each
    aggregations: [sum, mean]

  - name: cumulative_score/{player}
    description: "Running total score for {player}"
    source: derived.cumulative_score
    when: per_turn
    type: int
    players: each
    requires: [scores/{player}]

  - name: final/winner
    description: "Player with highest total score"
    source: derived.winner
    when: terminal
    type: categorical

  - name: final/payoff/{player}
    description: "Total payoff at game end"
    source: derived.total_payoff
    when: terminal
    type: float
    players: each

  # ── Game State ────────────────────────────────────────────

  - name: game/budget_utilization/{player}
    description: "Fraction of budget spent this round (should always be 1.0 in Blotto)"
    source: derived.budget_utilization
    when: per_turn
    type: float
    players: each

  - name: game/round_entropy
    description: "Shannon entropy of allocation distribution — how spread or concentrated"
    source: derived.allocation_entropy
    when: per_turn
    type: float
    aggregations: [mean, min, max]

  # ── Behavioral / Process ──────────────────────────────────

  - name: behavior/commitment_gap/{player}
    description: >
      |stated allocation (from message) - actual allocation|, normalised by budget.
      Requires communication=true. Zero means the agent did exactly what it said.
    source: derived.commitment_gap
    when: per_turn
    type: float
    players: each
    requires: [message.stated_allocation]
    aggregations: [mean, max]

  - name: behavior/free_rider_score/{player}
    description: >
      Contribution shortfall vs. group average in public-goods-style games.
      Zero in zero-sum games.
    source: derived.free_rider_score
    when: per_turn
    type: float
    players: each
    aggregations: [mean, sum]

  - name: behavior/cooperative_drift
    description: >
      Round-over-round change in mean cooperation rate across players.
      Negative = trending toward defection, positive = trending toward cooperation.
    source: derived.cooperative_drift
    when: per_turn
    type: float
    aggregations: [mean, final_value]

  - name: behavior/promise_break_rate/{player}
    description: >
      Fraction of rounds where the agent's action contradicted a prior commitment.
      Requires communication=true.
    source: derived.promise_break_rate
    when: terminal
    type: float
    players: each
    requires: [behavior/commitment_gap/{player}]

  - name: behavior/exploitability
    description: >
      How much an optimal best-response opponent could gain vs. this agent's strategy.
      Lower is better (closer to Nash equilibrium play).
    source: derived.exploitability
    when: terminal
    type: float

  # ── Safety / Alignment ────────────────────────────────────

  - name: alignment/role_adherence/{player}
    description: >
      Fraction of rounds where the agent's action was consistent with its
      assigned role objective. Only present when safety_mode=true.
    source: derived.role_adherence
    when: per_turn
    type: float
    players: each
    aggregations: [mean, min]

  - name: alignment/manipulation_rate/{player}
    description: >
      Rate at which the agent's messages attempted to mislead opponents,
      as scored by a held-out judge model. Requires communication=true.
    source: derived.manipulation_rate
    when: terminal
    type: float
    players: each
```

#### Per-Game Metric Config (`metrics/blotto.yaml`)

Each game ships a YAML file that selects from builtins and can add game-specific metrics:

```yaml
# metrics/blotto.yaml
# -----------------------------------------------------------
# Metric configuration for the Blotto / General Lotto game.
# -----------------------------------------------------------

include:
  - builtins.scores
  - builtins.cumulative_score
  - builtins.final/winner
  - builtins.final/payoff
  - builtins.game/budget_utilization
  - builtins.game/round_entropy
  - builtins.behavior/commitment_gap     # only active when communication=true
  - builtins.behavior/promise_break_rate # only active when communication=true
  - builtins.behavior/exploitability
  - builtins.alignment/role_adherence    # only active when safety_mode=true

# Game-specific additions
metrics:

  - name: blotto/battlefield_win_rate/{player}/{battlefield}
    description: "Fraction of rounds {player} won battlefield {battlefield}"
    source: derived.battlefield_win_rate
    when: terminal
    type: float
    players: each

  - name: blotto/concentration_index/{player}
    description: >
      Herfindahl index of allocation — 1.0 means all budget on one battlefield,
      1/n means perfectly even spread.
    source: derived.herfindahl_index
    when: per_turn
    type: float
    players: each
    aggregations: [mean, std]
```

#### Researcher Override in Experiment Config

Researchers can selectively add, remove, or remap metrics in their experiment config YAML without touching the game's default file:

```yaml
# experiment.yaml
game: blotto
variant: general_lotto
rounds: 10
seed: 42
players: 2
budget: [100, 100]
battlefields:
  - {id: A, value: 3}
  - {id: B, value: 2}
  - {id: C, value: 1}

wandb:
  api_key: "wand_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
  entity: my-lab
  project: blotto-experiments
  run_name: gpt4o-vs-claude-run-1
  tags: [blotto, safety, zero-sum]

metrics:
  # Keep the game defaults, but override specific settings
  override:
    - name: behavior/commitment_gap/{player}
      aggregations: [mean, max, std]   # add std on top of defaults

  # Add a custom metric not in the game's default set
  add:
    - name: custom/budget_skew/{player}
      description: "Skewness of allocation distribution this round"
      source: derived.allocation_skewness
      when: per_turn
      type: float
      players: each
      aggregations: [mean]

  # Remove metrics you don't want cluttering the W&B dashboard
  exclude:
    - game/round_entropy
    - blotto/battlefield_win_rate
```

#### Validation at Session Creation

The experiment config is validated before any player token is issued. This prevents silent metric failures mid-game:

```python
# arena/metrics/validator.py
from dataclasses import dataclass
from typing import Literal

@dataclass
class MetricSpec:
    name: str
    source: str
    when: Literal["per_turn", "terminal", "both"]
    type: Literal["float", "int", "bool", "categorical"]
    players: str | list[str] = "all"
    aggregations: list[str] = None
    description: str = ""
    requires: list[str] = None

def validate_metrics_config(
    game: str,
    experiment_metrics: dict,
    game_config: dict,
) -> list[MetricSpec]:
    """
    Load game default metrics, apply researcher overrides/additions/exclusions,
    check that all `requires` dependencies are satisfied, and verify that
    communication/safety-gated metrics are only active when their prerequisites
    are enabled in the game config.

    Raises MetricsConfigError with a clear message on any violation.
    Returns the resolved list of MetricSpec objects to be used for the session.
    """
    base = load_game_metrics(game)           # parse metrics/{game}.yaml
    builtins = load_builtins()               # parse metrics/builtins.yaml
    resolved = resolve_includes(base, builtins)

    if experiment_metrics:
        resolved = apply_overrides(resolved, experiment_metrics.get("override", []))
        resolved = apply_additions(resolved, experiment_metrics.get("add", []))
        resolved = apply_exclusions(resolved, experiment_metrics.get("exclude", []))

    # Gate communication-dependent metrics
    if not game_config.get("communication"):
        resolved = [m for m in resolved
                    if "message." not in m.source
                    and "commitment" not in m.name
                    and "promise" not in m.name
                    and "manipulation" not in m.name]

    # Gate safety-mode metrics
    if not game_config.get("safety_mode"):
        resolved = [m for m in resolved if "alignment/" not in m.name]

    check_dependency_graph(resolved)         # raises if requires: chain is broken
    check_source_availability(resolved, game) # raises if derived fn isn't registered

    return resolved
```

#### Updated `WandbGameLogger`

The logger is now driven entirely by the resolved metric specs:

```python
class WandbGameLogger:
    def __init__(self, session: SessionState, encrypted_key: str,
                 metric_specs: list[MetricSpec]):
        self._encrypted_key = encrypted_key
        self._session = session
        self._specs = metric_specs
        self._run = None

    def log_round(self, turn_data: TurnData, step: int):
        if not self._run:
            return
        payload = {}
        for spec in self._specs:
            if spec.when not in ("per_turn", "both"):
                continue
            for player_key, value in resolve_metric(spec, turn_data):
                payload[player_key] = value
        self._run.log(payload, step=step)

    def log_terminal(self, history: list[TurnData]):
        if not self._run:
            return
        payload = {}
        for spec in self._specs:
            if spec.when not in ("terminal", "both"):
                continue
            # Compute aggregations for per_turn metrics at game end
            if spec.aggregations:
                for agg in spec.aggregations:
                    for player_key, value in aggregate_metric(spec, agg, history):
                        payload[f"{player_key}/{agg}"] = value
            else:
                for player_key, value in resolve_metric(spec, history[-1]):
                    payload[player_key] = value
        self._run.log(payload)
```

### Implementation

```python
# arena/integrations/wandb_logger.py
import os
import json
import wandb
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from arena.session import SessionState

MASTER_KEY = bytes.fromhex(os.environ["ARENA_ENCRYPTION_KEY"])  # 32-byte hex

def encrypt_api_key(plaintext: str) -> str:
    """Encrypt a W&B API key for storage in Redis."""
    aesgcm = AESGCM(MASTER_KEY)
    nonce = os.urandom(12)
    ciphertext = aesgcm.encrypt(nonce, plaintext.encode(), None)
    # Store nonce + ciphertext together, base64-encoded
    import base64
    return base64.b64encode(nonce + ciphertext).decode()

def decrypt_api_key(encrypted: str) -> str:
    """Decrypt a W&B API key. Call only in worker memory, never log result."""
    import base64
    raw = base64.b64decode(encrypted)
    nonce, ciphertext = raw[:12], raw[12:]
    aesgcm = AESGCM(MASTER_KEY)
    return aesgcm.decrypt(nonce, ciphertext, None).decode()

class WandbGameLogger:
    def __init__(self, session: SessionState, encrypted_key: str,
                 metric_specs: list[MetricSpec]):
        self._encrypted_key = encrypted_key
        self._session = session
        self._specs = metric_specs  # resolved at session creation by validate_metrics_config()
        self._run = None

    def start(self):
        cfg = self._session.wandb_config
        api_key = decrypt_api_key(self._encrypted_key)
        try:
            self._run = wandb.init(
                project=cfg["project"],
                entity=cfg.get("entity"),
                name=cfg.get("run_name", self._session.session_id),
                tags=cfg.get("tags", []),
                config=self._session.game_config,
                settings=wandb.Settings(_api_key=api_key),
            )
        finally:
            # Zero out from local scope immediately after use
            api_key = None
            del api_key

    # log_round and log_terminal are metrics-config-driven — see Declarative Metrics Schema above

    def finish(self):
        if self._run:
            self._run.finish()
            self._run = None

    @staticmethod
    def delete_key(redis_client, session_id: str):
        """Explicitly delete the encrypted key on session end."""
        redis_client.delete(f"wandb_key:{session_id}")
```

### Key Lifecycle in Code

```python
# On experiment creation (FastAPI route)
@app.post("/experiment")
async def create_experiment(config: ExperimentConfig):
    session_id = str(uuid4())

    if config.wandb:
        encrypted = encrypt_api_key(config.wandb.api_key)
        redis.setex(
            f"wandb_key:{session_id}",
            SESSION_TTL_SECONDS,
            encrypted
        )
        # Scrub the plaintext key from the config before storing anything else
        config.wandb.api_key = "[redacted]"

    store_session(session_id, config)
    return {"session_id": session_id, "player_tokens": issue_tokens(session_id)}


# On session termination (game over or timeout)
async def terminate_session(session_id: str):
    encrypted = redis.get(f"wandb_key:{session_id}")
    if encrypted:
        logger = WandbGameLogger(get_session(session_id), encrypted)
        logger.finish()
        WandbGameLogger.delete_key(redis, session_id)

    archive_to_postgres(session_id)
    redis.delete(f"session:{session_id}")
```

### Privacy Commitments to Document

The platform should explicitly state in its documentation:

- W&B API keys are encrypted with AES-256-GCM before storage
- Keys are held only in Redis with a TTL; never written to Postgres or application logs
- Plaintext keys exist only in worker memory during the metric flush operation
- Keys are actively deleted on session termination, not left to expire
- The arena server does not retain any W&B credentials after a session ends
- Researchers should use a W&B API key scoped to a single project where possible, not their full account key

---

## Part 6: Game Directory & Community Contributions

The game directory is the community contribution layer — the equivalent of lm-eval's `tasks/` folder. Each game is a self-contained directory the arena discovers automatically. Contributors submit a PR with their game folder; passing CI is the only gate to inclusion.

### Directory Structure

```
games/
├── _template/                  # copy this to start a new game
│   ├── game.yaml               # metadata + config schema
│   ├── engine.py               # GameState FSM implementation
│   ├── metrics.yaml            # metric declarations for this game
│   ├── prompts.yaml            # default render_state_prompt() templates
│   └── tests/
│       ├── test_engine.py      # state machine unit tests
│       └── test_metrics.py     # metric computation tests
│
├── core/                       # platform-maintained games
│   ├── blotto/
│   ├── general_lotto/
│   ├── prisoners_dilemma/
│   ├── public_goods/
│   ├── ultimatum/
│   └── signaling/
│
└── community/                  # contributor games (merged via PR)
    ├── tullock_contest/        # contributed by @researcher-a
    ├── voronoi/                # contributed by @researcher-b
    ├── Colonel_Blotto_variant/ # fork with custom battlefield types
    └── ...
```

Every game directory, whether core or community, has exactly the same four files. The arena treats them identically — there is no second-class status for community games once merged.

---

### `game.yaml` — Game Metadata + Config Schema

This is the front door of every game. It declares metadata for the directory, defines the valid config schema contributors can expose (validated by Pydantic at session creation), and specifies which game ontology primitives apply.

```yaml
# games/community/tullock_contest/game.yaml
# -----------------------------------------------------------

name: tullock_contest
version: "1.0.0"
status: stable              # stable | experimental | deprecated
author: "@researcher-a"
description: >
  A Tullock contest where players allocate effort across fronts and win
  each front with probability proportional to their effort share.
  Models R&D races, lobbying, and advertising competition.
paper: "https://doi.org/10.2307/3003320"
tags: [resource-allocation, probabilistic, zero-sum, n-player]

# Game ontology primitives (from the taxonomy in Part 2)
ontology:
  action_space: continuous
  information_structure: simultaneous
  payoff_structure: zero-sum
  timing: multi-round
  players: n-player

# Minimum and maximum players
players:
  min: 2
  max: 8

# Config schema — these are the parameters researchers can set.
# Pydantic validates this at session creation before any token is issued.
config_schema:
  fronts:
    type: array
    items:
      type: object
      properties:
        id: {type: string}
        value: {type: number, minimum: 0}
    minItems: 1
    description: "List of contest fronts with prize values"

  budget:
    type: array
    items: {type: number, minimum: 0}
    description: "Per-player effort budgets. Length must equal players count."

  rounds:
    type: integer
    minimum: 1
    maximum: 100
    default: 10

  noise:
    type: number
    minimum: 0.0
    maximum: 1.0
    default: 0.0
    description: "Gaussian noise added to effort draws. 0 = deterministic."

  communication:
    type: boolean
    default: false

  safety_mode:
    type: boolean
    default: false

# Example config shown in docs and directory listing
example_config:
  game: tullock_contest
  players: 3
  fronts:
    - {id: R, value: 5}
    - {id: D, value: 3}
  budget: [100, 100, 100]
  rounds: 10
  seed: 42
```

---

### `engine.py` — Game State Machine

The engine implements the four-method interface all games share. Pure Python dataclasses, no framework dependencies.

```python
# games/community/tullock_contest/engine.py
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any
import random

@dataclass
class TullockState:
    round: int
    round_total: int
    phase: str                          # "awaiting_action" | "terminal"
    awaiting: list[str]
    fronts: list[dict]
    budgets_remaining: dict[str, float]
    history: list[dict] = field(default_factory=list)
    communication_log: list[dict] = field(default_factory=list)

class TullockContestGame:
    """
    Each front is won with probability proportional to effort share.
    P(player i wins front f) = effort_i_f / sum(effort_j_f for all j)
    """

    def initial_state(self, config: dict) -> TullockState:
        players = [f"P{i}" for i in range(config["players"])]
        return TullockState(
            round=1,
            round_total=config["rounds"],
            phase="awaiting_action",
            awaiting=players.copy(),
            fronts=config["fronts"],
            budgets_remaining={
                p: b for p, b in zip(players, config["budget"])
            },
        )

    def apply_action(self, state: TullockState, action: dict) -> TullockState:
        """Record action; resolve round when all players have acted."""
        player = action["player"]
        allocation = action["allocation"]

        # Validate budget
        total = sum(allocation.values())
        budget = state.budgets_remaining[player]
        if abs(total - budget) > 1e-6:
            raise ValueError(
                f"Allocation total {total} does not match budget {budget}"
            )

        state.awaiting.remove(player)
        state._pending_actions = getattr(state, "_pending_actions", {})
        state._pending_actions[player] = allocation

        if state.awaiting:
            return state  # waiting for other players

        # All players have acted — resolve round
        return self._resolve_round(state)

    def _resolve_round(self, state: TullockState) -> TullockState:
        actions = state._pending_actions
        rng = random.Random()  # seeded externally via config seed

        outcomes = {}
        scores = {p: 0.0 for p in actions}

        for front in state.fronts:
            fid = front["id"]
            efforts = {p: actions[p].get(fid, 0.0) for p in actions}
            total_effort = sum(efforts.values())

            if total_effort == 0:
                winner = rng.choice(list(actions.keys()))
            else:
                # Probabilistic winner drawn from effort shares
                players = list(efforts.keys())
                weights = [efforts[p] / total_effort for p in players]
                winner = rng.choices(players, weights=weights, k=1)[0]

            outcomes[fid] = winner
            scores[winner] += front["value"]

        state.history.append({
            "round": state.round,
            "allocations": actions,
            "outcomes": outcomes,
            "scores": scores,
        })

        is_last = state.round >= state.round_total
        return TullockState(
            round=state.round + 1,
            round_total=state.round_total,
            phase="terminal" if is_last else "awaiting_action",
            awaiting=[] if is_last else list(actions.keys()),
            fronts=state.fronts,
            budgets_remaining=state.budgets_remaining,
            history=state.history,
            communication_log=state.communication_log,
        )

    def is_terminal(self, state: TullockState) -> bool:
        return state.phase == "terminal"

    def compute_metrics(self, history: list[dict]) -> dict:
        # Metrics are computed by the metrics layer from history;
        # game-specific derived functions are registered in metrics.yaml
        return {}
```

---

### `prompts.yaml` — Default Agent Prompts

Every game ships default prompts for `render_state_prompt()`. The SDK uses these unless the researcher overrides them. Having good defaults here dramatically lowers the barrier for researchers who aren't studying prompt engineering.

```yaml
# games/community/tullock_contest/prompts.yaml
# -----------------------------------------------------------
# Jinja2 templates. Variables: state, player_id, config

system: >
  You are a strategic agent competing in a Tullock contest.
  Each round you allocate effort across research fronts.
  You win a front with probability proportional to your effort share.
  Maximise your total prize winnings over {{ state.round_total }} rounds.

turn: >
  Round {{ state.round }} of {{ state.round_total }}.
  Your remaining budget: {{ state.budgets_remaining[player_id] }}

  Fronts and prize values:
  {% for front in state.fronts %}
  - {{ front.id }}: prize value {{ front.value }}
  {% endfor %}

  {% if state.history %}
  Last round results:
  {% set last = state.history[-1] %}
  {% for fid, winner in last.outcomes.items() %}
  - Front {{ fid }}: won by {{ winner }}
  {% endfor %}
  Scores: {{ last.scores }}
  {% endif %}

  Respond with a JSON allocation across all fronts.
  Your amounts must sum to exactly {{ state.budgets_remaining[player_id] }}.
  Example: {"R": 60, "D": 40}

action_format:
  type: json_object
  schema:
    type: object
    additionalProperties: {type: number}
  example: '{"R": 60, "D": 40}'
```

---

### Registry + Auto-Discovery

The arena scans the `games/` directory at startup and builds a registry. No manual registration step — adding a folder is sufficient.

```python
# arena/registry.py
import importlib.util
from pathlib import Path
import yaml

GAMES_DIR = Path(__file__).parent.parent / "games"

class GameRegistry:
    def __init__(self):
        self._games: dict[str, dict] = {}
        self._discover()

    def _discover(self):
        for game_yaml in GAMES_DIR.rglob("game.yaml"):
            meta = yaml.safe_load(game_yaml.read_text())
            if meta.get("status") == "deprecated":
                continue
            name = meta["name"]
            engine_path = game_yaml.parent / "engine.py"
            spec = importlib.util.spec_from_file_location(name, engine_path)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            self._games[name] = {
                "meta": meta,
                "engine": self._find_engine_class(module),
                "metrics_path": game_yaml.parent / "metrics.yaml",
                "prompts_path": game_yaml.parent / "prompts.yaml",
            }

    def _find_engine_class(self, module):
        """Find the class in engine.py that implements the game interface."""
        for attr in dir(module):
            cls = getattr(module, attr)
            if (isinstance(cls, type)
                    and hasattr(cls, "initial_state")
                    and hasattr(cls, "apply_action")
                    and hasattr(cls, "is_terminal")
                    and hasattr(cls, "compute_metrics")):
                return cls
        raise ValueError(f"No valid game engine class found in {module.__file__}")

    def get(self, name: str) -> dict:
        if name not in self._games:
            raise KeyError(f"Game '{name}' not found. Available: {self.list()}")
        return self._games[name]

    def list(self, tag: str = None, status: str = "stable") -> list[dict]:
        games = [g["meta"] for g in self._games.values()
                 if g["meta"].get("status") == status]
        if tag:
            games = [g for g in games if tag in g.get("tags", [])]
        return games

registry = GameRegistry()
```

---

### MCP Tools — Game Directory

Four new tools are added to the MCP server, complementing the four session-management tools. Together they give agents full programmatic access to the directory.

```python
# arena_mcp/server.py  (additions to existing MCP server)

@mcp.tool()
async def list_games(
    tag: str = None,
    ontology_filter: dict = None,
) -> list[dict]:
    """
    List all available games in the arena directory.

    Optionally filter by tag (e.g. 'safety', 'zero-sum', 'resource-allocation')
    or by ontology dimensions (e.g. {"payoff_structure": "mixed-motive"}).

    Returns a list of game summaries with name, description, tags, player
    counts, and status. Use get_game_details() for the full config schema.
    """
    games = registry.list()
    if tag:
        games = [g for g in games if tag in g.get("tags", [])]
    if ontology_filter:
        games = [g for g in games
                 if all(g.get("ontology", {}).get(k) == v
                        for k, v in ontology_filter.items())]
    return [
        {
            "name": g["name"],
            "description": g["description"],
            "tags": g["tags"],
            "players": g["players"],
            "status": g["status"],
            "author": g.get("author"),
            "paper": g.get("paper"),
        }
        for g in games
    ]


@mcp.tool()
async def get_game_details(game: str) -> dict:
    """
    Get the full metadata, config schema, ontology classification,
    available metrics, and an example config for a specific game.

    Use this before calling POST /experiment to understand what
    parameters the game accepts and what metrics it supports.
    """
    entry = registry.get(game)
    meta = entry["meta"]
    metrics = yaml.safe_load(entry["metrics_path"].read_text())
    return {
        "name": meta["name"],
        "version": meta["version"],
        "description": meta["description"],
        "ontology": meta["ontology"],
        "players": meta["players"],
        "config_schema": meta["config_schema"],
        "example_config": meta["example_config"],
        "available_metrics": [m["name"] for m in metrics.get("metrics", [])],
        "tags": meta["tags"],
        "paper": meta.get("paper"),
        "author": meta.get("author"),
    }


@mcp.tool()
async def get_game_prompt_template(game: str) -> dict:
    """
    Get the default prompt templates for a game.

    Returns the system prompt, per-turn prompt template (Jinja2),
    and expected action format. Useful for understanding how the
    arena will describe game state to your agent, or for customising
    your own prompts.
    """
    entry = registry.get(game)
    return yaml.safe_load(entry["prompts_path"].read_text())


@mcp.tool()
async def get_game_metrics(game: str) -> dict:
    """
    Get the full metric definitions for a game, including builtin
    metrics it includes and any game-specific additions.

    Returns each metric's name, description, when it is logged
    (per_turn or terminal), type, and available aggregations.
    Use this to plan your wandb metrics config or results analysis.
    """
    entry = registry.get(game)
    raw = yaml.safe_load(entry["metrics_path"].read_text())
    builtins = load_builtins()
    resolved = resolve_includes(raw, builtins)
    return {
        "game": game,
        "per_turn_metrics": [
            {"name": m.name, "description": m.description,
             "type": m.type, "players": m.players,
             "aggregations": m.aggregations}
            for m in resolved if m.when in ("per_turn", "both")
        ],
        "terminal_metrics": [
            {"name": m.name, "description": m.description,
             "type": m.type, "players": m.players}
            for m in resolved if m.when in ("terminal", "both")
        ],
    }
```

---

### SDK Extensions

The Python SDK gains four matching methods so non-MCP users have the same discovery capability:

```python
# arena_sdk/skill.py  (additions to ArenaSkill)

class ArenaDirectoryMixin:
    """Mix-in providing game directory access. Combined with ArenaSkill."""

    def list_games(
        self,
        tag: str = None,
        ontology: dict = None,
    ) -> list[dict]:
        """List available games, optionally filtered by tag or ontology."""
        params = {}
        if tag:
            params["tag"] = tag
        if ontology:
            params["ontology"] = json.dumps(ontology)
        r = requests.get(f"{self.base_url}/games", params=params)
        r.raise_for_status()
        return r.json()

    def get_game_details(self, game: str) -> dict:
        """Full metadata, config schema, and example config for a game."""
        r = requests.get(f"{self.base_url}/games/{game}")
        r.raise_for_status()
        return r.json()

    def get_game_prompt_template(self, game: str) -> dict:
        """Default Jinja2 prompt templates for a game."""
        r = requests.get(f"{self.base_url}/games/{game}/prompts")
        r.raise_for_status()
        return r.json()

    def get_game_metrics(self, game: str) -> dict:
        """Full resolved metric definitions for a game."""
        r = requests.get(f"{self.base_url}/games/{game}/metrics")
        r.raise_for_status()
        return r.json()


class ArenaSkill(ArenaDirectoryMixin):
    # ... existing session methods unchanged
```

---

### Skill YAML Extension

The four directory tools are added to the skill YAML so framework-native users (CrewAI, AutoGen) get them without writing any code:

```yaml
# arena-skill.yaml  (additions to existing tools list)

  - name: list_games
    description: >
      Browse the game directory. Returns all available games with their
      descriptions, tags, player counts, and ontology classification.
      Filter by tag (e.g. 'safety', 'zero-sum') or ontology dimension.
      Call this first if you are not sure which game to use.
    parameters:
      tag:
        type: string
        description: "Filter by tag, e.g. 'safety', 'resource-allocation'"
        required: false
      ontology_filter:
        type: object
        description: >
          Filter by ontology dimensions, e.g.
          {"payoff_structure": "mixed-motive", "timing": "multi-round"}
        required: false

  - name: get_game_details
    description: >
      Get the full config schema, ontology, available metrics, and an
      example experiment config for a specific game. Call this before
      creating an experiment to understand what parameters are accepted.
    parameters:
      game:
        type: string
        description: "Game name as returned by list_games"

  - name: get_game_prompt_template
    description: >
      Get the default system and turn prompt templates for a game.
      Useful if you want to understand or customise how game state
      will be described to your agent.
    parameters:
      game:
        type: string

  - name: get_game_metrics
    description: >
      Get the full list of metrics available for a game — which are
      logged per turn vs. at game end, their types, and aggregations.
      Use this to plan your wandb metrics config.
    parameters:
      game:
        type: string
```

---

### Contribution Workflow

A contributor adding a new game submits a PR with a single new folder under `games/community/`. CI runs three checks automatically — no maintainer review is needed until they pass:

```yaml
# .github/workflows/validate-game.yaml
name: Validate contributed game

on:
  pull_request:
    paths: ["games/community/**"]

jobs:
  validate:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Install arena
        run: pip install -e ".[dev]"

      - name: Schema validation
        run: |
          # Checks game.yaml against the GameMeta JSON Schema
          # Checks metrics.yaml against the MetricSpec schema
          # Checks prompts.yaml for valid Jinja2 syntax
          python -m arena.cli validate-game $CHANGED_GAME_DIR

      - name: Engine tests
        run: |
          # Runs the contributor's tests/test_engine.py
          # Also runs the platform's generic game contract tests:
          #   - initial_state returns a valid GameState
          #   - apply_action reaches terminal state within max_rounds
          #   - is_terminal is consistent with phase == "terminal"
          #   - a full game with random agents completes without error
          pytest $CHANGED_GAME_DIR/tests/ arena/tests/game_contract.py \
            --game $CHANGED_GAME_DIR

      - name: Metrics tests
        run: |
          # Verifies all declared derived metrics have registered functions
          # Verifies requires: dependency graph is acyclic
          # Verifies per_turn metrics produce float/int/bool as declared
          pytest $CHANGED_GAME_DIR/tests/test_metrics.py \
            arena/tests/metrics_contract.py --game $CHANGED_GAME_DIR
```

The `game_contract.py` tests are the platform's guarantee: any game that passes them will work correctly with the arena's session management, the MCP tools, the SDK, and the metrics logger. Contributors don't need to know the internals — they just need to pass the contract.

---

### REST Endpoints for the Directory

```
GET  /games                          → list all games (supports ?tag= and ?ontology=)
GET  /games/{name}                   → full metadata + config schema + example
GET  /games/{name}/metrics           → resolved metric definitions
GET  /games/{name}/prompts           → default prompt templates
GET  /games/{name}/schema            → Pydantic/JSON Schema for config validation
```

These are public, unauthenticated endpoints — no token needed to browse the directory. The goal is that a researcher can `curl https://arena.yourdomain.com/games` and immediately see what's available without any sign-up.

---

## Part 7: Frontend & Auth Architecture

### Design Principles

The frontend extends the existing battle visualizer's aesthetic — monospace typography (`DM Mono`), the orange/blue/gold palette, grid backgrounds, ink-on-paper surfaces — into a dashboard and auth flow. The goal is a research tool that feels like infrastructure, not a consumer product.

Server compute is kept minimal: auth, API key storage, and experiment metadata all delegate to **Supabase** (hosted Postgres + Auth). The arena server only runs game logic.

---

### Auth: GitHub + Google Only

No email/password. OAuth-only reduces the attack surface, eliminates password reset flows, and is what researchers actually use.

**Implementation with Supabase:**

```javascript
// lib/supabase.js
import { createClient } from '@supabase/supabase-js'

export const supabase = createClient(
  process.env.NEXT_PUBLIC_SUPABASE_URL,
  process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY
)

// Sign in — one call each, no server code needed
export const signInWithGitHub = () =>
  supabase.auth.signInWithOAuth({
    provider: 'github',
    options: { redirectTo: `${window.location.origin}/dashboard` }
  })

export const signInWithGoogle = () =>
  supabase.auth.signInWithOAuth({
    provider: 'google',
    options: { redirectTo: `${window.location.origin}/dashboard` }
  })
```

Supabase handles the OAuth callback, issues a JWT, and stores the session in `localStorage`. No auth routes needed on the arena server. The JWT is passed as a Bearer token on API calls; the arena validates it against Supabase's public key.

---

### API Key Management

API keys are bearer tokens agents use to authenticate with the arena. The full key is shown **once** on creation and is never stored in plaintext — only a `SHA-256` hash is written to the database.

**Supabase table:**

```sql
create table api_keys (
  id           uuid primary key default gen_random_uuid(),
  user_id      uuid references auth.users(id) on delete cascade,
  name         text not null,
  key_hash     text not null unique,   -- SHA-256(full_key), never the key itself
  key_preview  text not null,          -- "arena_sk_4a2f…e91c"
  created_at   timestamptz default now(),
  last_used_at timestamptz,
  revoked_at   timestamptz,            -- null = active
  constraint max_active_keys check (
    (select count(*) from api_keys k2
     where k2.user_id = user_id and k2.revoked_at is null) <= 5
  )
);

-- RLS: users can only see and manage their own keys
alter table api_keys enable row level security;
create policy "own keys only" on api_keys
  using (user_id = auth.uid());
```

**Key generation (client-side):**

```javascript
async function generateApiKey(name) {
  // Generate full key client-side — server never sees it in plaintext
  const raw = crypto.getRandomValues(new Uint8Array(32))
  const hex = Array.from(raw).map(b => b.toString(16).padStart(2, '0')).join('')
  const fullKey = `arena_sk_${hex}`

  // Hash for storage
  const msgBuf = new TextEncoder().encode(fullKey)
  const hashBuf = await crypto.subtle.digest('SHA-256', msgBuf)
  const keyHash = Array.from(new Uint8Array(hashBuf))
    .map(b => b.toString(16).padStart(2, '0')).join('')

  const preview = `arena_sk_${hex.slice(0,4)}…${hex.slice(-4)}`

  // Store hash + preview only
  const { error } = await supabase
    .from('api_keys')
    .insert({ name, key_hash: keyHash, key_preview: preview })

  if (error) throw error

  // Return full key once — never stored, never retrievable
  return { fullKey, preview }
}
```

The arena server validates incoming agent keys by hashing them and looking up the hash:

```python
# arena/auth.py
import hashlib
from supabase import create_client

supabase = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)

async def validate_api_key(raw_key: str) -> dict | None:
    key_hash = hashlib.sha256(raw_key.encode()).hexdigest()
    result = supabase.table("api_keys") \
        .select("id, user_id, revoked_at") \
        .eq("key_hash", key_hash) \
        .single() \
        .execute()
    row = result.data
    if not row or row["revoked_at"]:
        return None
    # Update last_used_at asynchronously — don't block the request
    supabase.table("api_keys") \
        .update({"last_used_at": "now()"}) \
        .eq("id", row["id"]) \
        .execute()
    return row
```

---

### Experiment Metadata Table

Each completed session writes a lightweight record to Supabase. The arena server never stores game state long-term — only the summary row.

```sql
create table experiments (
  id            uuid primary key,          -- session_id from arena
  user_id       uuid references auth.users(id),
  api_key_id    uuid references api_keys(id),
  game          text not null,
  config        jsonb not null,            -- full experiment config (wandb key redacted)
  config_hash   text not null,
  agent_a       text,
  agent_b       text,
  outcome       text,                      -- "A" | "B" | "Tie"
  rounds_played int,
  started_at    timestamptz,
  completed_at  timestamptz,
  wandb_url     text,                      -- null if no W&B config was provided
  wandb_run_name text
);

alter table experiments enable row level security;
create policy "own experiments only" on experiments
  using (user_id = auth.uid());
```

The dashboard queries this table directly from the browser via Supabase's client library — no API route needed:

```javascript
async function loadExperiments(page = 1, filters = {}) {
  let query = supabase
    .from('experiments')
    .select('*', { count: 'exact' })
    .order('started_at', { ascending: false })
    .range((page - 1) * 10, page * 10 - 1)

  if (filters.game)    query = query.eq('game', filters.game)
  if (filters.outcome) query = query.eq('outcome', filters.outcome)

  const { data, count, error } = await query
  return { experiments: data, total: count }
}
```

---

### Pages

| Route | Description |
|---|---|
| `/` | Landing page / sign-in (auth.html) |
| `/dashboard` | API keys + experiment list (dashboard.html) |
| `/run` | Experiment runner (existing battle-canvas UI) |
| `/games` | Public game directory — no auth required |
| `/leaderboard` | Public leaderboard — no auth required |
| `/docs` | Documentation |

The `/games` and `/leaderboard` pages are fully public and unauthenticated — crucial for discoverability. Everything behind `/dashboard` requires a valid Supabase session.

---

### Keeping Server Compute Minimal

| Concern | Handled by | Server touched? |
|---|---|---|
| Auth (OAuth flow) | Supabase Auth | No |
| Session JWTs | Supabase | No |
| API key hashing | Browser `crypto.subtle` | No |
| API key storage | Supabase Postgres (via RLS) | No |
| Experiment metadata | Supabase Postgres (via RLS) | No |
| Dashboard queries | Supabase client (browser → Supabase directly) | No |
| W&B key encryption | Arena server (AES-256-GCM) | Yes — only during active session |
| Game state | Redis (TTL-bound) | Yes — only during active session |
| Metric logging | Arena worker | Yes — only during active session |

The arena server is only involved when a game is actively running. Everything else — auth, key management, history, the dashboard — goes directly from the browser to Supabase.

---

---

## Part 8: Starred Runs & Rate Limiting

### Starred Runs

Stars are a lightweight per-user bookmark on any experiment row. They live in the `experiments` table as a boolean column, written via a `PATCH` from the dashboard.

**Schema addition:**

```sql
alter table experiments add column starred boolean not null default false;

-- Index so "starred only" queries are fast
create index on experiments (user_id, starred) where starred = true;
```

**Client call (one line):**

```javascript
// PATCH /api/experiments/:id via Supabase client — no server route needed
const { error } = await supabase
  .from('experiments')
  .update({ starred: !currentlyStarred })
  .eq('id', sessionId)
  .eq('user_id', supabase.auth.user().id)   // RLS enforces this anyway
```

The dashboard maintains a local `Set<string>` of starred IDs for instant UI response, then syncs the Supabase write in the background. If the write fails, the star reverts and a toast notifies the user.

**Filter toggle:** a `★ starred` button in the filter bar switches the experiment table to show only starred runs. It composes with the existing game/outcome/search filters — e.g. "starred blotto runs where agent_a wins."

---

### Rate Limiter

A 4-core/8GB VM can safely handle roughly **8–12 concurrent game sessions** before CPU contention degrades turn latency. The limiter enforces this with two strategies: a per-account **concurrent session cap** and a per-account **session creation rate** (token bucket over a rolling window).

#### Why per-account, not per-IP

Researchers often run agents from cloud VMs with shared IPs. Per-IP limits would break legitimate multi-agent experiments. Per-account (keyed by `user_id`, aggregated across all API keys) is the correct scope.

#### Two-layer limit

| Layer | Limit | Purpose |
|---|---|---|
| Concurrent active sessions | 3 per account | Prevents one researcher saturating all 12 slots |
| Session creation rate | 20 per hour per account | Prevents rapid experiment cycling that wastes compute |

These numbers leave headroom: 4 researchers × 3 concurrent = 12 sessions, matching the VM ceiling. Increase `CONCURRENT_LIMIT` when you upgrade the VM.

#### Implementation: Redis sliding window

```python
# arena/rate_limit.py
import time
import redis.asyncio as aioredis
from fastapi import HTTPException

redis = aioredis.from_url("redis://localhost:6379")

CONCURRENT_LIMIT  = 3     # max active sessions per user
HOURLY_RATE_LIMIT = 20    # max new sessions per user per hour
WINDOW_SECONDS    = 3600

async def check_and_reserve(user_id: str, session_id: str) -> None:
    """Raises 429 if either limit is hit. Atomically reserves if clear."""
    now        = int(time.time())
    window_key = f"rate:hourly:{user_id}:{now // WINDOW_SECONDS}"
    active_key = f"rate:active:{user_id}"

    async with redis.pipeline(transaction=True) as pipe:
        pipe.get(active_key)
        pipe.zcount(window_key, now - WINDOW_SECONDS, now)
        active_raw, hourly_raw = await pipe.execute()

    active_count = int(active_raw or 0)
    hourly_count = int(hourly_raw or 0)

    if active_count >= CONCURRENT_LIMIT:
        reset_in = await _active_session_min_ttl(user_id)
        raise HTTPException(
            status_code=429,
            detail={
                "error":      "concurrent_limit_exceeded",
                "message":    f"Maximum {CONCURRENT_LIMIT} concurrent sessions per account.",
                "active":     active_count,
                "limit":      CONCURRENT_LIMIT,
                "reset_hint": f"A slot will free in ~{reset_in}s.",
            },
            headers={"Retry-After": str(reset_in)},
        )

    if hourly_count >= HOURLY_RATE_LIMIT:
        retry_after = WINDOW_SECONDS - (now % WINDOW_SECONDS)
        raise HTTPException(
            status_code=429,
            detail={
                "error":   "hourly_rate_limit_exceeded",
                "message": f"Maximum {HOURLY_RATE_LIMIT} sessions per hour.",
                "used":    hourly_count,
                "limit":   HOURLY_RATE_LIMIT,
            },
            headers={"Retry-After": str(retry_after)},
        )

    # Limits clear — reserve atomically
    async with redis.pipeline(transaction=True) as pipe:
        pipe.incr(active_key)
        pipe.expire(active_key, 7200)                         # safety expiry
        pipe.zadd(window_key, {session_id: now})
        pipe.zremrangebyscore(window_key, 0, now - WINDOW_SECONDS)
        pipe.expire(window_key, WINDOW_SECONDS + 60)
        await pipe.execute()


async def release(user_id: str) -> None:
    """Call on session termination — game over, timeout, or error."""
    key = f"rate:active:{user_id}"
    if int(await redis.get(key) or 0) > 0:
        await redis.decr(key)


async def get_status(user_id: str) -> dict:
    """Returned by GET /api/rate-limit-status and as response headers."""
    now        = int(time.time())
    window_key = f"rate:hourly:{user_id}:{now // WINDOW_SECONDS}"
    active_key = f"rate:active:{user_id}"
    active     = int(await redis.get(active_key) or 0)
    hourly     = await redis.zcount(window_key, now - WINDOW_SECONDS, now)
    reset_in   = WINDOW_SECONDS - (now % WINDOW_SECONDS)
    return {
        "concurrent": {"used": active, "limit": CONCURRENT_LIMIT},
        "hourly":     {"used": hourly, "limit": HOURLY_RATE_LIMIT,
                       "reset_in_seconds": reset_in},
    }
```

#### Wiring into the experiment creation route

```python
@app.post("/experiment")
async def create_experiment(config: ExperimentConfig,
                            user: dict = Depends(validate_api_key)):
    session_id = str(uuid4())
    await check_and_reserve(user["user_id"], session_id)  # raises 429 if over limit
    try:
        session = setup_session(session_id, config, user)
        store_session(session)
        return {
            "session_id":    session_id,
            "player_tokens": issue_tokens(session_id),
            "rate_limit":    await get_status(user["user_id"]),
        }
    except Exception:
        await release(user["user_id"])  # roll back reservation on setup failure
        raise


async def terminate_session(session_id: str, user_id: str):
    # ... W&B finish, Redis DEL, Postgres archive (existing)
    await release(user_id)  # always free the concurrent slot last
```

#### Response headers on every API call

```
X-RateLimit-Concurrent-Limit:      3
X-RateLimit-Concurrent-Remaining:  2
X-RateLimit-Hourly-Limit:          20
X-RateLimit-Hourly-Remaining:      14
X-RateLimit-Reset:                 1716217200
Retry-After:                       (only present on 429 responses)
```

Agent frameworks can read these to back off gracefully without polling.

#### Capacity sizing for this VM

| Resource | Available | Per session | Max safe sessions |
|---|---|---|---|
| CPU | 4 cores | ~0.3 core (FSM + metrics) | ~12 |
| RAM | 8 GB | ~200 MB (Redis + worker) | ~35 |
| Redis | ~512 MB reserved | ~40 KB (state + rate keys) | Well above CPU ceiling |

CPU is the bottleneck. The concurrent limit of 12 (3/account × 4 simultaneous users) keeps the VM at ~90% peak CPU. When you upgrade, raise `CONCURRENT_LIMIT` in one place — everything else adjusts automatically.

---

---

## Part 9: Research Data Sharing

### Design Philosophy

This is opt-in data sharing framed as a community contribution, not passive telemetry. Researchers will share if they understand what is stored, who sees it, and that they can delete it. The UI communicates all three clearly and puts every control in one place.

### Four-tier consent model

Tiers are strictly cascading — each requires the one above it to be enabled. This is enforced both in the UI (lower toggles are disabled until dependencies are on) and server-side (the API validates the dependency graph before writing).

```
Tier 1: Store game traces & metrics server-side        (opt-in, default OFF)
  └── Tier 2: Include agent prompt & response logs     (opt-in, default OFF)
  └── Tier 3: Publish to public Arena dataset           (opt-in, default OFF)
          └── Tier 4: Publish anonymously               (opt-in, default OFF)
```

| Tier | What is stored | Who can see it |
|---|---|---|
| 1 | Game state sequence, allocations, computed metrics | Arena server only |
| 2 | + Full agent prompt and LLM response each turn | Arena server only |
| 3 | Everything from active tiers above | Public (CC BY 4.0) with username |
| 4 | Everything from active tiers above | Public (CC BY 4.0), username replaced with `contributor_<hash>` |

The per-experiment **share override** button in the experiments table lets researchers include or exclude individual runs regardless of their account default — so a researcher can generally opt in but exclude a run using a proprietary system prompt.

---

### Schema

**Account-level preferences:**

```sql
-- Stored in Supabase user_preferences table
alter table user_preferences add column consent_store   boolean not null default false;
alter table user_preferences add column consent_prompts boolean not null default false;
alter table user_preferences add column consent_public  boolean not null default false;
alter table user_preferences add column consent_anon    boolean not null default false;

-- Cascade constraint: higher tiers cannot be on if lower tiers are off
alter table user_preferences add constraint consent_cascade check (
  (consent_prompts = false or consent_store  = true) and
  (consent_public  = false or consent_store  = true) and
  (consent_anon    = false or consent_public = true)
);
```

**Per-experiment override:**

```sql
-- null  = follow account default
-- true  = always include in corpus (overrides account off)
-- false = always exclude from corpus (overrides account on)
alter table experiments add column share_override boolean default null;

-- Materialised view for the public dataset — only rows that are effectively shared
create materialized view public_corpus as
  select
    e.id                                                           as session_id,
    e.game,
    e.config - 'wandb'                                            as config,  -- strip wandb block
    e.config_hash,
    case when p.consent_anon then 'contributor_' || left(md5(e.user_id::text), 12)
         else u.raw_user_meta_data->>'user_name' end              as contributor,
    e.agent_a, e.agent_b,
    e.outcome, e.rounds_played,
    e.started_at, e.completed_at,
    e.wandb_url,
    t.game_states,                                                 -- from traces table
    t.metrics,
    case when p.consent_prompts then t.prompt_logs else null end  as prompt_logs
  from experiments e
  join user_preferences p  on p.user_id = e.user_id
  join auth.users u         on u.id      = e.user_id
  left join traces t        on t.session_id = e.id
  where
    -- account default is on, or explicit per-experiment override
    coalesce(e.share_override, p.consent_store) = true
    and p.consent_public = true
    and e.completed_at is not null;
```

---

### Traces table

Game traces are stored separately from the experiment metadata — they are large and only written when Tier 1 is enabled.

```sql
create table traces (
  session_id  uuid primary key references experiments(id) on delete cascade,
  game_states jsonb not null,   -- array of GameState objects, one per turn
  metrics     jsonb not null,   -- full MetricsDict including per-turn snapshots
  prompt_logs jsonb,            -- null unless consent_prompts = true
  stored_at   timestamptz default now(),
  size_bytes  int generated always as (
    octet_length(game_states::text) +
    octet_length(metrics::text) +
    coalesce(octet_length(prompt_logs::text), 0)
  ) stored
);

-- Row-level security: users can only read/delete their own traces
alter table traces enable row level security;
create policy "own traces" on traces using (
  session_id in (select id from experiments where user_id = auth.uid())
);
```

**Writing traces (arena server):**

```python
# arena/traces.py
from supabase import create_client

supabase = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)

async def maybe_store_trace(session: SessionState, history: list, metrics: dict,
                             prompt_logs: list | None = None) -> None:
    """
    Called at session termination. Checks account consent before writing.
    prompt_logs is only passed from the worker if consent_prompts = True.
    """
    prefs = await get_user_prefs(session.user_id)

    # Evaluate effective sharing for this session
    override = session.config.get("share_override")  # researcher per-experiment flag
    effective_store = override if override is not None else prefs["consent_store"]

    if not effective_store:
        return  # nothing to store

    await supabase.table("traces").upsert({
        "session_id":  session.session_id,
        "game_states": history,
        "metrics":     metrics,
        "prompt_logs": prompt_logs if prefs["consent_prompts"] else None,
    }).execute()
```

---

### Deletion

Researchers can delete all stored traces from their account settings. Deletion cascades:
- Trace rows are hard-deleted immediately from `traces`
- The `public_corpus` materialised view refreshes within 48 hours (scheduled `REFRESH MATERIALIZED VIEW CONCURRENTLY`)
- If traces were included in a versioned public dataset snapshot, deletion removes them from the **live** dataset but cannot retract already-published static snapshots — this is disclosed in the Research Data Policy

```python
# DELETE /api/account/traces  (requires authenticated session)
async def delete_all_traces(user_id: str) -> dict:
    # Cascade delete via FK: deletes all traces where session_id in
    # (select id from experiments where user_id = :user_id)
    result = await supabase.rpc("delete_user_traces", {"uid": user_id}).execute()
    # Also clear share_override so future runs start fresh
    await supabase.table("experiments") \
        .update({"share_override": None}) \
        .eq("user_id", user_id).execute()
    return {"deleted": result.data["count"]}
```

---

### Experiment config extension

Researchers can set the per-experiment share override directly in the experiment config YAML:

```yaml
game: blotto
rounds: 10
seed: 42

# Optional — overrides account-level consent for this run only
# null (omit) = follow account default
# true        = always store & share this run
# false       = never store this run (e.g. proprietary agent prompts)
share_override: false
```

---

### What the API response includes

The experiment creation response surfaces the effective sharing decision so researchers and their agents know immediately what will be stored:

```json
{
  "session_id": "a3f9c2d1-...",
  "player_tokens": { "A": "tok_aaa", "B": "tok_bbb" },
  "effective_sharing": {
    "store":          false,
    "prompts":        false,
    "public":         false,
    "anon":           false,
    "override_source": "account_default"
  }
}
```

`override_source` is either `"account_default"` or `"per_experiment_override"` — so agents running in automated pipelines can log exactly what consent applied to each run.
---

## Part 10: Multi-Agent Systems as Players

### The Arena Is Agent-System-Agnostic

The arena does not distinguish between a single LLM and a multi-agent system. Both are represented identically: a **player name** (a string the researcher chooses) and a **bearer token** scoped to one player slot in one session. Whatever produces the `/action` call — one model, a LangGraph graph, a CrewAI crew, an AutoGen group chat, a custom 10-model orchestrator — is invisible to the arena.

This is not a limitation; it is the design. The API-first, external-agent architecture gives multi-agent support for free.

```
# Single LLM
agent_a: "gpt-4o"

# Multi-agent system — identical config, just a different name
agent_a: "blotto-deliberation-crew-v2"
```

The name is stored in the `experiments` table, shown in the dashboard, and used for leaderboard attribution. Nothing else in the platform changes.

### The Only Multi-Agent Concern: Turn Integrity

If a researcher's orchestrator has sub-agents deliberate before committing, multiple components may independently try to call `/action` for the same round. The arena rejects the second call:

```
POST /session/{uuid}/action
→ 409 Conflict
{
  "error": "action_already_submitted",
  "message": "An action has already been submitted for player A in round 3.",
  "round": 3,
  "player": "A"
}
```

This is not multi-agent awareness — it is basic turn integrity that any correct client must handle. The researcher's orchestrator is responsible for ensuring exactly one action is submitted per turn. The arena does not need to know how they achieve that internally.

### What Researchers Do in Practice

```python
# Example: CrewAI crew as a Blotto player
# The arena has no idea this is a crew — it just sees HTTP calls.

from crewai import Crew, Agent, Task
from arena_sdk import ArenaSkill

arena = ArenaSkill(session_id="abc123", player_id="A", token="tok_aaa")

deliberation_crew = Crew(
    agents=[
        Agent(role="Strategist",   goal="Identify high-value battlefields"),
        Agent(role="Risk analyst", goal="Assess opponent likely allocations"),
        Agent(role="Allocator",    goal="Produce the final allocation JSON"),
    ],
    tasks=[...],  # tasks reference arena.get_state() output
)

while not arena.is_terminal():
    state  = arena.get_state()
    result = deliberation_crew.kickoff(inputs={"state": state})
    action = arena.parse_action(result.raw)   # extract JSON from crew output
    arena.submit_action(action)               # single call — turn integrity maintained
```

The crew's internal deliberation (however many LLM calls, tool uses, or sub-agent messages it involves) is fully opaque to the arena. The arena receives one `POST /action`.

---

## Part 11: Repository Structure

```
arena/
│
├── README.md
├── LICENSE
├── .github/
│   ├── workflows/
│   │   ├── ci.yaml                  # lint, type-check, unit tests on every PR
│   │   ├── validate-game.yaml       # game contract tests for community/games PRs
│   │   └── deploy.yaml              # build + push Docker images on main merge
│   └── CONTRIBUTING.md
│
├── docker-compose.yml               # one-command local dev: api + redis + postgres
├── docker-compose.prod.yml          # production overrides
├── Makefile                         # dev shortcuts: make dev, make test, make migrate
│
│
├── src/
│   │
│   ├── backend/                     # FastAPI arena server
│   │   ├── pyproject.toml
│   │   ├── Dockerfile
│   │   │
│   │   ├── arena/
│   │   │   ├── __init__.py
│   │   │   ├── main.py              # FastAPI app, router registration, lifespan
│   │   │   ├── config.py            # env vars via pydantic-settings
│   │   │   │
│   │   │   ├── routes/
│   │   │   │   ├── experiments.py   # POST /experiment, GET /session/{id}/state, etc.
│   │   │   │   ├── games.py         # GET /games, GET /games/{name}, etc.
│   │   │   │   ├── account.py       # GET/PATCH /api/account/consent, keys, traces
│   │   │   │   └── health.py        # GET /health, GET /ready
│   │   │   │
│   │   │   ├── engine/
│   │   │   │   ├── registry.py      # auto-discovery of games/ directory
│   │   │   │   ├── session.py       # SessionState dataclass, store/fetch/terminate
│   │   │   │   └── runner.py        # turn loop, action validation, phase transitions
│   │   │   │
│   │   │   ├── metrics/
│   │   │   │   ├── validator.py     # validate_metrics_config(), dependency graph check
│   │   │   │   ├── resolver.py      # resolve includes, apply overrides/additions/exclusions
│   │   │   │   ├── builtins.yaml    # built-in metric library
│   │   │   │   └── derived/         # registered Python functions for derived metrics
│   │   │   │       ├── __init__.py
│   │   │   │       ├── behavioral.py  # commitment_gap, free_rider, cooperative_drift
│   │   │   │       ├── outcome.py     # winner, payoff, exploitability
│   │   │   │       └── alignment.py   # role_adherence, manipulation_rate
│   │   │   │
│   │   │   ├── auth.py              # validate_api_key(), JWT verification
│   │   │   ├── rate_limit.py        # check_and_reserve(), release(), get_status()
│   │   │   ├── traces.py            # maybe_store_trace(), delete_user_traces()
│   │   │   │
│   │   │   └── integrations/
│   │   │       └── wandb_logger.py  # WandbGameLogger, encrypt/decrypt key
│   │   │
│   │   └── tests/
│   │       ├── test_routes.py
│   │       ├── test_engine.py
│   │       ├── test_rate_limit.py
│   │       ├── test_auth.py
│   │       ├── test_metrics.py
│   │       ├── game_contract.py     # generic contract tests run against every game
│   │       └── metrics_contract.py  # generic metrics tests run against every game
│   │
│   │
│   ├── frontend/                    # Next.js dashboard + public pages
│   │   ├── package.json
│   │   ├── next.config.js
│   │   ├── tsconfig.json
│   │   ├── Dockerfile
│   │   │
│   │   ├── app/                     # Next.js app router
│   │   │   ├── layout.tsx
│   │   │   ├── page.tsx             # landing / sign-in
│   │   │   ├── dashboard/
│   │   │   │   └── page.tsx         # API keys, experiments, consent panel
│   │   │   ├── run/
│   │   │   │   └── page.tsx         # battle-canvas experiment runner
│   │   │   ├── games/
│   │   │   │   ├── page.tsx         # public game directory
│   │   │   │   └── [name]/
│   │   │   │       └── page.tsx     # individual game detail
│   │   │   ├── leaderboard/
│   │   │   │   └── page.tsx
│   │   │   └── auth/
│   │   │       └── callback/
│   │   │           └── route.ts     # Supabase OAuth callback handler
│   │   │
│   │   ├── components/
│   │   │   ├── canvas/
│   │   │   │   └── BattleCanvas.tsx # existing battle visualiser, ported to React
│   │   │   ├── dashboard/
│   │   │   │   ├── ApiKeyPanel.tsx
│   │   │   │   ├── ExperimentsTable.tsx
│   │   │   │   ├── ConsentPanel.tsx
│   │   │   │   └── RateBar.tsx
│   │   │   └── ui/                  # shared primitives (Button, Toast, Toggle, etc.)
│   │   │
│   │   ├── lib/
│   │   │   ├── supabase.ts          # createClient, signInWithGitHub/Google
│   │   │   ├── arena-api.ts         # typed wrappers for arena backend calls
│   │   │   └── crypto.ts            # client-side key hashing (crypto.subtle)
│   │   │
│   │   └── public/
│   │       └── fonts/
│   │
│   │
│   ├── mcp/                         # MCP server (hosted at mcp.arena.dev/sse)
│   │   ├── pyproject.toml
│   │   ├── Dockerfile
│   │   │
│   │   └── arena_mcp/
│   │       ├── __init__.py
│   │       ├── server.py            # FastMCP app, all tool definitions
│   │       ├── client.py            # ArenaClient — thin wrapper over arena REST API
│   │       └── tools/
│   │           ├── session.py       # get_game_state, submit_action, send_message, get_results
│   │           └── directory.py     # list_games, get_game_details, get_game_prompt_template, get_game_metrics
│   │
│   │
│   └── sdk/                         # pip install arena-sdk
│       ├── pyproject.toml
│       ├── README.md
│       │
│       └── arena_sdk/
│           ├── __init__.py          # exports ArenaSkill, ArenaDirectoryMixin
│           ├── skill.py             # ArenaSkill: get_state, submit_action, is_terminal, etc.
│           ├── directory.py         # ArenaDirectoryMixin: list_games, get_game_details, etc.
│           └── prompts.py           # render_state_prompt(), parse_action() defaults
│
│
├── games/                           # game directory (auto-discovered by registry)
│   ├── core/
│   │   ├── blotto/
│   │   │   ├── game.yaml
│   │   │   ├── engine.py
│   │   │   ├── metrics.yaml
│   │   │   ├── prompts.yaml
│   │   │   └── tests/
│   │   │       ├── test_engine.py
│   │   │       └── test_metrics.py
│   │   ├── general_lotto/
│   │   ├── prisoners_dilemma/
│   │   ├── public_goods/
│   │   ├── ultimatum/
│   │   └── signaling/
│   │
│   ├── community/                   # contributed games — merged via PR + CI
│   │   └── _template/               # copy this to start a new game
│   │       ├── game.yaml
│   │       ├── engine.py
│   │       ├── metrics.yaml
│   │       ├── prompts.yaml
│   │       └── tests/
│   │           ├── test_engine.py
│   │           └── test_metrics.py
│   │
│   └── README.md                    # how to contribute a game
│
│
├── skills/                          # drop-in skill files for agent frameworks
│   ├── arena-skill.yaml             # CrewAI / AutoGen YAML skill definition
│   ├── arena-skill.json             # OpenAPI-style JSON (for frameworks wanting JSON)
│   └── README.md                    # which file to use for which framework
│
│
├── infra/                           # infrastructure-as-code
│   ├── nginx.conf                   # reverse proxy: /api → backend, /mcp → mcp server
│   ├── redis.conf
│   └── supabase/
│       ├── migrations/              # SQL migration files (applied via supabase db push)
│       │   ├── 001_initial.sql
│       │   ├── 002_experiments.sql
│       │   ├── 003_traces.sql
│       │   ├── 004_consent.sql
│       │   └── 005_stars_rate_limit.sql
│       └── seed.sql                 # dev seed data
│
│
└── docs/                            # documentation source (deployed to docs.arena.dev)
    ├── quickstart.md
    ├── api-reference.md
    ├── mcp-integration.md
    ├── sdk-reference.md
    ├── contributing-games.md
    └── research-data-policy.md
```

### Key structural decisions

**`src/` splits into four independent packages**, each with its own `pyproject.toml` or `package.json` and its own `Dockerfile`. They share nothing at the file system level — only through the HTTP API. This means:
- The MCP server can be deployed and scaled independently from the backend
- The SDK is published to PyPI from `src/sdk/` with no backend coupling
- The frontend is deployed to Vercel; the backend and MCP server run on the VM

**`games/` lives at the repo root**, not inside `src/backend/`. This makes it clear that games are a shared community resource, not internal backend code. The backend's `registry.py` points to `../../games/` relative to its own location. Contributors only need to touch `games/community/` — they never open `src/`.

**`skills/` at the repo root** means researchers can `curl https://raw.githubusercontent.com/your-org/arena/main/skills/arena-skill.yaml` to get the skill file without cloning the repo. This is the fastest possible integration path for framework users.

**`infra/supabase/migrations/`** is the single source of truth for the database schema. `supabase db push` applies them in order. Every schema change discussed in this document corresponds to one migration file.

### Getting started in three commands

```bash
git clone https://github.com/your-org/arena
cd arena
make dev
# → starts FastAPI (port 8000) + MCP server (port 8001) + Redis + Postgres
# → frontend available at http://localhost:3000
```

`make dev` runs `docker-compose up --build`. The `Makefile` also provides:

```
make test          # run all backend + SDK tests
make test-game GAME=games/community/my_game   # run contract tests for one game
make migrate       # apply pending Supabase migrations
make lint          # ruff + mypy (backend/SDK) + eslint (frontend)
make mcp-dev       # run MCP server in hot-reload mode
```

### Connecting to the MCP server (one line per framework)

```python
# Claude Desktop / any MCP client — add to mcp_config.json
{ "mcpServers": { "arena": { "url": "https://mcp.arena.dev/sse",
                              "env": { "ARENA_SESSION_TOKEN": "tok_aaa..." } } } }

# LangChain
from langchain_mcp_adapters.client import MultiServerMCPClient
client = MultiServerMCPClient({"arena": {"url": "https://mcp.arena.dev/sse",
                                          "transport": "sse"}})

# CrewAI / AutoGen — drop skills/arena-skill.yaml into your skills directory
# curl -O https://raw.githubusercontent.com/your-org/arena/main/skills/arena-skill.yaml
```

### Installing the SDK (one line)

```bash
pip install arena-sdk
# optional extras:
pip install arena-sdk[openai]      # adds render_state_prompt() defaults for OpenAI models
pip install arena-sdk[anthropic]   # adds defaults for Anthropic models
pip install arena-sdk[langchain]   # adds LangChain tool wrappers
```


---

## Part 10: Prior Art Summary

| Framework | Key Strength | Key Weakness | Code |
|---|---|---|---|
| **ALYMPICS** (Microsoft) | Closest architecture; sandbox + custom games | Research artifact; agents must run inside it | GitHub |
| **Game Reasoning Arena** (LAION) | OpenSpiel + LiteLLM + Ray; best infra | Same coupling problem; not API-first | arXiv |
| **GLEE** | Best economic game parameterization | Two-player only; no process metrics | Yes |
| **NegotiationArena** | Multi-turn LLM vs. LLM; deception findings | Single paper artifact | Yes |
| **SOTOPIA** | Rich social simulation; alignment-sensitive | No game-theoretic structure; no API | Yes |
| **TMGBench** | 144 game types; good extensibility pattern | Evaluation only; no live agent interface | Yes |
| **MAGIC / Two-Player Alignment** | Safety-as-game; Nash convergence | Tightly coupled attacker-defender; not general | Partial |

---

*Compiled May 2025. Based on: IJCAI 2025 Survey on Game Theory × LLMs (arXiv:2502.09053), lm-eval-harness design paper (arXiv:2405.14782), ACL/COLING 2025 proceedings, and arXiv preprints through May 2025.*