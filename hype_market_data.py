"""ATLAS spot candle adapter with resilient public fallback.

HYPEUSDT keeps its dedicated provider order:
1) OKX HYPE-USDT spot 1h candles
2) Bybit HYPEUSDT spot 1h candles

All other ATLAS assets keep the existing Binance path as primary. If that
primary path fails (for example regional HTTP 451 responses), ATLAS falls back
to OKX spot candles for the same symbol. This module never changes scoring,
thresholds, forward logic, geometry, or execution rules.
"""

from __future__ import annotations

import json
import urllib.parse
import urllib.request

VERSION = "ATLAS_SPOT_RESILIENCE_V2"


def _f(value):
    return float(value)


def _get_json(url, ua):
    req = urllib.request.Request(url, headers={"User-Agent": ua, "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=15) as response:
        return json.loads(response.read().decode("utf-8"))


def _okx_symbol(symbol):
    normalized = str(symbol or "").upper().replace("BINANCE:", "")
    if not normalized.endswith("USDT"):
        raise RuntimeError(f"Unsupported OKX spot symbol: {normalized}")
    return normalized[:-4] + "-USDT"


def _okx(symbol, limit, ua):
    inst = _okx_symbol(symbol)
    query = urllib.parse.urlencode({"instId": inst, "bar": "1H", "limit": int(limit)})
    obj = _get_json("https://www.okx.com/api/v5/market/candles?" + query, ua)
    if str(obj.get("code")) != "0":
        raise RuntimeError(f"OKX code={obj.get('code')} msg={obj.get('msg')}")
    rows = obj.get("data") or []
    out = []
    for row in reversed(rows):
        if not isinstance(row, list) or len(row) < 6:
            continue
        out.append({
            "open_time": int(row[0]),
            "open": _f(row[1]),
            "high": _f(row[2]),
            "low": _f(row[3]),
            "close": _f(row[4]),
            "volume": _f(row[5]),
        })
    required = min(100, int(limit))
    if len(out) < required:
        raise RuntimeError(f"OKX insufficient {inst} candles: {len(out)} < {required}")
    return out[-int(limit):], "www.okx.com"


def _bybit_hype(limit, ua):
    query = urllib.parse.urlencode({
        "category": "spot",
        "symbol": "HYPEUSDT",
        "interval": "60",
        "limit": int(limit),
    })
    obj = _get_json("https://api.bybit.com/v5/market/kline?" + query, ua)
    if int(obj.get("retCode", -1)) != 0:
        raise RuntimeError(f"Bybit retCode={obj.get('retCode')} msg={obj.get('retMsg')}")
    rows = ((obj.get("result") or {}).get("list") or [])
    out = []
    for row in reversed(rows):
        if not isinstance(row, list) or len(row) < 6:
            continue
        out.append({
            "open_time": int(row[0]),
            "open": _f(row[1]),
            "high": _f(row[2]),
            "low": _f(row[3]),
            "close": _f(row[4]),
            "volume": _f(row[5]),
        })
    required = min(100, int(limit))
    if len(out) < required:
        raise RuntimeError(f"Bybit insufficient HYPE candles: {len(out)} < {required}")
    return out[-int(limit):], "api.bybit.com"


def _mark_success(atlas, provider):
    state = getattr(atlas, "MARKET_DATA_STATE", {}).get("spot")
    if state is not None:
        state["last_provider"] = provider
        state["last_success_at"] = atlas.now_iso()
        state["last_error"] = None


def _mark_error(atlas, message):
    state = getattr(atlas, "MARKET_DATA_STATE", {}).get("spot")
    if state is not None:
        state["last_error"] = message


def install(atlas):
    original_spot_klines = atlas._spot_klines

    def spot_klines(symbol, limit=220):
        normalized = str(symbol or "").upper().replace("BINANCE:", "")

        if normalized == "HYPEUSDT":
            errors = []
            for fetcher in (
                lambda: _okx(normalized, limit, atlas.UA),
                lambda: _bybit_hype(limit, atlas.UA),
            ):
                try:
                    rows, provider = fetcher()
                    _mark_success(atlas, provider)
                    return rows
                except Exception as exc:
                    errors.append(f"{type(exc).__name__}: {exc}")
            message = "HYPEUSDT spot providers failed: " + " | ".join(errors)
            _mark_error(atlas, message)
            raise RuntimeError(message)

        try:
            return original_spot_klines(normalized, limit)
        except Exception as primary:
            try:
                rows, provider = _okx(normalized, limit, atlas.UA)
                _mark_success(atlas, provider)
                return rows
            except Exception as fallback:
                message = (
                    f"{normalized} spot provider chain failed; "
                    f"primary={type(primary).__name__}: {primary}; "
                    f"OKX={type(fallback).__name__}: {fallback}"
                )
                _mark_error(atlas, message)
                raise RuntimeError(message) from fallback

    atlas._spot_klines = spot_klines
    atlas.HYPE_MARKET_DATA_VERSION = VERSION
    atlas.SPOT_MARKET_DATA_VERSION = VERSION
    return {
        "enabled": True,
        "version": VERSION,
        "hype_symbol": "HYPEUSDT",
        "primary": "existing Binance chain",
        "fallback": "OKX spot",
        "hype_providers": ["OKX", "Bybit"],
    }
