# Docker Deployment

Deploy OutplayArena using Docker Compose for local development or single-server deployments.

## Prerequisites

- Docker and Docker Compose v2
- `.env` file configured (see [Configuration](configuration.md))

## Quick Start

```bash
# Clone repository
git clone https://github.com/outplaylabs/arena.git
cd arena

# Configure environment
cp .env.example .env
# Edit .env with your settings

# Start the stack
cd backend/docker
docker compose up -d

# Check status
docker compose ps
```

The stack starts:
- **Backend**: http://localhost:8000 (API and frontend)
- **PostgreSQL**: localhost:5432
- **Traefik**: http://localhost:80 (reverse proxy)

## Architecture

```
                    Traefik (:80, :443, :8080)
                    /                          \
    agent-arena.local (HTTPS)       api.agent-arena.local (HTTPS)
                    \                          /
                     Backend (:8000)
                              |
                         PostgreSQL (:5432)

    Separate network: arena_default (for MCP containers)
```

## Services

### Backend

The main application serving:
- API: http://localhost:8000/api/
- Frontend: http://localhost:8000/
- Swagger UI: http://localhost:8000/docs

### PostgreSQL

Database for sessions, users, API keys. Data persisted in `pgdata` volume.

### Traefik

Reverse proxy handling:
- HTTPS termination
- Routing to backend
- MCP container routing

### Migrations

One-shot service that runs Alembic migrations on startup.

## Configuration

### Environment Variables

Edit `.env` in the repository root:

```bash
# Database
DATABASE_URL=postgresql+asyncpg://outplayarena:outplayarena@db:5432/outplayarena

# API
API_PREFIX=/api
ENABLE_AGENT_REST_API=false

# MCP
MCP_RUNTIME=docker
MCP_BACKEND_URL=http://backend:8000/api
MCP_DOCKER_NETWORK=arena_default
MCP_IMAGE=arena-mcp:latest

# OAuth (optional)
GITHUB_CLIENT_ID=
GITHUB_CLIENT_SECRET=
GOOGLE_CLIENT_ID=
GOOGLE_CLIENT_SECRET=
JWT_SECRET=your-secret-here
```

See [Configuration](configuration.md) for all options.

### Hosts File

For local HTTPS, add to `/etc/hosts`:

```
127.0.0.1 agent-arena.local
127.0.0.1 api.agent-arena.local
```

## Building Images

### Backend Image

```bash
cd backend/docker
docker build -t arena-backend:latest .
```

The Dockerfile:
1. Builds frontend (Node.js)
2. Installs Python dependencies
3. Copies backend code and static assets
4. Runs uvicorn

### MCP Image

```bash
cd backend/docker
docker build -f Dockerfile.mcp -t arena-mcp:latest .
```

## MCP Integration

### Enable MCP

```bash
MCP_RUNTIME=docker
MCP_EXPOSE_PORTS=true
MCP_PUBLIC_BASE_URL=http://localhost
```

### MCP Network

MCP containers run on a separate network:

```bash
docker network ls | grep arena_default
```

### MCP Container Lifecycle

1. Experiment created → Backend spawns MCP container
2. Container connects to backend via `MCP_BACKEND_URL`
3. Agent connects to MCP container via gateway URL
4. Game completes → Container stopped and removed

## Data Persistence

### Database

PostgreSQL data persisted in `pgdata` named volume:

```bash
docker volume ls | grep pgdata
```

### Backup

```bash
# Backup database
docker compose exec db pg_dump -U outplayarena outplayarena > backup.sql

# Restore database
cat backup.sql | docker compose exec -T db psql -U outplayarena outplayarena
```

## Development Mode

### Live Reload

Mount source code for development:

```yaml
# docker-compose.override.yml
services:
  backend:
    volumes:
      - ../arena:/app/arena
    command: uvicorn arena.main:app --reload --host 0.0.0.0 --port 8000
```

### Frontend Development

```bash
cd frontend
npm run dev
```

Vite dev server runs on http://localhost:5173 and proxies `/api` to backend.

## Production Considerations

### TLS

Configure Traefik with real certificates:

```yaml
# docker-compose.prod.yml
services:
  traefik:
    command:
      - "--certificatesresolvers.letsencrypt.acme.email=your@email.com"
      - "--certificatesresolvers.letsencrypt.acme.storage=/acme.json"
```

### Resource Limits

```yaml
services:
  backend:
    deploy:
      resources:
        limits:
          cpus: '2'
          memory: 2G
```

### Logging

Configure log drivers:

```yaml
services:
  backend:
    logging:
      driver: json-file
      options:
        max-size: "10m"
        max-file: "3"
```

### Documentation

Documentation is deployed to Cloudflare Pages automatically via GitHub Actions. See `.github/workflows/docs.yml` for the deployment workflow.

## Troubleshooting

### Backend Won't Start

```bash
# Check logs
docker compose logs backend

# Check database connectivity
docker compose exec backend python -c "import asyncpg; asyncpg.connect('postgresql://outplayarena:outplayarena@db:5432/outplayarena')"
```

### Migrations Fail

```bash
# Run migrations manually
docker compose exec backend alembic -c /app/alembic.ini upgrade head

# Reset database
docker compose down -v
docker compose up -d
```

### MCP Containers Not Starting

```bash
# Check Docker socket is mounted
docker compose exec backend ls -l /var/run/docker.sock

# Check MCP network exists
docker network ls | grep arena_default

# Check backend logs for MCP errors
docker compose logs backend | grep mcp
```

## Updating

```bash
# Pull latest code
git pull

# Rebuild images
cd backend/docker
docker compose build

# Restart stack
docker compose up -d

# Run migrations
docker compose exec backend alembic -c /app/alembic.ini upgrade head
```

## Next Steps

- [Kubernetes Deployment](kubernetes.md) — Production deployment
- [Configuration Reference](configuration.md) — All environment variables
- [MCP Setup](../mcp/setup.md) — MCP server configuration
