"""Re-apply Senaiy/SolvFast branding to the Pipecat prebuilt client UI.

Run after `uv sync` (which restores upstream files):
    uv run scripts/patch_branding.py
"""

import base64
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DIST = ROOT / ".venv/lib/python3.11/site-packages/pipecat_ai_small_webrtc_prebuilt/client/dist"
LOGO_PNG = ROOT / "static/logo.png"

if not DIST.exists():
    sys.exit(f"prebuilt dist not found at {DIST} — run `uv sync` first")
if not LOGO_PNG.exists():
    sys.exit(f"logo not found at {LOGO_PNG}")


def _backup_once(p: Path) -> Path:
    orig = p.with_suffix(p.suffix + ".orig")
    if not orig.exists():
        orig.write_bytes(p.read_bytes())
    return orig


def patch_js() -> None:
    js = next(DIST.glob("assets/index-*.js"))
    src = _backup_once(js).read_text()
    new = (
        src.replace("Pipecat Playground", "Senaiy Playground")
        .replace("Bot Audio", "Senaiy Audio")
        .replace("Bot Video", "Senaiy Video")
    )
    js.write_text(new)
    print(f"patched JS: {js.name}")


def patch_html() -> None:
    html = DIST / "index.html"
    src = _backup_once(html).read_text()
    new = src.replace("<title>Pipecat UI</title>", "<title>Senaiy — SolvFast</title>")
    html.write_text(new)
    print("patched index.html title")


def patch_logo() -> None:
    target = DIST / "pipecat-logo.svg"
    _backup_once(target)
    b64 = base64.b64encode(LOGO_PNG.read_bytes()).decode()
    svg = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1359 272" '
        'width="1359" height="272">\n'
        f'  <image href="data:image/png;base64,{b64}" width="1359" height="272"/>\n'
        '</svg>\n'
    )
    target.write_text(svg)
    print("patched pipecat-logo.svg with embedded SolvFast PNG")


if __name__ == "__main__":
    patch_js()
    patch_html()
    patch_logo()
    print("done.")
