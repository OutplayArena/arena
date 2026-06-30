# Single-VPS deployment

Production deployment for a single Hetzner CX22 (2 vCPU, 4 GB RAM, 40 GB SSD),
run as a single-node Docker Swarm stack so releases roll out with zero
downtime. See `docs/deployment/single-vps.md` for the full step-by-step
recipe; this README is a quick-reference for the contents of this directory.

## Layout

```
deploy/
├── docker-compose.yml             # production stack: Traefik + Postgres + Redis + backend + mcp + docs
├── .env.production.example        # template for /opt/arena/deploy/.env
├── README.md                      # you are here
└── scripts/
    ├── bootstrap.sh               # one-time VPS setup (Docker, firewall, user)
    ├── backup.sh                  # nightly restic backup to Hetzner Storage Box
    ├── restore.sh                 # interactive restore from a snapshot
    ├── swarm-deploy.sh            # migrate + zero-downtime rolling update (used by CI on every release tag)
    ├── migrate.sh                 # apply/inspect Alembic migrations
    ├── update.sh                  # git pull + rebuild + hard restart (fallback/manual recovery only)
    └── healthcheck.sh             # HTTP smoke tests
```

## Quick reference

```bash
# 1. First-time VPS setup (run as root)
sudo ./scripts/bootstrap.sh

# 2. Configure environment
cd /opt/arena/deploy
cp .env.production.example .env
$EDITOR .env
chmod 600 .env

# 3. Deploy
docker swarm init
docker stack deploy -c docker-compose.yml arena --with-registry-auth

# 4. Verify
./scripts/healthcheck.sh
```

## Continuous deployment

Pushing a `v*.*.*` tag triggers `.github/workflows/release.yml`, which builds
the images, pushes them to Docker Hub, then SSHes into this box and runs
`swarm-deploy.sh <tag>` — migrate, then roll `arena_backend` and `arena_mcp`
one at a time via `docker service update` (new task healthchecked before the
old one stops; auto-rollback on failure). Plain `main` merges build and
deploy nothing. See `docs/deployment/single-vps.md#continuous-deployment`
for the one-time SSH-key/secrets setup.

## Day-to-day

```bash
# Status
docker service ls
docker stack ps arena

# Logs
docker service logs -f --tail=100 arena_backend
docker service logs -f --tail=100 arena_mcp

# Restart a single service
docker service update --force arena_backend

# Roll to a specific release (normally automatic — see "Continuous deployment")
sudo ./scripts/swarm-deploy.sh v0.3.0

# Healthcheck
./scripts/healthcheck.sh

# Backup
sudo ./scripts/backup.sh

# Restore
sudo ./scripts/restore.sh              # interactive
sudo ./scripts/restore.sh latest      # latest snapshot
```
