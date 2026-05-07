#!/usr/bin/env bash
# Senaiy Voice — one-shot install script for a fresh Ubuntu/Debian VPS.
# Run as root (or via sudo) on the server. Idempotent — safe to re-run.
#
# Usage:
#   sudo DOMAIN=senaiy.solvfast.com bash install.sh
#
# Assumes: Ubuntu 22.04+/Debian 12+. Will install: Python 3.11, uv, Caddy, ffmpeg.

set -euo pipefail

DOMAIN="${DOMAIN:?Set DOMAIN env var, e.g. DOMAIN=senaiy.solvfast.com}"
APP_USER="senaiy"
APP_DIR="/opt/senaiy"
LOG_DIR="/var/log/senaiy"
REPO_DIR="$APP_DIR/server"

echo ">>> Updating apt and installing system packages..."
apt-get update -y
apt-get install -y --no-install-recommends \
    curl ca-certificates gnupg debian-keyring debian-archive-keyring \
    git python3.11 python3.11-venv python3.11-dev build-essential \
    ffmpeg sqlite3 libsndfile1 \
    apt-transport-https

echo ">>> Installing Caddy (reverse proxy + auto TLS)..."
if ! command -v caddy >/dev/null; then
    curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' | gpg --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg
    curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt' > /etc/apt/sources.list.d/caddy-stable.list
    apt-get update -y
    apt-get install -y caddy
fi

echo ">>> Creating $APP_USER user and directories..."
id -u "$APP_USER" >/dev/null 2>&1 || useradd --system --create-home --home-dir "$APP_DIR" --shell /usr/sbin/nologin "$APP_USER"
mkdir -p "$REPO_DIR" "$LOG_DIR"
chown -R "$APP_USER:$APP_USER" "$APP_DIR" "$LOG_DIR"

echo ">>> Installing uv (Python package manager) for $APP_USER..."
sudo -u "$APP_USER" sh -c 'curl -LsSf https://astral.sh/uv/install.sh | sh'

cat <<EOF
>>> Files install path is ready: $REPO_DIR

NEXT STEPS — do these on this server (as root or sudo):

  1. Sync the project source from your laptop:
       rsync -avz --exclude '.venv' --exclude 'data' \\
         /Users/solvfast/Documents/Senaiy-Voice/senaiy-voice/server/ \\
         root@$DOMAIN:$REPO_DIR/

  2. Place your production .env at $REPO_DIR/.env
     (start from .env.example, set PUBLIC_DOMAIN=$DOMAIN
      and PUBLIC_BASE_URL=https://$DOMAIN/admin)

  3. Install Python deps:
       cd $REPO_DIR
       sudo -u $APP_USER bash -c 'export PATH="\$HOME/.local/bin:\$PATH"; uv sync'
       sudo -u $APP_USER /opt/senaiy/.local/bin/uv run python scripts/patch_branding.py

  4. Install systemd units + Caddy site:
       cp deploy/systemd/*.service /etc/systemd/system/
       sed "s/senaiy.solvfast.com/$DOMAIN/" deploy/Caddyfile > /etc/caddy/Caddyfile
       systemctl daemon-reload
       systemctl enable --now senaiy-web senaiy-twilio senaiy-admin
       systemctl reload caddy

  5. Verify:
       systemctl status senaiy-web senaiy-twilio senaiy-admin caddy
       journalctl -u senaiy-admin -n 50 --no-pager
       curl -I https://$DOMAIN/
       curl -I https://$DOMAIN/admin/login

  6. Update Twilio webhook to:  https://$DOMAIN/twilio/

  7. Update OAuth redirect URI in your MCP server registration:
       https://$DOMAIN/admin/oauth/callback
     (admin will re-do Dynamic Client Registration on next Authorize click)

EOF
