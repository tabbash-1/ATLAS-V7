#!/usr/bin/env python3
"""Render boot patch for ATLAS web mode.

1) Keeps ATLAS internal HYPEUSDT mapping intact while using a valid TradingView
   market for the visual chart.
2) Ensures the Production decision UI is actually loaded in web-only mode.
3) Prevents the legacy workspace observer from overwriting Production-owned
   Command Center regime/cloud status after Production renders.

The patch is idempotent and only mutates the ephemeral Render checkout.
"""
from pathlib import Path

BASE = Path(__file__).resolve().parent
APP = BASE / "app.js"
INDEX = BASE / "index.html"
V7_UI = BASE / "v7-ui-redesign.js"


def patch_hype_chart():
    if not APP.exists():
        return
    text = APP.read_text(encoding="utf-8")
    old = "renderWatchlist(); renderAssetTable(); loadTradingView(asset.symbol); renderTrial(); renderActiveSignal(); renderBacktest(); renderV4();"
    new = "renderWatchlist(); renderAssetTable(); loadTradingView(asset.symbol==='BINANCE:HYPEUSDT'?'BYBIT:HYPEUSDT':asset.symbol); renderTrial(); renderActiveSignal(); renderBacktest(); renderV4();"
    if old in text:
        APP.write_text(text.replace(old, new, 1), encoding="utf-8")
        print("ATLAS Render boot patch: TradingView HYPE -> BYBIT:HYPEUSDT", flush=True)
    elif "BYBIT:HYPEUSDT" in text:
        print("ATLAS Render boot patch: HYPE chart mapping already present", flush=True)
    else:
        print("ATLAS Render boot patch: expected renderAll anchor not found; app.js left untouched", flush=True)


def patch_production_ui():
    if not INDEX.exists():
        return
    html = INDEX.read_text(encoding="utf-8")
    scripts = []
    if "atlas-production-decision.js" not in html:
        scripts.append('  <script src="atlas-production-decision.js?v=web-only-prod-v2"></script>')
    if "production-web-autoload.js" not in html:
        scripts.append('  <script src="production-web-autoload.js?v=web-only-prod-v2"></script>')
    if not scripts:
        print("ATLAS Render boot patch: Production UI scripts already present", flush=True)
        return
    injection = "\n" + "\n".join(scripts) + "\n"
    if "</body>" in html:
        html = html.replace("</body>", injection + "</body>", 1)
    else:
        html += injection
    INDEX.write_text(html, encoding="utf-8")
    print("ATLAS Render boot patch: Production decision UI enabled", flush=True)


def patch_legacy_command_mirrors():
    if not V7_UI.exists():
        return
    text = V7_UI.read_text(encoding="utf-8")
    changed = False

    old_cloud = "    ['driftBadge','cmdDriftValue'],\n    ['cloudForwardBadge','cmdCloudValue']"
    new_cloud = "    ['driftBadge','cmdDriftValue']"
    if old_cloud in text:
        text = text.replace(old_cloud, new_cloud, 1)
        changed = True

    old_regime = "    const rg=regimeSource();\n    if(rg) paint($('cmdRegimeValue'),rg.textContent.trim());"
    new_regime = "    const rg=regimeSource();\n    if(rg && !window.ATLAS_PRODUCTION_DECISION) paint($('cmdRegimeValue'),rg.textContent.trim());"
    if old_regime in text:
        text = text.replace(old_regime, new_regime, 1)
        changed = True

    if changed:
        V7_UI.write_text(text, encoding="utf-8")
        print("ATLAS Render boot patch: legacy regime/cloud mirrors disabled", flush=True)
    else:
        print("ATLAS Render boot patch: legacy command mirrors already safe or anchors changed", flush=True)


def apply():
    patch_hype_chart()
    patch_production_ui()
    patch_legacy_command_mirrors()


if __name__ == "__main__":
    apply()
