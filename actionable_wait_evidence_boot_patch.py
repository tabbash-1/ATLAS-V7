#!/usr/bin/env python3
"""Idempotently expose diagnostic closed-candle WAIT evidence in the web UI."""
from pathlib import Path
import re
BASE=Path(__file__).resolve().parent
INDEX=BASE/'index.html'
SCRIPT='atlas-actionable-wait-evidence.js'
MARKER='actionable-wait-evidence-v1'
def apply():
    if not INDEX.exists():
        raise RuntimeError('index.html missing; refusing WAIT evidence patch')
    html=INDEX.read_text(encoding='utf-8')
    html=re.sub(r'<script[^>]+src=["\']atlas-actionable-wait-evidence\.js(?:\?[^"\']*)?["\'][^>]*></script>','',html)
    tag=f'  <script src="{SCRIPT}?v={MARKER}"></script>\n'
    html=html.replace('</body>',tag+'</body>',1) if '</body>' in html else html+tag
    INDEX.write_text(html,encoding='utf-8')
    print('ATLAS boot patch: actionable closed-candle WAIT evidence UI enabled',flush=True)
    return True
if __name__=='__main__': apply()
