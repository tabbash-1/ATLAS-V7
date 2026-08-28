#!/usr/bin/env python3
"""Render boot patch for ATLAS web mode.

1) Keeps ATLAS internal HYPEUSDT mapping intact while using a valid TradingView
   market for the visual chart.
2) Ensures the Production decision UI is actually loaded in web-only mode.

The patch is idempotent and only mutates the ephemeral Render checkout.
"""
from pathlib import Path

BASE = Path(__file__).resolve().parent
APP = BASE / "app.js"
INDEX = BASE / "index.html"


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
        scripts.append('  <script src="atlas-production-decision.js?v=web-only-prod-v1"></script>')
    if "production-web-autoload.js" not in html:
        scripts.append('  <script src="production-web-autoload.js?v=web-only-prod-v1"></script>')
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


def apply():
    patch_hype_chart()
    patch_production_ui()


if __name__ == "__main__":
    apply()
