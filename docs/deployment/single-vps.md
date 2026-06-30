# Single-VPS Deployment (Hetzner)

Run the full stack — frontend, backend, 1× MCP server, docs, Postgres, Redis —
on a single Hetzner CX22 (€3.79/month) with backups to a Hetzner Storage Box
(€3.81/month, optional).

**Total cost: ~€5–8/month** (VPS + domain + optional Storage Box).

This recipe takes about an hour from a fresh VPS to a working deployment.

## What you get

```
Internet
   │
   ▼
Traefik (:80, :443)   ←  Let's Encrypt TLS
   │
   ├─ <DOMAIN>/              → backend (FastAPI + React SPA)
   ├─ <DOMAIN>/api/...       → backend
   ├─ <DOMAIN>/mcp/...       → mcp (1 long-running container)
   └─ <DOMAIN>/docs/         → docs (mkdocs Material; /docs prefix stripped)

postgres  ←  /opt/arena/postgres_data  (named volume)
redis     ←  /opt/arena/redis_data     (named volume, AOF)
```

Traefik is the only thing exposed on the host. Everything else is on a private
docker network.

## 1. Buy the VPS

1. Sign in to [Hetzner Robot](https://robot.hetzner.com/) (or Cloud Console)
2. Create a new server:
   - **Image:** Ubuntu 24.04
   - **Type:** CX22 (Shared — 2 vCPU, 4 GB RAM, 40 GB SSD, €3.79/mo)
   - **Location:** any (FSN1/NBG1/HEL1 are common in EU)
   - **SSH key:** paste your public key
3. Note the server's public IPv4 address

## 2. Buy a domain (if you don't have one)

Any registrar works. Recommended for low markup: [Cloudflare Registrar](https://www.cloudflare.com/products/registrar/)
($10–12/yr for most TLDs). A `.dev` or `.app` TLD is nice but not required.

In your registrar's DNS panel, create:

| Type | Name | Value | TTL |
|---|---|---|---|
| A | `@` (or your subdomain) | `<vps-ipv4>` | 300 |
| A | `traefik` | `<vps-ipv4>` | 300 |

You can use a subdomain (e.g. `arena.example.com`) instead of the apex if you
prefer to keep the apex for something else.

## 3. Point DNS and wait

```bash
dig +short your-domain.example.com   # should return the VPS IP
```

DNS can take a few minutes to propagate.

## 4. First-time VPS setup (as root)

SSH in as root:

```bash
ssh root@<vps-ipv4>
```

Clone the repo and run the bootstrap script:

```bash
git clone https://github.com/OutplayArena/arena.git /opt/arena
cd /opt/arena
bash deploy/scripts/bootstrap.sh
```

What this does (in order):

1. Creates a non-root user `arena` with sudo + docker group access
2. Installs and configures UFW (allow 22, 80, 443)
3. Installs Docker Engine + Compose plugin
4. Enables unattended security upgrades
5. Hardens SSH: disables root login + password auth (uses your SSH key only)

Log out and back in as the new user:

```bash
ssh arena@<vps-ipv4>
```

Verify Docker works:

```bash
docker ps
```

## 5. Lay out the stack

The bootstrap script cloned the repo to `/opt/arena`. The deploy artifacts
expect this layout. Verify and adjust if you cloned elsewhere:

```bash
cd /opt/arena
ls deploy/                  # docker-compose.yml, scripts/, .env.production.example
```

## 6. Configure environment

```bash
cd /opt/arena/deploy
cp .env.production.example .env
chmod 600 .env
$EDITOR .env
```

Fill in the required values:

| Variable | Notes |
|---|---|
| `DOMAIN` | The FQDN you pointed at the VPS in step 2 (e.g. `arena.example.com`) |
| `ACME_EMAIL` | Email for Let's Encrypt registration / expiry notices |
| `POSTGRES_PASSWORD` | Long random string (≥32 chars). `openssl rand -base64 32` |
| `JWT_SECRET` | Long random hex. `openssl rand -hex 32` |
| `TRAEFIK_DASHBOARD_AUTH` | Basic-auth user:hash for the Traefik dashboard. Generate with `htpasswd -nb admin 'your-password'` and paste the whole output (including the `$apr1$…` part) |
| `GITHUB_CLIENT_ID` / `_SECRET` | Optional. Register at https://github.com/settings/developers with callback `https://${DOMAIN}/api/auth/github/callback` |
| `GOOGLE_CLIENT_ID` / `_SECRET` | Optional. Register at Google Cloud Console with callback `https://${DOMAIN}/api/auth/google/callback` |

Note: the `.env` file is committed nowhere. The deploy compose reads it at
runtime; `backup.sh` snapshots it; the `restic-env` file (next step) holds
backup secrets.

## 7. Start the stack

Production runs as a single-node **Docker Swarm** stack (not plain `docker
compose`) so that releases can be rolled out with zero downtime — see
[Continuous deployment](#continuous-deployment) below. Turn this host into a
1-node swarm once, then deploy the stack:

```bash
cd /opt/arena/deploy
docker swarm init
./scripts/stack-deploy.sh
```

!!! warning
    Always deploy via `scripts/stack-deploy.sh`, not a bare `docker stack
    deploy -c docker-compose.yml arena --with-registry-auth`. Unlike `docker
    compose`, `docker stack deploy` does **not** auto-read `.env` from the
    working directory for `${VAR}` interpolation (there's no `--env-file`
    flag for it either) — run it directly and every `${DOMAIN}`,
    `${POSTGRES_PASSWORD}`, etc. silently resolves to an empty string.
    `stack-deploy.sh` exports `.env` into the shell first, then deploys.

The first pull/start takes a minute or two. Watch the progress:

```bash
docker stack ps arena
docker service logs -f arena_backend
```

Once everything is up, verify with the healthcheck:

```bash
./scripts/healthcheck.sh
```

Expected output:

```
Healthcheck for https://<DOMAIN>
  [OK]   Backend (root SPA)        .../  (HTTP 200)
  [OK]   API root                  .../api/  (HTTP 404)
  [OK]   API site-config           .../api/site-config  (HTTP 200)
  [OK]   API games                 .../api/games  (HTTP 200)
  [OK]   MCP health                .../mcp/health  (HTTP 200)
  [OK]   Docs index                .../docs/  (HTTP 200)
  [OK]   Docs page                 .../docs/getting-started/  (HTTP 200)
All checks passed.
```

Open in a browser:

- **App:** https://`${DOMAIN}`/
- **Docs:** https://`${DOMAIN}`/docs (the React SPA's iframe-rendered docs)
- **MCP:** https://`${DOMAIN}`/mcp/ (the SDK connects here)
- **Traefik dashboard:** https://traefik.`${DOMAIN}`/ (basic auth)

### Continuous deployment

Every `v*.*.*` tag pushed to the repo builds and publishes the `backend`/`mcp`
images (`.github/workflows/release.yml`'s `build` job, unchanged), then a
`deploy` job SSHes into this box and runs `deploy/scripts/swarm-deploy.sh
<tag>`, which:

1. Applies pending Alembic migrations against the *new* image, before
   touching the running service.
2. Rolls `arena_backend`, then `arena_mcp`, one at a time via `docker
   service update` — Swarm only stops the old task once the new one passes
   its healthcheck (`update_config: { order: start-first, failure_action:
   rollback }` in `deploy/docker-compose.yml`), so the rollout doesn't drop
   connections the way a `docker compose up -d` hard restart would.
3. Persists the new tag into `.env` and runs `healthcheck.sh` to confirm
   the rollout actually succeeded.

Plain merges to `main` build and deploy nothing — only a version tag does
(same trigger `release.yml` already used for Docker Hub/PyPI publishing).

This requires a one-time setup the first time you wire up CD: generate a
dedicated SSH keypair for GitHub Actions, add its public half to
`/home/arena/.ssh/authorized_keys` on this box, and add `DEPLOY_HOST`,
`DEPLOY_USER=arena`, `DEPLOY_SSH_KEY` as secrets in the repo's
`production-deploy` GitHub environment (same tag-only deployment-branch
policy as the existing `docker-hub-ci` environment).

To roll a release manually instead of waiting on CI:

```bash
sudo /opt/arena/deploy/scripts/swarm-deploy.sh v0.3.0
```

## 8. Set up backups to a Hetzner Storage Box (optional but recommended)

The Storage Box is a separate Hetzner product (€3.81/month, 1 TB) optimized for
backups. It exposes SFTP, which `restic` can use directly.

### 8.1 Buy the Storage Box

In Hetzner Robot → **Storage Boxes** → order the smallest (BX11, 1 TB).

Note the access credentials (e.g. `u123456` / password) and the hostname
(e.g. `u123456.your-storagebox.de`).

### 8.2 Create the backup sub-directory

```bash
ssh u123456@u123456.your-storagebox.de
> mkdir arena-backups
> exit
```

### 8.3 Install restic

```bash
sudo apt-get install -y restic
```

### 8.4 Write the restic env file

```bash
sudo mkdir -p /etc/arena
sudo install -m 600 /dev/null /etc/arena/restic-env
sudo $EDITOR /etc/arena/restic-env
```

Contents:

```bash
RESTIC_REPO=sftp:u123456@u123456.your-storagebox.de:/arena-backups
RESTIC_PASSWORD=<long-random-string>            # restic encryption key, store safely
```

Test it:

```bash
sudo /opt/arena/deploy/scripts/backup.sh
```

If it works, you should see `Backup complete.` and a new snapshot ID.

### 8.5 Schedule the nightly backup

```bash
sudo crontab -e
```

Add:

```cron
0 3 * * * /opt/arena/deploy/scripts/backup.sh >> /var/log/arena/backup.log 2>&1
```

The script keeps 7 daily, 4 weekly, 6 monthly snapshots.

## 9. Day-to-day

```bash
# Service status
docker service ls
docker stack ps arena

# Logs (any service)
docker service logs -f --tail=100 arena_backend
docker service logs -f --tail=100 arena_mcp

# Restart a service (re-runs its current image, same rolling-update behavior)
docker service update --force arena_backend

# Roll to a specific release (normally done automatically by CI — see
# "Continuous deployment" above)
sudo /opt/arena/deploy/scripts/swarm-deploy.sh v0.3.0

# Re-apply the full compose file (e.g. after editing docker-compose.yml or .env)
/opt/arena/deploy/scripts/stack-deploy.sh

# Healthcheck (run from anywhere)
DOMAIN=arena.example.com /opt/arena/deploy/scripts/healthcheck.sh

# Manual backup
sudo /opt/arena/deploy/scripts/backup.sh

# Restore
sudo /opt/arena/deploy/scripts/restore.sh            # interactive
sudo /opt/arena/deploy/scripts/restore.sh latest    # latest snapshot
```

`deploy/scripts/update.sh` (the old `git pull && docker compose up -d` hard
restart) still works as a fallback/manual-recovery path but is no longer the
routine update mechanism — see [Continuous deployment](#continuous-deployment).

## 10. Disaster recovery

Worst case (VPS gone, you have to start over on a new one):

1. Buy a new Hetzner CX22
2. Run `bootstrap.sh` on the new box
3. Clone the repo: `git clone https://github.com/OutplayArena/arena.git /opt/arena`
4. Edit the new `deploy/.env` to match the old one
5. Start the stack: `docker swarm init && deploy/scripts/stack-deploy.sh`
6. Restore from the Storage Box:
   ```bash
   sudo /opt/arena/deploy/scripts/restore.sh latest
   ```
   Answer `y` to "Restore database from this dump?"

Postgres comes back with the latest dump. Sessions created between the last
backup and the crash are lost — back up more often if that matters.

## 11. Performance and scaling

The CX22 (4 GB RAM) is fine for tens of concurrent users and a few active
games. To scale up:

| Symptom | Action |
|---|---|
| OOM under load | Upgrade to CX32 (8 GB, €6.49/mo) or CX42 (16 GB, €12.49/mo) |
| Slow Postgres | Add a managed Postgres (Neon free tier) and point `DATABASE_URL` at it |
| CPU-bound on backend | Scale up the CX plan; for vertical scaling this is the simplest knob |
| Need real HA | Move to k8s (see [Kubernetes](kubernetes.md)); single-VPS is not HA |

For most hobby workloads the CX22 is sufficient. Watch the resource usage:

```bash
docker stats
htop
```

## 12. Troubleshooting

### `docker stack deploy` fails with "port 80/443 is already in use"

Something else is bound to those ports. Check:

```bash
sudo ss -tlnp | grep -E ':80|:443'
```

Common culprits: Apache, nginx, caddy. Stop the offender or change Traefik's
ports in `deploy/docker-compose.yml`.

### Let's Encrypt certificate issuance fails

- Check that DNS resolves correctly: `dig +short <DOMAIN}` from anywhere
- Check the Traefik logs: `docker service logs arena_traefik`
- Common cause: the ACME rate limit (5 certs per week per domain). Wait or
  use a different subdomain for testing.

### Backend can't connect to Postgres

- Check the service is healthy: `docker service ps arena_backend`
- Check the password matches between `.env` and the running container
- Check logs: `docker service logs arena_backend | grep -i 'postgres\|asyncpg'`

### Postgres fails with "you must specify POSTGRES_PASSWORD"

You ran `docker stack deploy` directly instead of `scripts/stack-deploy.sh`.
`docker stack deploy` doesn't auto-read `.env` from the working directory
for `${VAR}` interpolation the way `docker compose` does — every `${VAR}` in
`docker-compose.yml` silently resolves to an empty string if you invoke it
bare. Postgres is the one service that fails loudly about it (refuses to
start with an empty password); other services with blank `${VAR}`s
(`DOMAIN`, `REDIS_PASSWORD`, etc.) may come up "successfully" misconfigured
instead. Always deploy via `scripts/stack-deploy.sh`, which exports `.env`
first.

### A `docker service update` rolled back unexpectedly

Swarm auto-rolls back when the new task fails its healthcheck
(`failure_action: rollback`). Check why the new image didn't come up
healthy:

```bash
docker service ps arena_backend --no-trunc   # shows the failed task's error
docker service logs arena_backend --since 10m
```

Common causes: a migration that doesn't apply cleanly, a missing/changed env
var the new release expects, or the image itself crash-looping.

### Restore is stuck on a huge database

The restore pipes the full `pg_dump` through the container. For very large
databases, restore to a fresh container instead of overwriting in place.

### I lost the restic password

You're out of luck — restic snapshots are encrypted with that key. Store it
in a password manager and/or print it to a paper backup.

## 13. Next steps

- Set up [UptimeRobot](https://uptimerobot.com/) (free) to monitor
  `https://<DOMAIN>/api/site-config` and alert you on downtime
- Enable Hetzner server backups (€0.012/GB/month) for the VPS itself
- Subscribe to the GitHub releases feed to know when updates are available
- Once you outgrow the single VPS, see [Kubernetes](kubernetes.md) for the
  multi-node setup
