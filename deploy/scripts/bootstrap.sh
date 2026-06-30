#!/usr/bin/env bash
# bootstrap.sh — initial setup for a fresh Hetzner CX22 (Ubuntu 24.04).
#
# Idempotent: safe to re-run.
#
# What it does:
#   1. Creates a non-root user 'arena' with sudo + docker group access
#   2. Installs the UFW firewall (allow 22, 80, 443)
#   3. Installs Docker Engine + Compose plugin
#   4. Enables unattended security upgrades
#   5. Hardens SSH (disables root login + password auth — assumes you've
#      already copied your SSH public key into /root/.ssh/authorized_keys
#      and can log in as root once more)
#
# Run as root, then re-login as the 'arena' user to continue.
set -euo pipefail

ARENA_USER="${ARENA_USER:-arena}"
SSH_PORT="${SSH_PORT:-22}"
LOG_PREFIX="[bootstrap]"

log() { echo "$LOG_PREFIX $*"; }

[[ $EUID -eq 0 ]] || { echo "must run as root" >&2; exit 1; }

# ── 1. Non-root user ────────────────────────────────────────────────
if ! id "$ARENA_USER" >/dev/null 2>&1; then
    log "Creating user '$ARENA_USER'"
    adduser --disabled-password --gecos "" "$ARENA_USER"
    echo "$ARENA_USER ALL=(ALL) NOPASSWD:ALL" > "/etc/sudoers.d/$ARENA_USER"
fi
mkdir -p "/home/$ARENA_USER/.ssh"
# Copy root's authorized_keys so the new user can SSH in with the same key
cp /root/.ssh/authorized_keys "/home/$ARENA_USER/.ssh/authorized_keys" 2>/dev/null || true
chown -R "$ARENA_USER:$ARENA_USER" "/home/$ARENA_USER/.ssh"
chmod 700 "/home/$ARENA_USER/.ssh"
chmod 600 "/home/$ARENA_USER/.ssh/authorized_keys" 2>/dev/null || true

# ── 2. UFW firewall ─────────────────────────────────────────────────
if ! command -v ufw >/dev/null 2>&1; then
    log "Installing UFW"
    DEBIAN_FRONTEND=noninteractive apt-get install -y ufw
fi
log "Configuring firewall (22, 80, 443)"
ufw allow "$SSH_PORT/tcp" comment "SSH"
ufw allow 80/tcp comment "HTTP"
ufw allow 443/tcp comment "HTTPS"
# Docker manipulates iptables directly; allow forwarding
sed -i 's/^DEFAULT_FORWARD_POLICY=.*/DEFAULT_FORWARD_POLICY="ACCEPT"/' /etc/default/ufw || true
echo "y" | ufw enable

# ── 3. Docker ───────────────────────────────────────────────────────
if ! command -v docker >/dev/null 2>&1; then
    log "Installing Docker"
    DEBIAN_FRONTEND=noninteractive apt-get install -y ca-certificates curl
    install -m 0755 -d /etc/apt/keyrings
    curl -fsSL https://download.docker.com/linux/ubuntu/gpg | gpg --dearmor -o /etc/apt/keyrings/docker.gpg
    chmod a+r /etc/apt/keyrings/docker.gpg
    echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo "$VERSION_CODENAME") stable" \
        > /etc/apt/sources.list.d/docker.list
    apt-get update
    DEBIAN_FRONTEND=noninteractive apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
fi
usermod -aG docker "$ARENA_USER"

# ── 4. Unattended upgrades ─────────────────────────────────────────
if ! dpkg -l unattended-upgrades >/dev/null 2>&1; then
    log "Installing unattended-upgrades"
    DEBIAN_FRONTEND=noninteractive apt-get install -y unattended-upgrades
    dpkg-reconfigure -f noninteractive unattended-upgrades
fi

# ── 5. SSH hardening ────────────────────────────────────────────────
SSHD="/etc/ssh/sshd_config"
if [[ -f "$SSHD" ]]; then
    log "Hardening SSH (disable root login + password auth)"
    cp "$SSHD" "$SSHD.bak.$(date +%s)"
    sed -i 's/^#\?PermitRootLogin.*/PermitRootLogin no/'  "$SSHD"
    sed -i 's/^#\?PasswordAuthentication.*/PasswordAuthentication no/' "$SSHD"
    sed -i 's/^#\?PubkeyAuthentication.*/PubkeyAuthentication yes/' "$SSHD"
    systemctl reload ssh || systemctl reload sshd
fi

log "Done."
log ""
log "Next steps:"
log "  1. Re-login as $ARENA_USER:  ssh $ARENA_USER@<this-host>"
log "  2. Verify docker:            docker ps"
log "  3. Follow docs/deployment/single-vps.md to deploy the stack"
