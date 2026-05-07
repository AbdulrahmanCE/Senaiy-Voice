# Senaiy Voice — Production Deployment

Single-domain VPS deployment with Caddy (HTTPS auto-TLS) + systemd.

## Architecture on the server

```
                     ┌──────────────┐
   internet ──TLS──▶ │  Caddy :443  │
                     └──────┬───────┘
                            │
       ┌────────────────────┼────────────────────┐
       │                    │                    │
       ▼                    ▼                    ▼
 / (root)             /twilio/*            /admin/*
   │                    │                    │
   │ proxy_pass         │ proxy_pass         │ proxy_pass
   ▼                    ▼ (strip prefix)     ▼ (strip prefix)
 localhost:7860      localhost:7861       localhost:8080
 senaiy-web.service  senaiy-twilio.service  senaiy-admin.service
```

All three services run as the `senaiy` user, log to `/var/log/senaiy/`, and
share the SQLite DB + recordings under `/opt/senaiy/server/data/`.

## Prerequisites

- Ubuntu 22.04+ (or Debian 12+) VPS with SSH root access
- A domain pointing to the VPS's public IP (A record), e.g. `senaiy.solvfast.com`
- Inbound `80/tcp` and `443/tcp` open in the firewall

## Deploy

### 1. On the server (as root):

```bash
ssh root@your-server
mkdir -p /tmp/senaiy && cd /tmp/senaiy
# (sync the deploy/ directory from your laptop first — see step 2)
sudo DOMAIN=senaiy.solvfast.com bash install.sh
```

The install script:
- Installs Python 3.11, uv, Caddy, ffmpeg, sqlite3
- Creates the `senaiy` user
- Sets up directories and log paths
- Prints the **exact next steps** at the end

### 2. Sync the source from your laptop:

```bash
rsync -avz --exclude '.venv' --exclude 'data' --exclude '__pycache__' \
  ~/Documents/Senaiy-Voice/senaiy-voice/server/ \
  root@senaiy.solvfast.com:/opt/senaiy/server/

# Plus the deploy/ folder (so install.sh + systemd units are on the server):
rsync -avz ~/Documents/Senaiy-Voice/senaiy-voice/deploy/ \
  root@senaiy.solvfast.com:/opt/senaiy/deploy/
```

### 3. Production `.env`

On the server, copy your dev `.env` to `/opt/senaiy/server/.env` and **set**:

```bash
PUBLIC_DOMAIN=senaiy.solvfast.com
PUBLIC_BASE_URL=https://senaiy.solvfast.com/admin

# Generate a real secret key:
ADMIN_SECRET_KEY=<output of: python -c "import secrets; print(secrets.token_hex(32))">

# Strong admin password!
ADMIN_PASSWORD=<something not 'Senaiy2026!'>
```

Make sure permissions are tight:
```bash
chown senaiy:senaiy /opt/senaiy/server/.env
chmod 600 /opt/senaiy/server/.env
```

### 4. Install Python deps + apply branding:

```bash
cd /opt/senaiy/server
sudo -u senaiy bash -c 'export PATH="$HOME/.local/bin:$PATH"; uv sync'
sudo -u senaiy /opt/senaiy/.local/bin/uv run python scripts/patch_branding.py
```

### 5. Wire up systemd + Caddy:

```bash
cp /opt/senaiy/deploy/systemd/*.service /etc/systemd/system/
sed "s/senaiy.solvfast.com/${DOMAIN}/" /opt/senaiy/deploy/Caddyfile > /etc/caddy/Caddyfile
systemctl daemon-reload
systemctl enable --now senaiy-web senaiy-twilio senaiy-admin
systemctl reload caddy
```

### 6. External configuration

| Where | What to update |
|-------|----------------|
| Twilio Console → your phone number | "A call comes in" webhook → `https://senaiy.solvfast.com/twilio/` (POST) |
| OAuth client (Frappe MCP) | Redirect URI → `https://senaiy.solvfast.com/admin/oauth/callback`. Re-authorize from admin (it'll re-run Dynamic Client Registration). |
| ngrok | Stop running it on your laptop — it's no longer needed. |

### 7. Verify

```bash
systemctl status senaiy-web senaiy-twilio senaiy-admin caddy
curl -I https://senaiy.solvfast.com/
curl -I https://senaiy.solvfast.com/admin/login
journalctl -u senaiy-admin -n 100 --no-pager
```

Open in a browser:
- `https://senaiy.solvfast.com/` → SmallWebRTC test page
- `https://senaiy.solvfast.com/admin/login` → admin

Place a phone call to your Twilio number to test the telephony path.

## Updating

```bash
# From your laptop
rsync -avz --exclude '.venv' --exclude 'data' --exclude '__pycache__' \
  ~/Documents/Senaiy-Voice/senaiy-voice/server/ \
  root@senaiy.solvfast.com:/opt/senaiy/server/

# On the server
ssh root@senaiy.solvfast.com '
  cd /opt/senaiy/server
  sudo -u senaiy bash -c "export PATH=\$HOME/.local/bin:\$PATH; uv sync"
  systemctl restart senaiy-web senaiy-twilio senaiy-admin
'
```

## Logs

```bash
tail -f /var/log/senaiy/web.log /var/log/senaiy/twilio.log /var/log/senaiy/admin.log
journalctl -u senaiy-admin -f
```

## Backup

The state worth backing up:
- `/opt/senaiy/server/data/senaiy.db` (calls, transcripts, MCP servers + tokens)
- `/opt/senaiy/server/data/recordings/` (call recordings, can be large)
- `/opt/senaiy/server/prompts/senaiy.md` (your hand-edited system prompt)
- `/opt/senaiy/server/.env` (secrets — keep this offline too)

A simple cron-driven backup:
```bash
0 3 * * * tar czf /backups/senaiy-$(date +\%F).tgz \
  /opt/senaiy/server/data /opt/senaiy/server/prompts /opt/senaiy/server/.env
```

## Troubleshooting

**Caddy fails to issue cert** → DNS not pointed at the VPS yet. Check `dig senaiy.solvfast.com` shows your server IP.

**`/admin/oauth/callback` returns 404** → Frappe redirected to the wrong URL. Make sure `PUBLIC_BASE_URL=https://senaiy.solvfast.com/admin` is set in `.env` and the admin service was restarted.

**Twilio call drops immediately** → Check `/var/log/senaiy/twilio.log`. The bot's TwiML response may have the wrong proxy URL — confirm `PUBLIC_DOMAIN=senaiy.solvfast.com` in `.env`.

**MCP returns 401 after some time** → Token expired. The bot auto-refreshes per session, but the admin's "Test" button uses the live token. Click "Refresh token" in admin if testing.
