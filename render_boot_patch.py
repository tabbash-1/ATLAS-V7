#!/usr/bin/env python3
"""Render boot patch for ATLAS web mode."""
from pathlib import Path
import re

BASE = Path(__file__).resolve().parent
APP = BASE / "app.js"
INDEX = BASE / "index.html"
V7_UI = BASE / "v7-ui-redesign.js"


def patch_hype_chart():
    if not APP.exists(): return
    text = APP.read_text(encoding="utf-8")
    old = "renderWatchlist(); renderAssetTable(); loadTradingView(asset.symbol); renderTrial(); renderActiveSignal(); renderBacktest(); renderV4();"
    new = "renderWatchlist(); renderAssetTable(); loadTradingView(asset.symbol==='BINANCE:HYPEUSDT'?'BYBIT:HYPEUSDT':asset.symbol); renderTrial(); renderActiveSignal(); renderBacktest(); renderV4();"
    if old in text:
        APP.write_text(text.replace(old, new, 1), encoding="utf-8")
        print("ATLAS Render boot patch: TradingView HYPE -> BYBIT:HYPEUSDT", flush=True)


def patch_production_ui():
    if not INDEX.exists(): return
    html = INDEX.read_text(encoding="utf-8")
    names=("atlas-production-decision.js","production-web-autoload.js","atlas-deep-analysis-ui.js","atlas-unified-terminal.js","atlas-unified-terminal-polish.js","atlas-research-validation-ui.js")
    for name in names:
        html = re.sub(rf'<script[^>]+src=["\']{re.escape(name)}(?:\?[^"\']*)?["\'][^>]*></script>', '', html)
    scripts = "\n".join([
        '  <script src="atlas-production-decision.js?v=web-only-prod-v4"></script>',
        '  <script src="production-web-autoload.js?v=web-only-prod-v4"></script>',
        '  <script src="atlas-deep-analysis-ui.js?v=rc10-1-deep-v2-primary-4-12h"></script>',
        '  <script src="atlas-unified-terminal.js?v=unified-terminal-v1"></script>',
        '  <script src="atlas-unified-terminal-polish.js?v=unified-terminal-polish-v2-execution-semantics"></script>',
        '  <script src="atlas-research-validation-ui.js?v=research-validation-v1"></script>',
    ])
    injection="\n"+scripts+"\n"
    html=html.replace("</body>",injection+"</body>",1) if "</body>" in html else html+injection
    INDEX.write_text(html,encoding="utf-8")
    print("ATLAS Render boot patch: unified terminal + isolated research validation + Production + RC10.1 enabled",flush=True)


def patch_legacy_command_mirrors():
    if not V7_UI.exists(): return
    text=V7_UI.read_text(encoding="utf-8");changed=False
    old_cloud="    ['driftBadge','cmdDriftValue'],\n    ['cloudForwardBadge','cmdCloudValue']"
    if old_cloud in text:text=text.replace(old_cloud,"    ['driftBadge','cmdDriftValue']",1);changed=True
    old_regime="    const rg=regimeSource();\n    if(rg) paint($('cmdRegimeValue'),rg.textContent.trim());"
    new_regime="    const rg=regimeSource();\n    if(rg && !window.ATLAS_PRODUCTION_DECISION) paint($('cmdRegimeValue'),rg.textContent.trim());"
    if old_regime in text:text=text.replace(old_regime,new_regime,1);changed=True
    if changed:V7_UI.write_text(text,encoding="utf-8")


def apply():
    patch_hype_chart();patch_production_ui();patch_legacy_command_mirrors()

if __name__ == "__main__": apply()
