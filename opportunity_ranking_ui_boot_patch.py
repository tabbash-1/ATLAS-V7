#!/usr/bin/env python3
"""Idempotently inject the Final Gate opportunity ranking UI script."""
from pathlib import Path
import re

BASE = Path(__file__).resolve().parent
INDEX = BASE / "index.html"
SCRIPT = "atlas-opportunity-ranking-ui.js"
VERSION = "opportunity-ranking-ui-v1-final-gate-diagnostic"


def apply():
    if not INDEX.exists():
        return
    html = INDEX.read_text(encoding="utf-8")
    html = re.sub(
        rf'<script[^>]+src=["\']{re.escape(SCRIPT)}(?:\?[^"\']*)?["\'][^>]*></script>',
        '',
        html,
    )
    tag = f'  <script src="{SCRIPT}?v={VERSION}"></script>\n'
    html = html.replace("</body>", tag + "</body>", 1) if "</body>" in html else html + "\n" + tag
    INDEX.write_text(html, encoding="utf-8")
    print("ATLAS boot patch: Final Gate opportunity ranking UI enabled", flush=True)


if __name__ == "__main__":
    apply()
