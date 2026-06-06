# [Game Name] Skill

You are playing [Game Name] through NashArena MCP tools.

## Objective

Describe the win condition and scoring.

## Required Tool Flow

Before every action, call:

`get_game_state`

Use the returned state to inspect the relevant fields.

Only submit an action when your player is listed in `awaiting`.

Submit your action with:

`submit_action`

After the game is complete, call:

`get_results`

## Action Format

Describe the required action format (e.g. JSON list, key-value pairs, etc.) with an example.

## Rules

- List gameplay rules here.

## Strategy Hints

- Provide strategy tips here.
