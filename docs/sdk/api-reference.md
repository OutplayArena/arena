# SDK API reference

Full reference for every public symbol in the `outplaylabs-arena-sdk` package.

## Top-level

::: outplaylabs_arena_sdk
    options:
      show_root_heading: false
      members:
        - BaseAgent
        - LLMConfig
        - ArenaClient
        - MCPClient
        - MCPAgent
        - ReasoningModerator
        - ReasoningConfig
        - ReasoningEffort
        - ReasoningStrategy
        - ModelProfile
        - MODEL_PROFILES
        - quick_play
        - GAME_AGENTS
        - get_agent_class
        - supported_games
        - build_api_params
        - build_system_prompt
        - get_limits
        - get_model_profile

## Per-game agents

::: outplaylabs_arena_sdk.agents.games
    options:
      show_root_heading: false
      members:
        - ColonelBlottoAgent
        - UltimatumAgent
        - PrisonersDilemmaAgent
        - RockPaperScissorsAgent
        - BattleOfTheSexesAgent
        - StagHuntAgent
        - CentipedeAgent
        - CournotDuopolyAgent
        - PublicGoodsAgent
        - TexasHoldEmAgent

## Modules

### `outplaylabs_arena_sdk.base`

::: outplaylabs_arena_sdk.base.BaseAgent
    options:
      members:
        - __init__
        - run
        - run_sync
        - session_id
        - config
        - seed
        - rng
        - transport
        - on_episode_start
        - on_round_start
        - on_observation
        - on_tool_call
        - on_action_decision
        - on_action_result
        - on_message_received
        - on_round_end
        - on_episode_end
        - on_error
        - parse_action
        - action_format_hint
        - maybe_communicate

### `outplaylabs_arena_sdk.client`

::: outplaylabs_arena_sdk.client.ArenaClient
    options:
      members:
        - __init__
        - create_experiment
        - for_player
        - get_state
        - get_observation
        - submit_action
        - get_results
        - is_terminal
        - list_games
        - get_game_details
        - get_game_metrics
        - get_game_prompts
        - get_game_skill
        - get_agent_manifest
        - get_mailbox
        - send_message

### `outplaylabs_arena_sdk.mcp_client`

::: outplaylabs_arena_sdk.mcp_client.MCPClient
    options:
      members:
        - __init__
        - connect
        - disconnect
        - get_observation
        - get_game_state
        - submit_action
        - get_results
        - list_games
        - get_game_details
        - get_game_metrics
        - get_game_prompts
        - get_game_skill
        - get_agent_manifest
        - get_mailbox
        - send_message

### `outplaylabs_arena_sdk.parsers`

::: outplaylabs_arena_sdk.parsers
    options:
      show_root_heading: false
      members:
        - parse_allocation
        - parse_offer
        - parse_accept_reject
        - parse_choice
        - parse_quantity
        - parse_poker_action

### `outplaylabs_arena_sdk.tools`

::: outplaylabs_arena_sdk.tools
    options:
      show_root_heading: false
      members:
        - build_backend_tools
        - get_observation_tool
        - get_game_state_tool
        - get_mailbox_tool
        - send_message_tool
        - submit_action_tool

### `outplaylabs_arena_sdk.transport`

::: outplaylabs_arena_sdk.transport.AsyncBackend
    options:
      members:
        - __init__
        - rest
        - mcp
        - transport
        - get_state
        - get_observation
        - submit_action
        - get_results
        - get_mailbox
        - send_message
        - set_player_id

### `outplaylabs_arena_sdk.registry`

::: outplaylabs_arena_sdk.registry
    options:
      show_root_heading: false
      members:
        - GAME_AGENTS
        - register
        - get_agent_class
        - supported_games

### `outplaylabs_arena_sdk.seed`

::: outplaylabs_arena_sdk.seed.SeedResolver
    options:
      members:
        - __init__
        - seed
        - rng
        - resolve_from_config

### `outplaylabs_arena_sdk.reasoning`

::: outplaylabs_arena_sdk.reasoning.ReasoningModerator
    options:
      members:
        - __init__
        - from_config
        - strategy
        - effort
        - get_api_params
        - get_limits
        - build_system_prompt
        - prepare_request_body
        - extract_response_text

::: outplaylabs_arena_sdk.reasoning.ReasoningEffort
    options:
      show_root_heading: true

::: outplaylabs_arena_sdk.reasoning.ReasoningStrategy
    options:
      show_root_heading: true

### `outplaylabs_arena_sdk.results`

::: outplaylabs_arena_sdk.results
    options:
      show_root_heading: false
      members:
        - format_results
        - save_results

### `outplaylabs_arena_sdk.quick_play`

::: outplaylabs_arena_sdk.quick_play
    options:
      show_root_heading: false
      members:
        - quick_play
