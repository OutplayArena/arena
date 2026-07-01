#!/usr/bin/env python3
"""
Build game documentation from YAML files.

Generates Markdown pages for the game catalog, metrics reference,
and game overview from game.yaml, metrics.yaml, agents.yaml, and prompts.yaml.
"""

import sys
from pathlib import Path

import yaml


def load_yaml(path: Path) -> dict:
    """Load YAML file."""
    if not path.exists():
        return {}
    with open(path) as f:
        return yaml.safe_load(f) or {}


def generate_game_page(game_dir: Path, game_yaml: dict) -> str:
    """Generate Markdown page for a single game."""
    name = game_yaml.get("name", game_dir.name)
    description = game_yaml.get("description", "")
    ontology = game_yaml.get("ontology", {})
    config_schema = game_yaml.get("config_schema", {})
    example_config = game_yaml.get("example_config", {})
    players = game_yaml.get("players", {})
    warnings = game_yaml.get("warnings", [])

    # Load metrics
    metrics_yaml = load_yaml(game_dir / "metrics.yaml")
    metrics = metrics_yaml.get("metrics", [])

    # Load agents
    agents_yaml = load_yaml(game_dir / "agents.yaml")
    agents = agents_yaml.get("agents", [])

    # Build page
    lines = [f"# {name}", ""]

    for w in warnings:
        title = w.get("title", "Warning")
        body = w.get("body", "").strip()
        lines += [f'!!! warning "{title}"', f"    {body}", ""]

    lines += [
        description,
        "",
        "## Overview",
        "",
        f"**Type**: {ontology.get('payoff_structure', 'unknown')}, "
        f"{ontology.get('information_structure', 'unknown')}, "
        f"{ontology.get('action_space', 'unknown')}",
        "",
        f"**Players**: {players.get('min', 2)}" + 
        (f"–{players.get('max', 2)}" if players.get('max', 2) != players.get('min', 2) else ""),
        "",
        "## Configuration",
        "",
        "| Parameter | Type | Default | Description |",
        "|-----------|------|---------|-------------|",
    ]
    
    for param, schema in config_schema.items():
        param_type = schema.get("type", "any")
        default = schema.get("default", "—")
        desc = schema.get("description", "")
        if schema.get("const"):
            default = f'`{schema["const"]}`'
        elif default is None:
            default = "—`"
        else:
            default = f"`{default}`"
        lines.append(f"| `{param}` | `{param_type}` | {default} | {desc} |")
    
    lines.extend([
        "",
        "## Metrics",
        "",
    ])
    
    if metrics:
        for metric in metrics:
            lines.append(f"- `{metric}`")
    else:
        lines.append("No game-specific metrics defined.")
    
    lines.extend([
        "",
        "## Built-in Agents",
        "",
    ])
    
    if agents:
        lines.append("| Agent | Name | Description |")
        lines.append("|-------|------|-------------|")
        for agent in agents:
            agent_id = agent.get("id", "")
            agent_name = agent.get("name", agent.get("label", ""))
            agent_desc = agent.get("description", "")
            lines.append(f"| `{agent_id}` | {agent_name} | {agent_desc} |")
    else:
        lines.append("No built-in agents defined.")
    
    lines.extend([
        "",
        "## Example",
        "",
        "```python",
        "from outplayarena_sdk import quick_play",
        "",
        "results = quick_play(",
        f'    game="{game_dir.name}",',
        "    agents={",
        '        "A": {"model": "gpt-4", "api_key": "sk-..."},',
        '        "B": {"model": "claude-3-opus", "api_key": "sk-ant-..."},',
        "    },",
        f"    config={example_config},",
        ")",
        "```",
        "",
    ])
    
    return "\n".join(lines)


