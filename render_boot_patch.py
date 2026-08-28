#!/usr/bin/env python3
"""Tiny Render-only boot patch.

Keeps ATLAS internal symbol HYPEUSDT/BINANCE:HYPEUSDT unchanged for APIs while
mapping only the TradingView chart request to an exchange where HYPEUSDT exists.
This intentionally avoids repository-time mutation of the large app.js file.
"""
from pathlib import Path

BASE = Path(__file__).resolve().parent
APP = BASE / "app.js"


def apply():
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


if __name__ == "__main__":
    apply()
