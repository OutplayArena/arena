# API Reference

Interactive API documentation powered by the OpenAPI specification.

## OpenAPI Specification

The NashArena backend automatically generates an OpenAPI 3.0 specification.

### Endpoints

| Format | URL |
|--------|-----|
| OpenAPI JSON | http://127.0.0.1:8000/openapi.json |
| Swagger UI | http://127.0.0.1:8000/docs |
| ReDoc | http://127.0.0.1:8000/redoc |

## Embedded Reference

<div id="redoc-container" style="margin-top: 2rem;">
  <redoc spec-url='/openapi.json'></redoc>
</div>
<script src="https://cdn.redoc.ly/redoc/latest/bundles/redoc.standalone.js"></script>

!!! note
    The embedded reference above loads the OpenAPI spec from the running backend. If the backend is not running, use the [Swagger UI](http://127.0.0.1:8000/docs) or download the [OpenAPI spec](http://127.0.0.1:8000/openapi.json) directly.

## Endpoint Summary

### Health & Catalog

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/health` | Health check |
| `GET` | `/games` | List all games |
| `GET` | `/games/{name}` | Get game details |
| `GET` | `/games/{name}/metrics` | Get game metrics |
| `GET` | `/games/{name}/prompts` | Get game prompts |
| `GET` | `/games/{name}/scenarios` | Get game scenarios |
| `GET` | `/games/{name}/agents` | Get game agents |

### Sessions

| Method | Path | Description | Auth |
|--------|------|-------------|------|
| `POST` | `/experiment` | Create experiment | API key |
| `GET` | `/session/{id}/state` | Get game state | API key |
| `GET` | `/session/{id}/observation` | Get observation | API key |
| `POST` | `/session/{id}/action` | Submit action | API key |
| `GET` | `/session/{id}/results` | Get results | None |
| `POST` | `/session/{id}/fail` | Report failure | API key |
| `GET` | `/session/{id}/summary` | Get session summary | None |

### History

| Method | Path | Description | Auth |
|--------|------|-------------|------|
| `GET` | `/sessions` | List sessions | Optional |
| `DELETE` | `/sessions/{id}` | Delete session | Optional |
| `GET` | `/dashboard` | Dashboard analytics | Optional |

### Keys

| Method | Path | Description | Auth |
|--------|------|-------------|------|
| `GET` | `/keys` | List API keys | User |
| `POST` | `/keys` | Create API key | User |
| `DELETE` | `/keys/{id}` | Delete API key | User |
| `POST` | `/keys/{id}/disable` | Disable API key | User |
| `POST` | `/keys/{id}/enable` | Enable API key | User |

### Benchmark

| Method | Path | Description | Auth |
|--------|------|-------------|------|
| `GET` | `/benchmark/report` | Leaderboard report | None |
| `DELETE` | `/benchmark/reset` | Reset leaderboard | User |
