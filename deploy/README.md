# Single-VPS deployment

Production deployment for a single Hetzner CX22 (2 vCPU, 4 GB RAM, 40 GB SSD).
See `docs/deployment/single-vps.md` for the full step-by-step recipe; this README is
a quick-reference for the contents of this directory.

## Layout

```
deploy/
├── docker-compose.yml             # production compose: Traefik + Postgres + Redis + backend + mcp + docs
├── .env.production.example        # template for /opt/arena/deploy/.env
├── README.md                      # you are here
└── scripts/
    ├── bootstrap.sh               # one-time VPS setup (Docker, firewall, user)
    ├── backup.sh                  # nightly restic backup to Hetzner Storage Box
    ├── restore.sh                 # interactive restore from a snapshot
    ├── update.sh                  # git pull + rebuild + restart
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
docker compose pull
docker compose up -d --build

# 4. Verify
./scripts/healthcheck.sh
```

## Day-to-day

```bash
# Logs
docker compose logs -f --tail=100 backend
docker compose logs -f --tail=100 mcp

# Restart a single service
docker compose restart backend

# Update to latest
sudo ./scripts/update.sh

# Healthcheck
./scripts/healthcheck.sh

# Backup
sudo ./scripts/backup.sh

# Restore
sudo ./scripts/restore.sh              # interactive
sudo ./scripts/restore.sh latest      # latest snapshot
```
