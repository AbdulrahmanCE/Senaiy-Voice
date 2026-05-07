"""Senaiy Admin Interface.

Run:
    uv run uvicorn admin:app --port 8080

Auth via env vars: ADMIN_USERNAME, ADMIN_PASSWORD, ADMIN_SECRET_KEY.
"""

import os
import logging
import secrets
from pathlib import Path
from html import escape as h

from dotenv import load_dotenv
from fastapi import FastAPI, Form, HTTPException, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse, FileResponse
from starlette.middleware.sessions import SessionMiddleware

import db as _db


load_dotenv(override=True)

ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "admin")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "change-me")
ADMIN_SECRET_KEY = os.getenv("ADMIN_SECRET_KEY") or secrets.token_hex(32)

ROOT = Path(__file__).resolve().parent
PROMPT_PATH = ROOT / "prompts" / "senaiy.md"
TOOLS_PROMPT_PATH = ROOT / "prompts" / "_tools.md"
RECORDINGS_DIR = ROOT / "data" / "recordings"
ENV_PATH = ROOT / ".env"


app = FastAPI(title="Senaiy Admin")
app.add_middleware(SessionMiddleware, secret_key=ADMIN_SECRET_KEY, max_age=60 * 60 * 24)
_db.init_db()


# ---------- helpers ----------

def is_authed(request: Request) -> bool:
    return request.session.get("user") == ADMIN_USERNAME


def require_admin(request: Request):
    if not is_authed(request):
        raise HTTPException(status_code=302, headers={"Location": "/login"})


