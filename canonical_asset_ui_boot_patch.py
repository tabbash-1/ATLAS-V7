"""Production UI patch for the canonical seven-asset ATLAS universe.

The browser historically exposed HYPE as an eighth selectable symbol. The
Production decision API is contractually limited to seven assets, so the UI
must not advertise or resurrect research-only symbols from localStorage.
"""
from __future__ import annotations

from pathlib import Path

VERSION = "ATLAS_CANONICAL_ASSET_UI_PATCH_V1"
CANONICAL_UI_SYMBOLS = (
    "BINANCE:BTCUSDT",
    "BINANCE:ETHUSDT",
    "BINANCE:SOLUSDT",
    "BINANCE:XRPUSDT",
    "BINANCE:BNBUSDT",
    "BINANCE:DOGEUSDT",
    "BINANCE:ZECUSDT",
)

_HYPE_ROW = "  { name: 'Hyperliquid / USDT', symbol: 'BINANCE:HYPEUSDT', cls: 'Crypto' }\n"
_HYPE_ROW_COMMA = "  { name: 'Hyperliquid / USDT', symbol: 'BINANCE:HYPEUSDT', cls: 'Crypto' },\n"
_FILTER_OLD = "? savedAssets.filter(a => a && a.cls === 'Crypto' && String(a.symbol || '').toUpperCase().endsWith('USDT'))"


def transform_app_js(text: str) -> str:
    text = str(text)
    text = text.replace(_HYPE_ROW_COMMA, "").replace(_HYPE_ROW, "")
    # If HYPE was the final array element, removing it leaves the previous ZEC
    # row with a trailing comma, which is valid JavaScript.
    if "const CANONICAL_PRODUCTION_SYMBOLS" not in text:
        marker = "const savedAssets = JSON.parse(localStorage.getItem('atlas.assets') || 'null');"
        allowed = ",".join(repr(s) for s in CANONICAL_UI_SYMBOLS)
        inject = (
            f"const CANONICAL_PRODUCTION_SYMBOLS = new Set([{allowed}]);\n\n"
            + marker
        )
        text = text.replace(marker, inject, 1)
    filter_new = (
        "? savedAssets.filter(a => a && a.cls === 'Crypto' && "
        "CANONICAL_PRODUCTION_SYMBOLS.has(String(a.symbol || '').toUpperCase()))"
    )
    text = text.replace(_FILTER_OLD, filter_new, 1)
    return text


def apply(base: Path | str) -> dict:
    path = Path(base) / "app.js"
    original = path.read_text(encoding="utf-8")
    patched = transform_app_js(original)
    if patched != original:
        path.write_text(patched, encoding="utf-8")
    return {
        "enabled": True,
        "version": VERSION,
        "assets": list(CANONICAL_UI_SYMBOLS),
        "count": len(CANONICAL_UI_SYMBOLS),
        "hype_exposed": "BINANCE:HYPEUSDT" in patched,
        "saved_assets_filtered": "CANONICAL_PRODUCTION_SYMBOLS.has" in patched,
        "score_changed": False,
        "threshold_changed": False,
        "live_execution": False,
    }
