"""Production UI patch for the canonical ATLAS asset universe.

The browser historically exposed HYPE as an extra selectable symbol. Earlier
Render boot patches can rewrite its provider from BINANCE to BYBIT before this
patch runs, so removal must be provider-agnostic. The Production decision API is
contractually limited to the frozen base-plus-expansion universe; research-only
symbols must not be shown or resurrected from localStorage. This guard is
intentionally strategy-neutral.
"""
from __future__ import annotations

import re
from pathlib import Path

VERSION = "ATLAS_CANONICAL_ASSET_UI_PATCH_V5_HYPE_EXPANSION"
CANONICAL_UI_SYMBOLS = (
    "BINANCE:BTCUSDT",
    "BINANCE:ETHUSDT",
    "BINANCE:SOLUSDT",
    "BINANCE:XRPUSDT",
    "BINANCE:BNBUSDT",
    "BINANCE:DOGEUSDT",
    "BINANCE:ZECUSDT",
    "BINANCE:ADAUSDT",
    "BINANCE:LINKUSDT",
    "BINANCE:AVAXUSDT",
    "BINANCE:LTCUSDT",
    "BYBIT:HYPEUSDT",
)
_FILTER_OLD = "? savedAssets.filter(a => a && a.cls === 'Crypto' && String(a.symbol || '').toUpperCase().endsWith('USDT'))"


def _remove_research_only_hype_rows(text: str) -> str:
    # Remove a complete JS object-list row containing HYPEUSDT regardless of the
    # chart provider prefix (BINANCE/BYBIT/etc.). Keep this narrowly scoped to a
    # single asset row rather than rewriting arbitrary JavaScript.
    return re.sub(
        r"^[ \t]*\{[^\n{}]*HYPEUSDT[^\n{}]*\},?[ \t]*\n?",
        "",
        text,
        flags=re.MULTILINE | re.IGNORECASE,
    )


def _has_research_only_hype_asset_reference(text: str) -> bool:
    """Return true only when HYPE remains configured as a selectable asset.

    Render's legacy TradingView compatibility patch intentionally leaves the
    token HYPEUSDT in a conditional expression even after HYPE is removed from
    the Production asset list. Treating any textual occurrence as UI exposure
    creates a false-positive runtime diagnostic. A selectable asset definition,
    by contrast, contains a JavaScript ``symbol: '...HYPEUSDT'`` property.
    """
    return bool(
        re.search(
            r"\bsymbol\s*:\s*['\"][^'\"]*HYPEUSDT['\"]",
            str(text),
            flags=re.IGNORECASE,
        )
    )


def transform_app_js(text: str) -> str:
    text = str(text)
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
    hype_exposed = "BYBIT:HYPEUSDT" in patched and _has_research_only_hype_asset_reference(patched)
    return {
        "enabled": True,
        "version": VERSION,
        "assets": list(CANONICAL_UI_SYMBOLS),
        "count": len(CANONICAL_UI_SYMBOLS),
        "hype_exposed": hype_exposed,
        "saved_assets_filtered": "CANONICAL_PRODUCTION_SYMBOLS.has" in patched,
        "score_changed": False,
        "threshold_changed": False,
        "live_execution": False,
    }