def generate_overview_page(games_data: list[tuple[Path, dict]]) -> str:
    """Generate games overview page."""
    lines = [
        "# Games Overview",
        "",
        "OutplayArena includes a catalog of game theory scenarios spanning the cooperative-competitive spectrum.",
        "",
        "## Game Catalog",
        "",
        "| Game | Players | Action Space | Payoff Structure | Information |",
        "|------|---------|--------------|------------------|-------------|",
    ]
    
    for game_dir, game_yaml in sorted(games_data, key=lambda x: x[1].get("name", "")):
        name = game_yaml.get("name", game_dir.name)
        slug = game_dir.name
        ontology = game_yaml.get("ontology", {})
        players = game_yaml.get("players", {})
        
        player_str = str(players.get("min", 2))
        if players.get("max", 2) != players.get("min", 2):
            player_str += f"–{players.get('max', 2)}"
        
        lines.append(
            f"| [{name}](catalog/{slug}.md) | {player_str} | "
            f"{ontology.get('action_space', '—')} | "
            f"{ontology.get('payoff_structure', '—')} | "
            f"{ontology.get('information_structure', '—')} |"
        )
    
    lines.extend([
        "",
        "## Ontology Taxonomy",
        "",
        "### By Payoff Structure",
        "",
    ])
    
    # Group by payoff structure
    by_payoff = {}
    for game_dir, game_yaml in games_data:
        payoff = game_yaml.get("ontology", {}).get("payoff_structure", "unknown")
        by_payoff.setdefault(payoff, []).append(game_yaml.get("name", game_dir.name))
    
    for payoff, games in sorted(by_payoff.items()):
        lines.append(f"**{payoff.replace('_', ' ').title()}**:")
        for game in sorted(games):
            lines.append(f"- {game}")
        lines.append("")
    
    lines.extend([
        "## Next Steps",
        "",
        "- Browse individual game pages for details",
        "- Learn about [metrics](metrics.md) tracked across games",
        "- Read about [creating new games](creating-games.md)",
        "",
    ])
    
    return "\n".join(lines)


def generate_metrics_page(games_data: list[tuple[Path, dict]]) -> str:
    """Generate metrics reference page."""
    lines = [
        "# Metrics Reference",
        "",
        "Comprehensive reference for all metrics tracked across OutplayArena games.",
        "",
        "## Universal Metrics",
        "",
        "These metrics are computed for every game:",
        "",
        "| Metric | Description |",
        "|--------|-------------|",
        "| `total_payoff` | Cumulative score across all rounds |",
        "| `average_payoff` | Mean score per round |",
        "| `strategy_entropy` | Predictability of strategy |",
        "| `behavioral_consistency` | Stability of behavior over time |",
        "| `cumulative_regret` | Deviation from optimal play |",
        "| `gini_coefficient` | Inequality in payoffs between players |",
        "| `social_welfare` | Total payoff across all players |",
        "| `pareto_efficiency` | How close to Pareto optimal |",
        "| `nash_gap` | Distance from Nash equilibrium |",
        "",
        "## Game-Specific Metrics",
        "",
    ]
    
    for game_dir, game_yaml in sorted(games_data, key=lambda x: x[1].get("name", "")):
        name = game_yaml.get("name", game_dir.name)
        metrics_yaml = load_yaml(game_dir / "metrics.yaml")
        metrics = metrics_yaml.get("metrics", [])
        
        # Filter out universal metrics
        universal = {
            "total_payoff", "average_payoff", "strategy_entropy",
            "behavioral_consistency", "cumulative_regret", "gini_coefficient",
            "social_welfare", "pareto_efficiency", "nash_gap"
        }
        specific = [m for m in metrics if m not in universal]
        
        if specific:
            lines.append(f"### {name}")
            lines.append("")
            for metric in specific:
                lines.append(f"- `{metric}`")
            lines.append("")
    
    return "\n".join(lines)


def main():
    """Main entry point."""
    repo_root = Path(__file__).parent.parent
    games_root = repo_root / "games" / "games" / "core"
    docs_dir = repo_root / "docs" / "games"
    
    if not games_root.exists():
        print(f"Error: Games directory not found: {games_root}")
        sys.exit(1)
    
    # Create output directories
    catalog_dir = docs_dir / "catalog"
    catalog_dir.mkdir(parents=True, exist_ok=True)
    
    # Load all games
    games_data = []
    for game_dir in sorted(games_root.iterdir()):
        if not game_dir.is_dir() or game_dir.name.startswith("_"):
            continue
        
        game_yaml = load_yaml(game_dir / "game.yaml")
        if not game_yaml:
            print(f"Warning: No game.yaml in {game_dir}")
            continue
        
        games_data.append((game_dir, game_yaml))
        
        # Generate game page
        page_content = generate_game_page(game_dir, game_yaml)
        output_path = catalog_dir / f"{game_dir.name}.md"
        with open(output_path, "w") as f:
            f.write(page_content)
        print(f"Generated: {output_path}")
    
    # Generate overview page
    overview_content = generate_overview_page(games_data)
    with open(docs_dir / "overview.md", "w") as f:
        f.write(overview_content)
    print(f"Generated: {docs_dir / 'overview.md'}")
    
    # Generate metrics page
    metrics_content = generate_metrics_page(games_data)
    with open(docs_dir / "metrics.md", "w") as f:
        f.write(metrics_content)
    print(f"Generated: {docs_dir / 'metrics.md'}")
    
    print(f"\nGenerated documentation for {len(games_data)} games")


if __name__ == "__main__":
    main()
