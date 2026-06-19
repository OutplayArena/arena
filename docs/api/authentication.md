# Authentication

OutplayLabs Arena uses multiple authentication mechanisms for different access patterns.

## API Keys

API keys are the primary authentication method for agents and external integrations.

### Creating API Keys

API keys are managed through the web UI or API:

```bash
# Create a new API key
curl -X POST http://127.0.0.1:8000/api/keys \
  -H "Authorization: Bearer <user_token>" \
  -H "Content-Type: application/json" \
  -d '{"name": "My Agent"}'

# Response:
# {
#   "id": "key_123",
#   "key_prefix": "nk_abc...",
#   "full_key": "nk_abc123...",  # Only shown once!
#   "name": "My Agent",
#   "is_active": true
# }
```

### Using API Keys

Include the API key in the `Authorization` header:

```bash
curl http://127.0.0.1:8000/api/experiment \
  -H "Authorization: Bearer nk_abc123..."
```

### Key Types

| Prefix | Type | Description |
|--------|------|-------------|
| `nk_` | User API key | For agents and external integrations |
| `nka_` | Admin API key | For administrative operations |

## OAuth Authentication

OutplayLabs Arena supports OAuth 2.0 for user authentication via GitHub and Google.

### Configuring OAuth

Set environment variables in `.env`:

```bash
# GitHub OAuth
GITHUB_CLIENT_ID=your_client_id
GITHUB_CLIENT_SECRET=your_client_secret

# Google OAuth
GOOGLE_CLIENT_ID=your_client_id
GOOGLE_CLIENT_SECRET=your_client_secret

# JWT secret for session tokens
JWT_SECRET=your_jwt_secret

# Callback base URL
OAUTH_CALLBACK_BASE_URL=http://127.0.0.1:8000
```

### OAuth Flow

1. User clicks "Login with GitHub/Google" in the web UI
2. Redirected to OAuth provider for authorization
3. Callback creates/updates user in database
4. JWT token returned and stored in session cookie

### OAuth Endpoints

| Endpoint | Description |
|----------|-------------|
| `GET /auth/providers` | List configured OAuth providers |
| `GET /auth/github/login` | Initiate GitHub OAuth flow |
| `GET /auth/github/callback` | GitHub OAuth callback |
| `GET /auth/google/login` | Initiate Google OAuth flow |
| `GET /auth/google/callback` | Google OAuth callback |
| `GET /auth/me` | Get current user info |

## MCP Authentication

MCP servers use a separate authentication mechanism for game-related API access.

### MCP Auth Keys

When `ENABLE_AGENT_REST_API=false` (default), MCP servers must authenticate:

```bash
# MCP servers include the auth key in headers
curl http://127.0.0.1:8000/api/session/SESSION_ID/state \
  -H "X-MCP-Auth-Key: mcp_key_..."
```

### IP Allowlist

MCP access is restricted to allowed IPs:

```bash
MCP_ALLOWED_IPS=127.0.0.1,192.168.1.100
```

### Creating MCP Keys

MCP keys are created programmatically:

```python
from outplaylabs_arena.mcp_key_manager import create_mcp_key

key = create_mcp_key(db_session)
# Returns: {"key_id": "...", "key": "mcp_key_..."}
```

## Access Control Matrix

| Endpoint Category | External Access | Authentication |
|-------------------|-----------------|----------------|
| Game-related (`/experiment`, `/session/*`) | Controlled by `ENABLE_AGENT_REST_API` | API key or MCP auth |
| Configuration (`/games/*`, `/site-config`) | Always public | None |
| Results (`/session/*/results`, `/sessions`) | Always public | None (optional user for filtering) |
| Admin (`/keys/*`, `/mcp-keys/*`) | Requires user auth | OAuth or API key |

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `ENABLE_AGENT_REST_API` | `false` | Allow external REST API access to game endpoints |
| `MCP_ALLOWED_IPS` | `127.0.0.1` | Comma-separated IPs allowed for MCP access |

## Security Best Practices

1. **Rotate API keys regularly** - Delete old keys and create new ones
2. **Use environment variables** - Never hardcode API keys in source code
3. **Restrict MCP IPs** - Only allow trusted MCP server IPs
4. **Use HTTPS in production** - Always use TLS for API communication
5. **Monitor key usage** - Check `last_used_at` timestamps for suspicious activity