def page(title: str, body: str, request: Request | None = None) -> str:
    nav = ""
    if request and is_authed(request):
        nav = (
            '<nav class="nav">'
            '<a href="/">Calls</a>'
            '<a href="/prompt">System Prompt</a>'
            '<a href="/mcp">MCP Servers</a>'
            '<a href="/twilio">Twilio</a>'
            '<a href="/env">Env</a>'
            '<a href="/config">Config</a>'
            '<form method="post" action="/logout" style="display:inline">'
            '<button class="logout">Logout</button></form>'
            "</nav>"
        )
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1.0" />
<title>{h(title)} · Senaiy Admin</title>
<style>
:root {{ --bg:#0f1116; --panel:#171a22; --border:#272b36; --text:#e8eaf0; --muted:#8a92a3; --accent:#ff5722; --accent2:#7c3aed; }}
* {{ box-sizing: border-box; }}
body {{ margin:0; font:14px/1.5 -apple-system, system-ui, "Segoe UI", sans-serif; background:var(--bg); color:var(--text); }}
header {{ display:flex; gap:16px; align-items:center; padding:14px 24px; border-bottom:1px solid var(--border); background:var(--panel); }}
header img {{ height:32px; }}
header h1 {{ font-size:16px; margin:0; font-weight:600; color:var(--muted); }}
.nav {{ margin-left:auto; display:flex; gap:14px; align-items:center; }}
.nav a {{ color:var(--text); text-decoration:none; padding:6px 10px; border-radius:6px; }}
.nav a:hover {{ background:var(--border); }}
.nav .logout {{ background:transparent; border:1px solid var(--border); color:var(--text); padding:6px 10px; border-radius:6px; cursor:pointer; }}
main {{ max-width:1100px; margin:0 auto; padding:24px; }}
h2 {{ margin-top:0; }}
table {{ width:100%; border-collapse:collapse; }}
th, td {{ text-align:left; padding:10px 12px; border-bottom:1px solid var(--border); }}
th {{ color:var(--muted); font-weight:500; font-size:12px; text-transform:uppercase; letter-spacing:0.5px; }}
tr:hover td {{ background:var(--panel); }}
a {{ color:var(--accent); }}
.badge {{ display:inline-block; font-size:11px; padding:2px 8px; border-radius:999px; background:var(--border); color:var(--muted); }}
.badge.twilio {{ color:#fff; background:#7c3aed; }}
.badge.webrtc {{ color:#fff; background:#0ea5e9; }}
form.card {{ background:var(--panel); border:1px solid var(--border); border-radius:10px; padding:20px; }}
input, textarea {{ width:100%; padding:10px 12px; background:var(--bg); color:var(--text); border:1px solid var(--border); border-radius:6px; font:inherit; font-family:inherit; }}
textarea {{ min-height:480px; font-family: ui-monospace, "SF Mono", Menlo, monospace; font-size:13px; }}
label {{ display:block; margin:14px 0 6px; color:var(--muted); }}
button.primary {{ background:var(--accent); color:#fff; border:0; padding:10px 18px; border-radius:6px; cursor:pointer; font-weight:600; }}
button.primary:hover {{ filter:brightness(1.1); }}
.error {{ color:#ef4444; margin:8px 0; }}
.ok {{ color:#10b981; margin:8px 0; }}
.transcript {{ background:var(--panel); border:1px solid var(--border); border-radius:8px; padding:12px 16px; margin:8px 0; }}
.transcript .role {{ font-size:11px; color:var(--muted); text-transform:uppercase; letter-spacing:1px; }}
.transcript.user {{ border-left:3px solid #0ea5e9; }}
.transcript.assistant {{ border-left:3px solid var(--accent); }}
.muted {{ color:var(--muted); }}
.kv td:first-child {{ color:var(--muted); width:200px; }}
</style>
</head>
<body>
<header>
<img src="/static/logo.png" alt="SolvFast" />
<h1>Senaiy Admin</h1>
{nav}
</header>
<main>
{body}
</main>
</body>
</html>"""


def fmt_time(iso: str | None) -> str:
    if not iso:
        return "—"
    return iso.replace("T", " ")[:19] + " UTC"


# ---------- auth ----------

@app.get("/login", response_class=HTMLResponse)
def login_form(request: Request, error: str = ""):
    if is_authed(request):
        return RedirectResponse("/", status_code=302)
    err = f'<p class="error">{h(error)}</p>' if error else ""
    body = f"""
<div style="max-width:380px; margin:80px auto;">
<form class="card" method="post" action="/login">
<h2>Sign in</h2>
{err}
<label>Username</label>
<input name="username" autocomplete="username" autofocus required />
<label>Password</label>
<input name="password" type="password" autocomplete="current-password" required />
<div style="margin-top:18px"><button class="primary" type="submit">Sign in</button></div>
</form>
</div>"""
    return HTMLResponse(page("Sign in", body, request))


@app.post("/login")
def login_submit(request: Request, username: str = Form(...), password: str = Form(...)):
    if username == ADMIN_USERNAME and password == ADMIN_PASSWORD:
        request.session["user"] = username
        return RedirectResponse("/mcp", status_code=302)
    return RedirectResponse("/login?error=Invalid+credentials", status_code=302)


@app.post("/logout")
def logout(request: Request):
    request.session.clear()
    return RedirectResponse("/login", status_code=302)


# ---------- pages ----------

@app.get("/", response_class=HTMLResponse)
def calls_list(request: Request):
    if not is_authed(request):
        return RedirectResponse("/login", status_code=302)
    rows = _db.list_calls(limit=200)
    if not rows:
        rows_html = '<tr><td colspan="5" class="muted">No calls yet.</td></tr>'
    else:
        rows_html = "".join(
            f'<tr>'
            f'<td><a href="/calls/{r["id"]}">#{r["id"]}</a></td>'
            f'<td><span class="badge {h(r["transport"])}">{h(r["transport"])}</span></td>'
            f'<td>{h(r.get("from_identifier") or "—")}</td>'
            f'<td>{h(fmt_time(r["started_at"]))}</td>'
            f'<td>{h(fmt_time(r["ended_at"]))}</td>'
            f'</tr>'
            for r in rows
        )
    body = f"""
<h2>Calls <span class="muted">({len(rows)})</span></h2>
<table>
<thead><tr><th>ID</th><th>Channel</th><th>From</th><th>Started</th><th>Ended</th></tr></thead>
<tbody>{rows_html}</tbody>
</table>"""
    return HTMLResponse(page("Calls", body, request))


@app.get("/calls/{call_id}", response_class=HTMLResponse)
def call_detail(request: Request, call_id: int):
    if not is_authed(request):
        return RedirectResponse("/login", status_code=302)
    calls = [c for c in _db.list_calls(limit=10000) if c["id"] == call_id]
    if not calls:
        raise HTTPException(404)
    call = calls[0]
    transcripts = _db.get_transcripts(call_id)

    rec_html = ""
    if call.get("recording_path"):
        rec_html = f'<audio controls src="/calls/{call_id}/recording" style="width:100%; margin:12px 0;"></audio>'

    t_html = "".join(
        f'<div class="transcript {h(t["role"])}"><div class="role">{h(t["role"])} · {h(fmt_time(t["timestamp"]))}</div><div>{h(t["content"])}</div></div>'
        for t in transcripts
    ) or '<p class="muted">No transcript captured.</p>'

    body = f"""
<p><a href="/">← Back to calls</a></p>
<h2>Call #{call_id}</h2>
<table class="kv">
<tr><td>Channel</td><td><span class="badge {h(call["transport"])}">{h(call["transport"])}</span></td></tr>
<tr><td>From</td><td>{h(call.get("from_identifier") or "—")}</td></tr>
<tr><td>To</td><td>{h(call.get("to_identifier") or "—")}</td></tr>
<tr><td>Started</td><td>{h(fmt_time(call["started_at"]))}</td></tr>
<tr><td>Ended</td><td>{h(fmt_time(call["ended_at"]))}</td></tr>
<tr><td>Recording</td><td>{h(call.get("recording_path") or "—")}</td></tr>
</table>
{rec_html}
<h3 style="margin-top:32px">Transcript ({len(transcripts)})</h3>
{t_html}"""
    return HTMLResponse(page(f"Call #{call_id}", body, request))


@app.get("/calls/{call_id}/recording")
def call_recording(request: Request, call_id: int):
    if not is_authed(request):
        return RedirectResponse("/login", status_code=302)
    calls = [c for c in _db.list_calls(limit=10000) if c["id"] == call_id]
    if not calls or not calls[0].get("recording_path"):
        raise HTTPException(404)
    path = Path(calls[0]["recording_path"])
    if not path.is_absolute():
        path = ROOT / path
    if not path.exists():
        raise HTTPException(404, "recording file missing on disk")
    return FileResponse(str(path), media_type="audio/wav", filename=path.name)


@app.get("/prompt", response_class=HTMLResponse)
def prompt_form(request: Request, saved: str = ""):
    if not is_authed(request):
        return RedirectResponse("/login", status_code=302)
    content = PROMPT_PATH.read_text(encoding="utf-8") if PROMPT_PATH.exists() else ""
    msg = '<p class="ok">Saved. Restart the bot for changes to take effect.</p>' if saved else ""
    body = f"""
<h2>System Prompt <span class="muted">({len(content):,} chars)</span></h2>
<p class="muted">Edit the instruction Senaiy follows. Saved to <code>prompts/senaiy.md</code>. The running bot must be restarted to pick up changes.</p>
{msg}
<form class="card" method="post" action="/prompt">
<textarea name="content" spellcheck="false">{h(content)}</textarea>
<div style="margin-top:14px"><button class="primary" type="submit">Save</button></div>
</form>"""
    return HTMLResponse(page("System Prompt", body, request))


@app.post("/prompt")
def prompt_save(request: Request, content: str = Form(...)):
    if not is_authed(request):
        return RedirectResponse("/login", status_code=302)
    PROMPT_PATH.parent.mkdir(parents=True, exist_ok=True)
    PROMPT_PATH.write_text(content, encoding="utf-8")
    return RedirectResponse("/prompt?saved=1", status_code=302)


# ---------- Twilio webhook management ----------

async def _twilio_get_phone_sid() -> tuple[str | None, str | None]:
    """Look up the SID for TWILIO_PHONE_NUMBER. Returns (sid, current_voice_url)."""
    import aiohttp
    sid = os.getenv("TWILIO_ACCOUNT_SID")
    token = os.getenv("TWILIO_AUTH_TOKEN")
    phone = os.getenv("TWILIO_PHONE_NUMBER")
    if not (sid and token and phone):
        return None, None
    auth = aiohttp.BasicAuth(sid, token)
    url = f"https://api.twilio.com/2010-04-01/Accounts/{sid}/IncomingPhoneNumbers.json"
    async with aiohttp.ClientSession() as s:
        async with s.get(url, params={"PhoneNumber": phone}, auth=auth,
                          timeout=aiohttp.ClientTimeout(total=10)) as r:
            if r.status >= 400:
                return None, None
            data = await r.json()
            for n in data.get("incoming_phone_numbers", []):
                return n.get("sid"), n.get("voice_url")
    return None, None


def _resolve_public_voice_url() -> tuple[str, str]:
    """Compute the desired Twilio voice URL from PUBLIC_DOMAIN, fall back to live ngrok.

    Returns (url, source_label).
    """
    domain = os.getenv("PUBLIC_DOMAIN", "").strip()
    if domain:
        return f"https://{domain}/twilio/", f"PUBLIC_DOMAIN ({domain})"
    # Try ngrok local API
    try:
        import urllib.request, json as _json
        with urllib.request.urlopen("http://127.0.0.1:4040/api/tunnels", timeout=2) as r:
            tunnels = _json.loads(r.read().decode()).get("tunnels", [])
        for t in tunnels:
            if t.get("proto") == "https":
                host = t["public_url"].replace("https://", "")
                return f"https://{host}/twilio/", f"ngrok ({host})"
    except Exception:
        pass
    return "", "no source available"


@app.get("/twilio", response_class=HTMLResponse)
async def twilio_view(request: Request, msg: str = "", error: str = ""):
    if not is_authed(request):
        return RedirectResponse("/login", status_code=302)
    sid, current_url = await _twilio_get_phone_sid()
    target_url, target_source = _resolve_public_voice_url()
    phone = os.getenv("TWILIO_PHONE_NUMBER", "—")

    flash = ""
    if msg:
        flash = f'<p class="ok">{h(msg)}</p>'
    if error:
        flash = f'<p class="error">{h(error)}</p>'

    if not sid:
        body = f"""
<h2>Twilio Webhook</h2>
<p class="error">Twilio credentials missing or phone number not found.</p>
<p class="muted">Set <code>TWILIO_ACCOUNT_SID</code>, <code>TWILIO_AUTH_TOKEN</code>, and <code>TWILIO_PHONE_NUMBER</code> in <code>.env</code> and restart admin.</p>
"""
        return HTMLResponse(page("Twilio", body, request))

    matches = (current_url or "").rstrip("/") == (target_url or "").rstrip("/")
    status_html = ""
    if target_url:
        if matches:
            status_html = f'<p class="ok">Webhook already matches the desired URL.</p>'
        else:
            status_html = f'<p class="muted">Click below to push <code>{h(target_url)}</code> to Twilio.</p>'

    body = f"""
<h2>Twilio Webhook</h2>
{flash}
<table class="kv">
<tr><td>Phone number</td><td>{h(phone)}</td></tr>
<tr><td>Phone SID</td><td><code>{h(sid)}</code></td></tr>
<tr><td>Current Voice URL</td><td><code>{h(current_url or "—")}</code></td></tr>
<tr><td>Desired Voice URL</td><td><code>{h(target_url or "(unable to compute)")}</code></td></tr>
<tr><td>Source</td><td>{h(target_source)}</td></tr>
</table>
{status_html}
<form class="card" method="post" action="/twilio/sync" style="margin-top:18px">
<button class="primary" type="submit"{' disabled' if not target_url else ''}>Push desired URL to Twilio now</button>
</form>"""
    return HTMLResponse(page("Twilio Webhook", body, request))


@app.post("/twilio/sync")
async def twilio_sync(request: Request):
    if not is_authed(request):
        return RedirectResponse("/login", status_code=302)
    import aiohttp
    sid, _ = await _twilio_get_phone_sid()
    target_url, _ = _resolve_public_voice_url()
    if not (sid and target_url):
        return RedirectResponse("/twilio?error=Missing+SID+or+target+URL", status_code=302)
    account = os.getenv("TWILIO_ACCOUNT_SID")
    token = os.getenv("TWILIO_AUTH_TOKEN")
    auth = aiohttp.BasicAuth(account, token)
    url = f"https://api.twilio.com/2010-04-01/Accounts/{account}/IncomingPhoneNumbers/{sid}.json"
    async with aiohttp.ClientSession() as s:
        async with s.post(url, data={"VoiceUrl": target_url, "VoiceMethod": "POST"},
                           auth=auth, timeout=aiohttp.ClientTimeout(total=10)) as r:
            if r.status >= 400:
                txt = await r.text()
                return RedirectResponse(f"/twilio?error=Twilio+API+{r.status}:+{h(txt[:200])}", status_code=302)
    return RedirectResponse(f"/twilio?msg=Webhook+pushed:+{h(target_url)}", status_code=302)


# ---------- .env editor ----------

SENSITIVE_KEY_PATTERNS = ("API_KEY", "SECRET", "TOKEN", "PASSWORD", "AUTH")


def _redact_env_text(text: str) -> str:
    """Replace values of sensitive keys with placeholder for safe display."""
    out = []
    for line in text.splitlines():
        stripped = line.lstrip()
        if not stripped or stripped.startswith("#") or "=" not in line:
            out.append(line)
            continue
        key, _, val = line.partition("=")
        key_upper = key.strip().upper()
        if val.strip() and any(p in key_upper for p in SENSITIVE_KEY_PATTERNS):
            out.append(f"{key}=••••••••(hidden — toggle to reveal)")
        else:
            out.append(line)
    return "\n".join(out)


@app.get("/env", response_class=HTMLResponse)
def env_view(request: Request, msg: str = "", error: str = "", reveal: int = 0):
    if not is_authed(request):
        return RedirectResponse("/login", status_code=302)
    raw = ENV_PATH.read_text(encoding="utf-8") if ENV_PATH.exists() else ""
    display = raw if reveal else _redact_env_text(raw)
    flash = ""
    if msg:
        flash = f'<p class="ok">{h(msg)}</p>'
    if error:
        flash = f'<p class="error">{h(error)}</p>'
    reveal_btn = (
        '<a href="/env?reveal=0" class="logout" style="text-decoration:none">Hide secrets</a>'
        if reveal else
        '<a href="/env?reveal=1" class="logout" style="text-decoration:none">Reveal secrets</a>'
    )
    body = f"""
<h2>Environment Variables <span class="muted">({len(raw):,} chars)</span></h2>
<p class="muted">Edit <code>server/.env</code> directly. Changes take effect only after services restart. Secrets are masked by default — click <em>Reveal secrets</em> to edit them, but never leave that view open on a shared screen.</p>
{flash}
<div style="margin:8px 0">{reveal_btn}
<form method="post" action="/env/restart" style="display:inline;margin-left:8px"><button class="logout" onclick="return confirm('Restart admin + bots? Active calls will be dropped.')">Restart services</button></form>
</div>
<form class="card" method="post" action="/env">
<input type="hidden" name="reveal" value="{1 if reveal else 0}" />
<textarea name="content" spellcheck="false"{' readonly' if not reveal else ''}>{h(display)}</textarea>
{'<p class="muted" style="margin-top:6px">Read-only while masked. Reveal secrets to edit.</p>' if not reveal else ''}
<div style="margin-top:14px"><button class="primary" type="submit"{' disabled' if not reveal else ''}>Save .env</button></div>
</form>"""
    return HTMLResponse(page("Environment", body, request))


@app.post("/env")
def env_save(request: Request, content: str = Form(...), reveal: int = Form(0)):
    if not is_authed(request):
        return RedirectResponse("/login", status_code=302)
    if not reveal:
        return RedirectResponse("/env?error=Cannot+save+from+masked+view", status_code=302)
    # Basic sanity check: must look like KEY=VALUE lines or comments
    bad_lines = []
    for i, line in enumerate(content.splitlines(), 1):
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if "=" not in line:
            bad_lines.append(f"line {i}: {line[:60]}")
    if bad_lines:
        return RedirectResponse(
            f"/env?reveal=1&error=Malformed+lines:+{h('; '.join(bad_lines[:3]))}",
            status_code=302,
        )
    ENV_PATH.write_text(content, encoding="utf-8")
    return RedirectResponse(
        "/env?reveal=0&msg=Saved.+Click+Restart+services+to+apply.",
        status_code=302,
    )


@app.post("/env/restart")
def env_restart(request: Request):
    """Restart this admin + the two bots. Strategy depends on environment:
       1. If running under systemd, use systemctl (requires NoNewPrivileges=false or sudo rule).
       2. Otherwise, pkill the bot.py processes (systemd or supervisor will respawn) and
          re-exec ourselves to pick up the new .env.
    """
    if not is_authed(request):
        return RedirectResponse("/login", status_code=302)

    import shutil
    import subprocess
    import signal

    # Try systemd first (production)
    if shutil.which("systemctl") and Path("/etc/systemd/system/senaiy-admin.service").exists():
        try:
            subprocess.run(["systemctl", "restart", "senaiy-web", "senaiy-twilio"],
                           timeout=15, check=False)
            # Restart admin LAST since it kills our own process
            subprocess.Popen(["systemctl", "restart", "senaiy-admin"])
            return RedirectResponse("/env?msg=Restart+triggered+via+systemd", status_code=302)
        except Exception as e:
            return RedirectResponse(f"/env?reveal=0&error=systemctl+restart+failed:+{h(str(e))}", status_code=302)

    # Dev fallback: kill the bot processes (supervisor/launchctl/manual will restart)
    try:
        subprocess.run(["pkill", "-f", "bot.py"], check=False)
    except Exception:
        pass

    # Re-exec admin so we pick up new .env. We need to do this AFTER returning the redirect.
    import os, sys, threading, time
    def _reexec():
        time.sleep(0.5)
        os.execv(sys.executable, [sys.executable] + sys.argv)
    threading.Thread(target=_reexec, daemon=True).start()
    return RedirectResponse(
        "/env?msg=Bots+killed+(supervisor+will+restart).+Admin+re-execing+now.",
        status_code=302,
    )


@app.get("/config", response_class=HTMLResponse)
def config_view(request: Request):
    if not is_authed(request):
        return RedirectResponse("/login", status_code=302)

    def mask(v: str | None) -> str:
        if not v:
            return "—"
        return v[:6] + "…" + v[-4:] if len(v) > 12 else "•" * len(v)

    keys = [
        ("OPENAI_API_KEY", os.getenv("OPENAI_API_KEY"), True),
        ("OPENAI_MODEL", os.getenv("OPENAI_MODEL"), False),
        ("OPENAI_VOICE_ID", os.getenv("OPENAI_VOICE_ID"), False),
        ("ELEVENLABS_API_KEY", os.getenv("ELEVENLABS_API_KEY"), True),
        ("ELEVENLABS_VOICE_ID", os.getenv("ELEVENLABS_VOICE_ID"), False),
        ("TWILIO_ACCOUNT_SID", os.getenv("TWILIO_ACCOUNT_SID"), True),
        ("TWILIO_AUTH_TOKEN", os.getenv("TWILIO_AUTH_TOKEN"), True),
        ("TWILIO_PHONE_NUMBER", os.getenv("TWILIO_PHONE_NUMBER"), False),
        ("ADMIN_USERNAME", os.getenv("ADMIN_USERNAME"), False),
    ]
    rows = "".join(
        f'<tr><td>{h(k)}</td><td>{h(mask(v) if secret else (v or "—"))}</td></tr>'
        for k, v, secret in keys
    )
    body = f"""
<h2>Configuration</h2>
<p class="muted">Read from environment / <code>.env</code>. Editing through the UI is not supported yet — open <code>server/.env</code> directly.</p>
<table class="kv">{rows}</table>
<h3 style="margin-top:24px">MCP Connections</h3>
<p class="muted">Coming in Phase 3.</p>"""
    return HTMLResponse(page("Config", body, request))


# ---------- MCP server management ----------

@app.get("/mcp", response_class=HTMLResponse)
def mcp_list(request: Request, msg: str = "", error: str = ""):
    if not is_authed(request):
        return RedirectResponse("/login", status_code=302)
    servers = _db.list_mcp_servers()
    rows = ""
    for s in servers:
        status_html = ""
        if s.get("last_status"):
            is_ok = s["last_status"].startswith("ok")
            color = "#10b981" if is_ok else "#ef4444"
            status_html = (
                f'<details><summary style="color:{color};cursor:pointer;font-size:12px">'
                f'{"ok" if is_ok else "error"} <span class="muted">· last checked '
                f'{h(fmt_time(s.get("last_checked_at")))}</span></summary>'
                f'<div style="font-family:ui-monospace,monospace;font-size:11px;white-space:pre-wrap;'
                f'word-break:break-all;margin-top:6px;color:var(--muted)">{h(s["last_status"])}</div>'
                f'</details>'
            )
        toggle_label = "Disable" if s["enabled"] else "Enable"
        rows += f"""
<tr>
<td>{s['id']}</td>
<td><strong>{h(s['name'])}</strong><div style="font-size:11px;color:var(--muted);margin-top:4px;max-width:320px;word-break:break-all">{h(s['url'])}</div>{status_html}</td>
<td><span class="badge">{h(s['transport'])}</span></td>
<td>{'Yes' if s['enabled'] else 'No'}</td>
<td>
<form method="post" action="/mcp/{s['id']}/oauth/start" style="display:inline"><button class="logout" style="background:#7c3aed;color:#fff;border-color:#7c3aed">{'Re-authorize' if s.get('oauth_access_token') else 'Authorize OAuth'}</button></form>
<form method="post" action="/mcp/{s['id']}/test" style="display:inline"><button class="logout">Test</button></form>
<form method="post" action="/mcp/{s['id']}/toggle" style="display:inline"><button class="logout">{toggle_label}</button></form>
<form method="post" action="/mcp/{s['id']}/delete" style="display:inline" onsubmit="return confirm('Delete {h(s['name'])}?')"><button class="logout" style="color:#ef4444">Delete</button></form>
{f'<form method="post" action="/mcp/{s["id"]}/oauth/refresh" style="display:inline"><button class="logout">Refresh token</button></form>' if s.get('oauth_refresh_token') else ''}
</td>
</tr>"""
    if not rows:
        rows = '<tr><td colspan="6" class="muted">No MCP servers configured.</td></tr>'

    flash = ""
    if msg:
        flash = f'<p class="ok">{h(msg)}</p>'
    if error:
        flash = f'<p class="error">{h(error)}</p>'

    tools_status = ""
    if TOOLS_PROMPT_PATH.exists():
        size = TOOLS_PROMPT_PATH.stat().st_size
        if size > 0:
            tools_status = f' · <code>prompts/_tools.md</code> auto-generated ({size:,} bytes)'

    body = f"""
<h2>MCP Servers <span class="muted">({len(servers)})</span></h2>
<p class="muted">Connect external tool servers (Model Context Protocol). New tools are auto-injected into Senaiy's system prompt whenever you Test, Authorize, Toggle, or Delete a server{tools_status}. The bot reads this on each new session.</p>
<form method="post" action="/mcp/regenerate-tools" style="display:inline;margin:8px 0">
<button class="logout">Refresh tools section now</button>
</form>
{flash}
<h3 style="margin-top:24px">Connected servers</h3>
<table>
<thead><tr><th>ID</th><th>Name & URL</th><th>Transport</th><th>Enabled</th><th>Actions</th></tr></thead>
<tbody>{rows}</tbody>
</table>

<h3 style="margin-top:32px">Add a new MCP server</h3>
<form class="card" method="post" action="/mcp/add">
<label>Name</label>
<input name="name" placeholder="solvfast-erp" required />
<label>URL <span class="muted">(streamable HTTP or SSE endpoint)</span></label>
<input name="url" placeholder="https://solvfast.com/api/mcp" required />
<label>Transport</label>
<select name="transport" style="width:100%; padding:10px 12px; background:var(--bg); color:var(--text); border:1px solid var(--border); border-radius:6px;">
<option value="streamable_http">Streamable HTTP (recommended)</option>
<option value="sse">SSE</option>
<option value="stdio">stdio (subprocess)</option>
</select>
<label>Auth header name <span class="muted">(optional, e.g. Authorization)</span></label>
<input name="auth_header_name" placeholder="Authorization" />
<label>Auth header value <span class="muted">(e.g. Bearer xyz, or token api_key:api_secret)</span></label>
<input name="auth_header_value" placeholder="Bearer ..." />
<label>Tool filter <span class="muted">(optional, comma-separated tool names — empty = expose all)</span></label>
<input name="tools_filter" placeholder="search_documents,create_document" />
<div style="margin-top:16px"><button class="primary" type="submit">Add server</button></div>
</form>

<p class="muted" style="margin-top:18px">OAuth-based MCP authorization (redirect flow) is not yet supported — for now paste the bearer token directly. Phase 3b adds the OAuth dance.</p>"""
    return HTMLResponse(page("MCP Servers", body, request))


@app.post("/mcp/add")
def mcp_add(
    request: Request,
    name: str = Form(...),
    url: str = Form(...),
    transport: str = Form("streamable_http"),
    auth_header_name: str = Form(""),
    auth_header_value: str = Form(""),
    tools_filter: str = Form(""),
):
    if not is_authed(request):
        return RedirectResponse("/login", status_code=302)
    try:
        _db.add_mcp_server(
            name=name.strip(),
            url=url.strip(),
            transport=transport,
            auth_header_name=auth_header_name.strip() or None,
            auth_header_value=auth_header_value.strip() or None,
            tools_filter=tools_filter.strip() or None,
        )
    except Exception as e:
        return RedirectResponse(f"/mcp?error={h(str(e))}", status_code=302)
    return RedirectResponse(f"/mcp?msg=Server+{name}+added.+Restart+the+bot+to+activate.", status_code=302)


@app.post("/mcp/regenerate-tools")
async def mcp_regenerate(request: Request):
    if not is_authed(request):
        return RedirectResponse("/login", status_code=302)
    try:
        count, _ = await regenerate_tools_md()
        return RedirectResponse(f"/mcp?msg=Refreshed+tools+section+from+{count}+server(s).", status_code=302)
    except Exception as e:
        return RedirectResponse(f"/mcp?error=Refresh+failed:+{h(str(e))}", status_code=302)


@app.post("/mcp/{server_id}/toggle")
async def mcp_toggle(request: Request, server_id: int):
    if not is_authed(request):
        return RedirectResponse("/login", status_code=302)
    _db.toggle_mcp_server(server_id)
    try:
        await regenerate_tools_md()
    except Exception as e:
        logging.getLogger("admin").warning(f"regenerate_tools_md after toggle failed: {e}")
    return RedirectResponse("/mcp?msg=Toggled+and+tools+section+refreshed.", status_code=302)


@app.post("/mcp/{server_id}/delete")
async def mcp_delete(request: Request, server_id: int):
    if not is_authed(request):
        return RedirectResponse("/login", status_code=302)
    _db.delete_mcp_server(server_id)
    try:
        await regenerate_tools_md()
    except Exception as e:
        logging.getLogger("admin").warning(f"regenerate_tools_md after delete failed: {e}")
    return RedirectResponse("/mcp?msg=Deleted+and+tools+section+refreshed.", status_code=302)


def _flatten_exceptions(exc: BaseException) -> list[str]:
    """Unwrap ExceptionGroup / __cause__ / __context__ chains into a flat list of strings."""
    out: list[str] = []

    def visit(e: BaseException, depth: int = 0):
        if isinstance(e, BaseExceptionGroup):
            for sub in e.exceptions:
                visit(sub, depth + 1)
            return
        out.append(f"{type(e).__name__}: {e}")
        if e.__cause__ is not None:
            visit(e.__cause__, depth + 1)
        elif e.__context__ is not None and not e.__suppress_context__:
            visit(e.__context__, depth + 1)

    visit(exc)
    return out


async def regenerate_tools_md() -> tuple[int, str]:
    """Connect to every enabled MCP server, list tools, and write prompts/_tools.md.

    Returns (server_count, summary_text). Errors per-server are tolerated and noted.
    """
    from mcp.client.session import ClientSession
    from mcp.client.streamable_http import streamablehttp_client
    from mcp.client.sse import sse_client

    parts: list[str] = [
        "## TOOLS — auto-generated from connected MCP servers",
        "",
        "These tools are live and callable. Prefer calling them over guessing.",
        "Never narrate the tool call. Just call it, then say the answer in plain spoken text.",
        "If a tool returns nothing or errors, say so and offer to take the caller's info instead.",
        "",
    ]
    server_count = 0
    for s in _db.list_mcp_servers(only_enabled=True):
        headers: dict[str, str] = {}
        if s.get("auth_header_name") and s.get("auth_header_value"):
            headers[s["auth_header_name"]] = s["auth_header_value"]
        transport = s.get("transport") or "streamable_http"

        try:
            if transport == "streamable_http":
                ctx = streamablehttp_client(s["url"], headers=headers or None)
            elif transport == "sse":
                ctx = sse_client(s["url"], headers=headers or None)
            else:
                parts.append(f"### {s['name']}\n_(transport `{s['transport']}` not introspected)_\n")
                continue

            async with ctx as transport_streams:
                read_stream, write_stream = transport_streams[0], transport_streams[1]
                async with ClientSession(read_stream, write_stream) as session:
                    await session.initialize()
                    tools_resp = await session.list_tools()
                    parts.append(f"### Tools from `{s['name']}` ({len(tools_resp.tools)})")
                    parts.append("")
                    for t in tools_resp.tools:
                        desc = (t.description or "").split("\n")[0].strip()[:200]
                        parts.append(f"- `{t.name}` — {desc}")
                    parts.append("")
                    server_count += 1
        except Exception as e:
            parts.append(f"### {s['name']}\n_Error introspecting: {type(e).__name__}: {e}_\n")

    if server_count == 0 and not any(line.startswith("### ") for line in parts):
        # No enabled servers — clear the tools file
        TOOLS_PROMPT_PATH.write_text("", encoding="utf-8")
        return 0, ""

    text = "\n".join(parts).rstrip() + "\n"
    TOOLS_PROMPT_PATH.parent.mkdir(parents=True, exist_ok=True)
    TOOLS_PROMPT_PATH.write_text(text, encoding="utf-8")
    return server_count, text


async def _probe_mcp(url: str, headers: dict[str, str] | None) -> str:
    """Raw HTTP probe to see what the server actually returns. Helpful for diagnosis."""
    import aiohttp
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                url,
                json={"jsonrpc": "2.0", "id": "probe", "method": "initialize",
                      "params": {"protocolVersion": "2024-11-05", "capabilities": {},
                                 "clientInfo": {"name": "senaiy-admin-probe", "version": "0.1"}}},
                headers={**(headers or {}),
                         "Content-Type": "application/json",
                         "Accept": "application/json, text/event-stream"},
                timeout=aiohttp.ClientTimeout(total=8),
            ) as r:
                ct = r.headers.get("Content-Type", "?")
                body = (await r.text())[:300]
                return f"HTTP {r.status} ({ct}) · body[:300]={body!r}"
    except Exception as e:
        return f"probe failed: {type(e).__name__}: {e}"


# ---------- OAuth 2.1 + PKCE + DCR flow for MCP servers ----------

import hashlib
import base64
import secrets as _secrets
from urllib.parse import urlencode, urljoin


def _pkce_pair() -> tuple[str, str]:
    verifier = base64.urlsafe_b64encode(_secrets.token_bytes(32)).rstrip(b"=").decode("ascii")
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode("ascii")
    return verifier, challenge


async def _discover_oauth(base_url: str) -> dict:
    """Fetch /.well-known/oauth-authorization-server to learn endpoints."""
    import aiohttp
    # base_url like https://erp.solvfast.com/api/method/...  -> we need just the origin
    from urllib.parse import urlparse
    p = urlparse(base_url)
    origin = f"{p.scheme}://{p.netloc}"
    async with aiohttp.ClientSession() as s:
        async with s.get(f"{origin}/.well-known/oauth-authorization-server", timeout=aiohttp.ClientTimeout(total=10)) as r:
            r.raise_for_status()
            return await r.json()


async def _register_client(registration_endpoint: str, redirect_uri: str) -> dict:
    """Dynamic Client Registration per RFC 7591."""
    import aiohttp
    body = {
        "client_name": "Senaiy Admin",
        "redirect_uris": [redirect_uri],
        "grant_types": ["authorization_code", "refresh_token"],
        "response_types": ["code"],
        "token_endpoint_auth_method": "none",  # public client
        "scope": "all",
    }
    async with aiohttp.ClientSession() as s:
        async with s.post(registration_endpoint, json=body, timeout=aiohttp.ClientTimeout(total=10)) as r:
            txt = await r.text()
            if r.status >= 400:
                raise RuntimeError(f"DCR failed ({r.status}): {txt[:300]}")
            import json
            return json.loads(txt)


PUBLIC_BASE_URL = os.getenv("PUBLIC_BASE_URL", "").rstrip("/")  # e.g. "https://senaiy.solvfast.com/admin"


def _admin_origin(request: Request) -> str:
    """Reconstruct the public-facing base URL of this admin server.

    Prefers PUBLIC_BASE_URL env var (set when deployed behind a reverse proxy
    with a path prefix), falling back to X-Forwarded-* headers, then the
    direct request URL (dev mode).
    """
    if PUBLIC_BASE_URL:
        return PUBLIC_BASE_URL
    proto = request.headers.get("x-forwarded-proto", request.url.scheme)
    host = request.headers.get("x-forwarded-host", request.url.netloc)
    return f"{proto}://{host}"


@app.post("/mcp/{server_id}/oauth/start")
async def mcp_oauth_start(request: Request, server_id: int):
    if not is_authed(request):
        return RedirectResponse("/login", status_code=302)
    server = _db.get_mcp_server(server_id)
    if not server:
        raise HTTPException(404)
    redirect_uri = urljoin(_admin_origin(request) + "/", "oauth/callback")
    try:
        meta = await _discover_oauth(server["url"])
        auth_ep = meta["authorization_endpoint"]
        token_ep = meta["token_endpoint"]
        reg_ep = meta.get("registration_endpoint")
    except Exception as e:
        return RedirectResponse(f"/mcp?error=Discovery+failed:+{h(str(e))}", status_code=302)

    # Reuse client_id if we already registered, else perform DCR
    client_id = server.get("oauth_client_id")
    client_secret = server.get("oauth_client_secret")
    if not client_id:
        if not reg_ep:
            return RedirectResponse(f"/mcp?error=No+registration_endpoint+and+no+client_id+stored", status_code=302)
        try:
            reg = await _register_client(reg_ep, redirect_uri)
            client_id = reg.get("client_id")
            client_secret = reg.get("client_secret")
        except Exception as e:
            return RedirectResponse(f"/mcp?error=Client+registration+failed:+{h(str(e))}", status_code=302)
        _db.update_mcp_fields(
            server_id,
            oauth_client_id=client_id,
            oauth_client_secret=client_secret,
            oauth_authorization_endpoint=auth_ep,
            oauth_token_endpoint=token_ep,
            oauth_registration_endpoint=reg_ep,
        )

    verifier, challenge = _pkce_pair()
    state = _secrets.token_urlsafe(24)
    _db.update_mcp_fields(server_id, oauth_state=state, oauth_code_verifier=verifier)

    params = {
        "response_type": "code",
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "code_challenge": challenge,
        "code_challenge_method": "S256",
        "state": state,
        "scope": "all",
    }
    return RedirectResponse(f"{auth_ep}?{urlencode(params)}", status_code=302)


@app.get("/oauth/callback")
async def oauth_callback(request: Request, code: str = "", state: str = "", error: str = ""):
    if not is_authed(request):
        return RedirectResponse("/login", status_code=302)
    if error:
        return RedirectResponse(f"/mcp?error=OAuth+error:+{h(error)}", status_code=302)
    if not code or not state:
        return RedirectResponse("/mcp?error=Missing+code+or+state+in+callback", status_code=302)

    # Find the server with this state
    matching = [s for s in _db.list_mcp_servers() if s.get("oauth_state") == state]
    if not matching:
        return RedirectResponse("/mcp?error=State+mismatch+—+possible+CSRF+or+expired", status_code=302)
    server = matching[0]
    redirect_uri = urljoin(_admin_origin(request) + "/", "oauth/callback")

    import aiohttp
    body = {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": redirect_uri,
        "client_id": server["oauth_client_id"],
        "code_verifier": server["oauth_code_verifier"],
    }
    if server.get("oauth_client_secret"):
        body["client_secret"] = server["oauth_client_secret"]

    try:
        async with aiohttp.ClientSession() as s:
            async with s.post(
                server["oauth_token_endpoint"],
                data=body,  # token endpoints expect form-encoded
                headers={"Accept": "application/json"},
                timeout=aiohttp.ClientTimeout(total=15),
            ) as r:
                txt = await r.text()
                if r.status >= 400:
                    return RedirectResponse(f"/mcp?error=Token+exchange+failed+({r.status}):+{h(txt[:240])}", status_code=302)
                import json
                tok = json.loads(txt)
    except Exception as e:
        return RedirectResponse(f"/mcp?error=Token+request+failed:+{h(str(e))}", status_code=302)

    import datetime as _dt
    expires_at = None
    if tok.get("expires_in"):
        expires_at = (_dt.datetime.now(_dt.timezone.utc) + _dt.timedelta(seconds=int(tok["expires_in"]))).isoformat()

    _db.update_mcp_fields(
        server["id"],
        oauth_access_token=tok.get("access_token"),
        oauth_refresh_token=tok.get("refresh_token"),
        oauth_token_expires_at=expires_at,
        oauth_state=None,
        oauth_code_verifier=None,
        # Mirror the bearer into the regular auth header fields so test+bot use it transparently
        auth_header_name="Authorization",
        auth_header_value=f"Bearer {tok.get('access_token')}",
    )
    _db.update_mcp_status(server["id"], "oauth: authorized")
    try:
        await regenerate_tools_md()
    except Exception as e:
        logging.getLogger("admin").warning(f"regenerate_tools_md after oauth failed: {e}")
    return RedirectResponse(f"/mcp?msg=Authorized+via+OAuth.+Tools+section+refreshed.", status_code=302)


@app.post("/mcp/{server_id}/oauth/refresh")
async def mcp_oauth_refresh(request: Request, server_id: int):
    if not is_authed(request):
        return RedirectResponse("/login", status_code=302)
    server = _db.get_mcp_server(server_id)
    if not server or not server.get("oauth_refresh_token"):
        return RedirectResponse("/mcp?error=No+refresh+token+stored", status_code=302)

    import aiohttp
    body = {
        "grant_type": "refresh_token",
        "refresh_token": server["oauth_refresh_token"],
        "client_id": server["oauth_client_id"],
    }
    if server.get("oauth_client_secret"):
        body["client_secret"] = server["oauth_client_secret"]

    try:
        async with aiohttp.ClientSession() as s:
            async with s.post(
                server["oauth_token_endpoint"],
                data=body,
                headers={"Accept": "application/json"},
                timeout=aiohttp.ClientTimeout(total=15),
            ) as r:
                txt = await r.text()
                if r.status >= 400:
                    return RedirectResponse(f"/mcp?error=Refresh+failed+({r.status}):+{h(txt[:240])}", status_code=302)
                import json
                tok = json.loads(txt)
    except Exception as e:
        return RedirectResponse(f"/mcp?error=Refresh+request+failed:+{h(str(e))}", status_code=302)

    import datetime as _dt
    expires_at = None
    if tok.get("expires_in"):
        expires_at = (_dt.datetime.now(_dt.timezone.utc) + _dt.timedelta(seconds=int(tok["expires_in"]))).isoformat()

    _db.update_mcp_fields(
        server_id,
        oauth_access_token=tok.get("access_token"),
        oauth_refresh_token=tok.get("refresh_token", server["oauth_refresh_token"]),
        oauth_token_expires_at=expires_at,
        auth_header_value=f"Bearer {tok.get('access_token')}",
    )
    return RedirectResponse("/mcp?msg=Token+refreshed.", status_code=302)


@app.post("/mcp/{server_id}/test")
async def mcp_test(request: Request, server_id: int):
    """Live-test an MCP server by connecting and listing tools."""
    if not is_authed(request):
        return RedirectResponse("/login", status_code=302)
    server = _db.get_mcp_server(server_id)
    if not server:
        raise HTTPException(404)

    import logging
    logger = logging.getLogger("admin.mcp_test")

    headers: dict[str, str] = {}
    if server.get("auth_header_name") and server.get("auth_header_value"):
        headers[server["auth_header_name"]] = server["auth_header_value"]

    transport = server.get("transport") or "streamable_http"
    try:
        from mcp.client.session import ClientSession
        from mcp.client.streamable_http import streamablehttp_client
        from mcp.client.sse import sse_client

        if transport == "streamable_http":
            ctx = streamablehttp_client(server["url"], headers=headers or None)
        elif transport == "sse":
            ctx = sse_client(server["url"], headers=headers or None)
        else:
            _db.update_mcp_status(server_id, f"test not supported for {transport}")
            return RedirectResponse("/mcp?error=Live+test+only+supported+for+streamable_http+and+sse", status_code=302)

        async with ctx as transport_streams:
            read_stream, write_stream = transport_streams[0], transport_streams[1]
            async with ClientSession(read_stream, write_stream) as session:
                await session.initialize()
                tools_resp = await session.list_tools()
                tool_names = [t.name for t in tools_resp.tools]
                status = f"ok · {len(tool_names)} tools: " + ", ".join(tool_names[:8]) + ("…" if len(tool_names) > 8 else "")
                _db.update_mcp_status(server_id, status)
                try:
                    await regenerate_tools_md()
                except Exception as e:
                    logging.getLogger("admin").warning(f"regenerate_tools_md after test failed: {e}")
                return RedirectResponse(f"/mcp?msg=Connected.+Found+{len(tool_names)}+tools.+Tools+section+refreshed.", status_code=302)

    except BaseException as e:
        # Flatten ExceptionGroup and chained exceptions
        details = _flatten_exceptions(e)
        # Also probe the URL with raw HTTP for extra diagnostic context
        probe = await _probe_mcp(server["url"], headers)
        full = " | ".join(details) + f" | probe: {probe}"
        logger.error(f"MCP test failed for #{server_id} ({server['name']}): {full}")
        _db.update_mcp_status(server_id, full[:500])
        # Surface only the first concrete error to the flash (full goes to last_status)
        first_line = details[0] if details else str(e)
        return RedirectResponse(f"/mcp?error={h(first_line)}", status_code=302)


# Serve the SolvFast logo for header
from fastapi.staticfiles import StaticFiles
app.mount("/static", StaticFiles(directory=str(ROOT / "static")), name="static")
